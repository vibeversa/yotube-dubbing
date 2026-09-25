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


import time

from youtube_dub.storage.artifacts import JobArtifactStore


def test_path_traversal_manifest(tmp_path: Path):
    store = ManifestStore(tmp_path)
    with pytest.raises(ValueError, match="Path traversal detected"):
        store._get_manifest_path("../outside")


def test_path_traversal_artifacts(tmp_path: Path):
    store = JobArtifactStore(ManifestStore(tmp_path))
    with pytest.raises(ValueError, match="Path traversal detected"):
        store.path_for("../outside", "source_media")


def test_path_traversal_segment_id(tmp_path: Path):
    store = JobArtifactStore(ManifestStore(tmp_path))
    store.job_root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="Path traversal detected"):
        store.path_for("job_1", "tts", "../../../outside")


def test_manifest_updated_at_mutation(tmp_path: Path):
    store = ManifestStore(tmp_path)
    job_id = uuid.uuid4()
    manifest = JobManifest(schema_version=1, pipeline_version="3.0", job_id=job_id)

    store.save(manifest)
    loaded_1 = store.load(str(job_id))

    time.sleep(0.01)

    store.save(manifest)
    loaded_2 = store.load(str(job_id))

    assert loaded_1.updated_at != loaded_2.updated_at
    assert loaded_2.updated_at > loaded_1.updated_at


def test_manifest_invalid_uuid(tmp_path: Path):
    store = ManifestStore(tmp_path)
    job_id = uuid.uuid4()
    manifest_path = store._get_manifest_path(str(job_id))
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        '{"schema_version": 1, "pipeline_version": "3.0", "job_id": "invalid"}'
    )

    with pytest.raises(ManifestError, match="Corrupt manifest"):
        store.load(str(job_id))


from unittest.mock import patch


def test_job_dir_path_traversal(tmp_path: Path):
    store = JobArtifactStore(ManifestStore(tmp_path))
    with pytest.raises(ValueError, match="Path traversal detected"):
        store.get_job_dir("../outside")


def test_path_for_invalid_artifact(tmp_path: Path):
    store = JobArtifactStore(ManifestStore(tmp_path))
    with pytest.raises(ValueError, match="Unknown artifact type: invalid"):
        store.path_for("job_1", "invalid")


def test_path_for_tts_missing_segment(tmp_path: Path):
    store = JobArtifactStore(ManifestStore(tmp_path))
    with pytest.raises(ValueError, match="tts artifact requires segment_id"):
        store.path_for("job_1", "tts")


def test_manifest_store_save_oserror(tmp_path: Path):
    store = ManifestStore(tmp_path)
    job_id = uuid.uuid4()
    manifest = JobManifest(schema_version=1, pipeline_version="3.0", job_id=job_id)

    with (
        patch("os.fsync", side_effect=OSError("Disk full")),
        pytest.raises(ManifestError, match="Failed to save manifest: Disk full"),
    ):
        store.save(manifest)


def test_path_for_separated_vocals(tmp_path: Path):
    store = JobArtifactStore(ManifestStore(tmp_path))
    path = store.path_for("job_1", "separated_vocals")
    assert path.name == "vocals.wav"
