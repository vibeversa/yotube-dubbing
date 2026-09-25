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


import asyncio
from unittest.mock import MagicMock

from youtube_dub.config.loader import AppConfig
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.manifest import JobManifest


def test_pipeline_context_cancellation():
    config = AppConfig(
        source_language="en",
        target_language="es",
        job_root="/tmp",
        transcription_model="model",
        translation_model="model",
        tts_model="model",
        separation_model="passthrough",
        api_keys=["k"],
    )
    import uuid

    manifest = JobManifest(1, "1.0", uuid.uuid4())
    context = PipelineContext(
        job_id=str(manifest.job_id),
        config=config,
        manifest=manifest,
        artifact_store=MagicMock(),
        process_runner=MagicMock(),
        logger=MagicMock(),
    )

    context.cancel_event.set()
    with pytest.raises(asyncio.CancelledError, match="Pipeline context cancelled"):
        context.check_cancelled()
