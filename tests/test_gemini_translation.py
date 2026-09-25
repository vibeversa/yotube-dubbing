import json
from unittest.mock import MagicMock

import pytest

from youtube_dub.domain.errors import ProviderError
from youtube_dub.domain.models import DubbingSegment
from youtube_dub.providers.gemini.executor import GeminiCallExecutor
from youtube_dub.providers.gemini.translation import GeminiTranslationProvider
from youtube_dub.providers.keys import ApiKeyPool


@pytest.fixture
def fake_executor():
    pool = ApiKeyPool(["fake_key"])

    async def sleep(x):
        pass

    return GeminiCallExecutor(["fake_model"], pool, sleeper=sleep)


@pytest.mark.asyncio
async def test_translate_success_preserves_timeline(fake_executor):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        [
            {"segment_id": "seg-1", "translated_text": "hola"},
            {"segment_id": "seg-2", "translated_text": "mundo"},
        ]
    )
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiTranslationProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    segments = [
        DubbingSegment("seg-1", 100, 500, "hello"),
        DubbingSegment("seg-2", 600, 1000, "world"),
    ]

    result = await provider.translate(segments, target_language="es")

    assert len(result) == 2
    assert result[0].translated_text == "hola"
    assert result[0].start_ms == 100
    assert result[0].end_ms == 500

    assert result[1].translated_text == "mundo"
    assert result[1].start_ms == 600
    assert result[1].end_ms == 1000


@pytest.mark.asyncio
async def test_translate_missing_segment_response(fake_executor):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        [{"segment_id": "seg-wrong", "translated_text": "hola"}]
    )
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiTranslationProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    segments = [DubbingSegment("seg-1", 100, 500, "hello")]

    with pytest.raises(ProviderError, match="Missing translation for segment seg-1"):
        await provider.translate(segments, target_language="es")
