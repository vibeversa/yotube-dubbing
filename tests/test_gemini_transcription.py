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
    from unittest.mock import AsyncMock

    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake audio content")

    mock_client = MagicMock()
    mock_client.aio.files.upload = AsyncMock(
        return_value=MagicMock(name="uploaded_file")
    )
    mock_client.aio.files.delete = AsyncMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps([{"word": "hello", "start_ms": 0, "end_ms": 500}])
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTranscriptionProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    result = await provider.transcribe(audio_file, language="en")

    assert len(result) == 1
    assert result[0] == WordTimestamp("hello", 0.0, 500.0)
    mock_client.aio.files.upload.assert_called_once()
    mock_client.aio.models.generate_content.assert_called_once()

    # Verify response schema was passed
    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert "config" in call_kwargs
    config = call_kwargs["config"]
    assert config.response_schema is not None
    assert config.response_schema["type"] == "array"


@pytest.mark.asyncio
async def test_transcribe_missing_file(fake_executor):
    provider = GeminiTranscriptionProvider(
        fake_executor, sdk_client_factory=MagicMock()
    )

    with pytest.raises(ProviderInvalidRequestError, match="Audio file not found"):
        await provider.transcribe(Path("nonexistent.wav"))


@pytest.mark.asyncio
async def test_transcribe_malformed_response(fake_executor, tmp_path):
    from unittest.mock import AsyncMock

    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake")

    mock_client = MagicMock()
    mock_client.aio.files.upload = AsyncMock()
    mock_client.aio.files.delete = AsyncMock()
    mock_response = MagicMock()
    mock_response.text = "not json"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTranscriptionProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    with pytest.raises(ProviderError, match="Malformed transcription response"):
        await provider.transcribe(audio_file)
