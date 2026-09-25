# Final Polish Audit Report

## 1. Current Architecture
- **Pipeline-Driven**: The app uses a linear pipeline of stages (`SOURCE_READY`, `TRANSCRIBED`, `SEGMENTED`, `TRANSLATED`, `TTS_PARTIAL`, `ALIGNED`, `TIMED`, `MIXED`, `RENDERED`, `COMPLETED`).
- **Dependencies & Injection**: Centralized in `src/youtube_dub/factory.py`, which injects dependencies (providers, storage, runners) into a `PipelineContext`.
- **Data Flow**: Absolute state source is the `JobManifest` (persisted via `ManifestStore`). Each stage operates on job-specific artifacts stored in a directory.
- **Provider Abstraction**: Generative APIs (transcription, translation, TTS) are abstracted via protocols in `providers/base.py`, with concrete Gemini implementations relying on a shared `GeminiCallExecutor` for fallback/retry.
- **Media Processing**: `media/process_runner.py` bounds all `subprocess` usage using `asyncio.create_subprocess_exec` (no `shell=True`), preventing shell injection and isolating external CLI dependencies (`ffmpeg`, `demucs`).
- **Interfaces**: FastAPI backend serves the Studio UI (`studio/server.py`), and a CLI provides terminal interaction (`cli.py`).

## 2. Current End-to-End Workflow
1. **Creation**: Job is created via CLI or Studio UI, generating a `JobManifest`.
2. **Media Prep**: `SOURCE_READY` probes media, extracts audio.
3. **NLP Processing**: `TRANSCRIBED` generates words. `SEGMENTED` batches words. `TRANSLATED` translates segments. `TTS_PARTIAL` synthesizes audio concurrently using bounded concurrency (Semaphore).
4. **Media Assembly**: `ALIGNED` validates TTS artifacts exist. `TIMED` adjusts synthesized audio duration to fit allowed bounds. `MIXED` separates vocals (currently hardcoded to `PassThroughVocalSeparator` but has `DemucsVocalSeparator` implemented), layers timed audio on background.
5. **Finalization**: `RENDERED` muxes final mixed audio with original video.

## 3. Concrete Defects / Findings
- **Placeholder Implementation in `AlignStage`**: `src/youtube_dub/pipeline/stages/align.py` only validates that artifacts exist but says "We don't have a complex alignment metadata algorithm yet, but this fulfills the stage boundary". This represents a placeholder implementation, but it satisfies the architecture boundary.
- **Missing Demucs Configuration Binding**: `docs/operations.md` specifies Demucs as an optional extra, but `src/youtube_dub/pipeline/stages/mix.py` hardcodes `PassThroughVocalSeparator()` instead of reading config to conditionally inject `DemucsVocalSeparator`.
- **`shell=True` risk**: `media/process_runner.py` correctly uses `asyncio.create_subprocess_exec` and passes arguments as lists, meaning it complies with the "no shell injection" rule. No `subprocess` import in `mix.py`, `separation.py`, etc (they use `ProcessRunner`).
- **Private-Member Coupling / Tests**: Subprocess mocking in tests sets `runner.run = AsyncMock()` on `ProcessRunner` (as seen in `tests/test_ffmpeg_mux.py`), which is acceptable for isolated unit tests.
- **Provider Retry Loop Rule**: `GeminiCallExecutor` correctly handles fallback loops, satisfying the "Providers must not implement their own retry loops" rule.
- **Subprocess Error Swallowing Check**: Tests indicate `ProcessRunner` raises custom errors correctly.
- **Missing Pipeline Context Cancellation Event Pass**: In `src/youtube_dub/pipeline/stages/time_fit.py` and `mix.py`, ffmpeg is called via `process_runner.run()`, which natively supports `cancel_event` logic but they are awaited directly. Wait, `context.check_cancelled()` should be called more regularly in media assembly loops. `time_fit.py` currently doesn't check for cancellation inside its loop over segments.

## 4. Task Ownership Mapping
- **T01 (Repository Audit)**: Produce this audit document (`docs/final-polish-audit.md`).
- **T02 (Pipeline Align/Placeholders)**: Address T02 constraints (e.g., placeholder implementations, missing checks).
- **T03 (Demucs/Config Binding)**: Fix the vocal separator initialization in `MixStage` to read from the application config rather than hardcoding `PassThroughVocalSeparator`, and wire Demucs option through.
- **T04 (Architecture Boundaries/Robustness)**: Enhance cancellation checks within stage loops (like `time_fit.py`, `align.py`) to fully respect `context.check_cancelled()`.
- **T05 (Tests)**: Ensure tests do not require real API keys and ensure fake subprocesses are used universally (currently looks mostly okay).
- **T06 (UI/CLI Polish)**: Ensure status commands map nicely.

## 5. Dependency Recommendations
- **FastAPI / Uvicorn**: Current version `0.141.1` / `0.53.0` is good.
- **Google GenAI SDK**: `google-genai>=2.25.0` is good.
- **FFmpeg**: Handled externally, ensure path exists.
- **Demucs**: Should remain an optional dependency, so it doesn't break the build for users without PyTorch.

## 6. Risks That Could Affect Integration
- **Unbounded file descriptors** in ffmpeg loops if not closed properly, but `ProcessRunner` seems to correctly clean up resources.
- **Corrupt Manifests**: The system allows direct JSON manipulation; if modified incorrectly, it throws `ValueError`. Need to ensure `JobManifest` always repairs or validates correctly on load.
