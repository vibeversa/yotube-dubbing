import json
from dataclasses import asdict

from youtube_dub.domain.enums import PipelineStage, StageStatus
from youtube_dub.pipeline.context import PipelineContext
from youtube_dub.pipeline.stages.base import PipelineStageRunner, StageResult


class TranscribeStage(PipelineStageRunner):
    @property
    def stage(self) -> PipelineStage:
        return PipelineStage.TRANSCRIBED

    async def run(self, context: PipelineContext) -> StageResult:
        context.logger.info("Running TRANSCRIBED stage")

        try:
            if not context.transcription_provider:
                return StageResult(
                    StageStatus.FAILED, "Transcription provider not configured"
                )

            source_audio_path = context.artifact_store.path_for(
                context.job_id, "source_audio"
            )
            words_path = context.artifact_store.path_for(context.job_id, "words")

            if not source_audio_path.exists():
                return StageResult(
                    StageStatus.FAILED, "Source audio artifact not found"
                )

            # Idempotency check
            if words_path.exists():
                context.logger.info("Using existing transcription artifact")
                return StageResult(StageStatus.COMPLETED)

            context.check_cancelled()

            # Call provider
            timestamps = await context.transcription_provider.transcribe(
                source_audio_path, language=context.manifest.source_language
            )

            # Write artifact atomically
            words_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = words_path.with_suffix(".tmp")

            with open(tmp_path, "w") as f:
                json.dump([asdict(w) for w in timestamps], f, indent=2)

            tmp_path.replace(words_path)

            context.logger.info(f"Persisted {len(timestamps)} word timestamps")
            return StageResult(StageStatus.COMPLETED)

        except Exception as e:
            context.logger.error(f"TRANSCRIBED failed: {e}")
            return StageResult(StageStatus.FAILED, str(e))
