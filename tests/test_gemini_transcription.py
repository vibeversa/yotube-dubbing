import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from youtube_dub.domain.errors import ProviderError, ProviderInvalidRequestError
from youtube_dub.domain.models import WordTimestamp
from youtube_dub.providers.gemini.executor import GeminiCallExecutor
from youtube_dub.providers.gemini.transcription import GeminiTranscriptionProvider
from youtube_dub.providers.keys import ApiKeyPool


@pytest.fixture
def fake_executor():
    pool = ApiKeyPool(["fake_key"])

    # Fake sleeper
    async def sleep(x):
        pass

    return GeminiCallExecutor(["fake_model"], pool, sleeper=sleep)


@pytest.mark.asyncio
async def test_transcribe_success(fake_executor, tmp_path):
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake audio content")

    provider = GeminiTranscriptionProvider(
        fake_executor, sdk_client_factory=MagicMock()
    )

    # Override the mock API call for testing
    async def mock_call(client, model, path, lang):
        return json.dumps([{"word": "hello", "start_ms": 0, "end_ms": 500}])

    provider._mock_api_call = mock_call

    result = await provider.transcribe(audio_file, language="en")

    assert len(result) == 1
    assert result[0] == WordTimestamp("hello", 0.0, 500.0)


@pytest.mark.asyncio
async def test_transcribe_missing_file(fake_executor):
    provider = GeminiTranscriptionProvider(
        fake_executor, sdk_client_factory=MagicMock()
    )

    with pytest.raises(ProviderInvalidRequestError, match="Audio file not found"):
        await provider.transcribe(Path("nonexistent.wav"))


@pytest.mark.asyncio
async def test_transcribe_malformed_response(fake_executor, tmp_path):
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake")

    provider = GeminiTranscriptionProvider(
        fake_executor, sdk_client_factory=MagicMock()
    )

    async def mock_call(client, model, path, lang):
        return "not json"

    provider._mock_api_call = mock_call

    with pytest.raises(ProviderError, match="Malformed transcription response"):
        await provider.transcribe(audio_file)
