from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class AlignStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.ALIGNED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running ALIGNED stage")

        # Validates that TTS artifacts exist for all SYNTHESIZED segments
        try:
            translations_path = context.artifact_store.path_for(
                context.job_id, "translations"
            )
            if not translations_path.exists():
                return StageResult(
                    StageStatus.FAILED, "Translations artifact not found"
                )

            import json

            with open(translations_path, "r") as f:
                segments_data = json.load(f)

            for s in segments_data:
                if s.get("status") == "SYNTHESIZED":
                    tts_path = context.artifact_store.path_for(
                        context.job_id, "tts", s["segment_id"]
                    )
                    if not tts_path.exists():
                        return StageResult(
                            StageStatus.FAILED,
                            f"Missing TTS artifact for {s['segment_id']}",
                        )

            # We don't have a complex alignment metadata algorithm yet, but this fulfills the stage boundary
            return StageResult(StageStatus.COMPLETED)
        except Exception as e:
            return StageResult(StageStatus.FAILED, str(e))
