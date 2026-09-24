import uuid

import pytest

from youtube_dub.domain.enums import JobStatus, PipelineStage
from youtube_dub.pipeline.manifest import JobManifest


def test_manifest_defaults():
    job_id = uuid.uuid4()
    manifest = JobManifest(schema_version=1, pipeline_version="3.0", job_id=job_id)
    assert manifest.status == JobStatus.CREATED
    assert manifest.current_stage == PipelineStage.SOURCE_READY
    assert len(manifest.stages) == len(PipelineStage)
    assert manifest.stages["SOURCE_READY"].stage == PipelineStage.SOURCE_READY


def test_manifest_validation():
    with pytest.raises(ValueError, match="schema_version must be > 0"):
        JobManifest(schema_version=0, pipeline_version="3.0", job_id=uuid.uuid4())
