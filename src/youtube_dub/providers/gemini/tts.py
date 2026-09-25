import base64
import json

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

            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )

                data = json.loads(response.text)
                b64_str = data["audio_base64"]
                return base64.b64decode(b64_str)

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
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                raise ProviderError(f"Malformed TTS response: {e}")

        return await self.executor.execute(_call_gemini)
