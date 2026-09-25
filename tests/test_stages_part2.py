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
        separation_model="passthrough",
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


from youtube_dub.pipeline.stages.mix import MixStage


@pytest.mark.asyncio
async def test_mix_stage_negative_start_ms(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "timed_artifact": "seg-1.wav"}], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "start_ms": -100, "end_ms": 1000}], f)

    source_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    timed_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "timing", "seg-1"
    )
    timed_audio.parent.mkdir(parents=True, exist_ok=True)
    timed_audio.touch()

    async def mock_run(cmd, **kwargs):
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = MixStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.FAILED
    assert "Invalid start_ms < 0" in res.error


@pytest.mark.asyncio
async def test_mix_stage_missing_timing(fake_context):
    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.FAILED
    assert "Timing artifact not found" in res.error


@pytest.mark.asyncio
async def test_mix_stage_missing_translations(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    timing_path.touch()

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.FAILED
    assert "Translations artifact not found" in res.error


@pytest.mark.asyncio
async def test_mix_stage_missing_source(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([], f)

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.FAILED
    assert "Source audio missing" in res.error


@pytest.mark.asyncio
async def test_mix_stage_already_mixed(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([], f)

    mix_path = fake_context.artifact_store.path_for(fake_context.job_id, "mix")
    mix_path.parent.mkdir(parents=True, exist_ok=True)
    mix_path.touch()

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_mix_stage_no_inputs_mixed(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([{"segment_id": "seg-1"}], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "start_ms": 100}], f)

    source_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    bg_path = fake_context.artifact_store.path_for(fake_context.job_id, "separated_bg")
    bg_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path.touch()

    # Note that timed_audio does not exist, so it will be skipped and `inputs` will be empty
    async def mock_run(cmd, **kwargs):
        if cmd[0] == "ffmpeg":
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.touch()
            return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_mix_stage_process_runner_error(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([{"segment_id": "seg-1"}], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "start_ms": 100}], f)

    source_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    bg_path = fake_context.artifact_store.path_for(fake_context.job_id, "separated_bg")
    bg_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path.touch()

    timed_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "timing", "seg-1"
    )
    timed_audio.parent.mkdir(parents=True, exist_ok=True)
    timed_audio.touch()

    async def mock_run(cmd, **kwargs):
        raise ValueError("FFmpeg error")

    fake_context.process_runner.run.side_effect = mock_run

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.FAILED
    assert "FFmpeg error" in res.error


@pytest.mark.asyncio
async def test_mix_stage_separate_vocals(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([], f)

    source_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    # Note bg_path does NOT exist so it will run separator

    async def mock_run(cmd, **kwargs):
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        # also touch background.wav
        bg = fake_context.artifact_store.path_for(fake_context.job_id, "separated_bg")
        bg.parent.mkdir(parents=True, exist_ok=True)
        bg.touch()
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_mix_stage_empty_timing_data_mixed(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([], f)

    source_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    bg_path = fake_context.artifact_store.path_for(fake_context.job_id, "separated_bg")
    bg_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path.touch()

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_mix_stage_segment_missing_timing(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([{"segment_id": "seg-2"}], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "start_ms": 100}], f)

    source_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    bg_path = fake_context.artifact_store.path_for(fake_context.job_id, "separated_bg")
    bg_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path.touch()

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_mix_stage_missing_timed_audio(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([{"segment_id": "seg-1"}], f)

    translations_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "translations"
    )
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "start_ms": 100}], f)

    source_audio = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    bg_path = fake_context.artifact_store.path_for(fake_context.job_id, "separated_bg")
    bg_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path.touch()

    # Leave timed_audio non-existent
    async def mock_run(cmd, **kwargs):
        if cmd[0] == "ffmpeg":
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.touch()
            return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = MixStage()
    res = await stage.run(fake_context)
    assert res.status == StageStatus.COMPLETED
