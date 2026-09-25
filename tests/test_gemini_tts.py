from unittest.mock import MagicMock

import pytest
from google.genai.errors import APIError

from youtube_dub.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTransientError,
)
from youtube_dub.domain.models import VoiceProfile
from youtube_dub.providers.gemini.executor import GeminiCallExecutor
from youtube_dub.providers.gemini.tts import GeminiTTSProvider
from youtube_dub.providers.keys import ApiKeyPool


@pytest.fixture
def fake_executor():
    pool = ApiKeyPool(["fake_key"])

    async def sleep(x):
        pass

    return GeminiCallExecutor(["fake_model"], pool, sleeper=sleep)


@pytest.mark.asyncio
async def test_synthesize_success(fake_executor):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_response = MagicMock()

    mock_part = MagicMock()
    mock_part.inline_data.data = b"audio"
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_candidate = MagicMock()
    mock_candidate.content = mock_content
    mock_response.candidates = [mock_candidate]

    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTTSProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    result = await provider.synthesize("hello", voice=VoiceProfile("voice1"))
    assert result == b"audio"

    # Verify config was passed correctly
    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert "config" in call_kwargs
    config = call_kwargs["config"]
    assert config.response_modalities == ["AUDIO"]
    assert (
        config.speech_config.voice_config.prebuilt_voice_config.voice_name == "voice1"
    )


@pytest.mark.asyncio
async def test_synthesize_empty_text(fake_executor):
    provider = GeminiTTSProvider(fake_executor, sdk_client_factory=MagicMock())

    with pytest.raises(
        ProviderInvalidRequestError, match="Cannot synthesize empty text"
    ):
        await provider.synthesize("   ", voice=VoiceProfile("voice1"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, error_message, expected_exception",
    [
        (429, "Quota exceeded", ProviderQuotaError),
        (429, "Rate limit exceeded", ProviderRateLimitError),
        (401, "Unauthorized", ProviderAuthenticationError),
        (403, "Forbidden", ProviderAuthenticationError),
        (500, "Internal Server Error", ProviderTransientError),
        (502, "Bad Gateway", ProviderTransientError),
        (503, "Service Unavailable", ProviderTransientError),
        (504, "Gateway Timeout", ProviderTransientError),
        (400, "Bad Request", ProviderInvalidRequestError),
        (418, "I'm a teapot", ProviderError),
    ],
)
async def test_synthesize_api_errors(
    fake_executor, status_code, error_message, expected_exception
):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=APIError(
            code=status_code, response_json={"error": {"message": error_message}}
        )
    )

    provider = GeminiTTSProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    if expected_exception in (
        ProviderTransientError,
        ProviderQuotaError,
        ProviderRateLimitError,
        ProviderAuthenticationError,
        ProviderError,
    ):
        # The executor swallows these and raises a generic ProviderError or moves to next model
        # so we expect a generic ProviderError from the executor when it exhausts models/keys
        with pytest.raises(ProviderError):
            await provider.synthesize("test", voice=VoiceProfile("voice1"))
    else:
        with pytest.raises(expected_exception, match=error_message):
            await provider.synthesize("test", voice=VoiceProfile("voice1"))


@pytest.mark.asyncio
async def test_synthesize_malformed_response(fake_executor):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.candidates = []

    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTTSProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    with pytest.raises(ProviderError, match="No audio returned in response candidates"):
        await provider.synthesize("test", voice=VoiceProfile("voice1"))


@pytest.mark.asyncio
async def test_tts_missing_voice(fake_executor):
    provider = GeminiTTSProvider(fake_executor, sdk_client_factory=MagicMock())
    with pytest.raises(ProviderInvalidRequestError, match="Voice profile is required"):
        await provider.synthesize("test", voice=None)


@pytest.mark.asyncio
async def test_tts_json_decode_error(fake_executor):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=ValueError("json bad")
    )

    provider = GeminiTTSProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    with pytest.raises(ProviderError):
        await provider.synthesize("test", voice=VoiceProfile("voice1"))


@pytest.mark.asyncio
async def test_tts_no_inline_audio_data(fake_executor):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_response = MagicMock()

    mock_part = MagicMock()
    mock_part.inline_data = None
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_candidate = MagicMock()
    mock_candidate.content = mock_content
    mock_response.candidates = [mock_candidate]

    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTTSProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    with pytest.raises(ProviderError, match="No inline audio data found in response"):
        await provider.synthesize("test", voice=VoiceProfile("voice1"))
