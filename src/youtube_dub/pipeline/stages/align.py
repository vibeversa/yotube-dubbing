from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class AlignStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.ALIGNED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running ALIGNED stage")

        # In a real implementation this would map synthesized audio back to words.
        # For v1, this is a placeholder keeping the canonical pipeline structural order intact.

        return StageResult(StageStatus.COMPLETED)
