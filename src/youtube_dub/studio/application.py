import asyncio
import logging
import uuid
from pathlib import Path

from youtube_dub.config.loader import AppConfig
from youtube_dub.domain.enums import JobStatus
from youtube_dub.domain.errors import JobError
from youtube_dub.media.process_runner import ProcessRunner
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.listeners import StageListenerRegistry
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.pipeline.runner import PipelineRunner
from youtube_dub.storage.artifacts import JobArtifactStore, ManifestStore


class StudioApplication:
    def __init__(
        self,
        config: AppConfig,
        manifest_store: ManifestStore,
        artifact_store: JobArtifactStore,
        pipeline_runner: PipelineRunner,
        process_runner: ProcessRunner,
        listener_registry: StageListenerRegistry,
    ):
        self.config = config
        self.manifest_store = manifest_store
        self.artifact_store = artifact_store
        self.pipeline_runner = pipeline_runner
        self.process_runner = process_runner
        self.listener_registry = listener_registry

        self.logger = logging.getLogger("studio_application")

        # Track active pipeline tasks for cancellation support
        self._active_tasks: dict[str, asyncio.Task] = {}
        # Track contexts so we can signal cancellation explicitly
        self._active_contexts: dict[str, PipelineContext] = {}

    def get_job(self, job_id: str) -> JobManifest:
        return self.manifest_store.load(job_id)

    def list_jobs(self) -> list[JobManifest]:
        jobs = []
        job_root = Path(self.config.job_root)
        if job_root.exists():
            for d in job_root.iterdir():
                if d.is_dir() and (d / "manifest.json").exists():
                    try:
                        jobs.append(self.manifest_store.load(d.name))
                    except Exception as e:
                        self.logger.warning(f"Failed to load job {d.name}: {e}")
        return jobs

    def create_job(self, source_lang: str, target_lang: str) -> JobManifest:
        job_id = uuid.uuid4()
        manifest = JobManifest(
            schema_version=1,
            pipeline_version="1.0",
            job_id=job_id,
            source_language=source_lang,
            target_language=target_lang,
        )
        self.manifest_store.save(manifest)
        return manifest

    def run_job(self, job_id: str) -> None:
        """Starts or resumes a job in the background."""
        if job_id in self._active_tasks and not self._active_tasks[job_id].done():
            raise JobError(f"Job {job_id} is already running.")

        manifest = self.get_job(job_id)
        if manifest.status == JobStatus.COMPLETED:
            raise JobError(f"Job {job_id} is already completed.")

        # Create pipeline context
        context = PipelineContext(
            job_id=job_id,
            config=self.config,
            manifest=manifest,
            artifact_store=self.artifact_store,
            process_runner=self.process_runner,
            logger=logging.getLogger(f"job_{job_id}"),
            # Note: In a fully wired application, we'd inject concrete providers here.
            # For simplicity in this structure, we assume they are wired appropriately.
        )

        self._active_contexts[job_id] = context

        async def _run_task():
            try:
                await self.pipeline_runner.run_pipeline(context)
            except asyncio.CancelledError:
                self.logger.info(f"Task for job {job_id} was cancelled.")
            except Exception as e:
                self.logger.error(f"Task for job {job_id} failed abruptly: {e}")
            finally:
                self._active_tasks.pop(job_id, None)
                self._active_contexts.pop(job_id, None)

        task = asyncio.create_task(_run_task())
        self._active_tasks[job_id] = task

    def cancel_job(self, job_id: str) -> None:
        """Requests cancellation of a running job."""
        if job_id not in self._active_tasks or self._active_tasks[job_id].done():
            manifest = self.get_job(job_id)
            if manifest.status == JobStatus.RUNNING:
                # It's marked running but not active in memory. Mark it cancelled.
                manifest.status = JobStatus.CANCELLED
                self.manifest_store.save(manifest)
            return

        # Signal the context explicitly
        context = self._active_contexts.get(job_id)
        if context:
            context.cancel_event.set()

        # Cancel the task
        task = self._active_tasks[job_id]
        task.cancel()

    def retry_job(self, job_id: str) -> None:
        """Retry implies resuming a failed job."""
        manifest = self.get_job(job_id)
        if manifest.status != JobStatus.FAILED:
            raise JobError("Can only retry a failed job. Use run/resume otherwise.")

        self.run_job(job_id)

    def resume_job(self, job_id: str) -> None:
        """Resume acts exactly like run."""
        self.run_job(job_id)
