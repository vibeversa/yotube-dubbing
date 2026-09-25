import os
from dataclasses import dataclass, field

from youtube_dub.domain.errors import ConfigurationError


@dataclass(frozen=True)
class AppConfig:
    source_language: str
    target_language: str
    job_root: str
    transcription_model: str
    translation_model: str
    tts_model: str
    separation_model: str
    api_keys: list[str]
    transcription_fallbacks: list[str] = field(default_factory=list)
    translation_fallbacks: list[str] = field(default_factory=list)
    tts_fallbacks: list[str] = field(default_factory=list)
    repair_model: str | None = None
    repair_fallbacks: list[str] = field(default_factory=list)
    max_duration_s: int = 3600
    chunk_ms: int = 60000
    output_audio_bitrate: str = "192k"
    ffmpeg_timeout_s: int = 300
    max_concurrent_tts_calls: int = 5
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.max_concurrent_tts_calls <= 0:
            raise ConfigurationError("max_concurrent_tts_calls must be > 0")
        if self.ffmpeg_timeout_s <= 0:
            raise ConfigurationError("ffmpeg_timeout_s must be > 0")
        if not self.job_root:
            raise ConfigurationError("job_root must be set")
        if not self.transcription_model:
            raise ConfigurationError("transcription_model must be set")


def load_config() -> AppConfig:
    """Loads configuration from environment variables."""

    def get_list(name: str) -> list[str]:
        val = os.environ.get(name, "")
        return [v.strip() for v in val.split(",") if v.strip()]

    job_root = os.environ.get("DUB_JOB_ROOT", "data/jobs")
    transcription_model = os.environ.get("DUB_TRANSCRIPTION_MODEL", "gemini-1.5-flash")
    translation_model = os.environ.get("DUB_TRANSLATION_MODEL", "gemini-1.5-pro")
    tts_model = os.environ.get("DUB_TTS_MODEL", "google-tts")

    api_keys = get_list("GEMINI_API_KEY")
    if not api_keys:
        api_keys = ["DUMMY_KEY"]

    source_language = os.environ.get("DUB_SOURCE_LANGUAGE", "en")
    target_language = os.environ.get("DUB_TARGET_LANGUAGE", "es")

    max_concurrent_tts = int(os.environ.get("DUB_MAX_CONCURRENT_TTS_CALLS", "5"))
    ffmpeg_timeout = int(os.environ.get("DUB_FFMPEG_TIMEOUT_S", "300"))

    return AppConfig(
        source_language=source_language,
        target_language=target_language,
        job_root=job_root,
        transcription_model=transcription_model,
        translation_model=translation_model,
        tts_model=tts_model,
        separation_model=os.environ.get("DUB_SEPARATION_MODEL", "passthrough"),
        api_keys=api_keys,
        transcription_fallbacks=get_list("DUB_TRANSCRIPTION_FALLBACKS"),
        translation_fallbacks=get_list("DUB_TRANSLATION_FALLBACKS"),
        tts_fallbacks=get_list("DUB_TTS_FALLBACKS"),
        repair_model=os.environ.get("DUB_REPAIR_MODEL"),
        repair_fallbacks=get_list("DUB_REPAIR_FALLBACKS"),
        max_duration_s=int(os.environ.get("DUB_MAX_DURATION_S", "3600")),
        chunk_ms=int(os.environ.get("DUB_CHUNK_MS", "60000")),
        output_audio_bitrate=os.environ.get("DUB_OUTPUT_AUDIO_BITRATE", "192k"),
        ffmpeg_timeout_s=ffmpeg_timeout,
        max_concurrent_tts_calls=max_concurrent_tts,
        log_level=os.environ.get("DUB_LOG_LEVEL", "INFO"),
    )
