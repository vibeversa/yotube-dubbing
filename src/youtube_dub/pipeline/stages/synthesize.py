import asyncio
import json
from dataclasses import asdict

from youtube_dub.domain.enums import PipelineStage, SegmentStatus, StageStatus
from youtube_dub.domain.models import DubbingSegment, VoiceProfile
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class SynthesizeStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.TTS_PARTIAL

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running TTS_PARTIAL stage")

        try:
            if not context.tts_provider:
                return StageResult(StageStatus.FAILED, "TTS provider not configured")

            translations_path = context.artifact_store.path_for(
                context.job_id, "translations"
            )

            if not translations_path.exists():
                return StageResult(
                    StageStatus.FAILED, "Translations artifact not found"
                )

            with open(translations_path, "r") as f:
                segments_data = json.load(f)

            segments = [
                DubbingSegment(
                    segment_id=s["segment_id"],
                    start_ms=s["start_ms"],
                    end_ms=s["end_ms"],
                    source_text=s["source_text"],
                    translated_text=s.get("translated_text"),
                    status=SegmentStatus(s.get("status", "PENDING")),
                    tts_artifact=s.get("tts_artifact"),
                    error=s.get("error"),
                )
                for s in segments_data
            ]

            context.check_cancelled()

            # Setup concurrency boundaries
            semaphore = asyncio.Semaphore(context.config.max_concurrent_tts_calls)

            async def _synthesize_segment(seg: DubbingSegment) -> None:
                if (
                    seg.status == SegmentStatus.SYNTHESIZED
                    and context.artifact_store.exists(
                        context.job_id, "tts", seg.segment_id
                    )
                ):
                    return  # skip already successful

                if not seg.translated_text:
                    seg.status = SegmentStatus.FAILED
                    seg.error = "No translated text available"
                    return

                async with semaphore:
                    context.check_cancelled()
                    try:
                        if not context.tts_provider:
                            raise ValueError(
                                "TTS provider is None in synthesize segment logic"
                            )

                        voice = VoiceProfile(
                            "default"
                        )  # Placeholder for actual voice profile selection

                        audio_bytes = await context.tts_provider.synthesize(
                            seg.translated_text, voice=voice
                        )

                        out_path = context.artifact_store.path_for(
                            context.job_id, "tts", seg.segment_id
                        )
                        out_path.parent.mkdir(parents=True, exist_ok=True)

                        tmp_path = out_path.with_suffix(".tmp")
                        with open(tmp_path, "wb") as f:
                            f.write(audio_bytes)
                        tmp_path.replace(out_path)

                        seg.status = SegmentStatus.SYNTHESIZED
                        seg.tts_artifact = str(out_path.name)
                        seg.error = None

                    except Exception as e:
                        context.logger.warning(f"TTS failed for {seg.segment_id}: {e}")
                        seg.status = SegmentStatus.FAILED
                        seg.error = str(e)

            # Execute with bounded concurrency
            tasks = [_synthesize_segment(seg) for seg in segments]
            await asyncio.gather(*tasks)

            # Persist the updated segment state (which may include partial failures)
            tmp_path = translations_path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump([asdict(s) for s in segments], f, indent=2)
            tmp_path.replace(translations_path)

            failed_count = sum(1 for s in segments if s.status == SegmentStatus.FAILED)
            if failed_count > 0:
                context.logger.warning(f"{failed_count} segments failed TTS synthesis")
                return StageResult(
                    StageStatus.FAILED,
                    f"Partial completion: {failed_count} segments failed",
                )

            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"TTS_PARTIAL failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
