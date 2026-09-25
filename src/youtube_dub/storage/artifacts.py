import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from youtube_dub.domain.enums import JobStatus, PipelineStage, StageStatus
from youtube_dub.domain.errors import ManifestError
from youtube_dub.pipeline.manifest import JobManifest, StageRecord


class ManifestStore:
    def __init__(self, job_root: Path):
        self.job_root = job_root

    def _get_manifest_path(self, job_id: str) -> Path:
        path = self.job_root / str(job_id) / "manifest.json"
        if not path.resolve().is_relative_to(self.job_root.resolve()):
            raise ValueError("Path traversal detected")
        return path

    def _serialize_manifest(self, manifest: JobManifest) -> str:
        data = {
            "schema_version": manifest.schema_version,
            "pipeline_version": manifest.pipeline_version,
            "job_id": str(manifest.job_id),
            "source_language": manifest.source_language,
            "target_language": manifest.target_language,
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
                source_language=data.get("source_language", "en"),
                target_language=data.get("target_language", "es"),
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

        manifest.updated_at = datetime.now(UTC).isoformat()

        try:
            content = self._serialize_manifest(manifest)
            with open(tmp_path, "w") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            tmp_path.replace(path)
        except OSError as e:
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


class JobArtifactStore:
    def __init__(self, manifest_store: ManifestStore):
        self.job_root = manifest_store.job_root
        self.manifest_store = manifest_store

    def get_job_dir(self, job_id: str) -> Path:
        path = self.job_root / job_id
        if not path.resolve().is_relative_to(self.job_root.resolve()):
            raise ValueError("Path traversal detected")
        return path

    def path_for(
        self, job_id: str, artifact_type: str, segment_id: str | None = None
    ) -> Path:
        job_dir = self.get_job_dir(job_id)

        if artifact_type == "source_media":
            result = job_dir / "source" / "input.mp4"  # Simplify extension for now
        elif artifact_type == "source_audio":
            result = job_dir / "source" / "source_audio.wav"
        elif artifact_type == "separated_vocals":
            result = job_dir / "source" / "vocals.wav"
        elif artifact_type == "separated_bg":
            result = job_dir / "source" / "background.wav"
        elif artifact_type == "words":
            result = job_dir / "transcription" / "words.json"
        elif artifact_type == "segments":
            result = job_dir / "segmentation" / "segments.json"
        elif artifact_type == "translations":
            result = job_dir / "translation" / "translations.json"
        elif artifact_type == "tts":
            if not segment_id:
                raise ValueError("tts artifact requires segment_id")
            result = job_dir / "tts" / f"{segment_id}.wav"
        elif artifact_type == "timing":
            result = job_dir / "timing" / "timing.json"
        elif artifact_type == "mix":
            result = job_dir / "mix" / "dubbed_audio.wav"
        elif artifact_type == "render":
            result = job_dir / "render" / "final.mp4"
        else:
            raise ValueError(f"Unknown artifact type: {artifact_type}")

        job_dir.mkdir(parents=True, exist_ok=True)
        if not result.resolve().is_relative_to(job_dir.resolve()):
            raise ValueError("Path traversal detected")

        return result

    def exists(
        self, job_id: str, artifact_type: str, segment_id: str | None = None
    ) -> bool:
        return self.path_for(job_id, artifact_type, segment_id).exists()
