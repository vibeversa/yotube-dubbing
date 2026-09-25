import json

from youtube_dub.domain.enums import PipelineStage, SegmentStatus, StageStatus
from youtube_dub.domain.errors import ProcessError
from youtube_dub.media.ffmpeg.probe import probe_media
from youtube_dub.media.timing import apply_timing_fit
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class TimeFitStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.TIMED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running TIMED stage")

        try:
            translations_path = context.artifact_store.path_for(
                context.job_id, "translations"
            )
            timing_path = context.artifact_store.path_for(context.job_id, "timing")

            if not translations_path.exists():
                return StageResult(
                    StageStatus.FAILED, "Translations artifact not found"
                )

            if timing_path.exists():
                context.logger.info("Using existing timing artifact")
                return StageResult(StageStatus.COMPLETED)

            with open(translations_path, "r") as f:
                segments_data = json.load(f)

            timing_data = []

            for s in segments_data:
                seg_id = s["segment_id"]
                if s.get("status") != SegmentStatus.SYNTHESIZED.value:
                    context.logger.warning(
                        f"Skipping timing for incomplete segment {seg_id}"
                    )
                    continue

                tts_audio = context.artifact_store.path_for(
                    context.job_id, "tts", seg_id
                )
                if not tts_audio.exists():
                    continue

                # Find current duration
                try:
                    probe_info = await probe_media(tts_audio, context.process_runner)
                except ProcessError as e:
                    context.logger.warning(
                        f"Could not probe TTS audio for {seg_id}: {e}"
                    )
                    continue

                target_duration_s = probe_info.duration_s

                # Find allowed duration
                allowed_duration_s = (s["end_ms"] - s["start_ms"]) / 1000.0

                # Calculate ratio (target / allowed means if target is 2s and allowed is 1s, speed up by 2.0x)
                if allowed_duration_s <= 0:
                    ratio = 1.0
                else:
                    ratio = target_duration_s / allowed_duration_s

                timed_audio = context.artifact_store.path_for(
                    context.job_id, "timing", seg_id
                )
                timed_audio.parent.mkdir(parents=True, exist_ok=True)

                await apply_timing_fit(
                    tts_audio, timed_audio, context.process_runner, ratio
                )

                timing_data.append(
                    {
                        "segment_id": seg_id,
                        "target_duration_s": target_duration_s,
                        "allowed_duration_s": allowed_duration_s,
                        "ratio": ratio,
                        "timed_artifact": str(timed_audio.name),
                    }
                )

            tmp_path = timing_path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(timing_data, f, indent=2)
            tmp_path.replace(timing_path)

            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"TIMED failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
