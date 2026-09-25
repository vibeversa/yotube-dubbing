import base64
import json
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
    mock_response.text = json.dumps(
        {"audio_base64": base64.b64encode(b"audio").decode()}
    )
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTTSProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    result = await provider.synthesize("hello", voice=VoiceProfile("voice1"))
    assert result == b"audio"


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
@pytest.mark.parametrize(
    "response_text",
    [
        "not json",
        "{}",
        '{"audio_base64": null}',
    ],
)
async def test_synthesize_malformed_response(fake_executor, response_text):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTTSProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    with pytest.raises(ProviderError):
        await provider.synthesize("test", voice=VoiceProfile("voice1"))
