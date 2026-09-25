with open("src/youtube_dub/pipeline/stages/mix.py", "r") as f:
    content = f.read()

content = content.replace(
    "context.process_runner.run(cmd, check=True)",
    "context.process_runner.run(cmd, timeout_s=context.config.ffmpeg_timeout_s, check=True)",
)
content = content.replace(
    "await sep.separate(\n                    source_audio, bg_path.parent, context.process_runner\n                )",
    "await sep.separate(\n                    source_audio, bg_path.parent, context.process_runner, timeout_s=context.config.ffmpeg_timeout_s\n                )",
)
content = content.replace(
    "await mix_audio(\n                    mixed_vocals_path, bg_path, mix_path, context.process_runner\n                )",
    "await mix_audio(\n                    mixed_vocals_path, bg_path, mix_path, context.process_runner, timeout_s=context.config.ffmpeg_timeout_s\n                )",
)

with open("src/youtube_dub/pipeline/stages/mix.py", "w") as f:
    f.write(content)

with open("src/youtube_dub/media/separation.py", "r") as f:
    content = f.read()

content = content.replace(
    "def separate(\n        self, audio_path: Path, output_dir: Path, runner: ProcessRunner\n    )",
    "def separate(\n        self, audio_path: Path, output_dir: Path, runner: ProcessRunner, timeout_s: int | None = None\n    )",
)
content = content.replace(
    "await runner.run(cmd, check=True)",
    "await runner.run(cmd, timeout_s=timeout_s, check=True)",
)

with open("src/youtube_dub/media/separation.py", "w") as f:
    f.write(content)

with open("src/youtube_dub/media/mixing.py", "r") as f:
    content = f.read()

content = content.replace(
    "def mix_audio(\n    vocals_path: Path,\n    background_path: Path,\n    output_path: Path,\n    runner: ProcessRunner,\n    background_volume: float = 0.5,\n) -> Path:",
    "def mix_audio(\n    vocals_path: Path,\n    background_path: Path,\n    output_path: Path,\n    runner: ProcessRunner,\n    background_volume: float = 0.5,\n    timeout_s: int | None = None,\n) -> Path:",
)
content = content.replace(
    "await runner.run(cmd, check=True)",
    "await runner.run(cmd, timeout_s=timeout_s, check=True)",
)

with open("src/youtube_dub/media/mixing.py", "w") as f:
    f.write(content)

with open("src/youtube_dub/pipeline/stages/render.py", "r") as f:
    content = f.read()

content = content.replace(
    "audio_bitrate=context.config.output_audio_bitrate,",
    "audio_bitrate=context.config.output_audio_bitrate,\n                timeout_s=context.config.ffmpeg_timeout_s,",
)

with open("src/youtube_dub/pipeline/stages/render.py", "w") as f:
    f.write(content)

with open("src/youtube_dub/media/ffmpeg/mux.py", "r") as f:
    content = f.read()

content = content.replace(
    'def mux_media(\n    video_path: Path,\n    audio_path: Path,\n    output_path: Path,\n    runner: ProcessRunner,\n    allow_stream_copy: bool = True,\n    audio_bitrate: str = "192k",\n) -> Path:',
    'def mux_media(\n    video_path: Path,\n    audio_path: Path,\n    output_path: Path,\n    runner: ProcessRunner,\n    allow_stream_copy: bool = True,\n    audio_bitrate: str = "192k",\n    timeout_s: int | None = None,\n) -> Path:',
)
content = content.replace(
    "await runner.run(cmd, check=True)",
    "await runner.run(cmd, timeout_s=timeout_s, check=True)",
)

with open("src/youtube_dub/media/ffmpeg/mux.py", "w") as f:
    f.write(content)
