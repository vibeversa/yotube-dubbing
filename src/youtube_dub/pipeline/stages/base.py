from typing import Protocol

from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.pipeline.context import PipelineContext


class StageResult:
    def __init__(self, status: StageStatus, error: str | None = None):
        self.status = status
        self.error = error


class PipelineStageRunner(Protocol):
    """Protocol for a single pipeline stage implementation."""

    @property
    def stage(self) -> PipelineStage: ...

    async def run(self, context: PipelineContext) -> StageResult: ...
