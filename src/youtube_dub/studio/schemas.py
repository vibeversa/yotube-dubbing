from typing import Any

from pydantic import BaseModel


class SuggestedAction(BaseModel):
    id: str
    label: str


class JobFailureDetails(BaseModel):
    stage: str
    segment_id: str | None = None
    error_code: str
    message: str
    retryable: bool
    suggested_actions: list[SuggestedAction]


class JobResponse(BaseModel):
    manifest: Any
    failure: JobFailureDetails | None = None
