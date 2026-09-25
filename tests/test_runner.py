import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from youtube_dub.domain.enums import JobStatus, PipelineStage, StageStatus
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.listeners import StageListenerRegistry
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.pipeline.runner import PipelineRunner


@pytest.fixture
def manifest_store():
    store = MagicMock()
    return store


@pytest.fixture
def fake_context(manifest_store):
    context = MagicMock(spec=PipelineContext)
    context.manifest = JobManifest(1, "v1", "job1")
    context.logger = logging.getLogger("test")
    context.check_cancelled = MagicMock()
    return context


@pytest.mark.asyncio
async def test_pipeline_runner_success(manifest_store, fake_context):
    stage1 = MagicMock()
    stage1.stage = PipelineStage.SOURCE_READY
    stage1.run = AsyncMock(
        return_value=MagicMock(status=StageStatus.COMPLETED, error=None)
    )

    stage2 = MagicMock()
    stage2.stage = PipelineStage.TRANSCRIBED
    stage2.run = AsyncMock(
        return_value=MagicMock(status=StageStatus.COMPLETED, error=None)
    )

    listeners = StageListenerRegistry()
    runner = PipelineRunner([stage1, stage2], manifest_store, listeners)

    await runner.run_pipeline(fake_context)

    assert fake_context.manifest.status == JobStatus.COMPLETED
    assert fake_context.manifest.stages["SOURCE_READY"].status == StageStatus.COMPLETED
    assert fake_context.manifest.stages["TRANSCRIBED"].status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_pipeline_runner_resume(manifest_store, fake_context):
    stage1 = MagicMock()
    stage1.stage = PipelineStage.SOURCE_READY
    stage1.run = AsyncMock()

    stage2 = MagicMock()
    stage2.stage = PipelineStage.TRANSCRIBED
    stage2.run = AsyncMock(
        return_value=MagicMock(status=StageStatus.COMPLETED, error=None)
    )

    # Mark stage 1 as COMPLETED already
    fake_context.manifest.stages["SOURCE_READY"].status = StageStatus.COMPLETED
    fake_context.manifest.stages["SOURCE_READY"].completed_at = "now"

    listeners = StageListenerRegistry()
    runner = PipelineRunner([stage1, stage2], manifest_store, listeners)

    await runner.run_pipeline(fake_context)

    # Stage 1 run should be skipped
    stage1.run.assert_not_called()
    # Stage 2 should be run
    stage2.run.assert_called_once()
    assert fake_context.manifest.status == JobStatus.COMPLETED
    assert fake_context.manifest.stages["TRANSCRIBED"].status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_pipeline_runner_failure(manifest_store, fake_context):
    stage1 = MagicMock()
    stage1.stage = PipelineStage.SOURCE_READY
    stage1.run = AsyncMock(
        return_value=MagicMock(status=StageStatus.FAILED, error="fail")
    )

    stage2 = MagicMock()
    stage2.stage = PipelineStage.TRANSCRIBED
    stage2.run = AsyncMock()  # Should not be called

    listeners = StageListenerRegistry()
    runner = PipelineRunner([stage1, stage2], manifest_store, listeners)

    await runner.run_pipeline(fake_context)

    assert fake_context.manifest.status == JobStatus.FAILED
    assert fake_context.manifest.stages["SOURCE_READY"].status == StageStatus.FAILED
    stage2.run.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_runner_cancellation(manifest_store, fake_context):
    stage1 = MagicMock()
    stage1.stage = PipelineStage.SOURCE_READY
    stage1.run = AsyncMock(side_effect=asyncio.CancelledError())

    listeners = StageListenerRegistry()
    runner = PipelineRunner([stage1], manifest_store, listeners)

    with pytest.raises(asyncio.CancelledError):
        await runner.run_pipeline(fake_context)

    assert fake_context.manifest.status == JobStatus.CANCELLED
    assert fake_context.manifest.stages["SOURCE_READY"].status == StageStatus.FAILED


@pytest.mark.asyncio
async def test_pipeline_runner_retry(manifest_store, fake_context):
    stage1 = MagicMock()
    stage1.stage = PipelineStage.SOURCE_READY
    stage1.run = AsyncMock(
        side_effect=[
            MagicMock(status=StageStatus.FAILED, error="fail1"),
            MagicMock(status=StageStatus.COMPLETED, error=None),
        ]
    )

    stage2 = MagicMock()
    stage2.stage = PipelineStage.TRANSCRIBED
    stage2.run = AsyncMock(
        return_value=MagicMock(status=StageStatus.COMPLETED, error=None)
    )

    listeners = StageListenerRegistry()
    runner = PipelineRunner([stage1, stage2], manifest_store, listeners)

    # First run fails
    await runner.run_pipeline(fake_context)
    assert fake_context.manifest.status == JobStatus.FAILED
    assert fake_context.manifest.stages["SOURCE_READY"].status == StageStatus.FAILED
    assert fake_context.manifest.stages["SOURCE_READY"].attempt_count == 1
    stage2.run.assert_not_called()

    # Second run succeeds
    await runner.run_pipeline(fake_context)
    assert fake_context.manifest.status == JobStatus.COMPLETED
    assert fake_context.manifest.stages["SOURCE_READY"].status == StageStatus.COMPLETED
    assert fake_context.manifest.stages["SOURCE_READY"].attempt_count == 2
    stage2.run.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_runner_restart_recovery(manifest_store, fake_context):
    stage1 = MagicMock()
    stage1.stage = PipelineStage.SOURCE_READY
    stage1.run = AsyncMock()

    stage2 = MagicMock()
    stage2.stage = PipelineStage.TRANSCRIBED
    stage2.run = AsyncMock(
        return_value=MagicMock(status=StageStatus.COMPLETED, error=None)
    )

    # Simulate a crash during stage2
    fake_context.manifest.status = JobStatus.RUNNING
    fake_context.manifest.current_stage = PipelineStage.TRANSCRIBED
    fake_context.manifest.stages["SOURCE_READY"].status = StageStatus.COMPLETED
    fake_context.manifest.stages["TRANSCRIBED"].status = StageStatus.RUNNING

    listeners = StageListenerRegistry()
    runner = PipelineRunner([stage1, stage2], manifest_store, listeners)

    await runner.run_pipeline(fake_context)

    # Stage 1 should be skipped, Stage 2 should resume
    stage1.run.assert_not_called()
    stage2.run.assert_called_once()
    assert fake_context.manifest.status == JobStatus.COMPLETED
    assert fake_context.manifest.stages["TRANSCRIBED"].status == StageStatus.COMPLETED


@pytest.mark.asyncio
async def test_pipeline_runner_idempotency(manifest_store, fake_context):
    stage1 = MagicMock()
    stage1.stage = PipelineStage.SOURCE_READY
    stage1.run = AsyncMock(
        return_value=MagicMock(status=StageStatus.COMPLETED, error=None)
    )

    listeners = StageListenerRegistry()
    runner = PipelineRunner([stage1], manifest_store, listeners)

    # First run
    await runner.run_pipeline(fake_context)
    assert stage1.run.call_count == 1
    assert fake_context.manifest.status == JobStatus.COMPLETED

    # Second run should return early
    await runner.run_pipeline(fake_context)
    assert stage1.run.call_count == 1
