import base64

from google import genai
from google.genai import types

from youtube_dub.domain.errors import ProviderError, ProviderInvalidRequestError
from youtube_dub.domain.models import VoiceProfile
from youtube_dub.providers.base import TTSProvider
from youtube_dub.providers.gemini.executor import GeminiCallExecutor


class GeminiTTSProvider(TTSProvider):
    def __init__(self, executor: GeminiCallExecutor, sdk_client_factory=genai.Client):
        self.executor = executor
        self.sdk_client_factory = sdk_client_factory

    async def synthesize(
        self,
        text: str,
        *,
        voice: VoiceProfile,
    ) -> bytes:

        if not text.strip():
            raise ProviderInvalidRequestError("Cannot synthesize empty text")

        async def _call_gemini(model_name: str, api_key: str) -> bytes:
            client = self.sdk_client_factory(api_key=api_key)

            prompt = (
                f"Synthesize the following text into spoken audio using a voice resembling {voice.name}. "
                "Return the raw audio bytes as a base64 encoded string in a JSON object under the key 'audio_base64'.\n\n"
                f"{text}"
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            try:
                import json

                data = json.loads(response.text)
                b64_str = data["audio_base64"]
                return base64.b64decode(b64_str)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                raise ProviderError(f"Malformed TTS response: {e}")

        return await self.executor.execute(_call_gemini)
