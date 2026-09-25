import base64
import json
from unittest.mock import MagicMock

import pytest

from youtube_dub.domain.errors import ProviderInvalidRequestError
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
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {"audio_base64": base64.b64encode(b"audio").decode()}
    )
    mock_client.models.generate_content.return_value = mock_response

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
