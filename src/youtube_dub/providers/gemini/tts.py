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

            prompt = text

            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice.name,
                                )
                            )
                        ),
                    ),
                )

                if (
                    not response.candidates
                    or not response.candidates[0].content
                    or not response.candidates[0].content.parts
                ):
                    raise ProviderError("No audio returned in response candidates")

                audio_bytes = None
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        audio_bytes = part.inline_data.data
                        break

                if not audio_bytes:
                    raise ProviderError("No inline audio data found in response")

                return audio_bytes

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
