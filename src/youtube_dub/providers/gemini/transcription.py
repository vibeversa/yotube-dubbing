import json
from pathlib import Path

from google import genai
from google.genai import types

from youtube_dub.domain.errors import ProviderError, ProviderInvalidRequestError
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
                uploaded_file = client.files.upload(file=str(audio_path))

                prompt = (
                    "Transcribe the following audio file. Return a JSON array "
                    "of objects, where each object has 'word', 'start_ms', and 'end_ms'."
                )
                if language:
                    prompt += f" The language is {language}."

                response = client.models.generate_content(
                    model=model_name,
                    contents=[uploaded_file, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )

                return self._parse_response(response.text)

            finally:
                # Cleanup the file from Gemini if it was successfully uploaded
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        f"Failed to cleanup file {uploaded_file.name}: {e}"
                    )

        return await self.executor.execute(_call_gemini)

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
            raise ProviderError(f"Malformed transcription response: {e}")
