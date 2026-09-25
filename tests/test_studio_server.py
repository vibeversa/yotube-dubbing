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
    response = await client.post(
        "/api/jobs", json={"source_language": "en", "target_language": "es"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "manifest" in data
    assert "job_id" in data["manifest"]
    assert data["manifest"]["status"] == "CREATED"


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
