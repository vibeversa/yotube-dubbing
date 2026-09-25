from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.media.ffmpeg.extract import extract_audio
from youtube_dub.media.ffmpeg.probe import probe_media
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class SourceReadyStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.SOURCE_READY

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running SOURCE_READY stage")

        try:
            # 1. Identify input media
            # The input file is expected to be placed manually or via API into the job's source dir
            input_path = context.artifact_store.path_for(context.job_id, "source_media")
            if not input_path.exists():
                return StageResult(
                    StageStatus.FAILED, f"Source media not found at {input_path}"
                )

            # 2. Probe media
            probe_info = await probe_media(input_path, context.process_runner)
            context.logger.info(
                f"Source media probed: {probe_info.duration_s}s, {probe_info.container}"
            )

            # Enforce constraints
            if probe_info.duration_s > context.config.max_duration_s:
                return StageResult(
                    StageStatus.FAILED,
                    f"Source media duration ({probe_info.duration_s}s) exceeds max allowed ({context.config.max_duration_s}s)",
                )

            # 3. Extract audio
            source_audio_path = context.artifact_store.path_for(
                context.job_id, "source_audio"
            )

            # Check for existing artifact to support idempotency / reuse
            if not source_audio_path.exists():
                context.logger.info(f"Extracting audio to {source_audio_path}")
                source_audio_path.parent.mkdir(parents=True, exist_ok=True)
                await extract_audio(
                    input_path, source_audio_path, context.process_runner
                )
            else:
                context.logger.info(
                    f"Using existing source audio at {source_audio_path}"
                )

            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"SOURCE_READY failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
