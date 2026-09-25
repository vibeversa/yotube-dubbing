import os
from unittest.mock import patch

import pytest

from youtube_dub.config.loader import AppConfig, load_config
from youtube_dub.domain.errors import ConfigurationError


def test_load_config_defaults():
    with patch.dict(os.environ, {}, clear=True):
        config = load_config()
        assert config.source_language == "en"
        assert config.target_language == "es"
        assert config.transcription_model == "gemini-1.5-flash"
        assert config.max_concurrent_tts_calls == 5


def test_load_config_from_env():
    env = {
        "DUB_SOURCE_LANGUAGE": "fr",
        "DUB_TARGET_LANGUAGE": "de",
        "DUB_MAX_CONCURRENT_TTS_CALLS": "10",
        "DUB_TRANSCRIPTION_FALLBACKS": "gemini-1.5-pro,gemini-1.0-pro",
    }
    with patch.dict(os.environ, env, clear=True):
        config = load_config()
        assert config.source_language == "fr"
        assert config.target_language == "de"
        assert config.max_concurrent_tts_calls == 10
        assert config.transcription_fallbacks == ["gemini-1.5-pro", "gemini-1.0-pro"]


def test_config_validation():
    with pytest.raises(ConfigurationError):
        AppConfig(
            source_language="en",
            target_language="es",
            job_root="",
            transcription_model="model",
            translation_model="model",
            tts_model="model",
            api_keys=["k"],
        )
