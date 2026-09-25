with open("src/youtube_dub/pipeline/stages/time_fit.py", "r") as f:
    content = f.read()

content = content.replace(
    "await apply_timing_fit(\n                    tts_audio, timed_audio, context.process_runner, ratio\n                )",
    "await apply_timing_fit(\n                    tts_audio, timed_audio, context.process_runner, ratio, timeout_s=context.config.ffmpeg_timeout_s\n                )",
)

with open("src/youtube_dub/pipeline/stages/time_fit.py", "w") as f:
    f.write(content)

with open("src/youtube_dub/media/timing.py", "r") as f:
    content = f.read()

content = content.replace(
    "def apply_timing_fit(\n    input_path: Path, output_path: Path, runner: ProcessRunner, ratio: float\n) -> Path:",
    "def apply_timing_fit(\n    input_path: Path, output_path: Path, runner: ProcessRunner, ratio: float, timeout_s: int | None = None\n) -> Path:",
)
content = content.replace(
    "await runner.run(cmd, check=True)",
    "await runner.run(cmd, timeout_s=timeout_s, check=True)",
)

with open("src/youtube_dub/media/timing.py", "w") as f:
    f.write(content)
