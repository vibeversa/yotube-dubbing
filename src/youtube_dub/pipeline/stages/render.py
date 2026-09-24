from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.media.ffmpeg.mux import mux_media
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class RenderStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.RENDERED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running RENDERED stage")

        try:
            source_media = context.artifact_store.path_for(
                context.job_id, "source_media"
            )
            mixed_audio = context.artifact_store.path_for(context.job_id, "mix")
            final_video = context.artifact_store.path_for(context.job_id, "render")

            if not source_media.exists():
                return StageResult(StageStatus.FAILED, "Source media not found")

            if not mixed_audio.exists():
                return StageResult(StageStatus.FAILED, "Mixed audio not found")

            if final_video.exists():
                context.logger.info("Using existing rendered artifact")
                return StageResult(StageStatus.COMPLETED)

            final_video.parent.mkdir(parents=True, exist_ok=True)

            await mux_media(
                video_path=source_media,
                audio_path=mixed_audio,
                output_path=final_video,
                runner=context.process_runner,
                allow_stream_copy=True,
                audio_bitrate=context.config.output_audio_bitrate,
            )

            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"RENDERED failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
