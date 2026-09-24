import json
import os
from pathlib import Path
from typing import Any

from youtube_dub.domain.enums import JobStatus, PipelineStage, StageStatus
from youtube_dub.domain.errors import ManifestError
from youtube_dub.pipeline.manifest import JobManifest, StageRecord


class ManifestStore:
    def __init__(self, job_root: Path):
        self.job_root = job_root

    def _get_manifest_path(self, job_id: str) -> Path:
        return self.job_root / str(job_id) / "manifest.json"

    def _serialize_manifest(self, manifest: JobManifest) -> str:
        data = {
            "schema_version": manifest.schema_version,
            "pipeline_version": manifest.pipeline_version,
            "job_id": str(manifest.job_id),
            "status": manifest.status.value,
            "current_stage": manifest.current_stage.value,
            "created_at": manifest.created_at,
            "updated_at": manifest.updated_at,
            "stages": {
                name: {
                    "stage": record.stage.value,
                    "status": record.status.value,
                    "started_at": record.started_at,
                    "completed_at": record.completed_at,
                    "attempt_count": record.attempt_count,
                    "artifacts": record.artifacts,
                    "error": record.error,
                }
                for name, record in manifest.stages.items()
            },
        }
        return json.dumps(data, indent=2)

    def _deserialize_manifest(self, data: dict[str, Any]) -> JobManifest:
        try:
            import uuid

            stages = {
                name: StageRecord(
                    stage=PipelineStage(record_data["stage"]),
                    status=StageStatus(record_data["status"]),
                    started_at=record_data.get("started_at"),
                    completed_at=record_data.get("completed_at"),
                    attempt_count=record_data.get("attempt_count", 0),
                    artifacts=record_data.get("artifacts", []),
                    error=record_data.get("error"),
                )
                for name, record_data in data.get("stages", {}).items()
            }
            return JobManifest(
                schema_version=data["schema_version"],
                pipeline_version=data["pipeline_version"],
                job_id=uuid.UUID(data["job_id"]),
                status=JobStatus(data["status"]),
                current_stage=PipelineStage(data["current_stage"]),
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                stages=stages,
            )
        except (KeyError, ValueError) as e:
            raise ManifestError(f"Corrupt manifest: {e}")

    def save(self, manifest: JobManifest) -> None:
        path = self._get_manifest_path(str(manifest.job_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")

        try:
            content = self._serialize_manifest(manifest)
            with open(tmp_path, "w") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            tmp_path.replace(path)
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise ManifestError(f"Failed to save manifest: {e}")

    def load(self, job_id: str) -> JobManifest:
        path = self._get_manifest_path(job_id)
        if not path.exists():
            raise ManifestError(f"Manifest not found for job: {job_id}")

        try:
            with open(path, "r") as f:
                data = json.load(f)
            return self._deserialize_manifest(data)
        except json.JSONDecodeError as e:
            raise ManifestError(f"Manifest JSON corrupt: {e}")
