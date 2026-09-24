from pathlib import Path

from youtube_dub.domain.errors import ArtifactError
from youtube_dub.media.process_runner import ProcessRunner


async def extract_audio(
    input_path: Path,
    output_path: Path,
    runner: ProcessRunner,
    sample_rate: str = "44100",
    channels: str = "2",
) -> Path:
    """Extracts audio to wav format deterministically."""

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",  # disable video
        "-acodec",
        "pcm_s16le",  # standard 16-bit PCM wav
        "-ar",
        sample_rate,
        "-ac",
        channels,
        str(output_path),
    ]

    await runner.run(cmd, check=True)

    if not output_path.exists():
        raise ArtifactError(
            f"Audio extraction failed. Expected artifact not found at {output_path}"
        )

    return output_path
