# Operations Runbook

## Startup

### Required Environment
Ensure that the machine running `youtube-dub` has `ffmpeg` and `ffprobe` installed and accessible from the system `PATH`.
Set the required environment variable `GEMINI_API_KEY`. You can supply multiple comma-separated keys to enable rotation.

### Advanced Configuration

The application exposes several advanced configuration options via environment variables:

- `DUB_MAX_DURATION_S`: The maximum permitted media duration in seconds (default: 3600).
- `DUB_CHUNK_MS`: The chunk size in milliseconds used during segmentation (default: 60000).
- `DUB_OUTPUT_AUDIO_BITRATE`: The audio bitrate used during the final ffmpeg mixing step (default: "192k").

### Dependency Installation
Use `uv` for reproducible environment installation:
```bash
uv sync
```

### Optional Demucs Setup
Installing the optional `demucs` extra allows for native AI vocal separation:
```bash
uv add "youtube-dub[demucs]"
```

### Storage Permissions
The application requires read and write permissions to the configured `DUB_JOB_ROOT` (default: `data/jobs`). Ensure the executing user owns this directory.

---

## Common Failures

### Quota Exhaustion
**Symptom:** Job fails during Transcribe, Translate, or TTS stages with `PROVIDER_QUOTA_EXHAUSTED`.
**Action:** The shared `GeminiCallExecutor` will automatically rotate keys. If all keys are exhausted, the job will fail. Add more valid keys to `GEMINI_API_KEY` or wait for quota reset, then click **Retry** in the Studio UI or run `youtube-dub resume --job-id <id>`.

### Provider Authentication
**Symptom:** Job fails with `PROVIDER_AUTH_FAILED`.
**Action:** Inspect the provided API keys. An invalid key was encountered.

### ffmpeg Not Found
**Symptom:** `ProcessError` or `ProcessExitCodeError` occurring instantly on audio extraction or muxing.
**Action:** Verify `ffmpeg` is installed: `ffmpeg -version`.

### Demucs Failure
**Symptom:** Artifact missing error during separation stage.
**Action:** The system currently falls back to `PassThroughVocalSeparator` if demucs fails or is unavailable. If Demucs is explicitly required, check GPU availability and `demucs` command-line functionality.

### Corrupt Job
**Symptom:** `ManifestError: Corrupt manifest` when loading a job.
**Action:** The `manifest.json` might have been manually edited and broken. It must be manually repaired using standard JSON validation, or the job must be deleted and recreated.

### Disk Exhaustion
**Symptom:** `OSError` during manifest save or `ProcessExitCodeError` during ffmpeg extraction.
**Action:** Free up disk space in the `DUB_JOB_ROOT` partition.

---

## Recovery

### Resume a Cancelled Job
Use the Studio UI "Resume" button or the CLI command:
```bash
uv run youtube-dub resume --job-id <id>
```
The application will safely inspect the manifest and automatically resume from the last uncompleted stage.

### Retry a Failed Segment
In the event of a `TTS_PARTIAL` failure where a specific segment failed to synthesize, use the UI or run a resume. The pipeline will automatically skip successfully synthesized segments and only retry the failed ones.

### Rebuild a Failed Stage
Resume the job. The runner uses the manifest as the absolute source of truth.

### Remove Invalid Temporary Artifacts
If a process crashes hard (e.g. OOM kill), `.tmp` files may be left in the job directories. They are harmless but can be manually deleted.

### Preserve Forensic Logs
Check standard output or standard error (if redirected) for detailed `process_runner` redactions. The UI maps domain failures cleanly, but the raw logs contain specific ffmpeg/demucs exit codes.

---

## Maintenance

### Cleanup Completed Jobs
Delete the job directory from `data/jobs/<job_id>`. There is no hidden global database state.

### Rotate Credentials
Restart the server process with the updated `GEMINI_API_KEY` environment variable.

### Inspect Failed Jobs
Use the Studio Web UI or the CLI `status` command:
```bash
uv run youtube-dub status --job-id <id>
```

### Upgrade Dependencies Safely
Use `uv lock` to update the lockfile and test against the test suite.
