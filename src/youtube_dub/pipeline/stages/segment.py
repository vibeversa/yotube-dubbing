import json
from dataclasses import asdict

from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.domain.models import DubbingSegment
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class SegmentStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.SEGMENTED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running SEGMENTED stage")

        try:
            words_path = context.artifact_store.path_for(context.job_id, "words")
            segments_path = context.artifact_store.path_for(context.job_id, "segments")

            if not words_path.exists():
                return StageResult(StageStatus.FAILED, "Words artifact not found")

            if segments_path.exists():
                context.logger.info("Using existing segmentation artifact")
                return StageResult(StageStatus.COMPLETED)

            with open(words_path, "r") as f:
                words_data = json.load(f)

            if not words_data:
                context.logger.warning("No words to segment")
                segments: list[DubbingSegment] = []
            else:
                # Simplistic dummy segmentation for now based on chunk_ms
                # In real life, we would break on punctuation or silence gaps.
                segments = []
                current_words = []
                current_start = words_data[0]["start_ms"]

                chunk_ms = context.config.chunk_ms
                seg_idx = 1

                for w in words_data:
                    current_words.append(w["word"])

                    if w["end_ms"] - current_start >= chunk_ms:
                        segments.append(
                            DubbingSegment(
                                segment_id=f"seg-{seg_idx:06d}",
                                start_ms=current_start,
                                end_ms=w["end_ms"],
                                source_text=" ".join(current_words),
                            )
                        )
                        current_words = []
                        current_start = w[
                            "end_ms"
                        ]  # Next chunk starts where this ended
                        seg_idx += 1

                if current_words:
                    # push remainder
                    segments.append(
                        DubbingSegment(
                            segment_id=f"seg-{seg_idx:06d}",
                            start_ms=current_start,
                            end_ms=words_data[-1]["end_ms"],
                            source_text=" ".join(current_words),
                        )
                    )

            segments_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = segments_path.with_suffix(".tmp")

            with open(tmp_path, "w") as f:
                json.dump([asdict(s) for s in segments], f, indent=2)

            tmp_path.replace(segments_path)

            context.logger.info(f"Generated {len(segments)} segments")
            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"SEGMENTED failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
