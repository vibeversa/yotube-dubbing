import uuid
from pathlib import Path

import pytest

from youtube_dub.domain.enums import JobStatus
from youtube_dub.domain.errors import ManifestError
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.storage.artifacts import ManifestStore


def test_manifest_store_save_load(tmp_path: Path):
    store = ManifestStore(tmp_path)
    job_id = uuid.uuid4()
    manifest = JobManifest(schema_version=1, pipeline_version="3.0", job_id=job_id)

    # modify a field to verify it survives serialization
    manifest.status = JobStatus.RUNNING

    store.save(manifest)

    loaded = store.load(str(job_id))

    assert loaded.job_id == job_id
    assert loaded.schema_version == 1
    assert loaded.status == JobStatus.RUNNING
    assert len(loaded.stages) == len(manifest.stages)
    assert (
        loaded.stages["SOURCE_READY"].status == manifest.stages["SOURCE_READY"].status
    )


def test_manifest_store_not_found(tmp_path: Path):
    store = ManifestStore(tmp_path)
    with pytest.raises(ManifestError, match="Manifest not found"):
        store.load(str(uuid.uuid4()))


def test_manifest_store_corrupt(tmp_path: Path):
    store = ManifestStore(tmp_path)
    job_id = uuid.uuid4()
    manifest_path = store._get_manifest_path(str(job_id))
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{ invalid json }")

    with pytest.raises(ManifestError, match="Manifest JSON corrupt"):
        store.load(str(job_id))
