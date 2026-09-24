from dataclasses import dataclass
from uuid import UUID

from youtube_dub.domain.enums import PipelineStage, SegmentStatus


@dataclass
class VoiceProfile:
    name: str


@dataclass
class WordTimestamp:
    word: str
    start_ms: float
    end_ms: float

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be >= start_ms")


@dataclass
class DubbingSegment:
    segment_id: str
    start_ms: float
    end_ms: float
    source_text: str
    translated_text: str | None = None
    status: SegmentStatus = SegmentStatus.PENDING
    tts_artifact: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be > start_ms")


@dataclass
class DubbingProject:
    job_id: UUID
    source_language: str
    target_language: str
    current_stage: PipelineStage = PipelineStage.SOURCE_READY
