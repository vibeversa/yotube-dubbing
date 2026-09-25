# Youtube Dubbing

Welcome to the `Youtube Dubbing` project! This is a deterministic, resumable, pipeline-driven video dubbing architecture.

## Supported Python version
Python 3.12+

## Install
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Configuration
Use environment variables or CLI arguments (e.g., `DUB_SOURCE_LANGUAGE`, `DUB_TARGET_LANGUAGE`).
See the [Operations Runbook](docs/operations.md) for more details on advanced configuration.

## Supported commands
```bash
uv run youtube-dub create --source en --target es
uv run youtube-dub run --job-id <uuid>
uv run youtube-dub status --job-id <uuid>
uv run youtube-dub resume --job-id <uuid>
uv run youtube-dub cancel --job-id <uuid>
```

## Web UI
Run the Studio server using Uvicorn:
```bash
uv run uvicorn youtube_dub.studio.server:app --reload
```
Navigate to `http://localhost:8000/` to access the graphical job manager.

## Pipeline Stage Order
The application processes media deterministically through the following sequence:
```text
SOURCE_READY
    -> TRANSCRIBED
    -> SEGMENTED
    -> TRANSLATED
    -> TTS_PARTIAL
    -> ALIGNED
    -> TIMED
    -> MIXED
    -> RENDERED
    -> COMPLETED
```

## Provider setup
Configure `DUB_TRANSCRIPTION_MODEL`, `DUB_TRANSLATION_MODEL`, `DUB_TTS_MODEL`, and related fallbacks. Set appropriate API keys like `GEMINI_API_KEY`.

## Optional Demucs support
Install with `uv add "youtube-dub[demucs]"` (coming soon).
For troubleshooting missing binaries, please read the [Operations Runbook](docs/operations.md).

## Development/test commands
```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy .
```
