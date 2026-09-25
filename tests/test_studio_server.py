import uuid
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from youtube_dub.domain.enums import JobStatus
from youtube_dub.domain.errors import JobError, ManifestError
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.studio.application import StudioApplication
from youtube_dub.studio.server import app


@pytest.fixture
def mock_studio():
    studio = MagicMock(spec=StudioApplication)

    def fake_create(source, target):
        return JobManifest(1, "1", uuid.uuid4())

    studio.create_job = fake_create
    studio.list_jobs.return_value = []

    def fake_get(jid):
        if jid == "bad":
            raise ManifestError("bad")
        m = JobManifest(1, "1", uuid.UUID(jid))
        m.status = JobStatus.CREATED
        return m

    studio.get_job = fake_get

    def fake_run(jid):
        if jid == "bad":
            raise ManifestError("bad")
        if jid == "running":
            raise JobError("running")

    studio.run_job = fake_run
    studio.cancel_job = fake_run
    studio.resume_job = fake_run

    def fake_retry(jid):
        if jid == "not-failed":
            raise JobError("not failed")

    studio.retry_job = fake_retry

    app.state.studio = studio
    return studio


@pytest.fixture
def client(mock_studio):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_create_job(client, mock_studio):
    # Test basic create
    response = await client.post(
        "/api/jobs", json={"source_language": "en", "target_language": "es"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "manifest" in data
    assert "job_id" in data["manifest"]
    assert data["manifest"]["status"] == "CREATED"

    # Test create with URL
    response_url = await client.post(
        "/api/jobs",
        json={
            "source_language": "en",
            "target_language": "es",
            "source_url": "https://youtube.com/123",
        },
    )
    assert response_url.status_code == 200
    mock_studio.download_youtube_media.assert_called_once()

    # Test create with local path
    response_path = await client.post(
        "/api/jobs",
        json={
            "source_language": "en",
            "target_language": "es",
            "local_path": "/tmp/file.mp4",
        },
    )
    assert response_path.status_code == 200
    mock_studio.ingest_media.assert_called_once()


@pytest.mark.asyncio
async def test_list_jobs(client, mock_studio):
    response = await client.get("/api/jobs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_job(client, mock_studio):
    valid_id = str(uuid.uuid4())
    response = await client.get(f"/api/jobs/{valid_id}")
    assert response.status_code == 200
    assert response.json()["manifest"]["job_id"] == valid_id

    response = await client.get("/api/jobs/bad")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_job(client, mock_studio):
    valid_id = str(uuid.uuid4())
    response = await client.post(f"/api/jobs/{valid_id}/run")
    assert response.status_code == 200

    response = await client.post("/api/jobs/running/run")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_retry_job(client, mock_studio):
    response = await client.post("/api/jobs/not-failed/retry")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_artifact_success(client, mock_studio, tmp_path):
    job_id = str(uuid.uuid4())
    mock_studio.artifact_store = MagicMock()
    mock_studio.artifact_store.path_for.return_value = tmp_path / "test.mp4"
    (tmp_path / "test.mp4").touch()

    response = await client.get(f"/api/jobs/{job_id}/artifacts/source_media")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_artifact_not_found(client, mock_studio, tmp_path):
    job_id = str(uuid.uuid4())
    mock_studio.artifact_store = MagicMock()
    path_mock = MagicMock()
    path_mock.exists.return_value = False
    mock_studio.artifact_store.path_for.return_value = path_mock

    response = await client.get(f"/api/jobs/{job_id}/artifacts/source_media")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_artifact_value_error(client, mock_studio):
    job_id = str(uuid.uuid4())
    mock_studio.artifact_store = MagicMock()
    mock_studio.artifact_store.path_for.side_effect = ValueError("Invalid artifact")

    response = await client.get(f"/api/jobs/{job_id}/artifacts/invalid")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_artifact_internal_error(client, mock_studio):
    job_id = str(uuid.uuid4())
    mock_studio.artifact_store = MagicMock()
    mock_studio.artifact_store.path_for.side_effect = Exception("Internal explosion")

    response = await client.get(f"/api/jobs/{job_id}/artifacts/source_media")
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_resume_job_success(client, mock_studio):
    response = await client.post("/api/jobs/valid/resume")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_resume_job_invalid_state(client, mock_studio):
    mock_studio.resume_job.side_effect = JobError("invalid state")
    response = await client.post("/api/jobs/running/resume")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_read_index_missing(client, monkeypatch):
    import os

    real_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda x: False if str(x).endswith("index.html") else real_exists(x))
    response = await client.get("/")
    assert response.status_code == 200
    assert "Static files missing" in response.text




@pytest.mark.asyncio
async def test_get_job_failed_structured_response(client, mock_studio):
    from youtube_dub.domain.enums import PipelineStage, StageStatus

    m = JobManifest(1, "1", uuid.uuid4())
    m.status = JobStatus.FAILED
    m.current_stage = PipelineStage.TRANSCRIBED
    m.stages["TRANSCRIBED"].status = StageStatus.FAILED
    m.stages["TRANSCRIBED"].error = "Some explicit error"

    def fake_get(jid):
        return m

    mock_studio.get_job = fake_get

    response = await client.get(f"/api/jobs/{m.job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["failure"]["stage"] == "TRANSCRIBED"
    assert data["failure"]["message"] == "Some explicit error"


@pytest.mark.asyncio
async def test_get_job_failed_unknown_error(client, mock_studio):
    from youtube_dub.domain.enums import PipelineStage, StageStatus

    m = JobManifest(1, "1", uuid.uuid4())
    m.status = JobStatus.FAILED
    m.current_stage = PipelineStage.TRANSCRIBED
    m.stages["TRANSCRIBED"].status = StageStatus.FAILED
    m.stages["TRANSCRIBED"].error = None

    def fake_get(jid):
        return m

    mock_studio.get_job = fake_get

    response = await client.get(f"/api/jobs/{m.job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["failure"]["stage"] == "TRANSCRIBED"
    assert data["failure"]["message"] == "Unknown failure"


@pytest.mark.asyncio
async def test_list_jobs_success(client, mock_studio):
    mock_studio.list_jobs.return_value = [JobManifest(1, "1", uuid.uuid4())]
    response = await client.get("/api/jobs")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_run_job_success(client, mock_studio):
    response = await client.post("/api/jobs/valid/run")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cancel_job_success(client, mock_studio):
    response = await client.post("/api/jobs/valid/cancel")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_retry_job_success_route(client, mock_studio):
    response = await client.post("/api/jobs/valid/retry")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_lifespan():
    from unittest.mock import patch

    from youtube_dub.studio.server import lifespan

    app_mock = MagicMock()
    app_mock.state = MagicMock()
    del app_mock.state.studio

    with patch("youtube_dub.studio.server.create_studio_application") as m_create:
        m_create.return_value = "studio_obj"
        async with lifespan(app_mock):
            assert app_mock.state.studio == "studio_obj"


@pytest.mark.asyncio
async def test_get_studio_uninitialized():
    from fastapi import HTTPException

    from youtube_dub.studio.server import get_studio

    request = MagicMock()
    request.app.state = MagicMock()
    del request.app.state.studio

    with pytest.raises(HTTPException) as exc:
        get_studio(request)
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_read_index(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "youtube-dub Studio" in response.text


@pytest.mark.asyncio
async def test_create_job_with_url_success(client, mock_studio):
    mock_studio.download_youtube_media = MagicMock()
    # Also need to mock create_job return value
    mock_studio.create_job.return_value = JobManifest(1, "1", uuid.uuid4())
    response = await client.post(
        "/api/jobs",
        json={
            "source_language": "en",
            "target_language": "es",
            "source_url": "http://test",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_job_with_local_path_success(client, mock_studio):
    mock_studio.ingest_media = MagicMock()
    mock_studio.create_job.return_value = JobManifest(1, "1", uuid.uuid4())
    response = await client.post(
        "/api/jobs",
        json={
            "source_language": "en",
            "target_language": "es",
            "local_path": "/test.mp4",
        },
    )
    assert response.status_code == 200
