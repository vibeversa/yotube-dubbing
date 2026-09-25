import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from youtube_dub.config.loader import AppConfig
from youtube_dub.domain.enums import SegmentStatus, StageStatus
from youtube_dub.domain.models import DubbingSegment
from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.pipeline.stages.render import RenderStage
from youtube_dub.pipeline.stages.synthesize import SynthesizeStage
from youtube_dub.pipeline.stages.time_fit import TimeFitStage
from youtube_dub.pipeline.stages.translate import TranslateStage
from youtube_dub.storage.artifacts import JobArtifactStore, ManifestStore


@pytest.fixture
def fake_context(tmp_path):
    job_id = "test-job"
    manifest = JobManifest(1, "1", job_id)
    manifest_store = ManifestStore(tmp_path)
    artifact_store = JobArtifactStore(manifest_store)

    config = AppConfig(
        source_language="en",
        target_language="es",
        job_root=str(tmp_path),
        transcription_model="m1",
        translation_model="m2",
        tts_model="m3",
        api_keys=["k"],
    )

    runner = ProcessRunner()
    runner.run = AsyncMock()  # type: ignore

    logger = logging.getLogger("test")

    return PipelineContext(
        job_id=job_id,
        config=config,
        manifest=manifest,
        artifact_store=artifact_store,
        process_runner=runner,
        logger=logger,
    )


@pytest.mark.asyncio
async def test_translate_stage(fake_context):
    segments_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "segments"
    )
    segments_path.parent.mkdir(parents=True, exist_ok=True)

    with open(segments_path, "w") as f:
        json.dump(
            [
                {
                    "segment_id": "seg-1",
                    "start_ms": 100,
                    "end_ms": 500,
                    "source_text": "hello",
                }
            ],
            f,
        )

    provider = MagicMock()
    provider.translate = AsyncMock(
        return_value=[
            DubbingSegment(
                "seg-1",
                100,
                500,
                "hello",
                translated_text="hola",
                status=SegmentStatus.TRANSLATED,
            )
        ]
    )
    fake_context.translation_provider = provider

    stage = TranslateStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.COMPLETED
    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    with open(translations_path) as f:
        data = json.load(f)
    assert data[0]["translated_text"] == "hola"


@pytest.mark.asyncio
async def test_synthesize_stage(fake_context):
    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)

    with open(translations_path, "w") as f:
        json.dump(
            [
                {
                    "segment_id": "seg-1",
                    "start_ms": 100,
                    "end_ms": 500,
                    "source_text": "hello",
                    "translated_text": "hola",
                }
            ],
            f,
        )

    provider = MagicMock()
    provider.synthesize = AsyncMock(return_value=b"audio")
    fake_context.tts_provider = provider

    stage = SynthesizeStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.COMPLETED
    tts_path = fake_context.artifact_store.path_for(fake_context.job_id, "tts", "seg-1")
    assert tts_path.exists()
    assert tts_path.read_bytes() == b"audio"


@pytest.mark.asyncio
async def test_synthesize_stage_partial_failure(fake_context):
    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)

    with open(translations_path, "w") as f:
        json.dump(
            [
                {
                    "segment_id": "seg-1",
                    "start_ms": 100,
                    "end_ms": 500,
                    "source_text": "hello",
                    "translated_text": "hola",
                },
                {
                    "segment_id": "seg-2",
                    "start_ms": 600,
                    "end_ms": 1000,
                    "source_text": "world",
                    "translated_text": "mundo",
                },
            ],
            f,
        )

    provider = MagicMock()

    # Make the second segment fail synthesis
    async def mock_synthesize(text, voice):
        if text == "mundo":
            raise ValueError("Provider error")
        return b"audio"

    provider.synthesize.side_effect = mock_synthesize
    fake_context.tts_provider = provider

    stage = SynthesizeStage()
    res = await stage.run(fake_context)

    # Should return FAILED because of partial completion
    assert res.status == StageStatus.FAILED
    assert "Partial completion" in res.error

    tts_path_1 = fake_context.artifact_store.path_for(
        fake_context.job_id, "tts", "seg-1"
    )
    assert tts_path_1.exists()

    tts_path_2 = fake_context.artifact_store.path_for(
        fake_context.job_id, "tts", "seg-2"
    )
    assert not tts_path_2.exists()

    # Verify translations file has updated status
    with open(translations_path) as f:
        data = json.load(f)
    assert data[0]["status"] == "SYNTHESIZED"
    assert data[1]["status"] == "FAILED"


@pytest.mark.asyncio
async def test_time_fit_stage(fake_context):
    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)

    with open(translations_path, "w") as f:
        json.dump(
            [
                {
                    "segment_id": "seg-1",
                    "start_ms": 100,
                    "end_ms": 1100,
                    "status": "SYNTHESIZED",
                }  # 1s allowed
            ],
            f,
        )

    tts_path = fake_context.artifact_store.path_for(fake_context.job_id, "tts", "seg-1")
    tts_path.parent.mkdir(parents=True, exist_ok=True)
    tts_path.touch()

    async def mock_run(cmd, **kwargs):
        if cmd[0] == "ffprobe":
            return CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps({"format": {"duration": "2.0"}}).encode(),
                stderr=b"",
            )
        if cmd[0] == "ffmpeg":
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.touch()
            return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = TimeFitStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.COMPLETED
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    with open(timing_path) as f:
        data = json.load(f)
    assert data[0]["ratio"] == 2.0


@pytest.mark.asyncio
async def test_render_stage(fake_context):
    source = fake_context.artifact_store.path_for(fake_context.job_id, "source_media")
    mix = fake_context.artifact_store.path_for(fake_context.job_id, "mix")

    source.parent.mkdir(parents=True, exist_ok=True)
    mix.parent.mkdir(parents=True, exist_ok=True)
    source.touch()
    mix.touch()

    async def mock_run(cmd, **kwargs):
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = RenderStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.COMPLETED
    assert fake_context.artifact_store.path_for(fake_context.job_id, "render").exists()
