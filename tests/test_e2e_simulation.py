import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from youtube_dub.config.loader import AppConfig
from youtube_dub.domain.enums import (
    JobStatus,
    PipelineStage,
    SegmentStatus,
    StageStatus,
)
from youtube_dub.domain.models import DubbingSegment, WordTimestamp
from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.listeners import StageListenerRegistry
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.pipeline.runner import PipelineRunner
from youtube_dub.pipeline.stages.mix import MixStage
from youtube_dub.pipeline.stages.render import RenderStage
from youtube_dub.pipeline.stages.segment import SegmentStage
from youtube_dub.pipeline.stages.source_ready import SourceReadyStage
from youtube_dub.pipeline.stages.synthesize import SynthesizeStage
from youtube_dub.pipeline.stages.time_fit import TimeFitStage
from youtube_dub.pipeline.stages.transcribe import TranscribeStage
from youtube_dub.pipeline.stages.translate import TranslateStage
from youtube_dub.storage.artifacts import JobArtifactStore, ManifestStore


@pytest.fixture
def e2e_setup(tmp_path):
    config = AppConfig(
        source_language="en",
        target_language="es",
        job_root=str(tmp_path),
        transcription_model="m1",
        translation_model="m2",
        tts_model="m3",
        api_keys=["fake"],
        chunk_ms=60000,
    )

    manifest_store = ManifestStore(tmp_path)
    artifact_store = JobArtifactStore(manifest_store)

    import uuid

    # Create the job
    job_id = str(uuid.uuid4())
    manifest = JobManifest(1, "1.0", uuid.UUID(job_id))
    manifest_store.save(manifest)

    # Fake runner that fakes media creation
    process_runner = ProcessRunner()

    async def mock_run(cmd, **kwargs):
        # Determine what file to touch based on the last arg or filter
        if cmd[0] == "ffprobe":
            # For timing stage
            data = {"format": {"duration": "1.0"}}
            return CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(data).encode(), stderr=b""
            )

        if cmd[0] == "ffmpeg":
            out_path = Path(cmd[-1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.touch()
            return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    process_runner.run = AsyncMock(side_effect=mock_run)  # type: ignore

    # Providers
    transcription_provider = MagicMock()
    transcription_provider.transcribe = AsyncMock(
        return_value=[WordTimestamp("hello", 0.0, 1000.0)]
    )

    translation_provider = MagicMock()
    translation_provider.translate = AsyncMock(
        return_value=[
            DubbingSegment(
                "seg-000001",
                0.0,
                1000.0,
                "hello",
                translated_text="hola",
                status=SegmentStatus.TRANSLATED,
            )
        ]
    )

    tts_provider = MagicMock()
    tts_provider.synthesize = AsyncMock(return_value=b"fake_audio_bytes")

    context = PipelineContext(
        job_id=job_id,
        config=config,
        manifest=manifest,
        artifact_store=artifact_store,
        process_runner=process_runner,
        logger=logging.getLogger("e2e"),
        transcription_provider=transcription_provider,
        translation_provider=translation_provider,
        tts_provider=tts_provider,
    )

    stages = [
        SourceReadyStage(),
        TranscribeStage(),
        SegmentStage(),
        TranslateStage(),
        SynthesizeStage(),
        TimeFitStage(),
        MixStage(),
        RenderStage(),
    ]

    runner = PipelineRunner(stages, manifest_store, StageListenerRegistry())

    return context, runner


@pytest.mark.asyncio
async def test_full_pipeline_success(e2e_setup):
    context, runner = e2e_setup

    # 1. Provide the input source media to start the pipeline
    source_media = context.artifact_store.path_for(context.job_id, "source_media")
    source_media.parent.mkdir(parents=True, exist_ok=True)
    source_media.touch()

    # Run entire pipeline
    await runner.run_pipeline(context)

    # Assert
    manifest = context.manifest
    if manifest.status != JobStatus.COMPLETED:
        print("FAILED STAGE ERROR:")
        print(manifest.stages[manifest.current_stage.name].error)
        for stage in PipelineStage:
            print(f"{stage.name}: {manifest.stages[stage.name].status}")

    assert manifest.status == JobStatus.COMPLETED

    for stage in PipelineStage:
        assert manifest.stages[stage.name].status == StageStatus.COMPLETED

    assert context.artifact_store.path_for(context.job_id, "render").exists()


@pytest.mark.asyncio
async def test_pipeline_resume_after_failure(e2e_setup):
    context, runner = e2e_setup

    source_media = context.artifact_store.path_for(context.job_id, "source_media")
    source_media.parent.mkdir(parents=True, exist_ok=True)
    source_media.touch()

    # Intentionally break translation to simulate failure
    context.translation_provider.translate.side_effect = Exception(
        "Simulated provider crash"
    )

    await runner.run_pipeline(context)

    manifest = context.artifact_store.manifest_store.load(context.job_id)
    assert manifest.status == JobStatus.FAILED
    assert manifest.current_stage == PipelineStage.TRANSLATED
    assert manifest.stages["TRANSCRIBED"].status == StageStatus.COMPLETED

    # Fix the issue
    context.translation_provider.translate.side_effect = None

    # Resume the pipeline (use loaded manifest to prove persistence)
    context.manifest = manifest
    await runner.run_pipeline(context)

    # Assert
    manifest = context.artifact_store.manifest_store.load(context.job_id)
    assert manifest.status == JobStatus.COMPLETED
    assert manifest.stages["TRANSLATED"].attempt_count == 2
    assert manifest.stages["RENDERED"].status == StageStatus.COMPLETED
