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
                segments = []
                current_words = []
                current_start = words_data[0]["start_ms"]

                chunk_ms = context.config.chunk_ms
                seg_idx = 1

                # Minimum duration constraint so we don't end up with 10ms micro-segments
                MIN_GAP_MS = 200

                for i, w in enumerate(words_data):
                    current_words.append(w["word"])

                    next_word = words_data[i + 1] if i + 1 < len(words_data) else None
                    gap = next_word["start_ms"] - w["end_ms"] if next_word else 0

                    duration = w["end_ms"] - current_start

                    # Split if we exceed chunk size AND there's a reasonable gap to pause on
                    if duration >= chunk_ms and gap >= MIN_GAP_MS:
                        segments.append(
                            DubbingSegment(
                                segment_id=f"seg-{seg_idx:06d}",
                                start_ms=current_start,
                                end_ms=w["end_ms"],
                                source_text=" ".join(current_words),
                            )
                        )
                        current_words = []
                        if next_word:
                            current_start = next_word["start_ms"]
                        seg_idx += 1

                if current_words:
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
