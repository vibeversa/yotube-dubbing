from typing import Protocol

from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.pipeline.manifest import JobManifest


class StageListener(Protocol):
    def on_stage_status_changed(
        self, manifest: JobManifest, stage: PipelineStage, status: StageStatus
    ) -> None: ...

    def on_job_status_changed(self, manifest: JobManifest) -> None: ...


class StageListenerRegistry:
    def __init__(self):
        self._listeners: list[StageListener] = []

    def add(self, listener: StageListener) -> None:
        self._listeners.append(listener)

    def remove(self, listener: StageListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def notify_stage_status(
        self, manifest: JobManifest, stage: PipelineStage, status: StageStatus
    ) -> None:
        for listener in self._listeners:
            try:
                listener.on_stage_status_changed(manifest, stage, status)
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(f"Listener failed: {e}")

    def notify_job_status(self, manifest: JobManifest) -> None:
        for listener in self._listeners:
            try:
                listener.on_job_status_changed(manifest)
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(f"Listener failed: {e}")
