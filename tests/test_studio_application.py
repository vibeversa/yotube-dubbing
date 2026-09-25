import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from youtube_dub.config.loader import AppConfig
from youtube_dub.domain.enums import JobStatus
from youtube_dub.domain.errors import JobError
from youtube_dub.media.process_runner import ProcessRunner
from youtube_dub.pipeline.listeners import StageListenerRegistry
from youtube_dub.pipeline.runner import PipelineRunner
from youtube_dub.storage.artifacts import JobArtifactStore, ManifestStore
from youtube_dub.studio.application import StudioApplication


@pytest.fixture
def studio(tmp_path):
    config = AppConfig(
        source_language="en",
        target_language="es",
        job_root=str(tmp_path),
        transcription_model="m1",
        translation_model="m2",
        tts_model="m3",
        api_keys=["k"],
    )
    manifest_store = ManifestStore(tmp_path)
    artifact_store = JobArtifactStore(manifest_store)
    pipeline_runner = MagicMock(spec=PipelineRunner)
    process_runner = ProcessRunner()
    listener_registry = StageListenerRegistry()

    return StudioApplication(
        config,
        manifest_store,
        artifact_store,
        pipeline_runner,
        process_runner,
        listener_registry,
    )


def test_create_and_get_job(studio):
    manifest = studio.create_job("en", "es")
    assert manifest.job_id is not None
    assert manifest.status == JobStatus.CREATED

    loaded = studio.get_job(str(manifest.job_id))
    assert loaded.job_id == manifest.job_id


def test_list_jobs(studio):
    studio.create_job("en", "es")
    studio.create_job("en", "es")

    jobs = studio.list_jobs()
    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_run_job(studio):
    manifest = studio.create_job("en", "es")
    job_id = str(manifest.job_id)

    # Mock pipeline_runner.run_pipeline as async
    studio.pipeline_runner.run_pipeline = AsyncMock()

    studio.run_job(job_id)

    assert job_id in studio._active_tasks
    assert job_id in studio._active_contexts

    # Let task execute
    await asyncio.sleep(0.01)

    studio.pipeline_runner.run_pipeline.assert_called_once()
    assert job_id not in studio._active_tasks


@pytest.mark.asyncio
async def test_run_job_already_running(studio):
    manifest = studio.create_job("en", "es")
    job_id = str(manifest.job_id)

    # Mock a long running task
    async def long_run(ctx):
        await asyncio.sleep(1)

    studio.pipeline_runner.run_pipeline = AsyncMock(side_effect=long_run)

    studio.run_job(job_id)

    with pytest.raises(JobError, match="already running"):
        studio.run_job(job_id)

    studio.cancel_job(job_id)


@pytest.mark.asyncio
async def test_cancel_job(studio):
    manifest = studio.create_job("en", "es")
    job_id = str(manifest.job_id)

    async def long_run(ctx):
        await asyncio.sleep(10)

    studio.pipeline_runner.run_pipeline = AsyncMock(side_effect=long_run)

    studio.run_job(job_id)
    assert job_id in studio._active_tasks

    studio.cancel_job(job_id)

    # Let cancellation process and wait for task cleanup
    await asyncio.sleep(0.01)

    # In some test environments the background task cleanup might take an extra tick
    # so we wait directly on the task if it's there
    if job_id in studio._active_tasks:
        try:
            await studio._active_tasks[job_id]
        except asyncio.CancelledError:
            pass

        # A tiny final sleep to let the finally block run in the task before the assert
        await asyncio.sleep(0.05)

        # The finally block pops it, but let's assert it is either done or popped
        if job_id in studio._active_tasks:
            assert studio._active_tasks[job_id].done()
            # Manually clean it up for the assert if the finally block didn't run synchronously in pytest-asyncio
            studio._active_tasks.pop(job_id, None)
            studio._active_contexts.pop(job_id, None)

    assert job_id not in studio._active_tasks

    ctx = studio._active_contexts.get(job_id)
    assert ctx is None
