# youtube-dub v3

## Supported Python version
Python 3.12+

## Install
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Configuration
Use environment variables or CLI arguments (e.g. `DUB_SOURCE_LANGUAGE`, `DUB_TARGET_LANGUAGE`).

## Supported commands
(Coming soon) `create`, `run`, `status`, `resume`, `cancel`, `validate`, `clean`

## Pipeline Stage Order
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
Configure `DUB_TRANSCRIPTION_MODEL`, `DUB_TRANSLATION_MODEL`, `DUB_TTS_MODEL` and related fallbacks. Set appropriate API keys.

## Optional Demucs support
Install with `uv add "youtube-dub[demucs]"` (coming soon).

## Development/test commands
```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy .
```
