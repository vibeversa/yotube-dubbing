from google import genai

from youtube_dub.domain.errors import ProviderInvalidRequestError
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

            return await self._mock_api_call(client, model_name, text, voice)

        return await self.executor.execute(_call_gemini)

    async def _mock_api_call(
        self, client: genai.Client, model: str, text: str, voice: VoiceProfile
    ) -> bytes:
        # Overridden in tests
        return b"mock_audio_data"
