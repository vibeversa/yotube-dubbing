import asyncio
from datetime import UTC, datetime

from youtube_dub.domain.enums import JobStatus, PipelineStage, StageStatus
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.listeners import StageListenerRegistry
from youtube_dub.pipeline.stages.base import PipelineStageRunner
from youtube_dub.storage.artifacts import ManifestStore


class PipelineRunner:
    def __init__(
        self,
        stages: list[PipelineStageRunner],
        manifest_store: ManifestStore,
        listeners: StageListenerRegistry,
    ):
        self.stages = stages
        self.manifest_store = manifest_store
        self.listeners = listeners

    async def run_pipeline(self, context: PipelineContext) -> None:
        manifest = context.manifest

        if manifest.status == JobStatus.COMPLETED:
            return

        manifest.status = JobStatus.RUNNING
        self._save_manifest(manifest)

        try:
            for stage_runner in self.stages:
                stage_enum = stage_runner.stage

                # Check resume logic: skip if already completed
                record = manifest.stages[stage_enum.name]
                if record.status == StageStatus.COMPLETED:
                    context.logger.info(f"Skipping completed stage: {stage_enum.name}")
                    continue

                context.check_cancelled()

                # Update manifest pre-run
                record.status = StageStatus.RUNNING
                record.started_at = datetime.now(UTC).isoformat()
                record.attempt_count += 1
                manifest.current_stage = stage_enum
                self._save_manifest(manifest)
                self.listeners.notify_stage_status(
                    manifest, stage_enum, StageStatus.RUNNING
                )

                # Run stage
                try:
                    result = await stage_runner.run(context)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    context.logger.error(
                        f"Unexpected error in stage {stage_enum.name}: {e}"
                    )
                    record.status = StageStatus.FAILED
                    record.error = str(e)
                    record.completed_at = datetime.now(UTC).isoformat()
                    manifest.status = JobStatus.FAILED
                    self._save_manifest(manifest)
                    self.listeners.notify_stage_status(
                        manifest, stage_enum, StageStatus.FAILED
                    )
                    self.listeners.notify_job_status(manifest)
                    return

                # Process result
                record.status = result.status
                record.error = result.error
                record.completed_at = datetime.now(UTC).isoformat()
                self._save_manifest(manifest)
                self.listeners.notify_stage_status(manifest, stage_enum, result.status)

                if result.status == StageStatus.FAILED:
                    manifest.status = JobStatus.FAILED
                    self._save_manifest(manifest)
                    self.listeners.notify_job_status(manifest)
                    return

            # All stages complete
            if PipelineStage.COMPLETED.name in manifest.stages:
                manifest.stages[
                    PipelineStage.COMPLETED.name
                ].status = StageStatus.COMPLETED
                manifest.stages[
                    PipelineStage.COMPLETED.name
                ].completed_at = datetime.now(UTC).isoformat()
            manifest.status = JobStatus.COMPLETED
            self._save_manifest(manifest)
            self.listeners.notify_job_status(manifest)

        except asyncio.CancelledError:
            context.logger.info("Pipeline cancelled.")
            manifest.status = JobStatus.CANCELLED
            if manifest.current_stage:
                manifest.stages[manifest.current_stage.name].status = StageStatus.FAILED
                manifest.stages[manifest.current_stage.name].error = "Cancelled"
            self._save_manifest(manifest)
            self.listeners.notify_job_status(manifest)
            raise

    def _save_manifest(self, manifest) -> None:
        self.manifest_store.save(manifest)
