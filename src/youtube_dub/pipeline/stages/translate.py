import json
from dataclasses import asdict

from youtube_dub.domain.enums import PipelineStage, SegmentStatus, StageStatus
from youtube_dub.domain.errors import ProviderError
from youtube_dub.domain.models import DubbingSegment
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class TranslateStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.TRANSLATED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running TRANSLATED stage")

        try:
            if not context.translation_provider:
                return StageResult(
                    StageStatus.FAILED, "Translation provider not configured"
                )

            segments_path = context.artifact_store.path_for(context.job_id, "segments")
            translations_path = context.artifact_store.path_for(
                context.job_id, "translations"
            )

            if not segments_path.exists():
                return StageResult(StageStatus.FAILED, "Segments artifact not found")

            if translations_path.exists():
                context.logger.info("Using existing translation artifact")
                return StageResult(StageStatus.COMPLETED)

            with open(segments_path, "r") as f:
                segments_data = json.load(f)

            segments = [
                DubbingSegment(
                    segment_id=s["segment_id"],
                    start_ms=s["start_ms"],
                    end_ms=s["end_ms"],
                    source_text=s["source_text"],
                    status=SegmentStatus(s.get("status", "PENDING")),
                )
                for s in segments_data
            ]

            context.check_cancelled()

            try:
                translated_segments = await context.translation_provider.translate(
                    segments, target_language=context.config.target_language
                )
            except ProviderError as e:
                return StageResult(StageStatus.FAILED, str(e))

            # Hard invariant validation: Provider must NOT mutate timeline
            if len(translated_segments) != len(segments):
                return StageResult(
                    StageStatus.FAILED,
                    "Translation provider returned mismatched segment count",
                )

            for orig, trans in zip(segments, translated_segments):
                if orig.segment_id != trans.segment_id:
                    return StageResult(
                        StageStatus.FAILED,
                        "Translation provider modified segment order/identity",
                    )
                if orig.start_ms != trans.start_ms or orig.end_ms != trans.end_ms:
                    return StageResult(
                        StageStatus.FAILED,
                        f"Translation invariant broken: segment {orig.segment_id} timing mutated",
                    )

                # Mark them translated
                trans.status = SegmentStatus.TRANSLATED

            translations_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = translations_path.with_suffix(".tmp")

            with open(tmp_path, "w") as f:
                json.dump([asdict(s) for s in translated_segments], f, indent=2)

            tmp_path.replace(translations_path)

            context.logger.info(f"Persisted {len(translated_segments)} translations")
            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"TRANSLATED failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
