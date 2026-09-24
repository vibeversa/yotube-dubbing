# AGENTS.md

## Package Boundaries
- Pipeline stages depend on protocols, not concrete SDK classes.
- CLI and HTTP layers depend on the application service boundary.
- Pipeline runner sequences stages but does not implement stage details.

## Subprocess Rule
- Only `media/process_runner.py` may import `subprocess`.
- Do not construct shell strings from untrusted input. Avoid `shell=True`.

## Provider Rule
- Provider implementations must not read environment variables, implement their own retry loops, rotate API keys directly, import pipeline internals, write arbitrary job artifacts, or call subprocesses.
- Only the shared Gemini executor performs model/key fallback loops.

## Test Rules
- No test dependence on ambient environment.
- Use fake SDK/HTTP layers for provider tests.
- Never require a real API key for unit tests.
- Tests must use fake process runner for stage unit tests.

## Naming Conventions
- Use standard PEP8 naming conventions.

## Commands to Run Before Committing
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```
