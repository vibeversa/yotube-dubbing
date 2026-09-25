import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from youtube_dub.config.loader import AppConfig
from youtube_dub.domain.enums import StageStatus
from youtube_dub.domain.models import WordTimestamp
from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.pipeline.stages.segment import SegmentStage
from youtube_dub.pipeline.stages.source_ready import SourceReadyStage
from youtube_dub.pipeline.stages.transcribe import TranscribeStage
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
async def test_source_ready_success(fake_context, tmp_path):
    # Setup source media mock
    source_media = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_media"
    )
    source_media.parent.mkdir(parents=True)
    source_media.touch()

    # Mock probe and extract
    async def mock_run(cmd, **kwargs):
        if cmd[0] == "ffprobe":
            data = {"format": {"duration": "100.0", "format_name": "mp4"}}
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(data).encode(), stderr=b""
            )
        if cmd[0] == "ffmpeg":
            out_path = Path(cmd[-1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.touch()
            return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = SourceReadyStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.COMPLETED
    assert fake_context.artifact_store.exists(fake_context.job_id, "source_audio")


@pytest.mark.asyncio
async def test_transcribe_stage_success(fake_context, tmp_path):
    audio_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "source_audio"
    )
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.touch()

    provider = MagicMock()
    provider.transcribe = AsyncMock(return_value=[WordTimestamp("hello", 0, 1000)])
    fake_context.transcription_provider = provider

    stage = TranscribeStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.COMPLETED
    assert fake_context.artifact_store.exists(fake_context.job_id, "words")


@pytest.mark.asyncio
async def test_segment_stage_success(fake_context, tmp_path):
    words_path = fake_context.artifact_store.path_for(fake_context.job_id, "words")
    words_path.parent.mkdir(parents=True, exist_ok=True)

    # Write words json
    words = [
        {"word": "a", "start_ms": 0, "end_ms": 1000},
        {"word": "b", "start_ms": 1000, "end_ms": 61000},  # Triggers chunk boundary
        {"word": "c", "start_ms": 61500, "end_ms": 62000},  # Gap > 200ms
    ]
    with open(words_path, "w") as f:
        json.dump(words, f)

    stage = SegmentStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.COMPLETED

    segments_path = fake_context.artifact_store.path_for(
        fake_context.job_id, "segments"
    )
    with open(segments_path) as f:
        segments = json.load(f)

    assert len(segments) == 2
    assert segments[0]["source_text"] == "a b"
    assert segments[1]["source_text"] == "c"
