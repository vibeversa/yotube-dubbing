from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from youtube_dub.domain.enums import JobStatus, PipelineStage, StageStatus


@dataclass
class StageRecord:
    stage: PipelineStage
    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    attempt_count: int = 0
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class JobManifest:
    schema_version: int
    pipeline_version: str
    job_id: UUID
    source_language: str = "en"
    target_language: str = "es"
    status: JobStatus = JobStatus.CREATED
    current_stage: PipelineStage = PipelineStage.SOURCE_READY
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    stages: dict[str, StageRecord] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.stages:
            self.stages = {
                stage.name: StageRecord(stage=stage) for stage in PipelineStage
            }

        # Validation rules:
        if self.schema_version <= 0:
            raise ValueError("schema_version must be > 0")
