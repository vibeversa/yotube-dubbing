from pathlib import Path

from google import genai

from youtube_dub.config.loader import load_config
from youtube_dub.media.process_runner import ProcessRunner
from youtube_dub.media.separation import (
    DemucsVocalSeparator,
    PassThroughVocalSeparator,
    VocalSeparator,
)
from youtube_dub.pipeline.listeners import StageListenerRegistry
from youtube_dub.pipeline.runner import PipelineRunner
from youtube_dub.pipeline.stages.align import AlignStage
from youtube_dub.pipeline.stages.mix import MixStage
from youtube_dub.pipeline.stages.render import RenderStage
from youtube_dub.pipeline.stages.segment import SegmentStage
from youtube_dub.pipeline.stages.source_ready import SourceReadyStage
from youtube_dub.pipeline.stages.synthesize import SynthesizeStage
from youtube_dub.pipeline.stages.time_fit import TimeFitStage
from youtube_dub.pipeline.stages.transcribe import TranscribeStage
from youtube_dub.pipeline.stages.translate import TranslateStage
from youtube_dub.providers.gemini.executor import GeminiCallExecutor
from youtube_dub.providers.gemini.transcription import GeminiTranscriptionProvider
from youtube_dub.providers.gemini.translation import GeminiTranslationProvider
from youtube_dub.providers.gemini.tts import GeminiTTSProvider
from youtube_dub.providers.keys import ApiKeyPool
from youtube_dub.storage.artifacts import JobArtifactStore, ManifestStore
from youtube_dub.studio.application import StudioApplication


def create_studio_application() -> StudioApplication:
    """Wires together all dependencies for the Studio Application."""
    config = load_config()

    # Storage
    job_root = Path(config.job_root)
    manifest_store = ManifestStore(job_root)
    artifact_store = JobArtifactStore(manifest_store)

    # Process
    process_runner = ProcessRunner()

    # Orchestration
    listener_registry = StageListenerRegistry()

    # Provider Execution
    key_pool = ApiKeyPool(config.api_keys)

    # Models logic
    # In a full app we'd map config fallbacks here explicitly per service
    transcription_executor = GeminiCallExecutor(
        models=[config.transcription_model] + config.transcription_fallbacks,
        key_pool=key_pool,
    )
    translation_executor = GeminiCallExecutor(
        models=[config.translation_model] + config.translation_fallbacks,
        key_pool=key_pool,
    )
    tts_executor = GeminiCallExecutor(
        models=[config.tts_model] + config.tts_fallbacks,
        key_pool=key_pool,
    )

    # Providers
    def _client_factory(api_key: str):
        return genai.Client(api_key=api_key)

    transcription_provider = GeminiTranscriptionProvider(
        transcription_executor, sdk_client_factory=_client_factory
    )
    translation_provider = GeminiTranslationProvider(
        translation_executor, sdk_client_factory=_client_factory
    )
    tts_provider = GeminiTTSProvider(tts_executor, sdk_client_factory=_client_factory)

    # Pipeline
    stages = [
        SourceReadyStage(),
        TranscribeStage(),
        SegmentStage(),
        TranslateStage(),
        SynthesizeStage(),
        AlignStage(),
        TimeFitStage(),
        MixStage(),
        RenderStage(),
    ]

    # Separator
    if config.separation_model == "demucs":
        separator: VocalSeparator = DemucsVocalSeparator()
    else:
        separator = PassThroughVocalSeparator()

    pipeline_runner = PipelineRunner(stages, manifest_store, listener_registry)

    # Wrap the runner to inject providers to context
    original_run = pipeline_runner.run_pipeline

    async def _injected_run(context):
        context.transcription_provider = transcription_provider
        context.translation_provider = translation_provider
        context.tts_provider = tts_provider
        context.separator = separator
        await original_run(context)

    pipeline_runner.run_pipeline = _injected_run  # type: ignore

    return StudioApplication(
        config=config,
        manifest_store=manifest_store,
        artifact_store=artifact_store,
        pipeline_runner=pipeline_runner,
        process_runner=process_runner,
        listener_registry=listener_registry,
    )
