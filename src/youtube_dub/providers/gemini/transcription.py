import json
from pathlib import Path

from google import genai

from youtube_dub.domain.errors import ProviderInvalidRequestError
from youtube_dub.domain.models import WordTimestamp
from youtube_dub.providers.base import TranscriptionProvider
from youtube_dub.providers.gemini.executor import GeminiCallExecutor


class GeminiTranscriptionProvider(TranscriptionProvider):
    def __init__(self, executor: GeminiCallExecutor, sdk_client_factory=genai.Client):
        self.executor = executor
        self.sdk_client_factory = sdk_client_factory

    async def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> list[WordTimestamp]:

        if not audio_path.exists():
            raise ProviderInvalidRequestError(f"Audio file not found: {audio_path}")

        async def _call_gemini(model_name: str, api_key: str) -> list[WordTimestamp]:
            client = self.sdk_client_factory(api_key=api_key)

            # Simulated call for now until we fully integrate the real API wrapper,
            # this represents mapping the provider's domain request to the SDK request.
            # In real implementation we'd upload the file and prompt it for timestamps.

            # Using a stub response mapping
            # We would call client.models.generate_content(...) here
            response_text = await self._mock_api_call(
                client, model_name, audio_path, language
            )
            return self._parse_response(response_text)

        return await self.executor.execute(_call_gemini)

    async def _mock_api_call(
        self, client: genai.Client, model: str, path: Path, lang: str | None
    ) -> str:
        # A real implementation would upload and prompt.
        # This is overridden in tests.
        return '[{"word": "hello", "start_ms": 0, "end_ms": 500}]'

    def _parse_response(self, text: str) -> list[WordTimestamp]:
        try:
            data = json.loads(text)
            return [
                WordTimestamp(
                    word=item["word"],
                    start_ms=float(item["start_ms"]),
                    end_ms=float(item["end_ms"]),
                )
                for item in data
            ]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # We map malformed response to an invalid request or specific provider error
            # For simplicity, treating it as a generic exception that the executor will catch
            # and bubble up or we can raise a ProviderError explicitly.
            from youtube_dub.domain.errors import ProviderError

            raise ProviderError(f"Malformed transcription response: {e}")
