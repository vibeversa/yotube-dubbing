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
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        [
            {"segment_id": "seg-1", "translated_text": "hola"},
            {"segment_id": "seg-2", "translated_text": "mundo"},
        ]
    )
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

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

    # Verify response schema was passed
    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert "config" in call_kwargs
    config = call_kwargs["config"]
    assert config.response_schema is not None
    assert config.response_schema["type"] == "array"


@pytest.mark.asyncio
async def test_translate_missing_segment_response(fake_executor):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        [{"segment_id": "seg-wrong", "translated_text": "hola"}]
    )
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTranslationProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    segments = [DubbingSegment("seg-1", 100, 500, "hello")]

    with pytest.raises(ProviderError, match="Missing translation for segment seg-1"):
        await provider.translate(segments, target_language="es")


@pytest.mark.asyncio
async def test_translate_empty_segments(fake_executor):
    provider = GeminiTranslationProvider(fake_executor, sdk_client_factory=MagicMock())
    result = await provider.translate([], target_language="es")
    assert result == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_text,expected_match",
    [
        ("{}", "Translation response is not a JSON array"),
        (json.dumps([{"segment_id": "seg-1"}]), "Missing expected fields"),
        (json.dumps([{"translated_text": "hola"}]), "Missing expected fields"),
        (
            json.dumps(
                [
                    {"segment_id": "seg-1", "translated_text": "hola"},
                    {"segment_id": "seg-1", "translated_text": "mundo"},
                ]
            ),
            "Duplicate translation for segment seg-1",
        ),
    ],
)
async def test_translate_parse_errors(fake_executor, response_text, expected_match):
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiTranslationProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    segments = [DubbingSegment("seg-1", 100, 500, "hello")]

    with pytest.raises(ProviderError, match=expected_match):
        await provider.translate(segments, target_language="es")


@pytest.mark.asyncio
async def test_translate_api_error(fake_executor):
    from unittest.mock import AsyncMock

    from google.genai.errors import APIError

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=APIError(
            code=400, response_json={"error": {"message": "bad request"}}
        )
    )

    provider = GeminiTranslationProvider(
        fake_executor, sdk_client_factory=lambda **kwargs: mock_client
    )

    segments = [DubbingSegment("seg-1", 100, 500, "hello")]

    with pytest.raises(ProviderError):
        await provider.translate(segments, target_language="es")
