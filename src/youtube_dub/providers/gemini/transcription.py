import json
from pathlib import Path

from google import genai
from google.genai import types
from google.genai.errors import APIError

from youtube_dub.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTransientError,
)
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

            # Upload the file
            try:
                uploaded_file = await client.aio.files.upload(file=str(audio_path))

                prompt = (
                    "Transcribe the following audio file. Return a JSON array "
                    "of objects, where each object has 'word', 'start_ms', and 'end_ms'."
                )
                if language:
                    prompt += f" The language is {language}."

                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=[uploaded_file, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema={
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "word": {"type": "string"},
                                    "start_ms": {"type": "number"},
                                    "end_ms": {"type": "number"},
                                },
                                "required": ["word", "start_ms", "end_ms"],
                            },
                        },
                    ),
                )

                return self._parse_response(response.text)

            except APIError as e:
                # Map SDK errors to domain errors
                if e.code == 429:
                    if "quota" in str(e).lower():
                        raise ProviderQuotaError(str(e))
                    raise ProviderRateLimitError(str(e))
                elif e.code in [401, 403]:
                    raise ProviderAuthenticationError(str(e))
                elif e.code in [500, 502, 503, 504]:
                    raise ProviderTransientError(str(e))
                elif e.code == 400:
                    raise ProviderInvalidRequestError(str(e))
                else:
                    raise ProviderError(str(e))
            finally:
                # Cleanup the file from Gemini if it was successfully uploaded
                try:
                    if "uploaded_file" in locals() and hasattr(uploaded_file, "name"):
                        await client.aio.files.delete(name=uploaded_file.name)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(f"Failed to cleanup file: {e}")

        return await self.executor.execute(_call_gemini)

    def _parse_response(self, text: str) -> list[WordTimestamp]:
        try:
            data = json.loads(text)
            if not isinstance(data, list):
                raise ProviderError("Transcription response is not a JSON array")

            timestamps = []
            for item in data:
                if "word" not in item or "start_ms" not in item or "end_ms" not in item:
                    raise ProviderError("Missing expected fields in transcription word")

                word = str(item["word"])
                if not word:
                    raise ProviderError("Word cannot be empty")

                start_ms = float(item["start_ms"])
                end_ms = float(item["end_ms"])

                if start_ms < 0:
                    raise ProviderError(
                        f"Invalid timing for word '{word}': start_ms must be >= 0"
                    )
                if end_ms < start_ms:
                    raise ProviderError(
                        f"Invalid timing for word '{word}': end_ms must be >= start_ms"
                    )

                timestamps.append(
                    WordTimestamp(
                        word=word,
                        start_ms=start_ms,
                        end_ms=end_ms,
                    )
                )

            # Guarantee deterministic order and timing logic
            timestamps.sort(key=lambda w: w.start_ms)

            return timestamps
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ProviderError(f"Malformed transcription response: {e}")
