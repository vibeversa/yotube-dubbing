import json

from google import genai
from google.genai import types

from youtube_dub.domain.errors import ProviderError
from youtube_dub.domain.models import DubbingSegment
from youtube_dub.providers.base import ContentContext, TranslationProvider
from youtube_dub.providers.gemini.executor import GeminiCallExecutor


class GeminiTranslationProvider(TranslationProvider):
    def __init__(self, executor: GeminiCallExecutor, sdk_client_factory=genai.Client):
        self.executor = executor
        self.sdk_client_factory = sdk_client_factory

    async def translate(
        self,
        segments: list[DubbingSegment],
        *,
        target_language: str,
        context: ContentContext | None = None,
    ) -> list[DubbingSegment]:

        if not segments:
            return []

        async def _call_gemini(model_name: str, api_key: str) -> list[DubbingSegment]:
            client = self.sdk_client_factory(api_key=api_key)

            # Prepare payload
            payload = [
                {"segment_id": s.segment_id, "source_text": s.source_text}
                for s in segments
            ]

            prompt = (
                f"Translate the following text to {target_language}. "
                "Return a JSON array of objects with 'segment_id' and 'translated_text'.\n\n"
                f"{json.dumps(payload)}"
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            return self._parse_response(segments, response.text)

        return await self.executor.execute(_call_gemini)

    def _parse_response(
        self, original_segments: list[DubbingSegment], text: str
    ) -> list[DubbingSegment]:
        try:
            data = json.loads(text)
            translation_map = {
                item["segment_id"]: item["translated_text"] for item in data
            }

            translated_segments = []
            for seg in original_segments:
                if seg.segment_id not in translation_map:
                    raise ProviderError(
                        f"Missing translation for segment {seg.segment_id}"
                    )

                # We return a new instance to preserve invariants explicitly
                translated_segments.append(
                    DubbingSegment(
                        segment_id=seg.segment_id,
                        start_ms=seg.start_ms,  # Immutable timeline
                        end_ms=seg.end_ms,  # Immutable timeline
                        source_text=seg.source_text,
                        translated_text=translation_map[seg.segment_id],
                        status=seg.status,
                    )
                )
            return translated_segments
        except (json.JSONDecodeError, KeyError) as e:
            raise ProviderError(f"Malformed translation response: {e}")
