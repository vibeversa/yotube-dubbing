import json
import shutil
import tempfile
from pathlib import Path

from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.media.mixing import mix_audio
from youtube_dub.media.separation import PassThroughVocalSeparator
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class MixStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.MIXED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running MIXED stage")

        try:
            # 1. Gather timed segments
            timing_path = context.artifact_store.path_for(context.job_id, "timing")
            if not timing_path.exists():
                return StageResult(StageStatus.FAILED, "Timing artifact not found")

            translations_path = context.artifact_store.path_for(
                context.job_id, "translations"
            )
            if not translations_path.exists():
                return StageResult(
                    StageStatus.FAILED, "Translations artifact not found"
                )

            with open(timing_path, "r") as f:
                timing_data = {t["segment_id"]: t for t in json.load(f)}

            with open(translations_path, "r") as f:
                segments_data = json.load(f)

            mix_path = context.artifact_store.path_for(context.job_id, "mix")
            if mix_path.exists():
                return StageResult(StageStatus.COMPLETED)

            # 2. Get separated background
            source_audio = context.artifact_store.path_for(
                context.job_id, "source_audio"
            )
            if not source_audio.exists():
                return StageResult(StageStatus.FAILED, "Source audio missing")

            bg_path = context.artifact_store.path_for(context.job_id, "separated_bg")
            if not bg_path.exists():
                sep = PassThroughVocalSeparator()
                _, new_bg = await sep.separate(
                    source_audio, bg_path.parent, context.process_runner
                )
                bg_path = new_bg

            mix_path.parent.mkdir(parents=True, exist_ok=True)

            if not timing_data:
                shutil.copy2(bg_path, mix_path)
                return StageResult(StageStatus.COMPLETED)

            # Build a complex filter mapping
            with tempfile.TemporaryDirectory() as td:
                temp_dir = Path(td)

                # Combine multiple timed tracks on their timeline using ffmpeg adelay
                inputs = []
                filter_parts = []
                input_idx = 0

                for s in segments_data:
                    seg_id = s["segment_id"]
                    if seg_id not in timing_data:
                        continue

                    timed_audio = context.artifact_store.path_for(
                        context.job_id, "timing", seg_id
                    )

                    if not timed_audio.exists():
                        continue

                    start_ms = s["start_ms"]
                    inputs.extend(["-i", str(timed_audio)])
                    filter_parts.append(
                        f"[{input_idx}:a]adelay={start_ms}|{start_ms}[a{input_idx}];"
                    )
                    input_idx += 1

                if not inputs:
                    shutil.copy2(bg_path, mix_path)
                    return StageResult(StageStatus.COMPLETED)

                # amix all delayed segments together into one vocal track
                mix_parts = "".join([f"[a{i}]" for i in range(input_idx)])
                filter_parts.append(
                    f"{mix_parts}amix=inputs={input_idx}:duration=longest[vocals]"
                )

                filter_str = "".join(filter_parts)

                mixed_vocals_path = temp_dir / "mixed_vocals.wav"

                cmd = (
                    ["ffmpeg", "-y"]
                    + inputs
                    + [
                        "-filter_complex",
                        filter_str,
                        "-map",
                        "[vocals]",
                        str(mixed_vocals_path),
                    ]
                )

                await context.process_runner.run(cmd, check=True)

                # Mix vocals with background
                await mix_audio(
                    mixed_vocals_path, bg_path, mix_path, context.process_runner
                )

            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"MIXED failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
