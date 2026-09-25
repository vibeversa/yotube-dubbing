from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from youtube_dub.domain.enums import JobStatus, StageStatus
from youtube_dub.domain.errors import JobError, ManifestError
from youtube_dub.studio.application import StudioApplication
from youtube_dub.studio.schemas import JobFailureDetails, JobResponse, SuggestedAction

app = FastAPI(title="youtube-dub Studio API")

# Dependency injection for StudioApplication would typically happen here.
# For simplicity, we assume app.state.studio holds the instance.


def _build_job_response(manifest) -> JobResponse:
    failure = None
    if manifest.status == JobStatus.FAILED:
        failed_stage = manifest.stages.get(manifest.current_stage.name)
        if failed_stage and failed_stage.status == StageStatus.FAILED:
            # We construct a generic structured failure
            failure = JobFailureDetails(
                stage=manifest.current_stage.name,
                segment_id=None,
                error_code="STAGE_FAILED",
                message=failed_stage.error or "Unknown failure",
                retryable=True,
                suggested_actions=[
                    SuggestedAction(id="retry_stage", label="Retry Stage")
                ],
            )

    return JobResponse(manifest=manifest, failure=failure)


def get_studio(request: Request) -> StudioApplication:
    studio = getattr(request.app.state, "studio", None)
    if not studio:
        raise HTTPException(
            status_code=500, detail="Studio application not initialized"
        )
    return studio


class CreateJobRequest(BaseModel):
    source_language: str
    target_language: str


@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    req: CreateJobRequest, studio: StudioApplication = Depends(get_studio)
):
    try:
        manifest = studio.create_job(req.source_language, req.target_language)
        return _build_job_response(manifest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs", response_model=list[JobResponse])
async def list_jobs(studio: StudioApplication = Depends(get_studio)):
    return [_build_job_response(m) for m in studio.list_jobs()]


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, studio: StudioApplication = Depends(get_studio)):
    try:
        manifest = studio.get_job(job_id)
        return _build_job_response(manifest)
    except ManifestError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.post("/api/jobs/{job_id}/run")
async def run_job(job_id: str, studio: StudioApplication = Depends(get_studio)):
    try:
        studio.run_job(job_id)
        return {"status": "started"}
    except ManifestError:
        raise HTTPException(status_code=404, detail="Job not found")
    except JobError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, studio: StudioApplication = Depends(get_studio)):
    try:
        studio.cancel_job(job_id)
        return {"status": "cancelled"}
    except ManifestError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.post("/api/jobs/{job_id}/resume")
async def resume_job(job_id: str, studio: StudioApplication = Depends(get_studio)):
    try:
        studio.resume_job(job_id)
        return {"status": "resumed"}
    except ManifestError:
        raise HTTPException(status_code=404, detail="Job not found")
    except JobError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str, studio: StudioApplication = Depends(get_studio)):
    try:
        studio.retry_job(job_id)
        return {"status": "retrying"}
    except ManifestError:
        raise HTTPException(status_code=404, detail="Job not found")
    except JobError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/jobs/{job_id}/artifacts/{artifact_type}")
async def get_artifact(
    job_id: str, artifact_type: str, studio: StudioApplication = Depends(get_studio)
):
    try:
        path = studio.artifact_store.path_for(job_id, artifact_type)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
