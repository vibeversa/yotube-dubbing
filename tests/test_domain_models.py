import uuid

import pytest

from youtube_dub.domain.enums import PipelineStage
from youtube_dub.domain.models import DubbingProject, DubbingSegment, WordTimestamp


def test_word_timestamp_validation():
    with pytest.raises(ValueError, match="start_ms must be >= 0"):
        WordTimestamp(word="hello", start_ms=-10, end_ms=10)

    with pytest.raises(ValueError, match="end_ms must be >= start_ms"):
        WordTimestamp(word="hello", start_ms=10, end_ms=5)

    wt = WordTimestamp(word="hello", start_ms=5.0, end_ms=10.0)
    assert wt.word == "hello"


def test_dubbing_segment_validation():
    with pytest.raises(ValueError):
        DubbingSegment(segment_id="1", start_ms=-1, end_ms=5, source_text="test")

    with pytest.raises(ValueError):
        DubbingSegment(segment_id="1", start_ms=10, end_ms=10, source_text="test")

    ds = DubbingSegment(segment_id="seg-1", start_ms=0, end_ms=1000, source_text="test")
    assert ds.segment_id == "seg-1"


def test_dubbing_project():
    job_id = uuid.uuid4()
    proj = DubbingProject(job_id=job_id, source_language="en", target_language="es")
    assert proj.job_id == job_id
    assert proj.current_stage == PipelineStage.SOURCE_READY
