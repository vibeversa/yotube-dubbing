import asyncio
import logging
from dataclasses import dataclass, field

from youtube_dub.config.loader import AppConfig
from youtube_dub.media.process_runner import ProcessRunner
from youtube_dub.pipeline.manifest import JobManifest
from youtube_dub.providers.base import (
    TranscriptionProvider,
    TranslationProvider,
    TTSProvider,
)
from youtube_dub.storage.artifacts import JobArtifactStore


@dataclass
class PipelineContext:
    job_id: str
    config: AppConfig
    manifest: JobManifest
    artifact_store: JobArtifactStore
    process_runner: ProcessRunner
    logger: logging.Logger

    # Optional because not all stages need all providers
    transcription_provider: TranscriptionProvider | None = None
    translation_provider: TranslationProvider | None = None
    tts_provider: TTSProvider | None = None

    # Simple cancellation event
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def check_cancelled(self) -> None:
        """Throws asyncio.CancelledError if the pipeline is cancelled."""
        if self.is_cancelled():
            raise asyncio.CancelledError("Pipeline context cancelled")
