from pathlib import Path
from typing import Protocol

from youtube_dub.domain.models import DubbingSegment, VoiceProfile, WordTimestamp


class TranscriptionProvider(Protocol):
    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> list[WordTimestamp]: ...


class ContentContext(Protocol):
    pass


class TranslationProvider(Protocol):
    async def translate(
        self,
        segments: list[DubbingSegment],
        *,
        target_language: str,
        context: ContentContext | None = None,
    ) -> list[DubbingSegment]: ...


class TTSProvider(Protocol):
    async def synthesize(
        self,
        text: str,
        *,
        voice: VoiceProfile,
    ) -> bytes: ...
