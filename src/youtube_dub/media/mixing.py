from pathlib import Path

from youtube_dub.domain.errors import ArtifactError
from youtube_dub.media.process_runner import ProcessRunner


async def mix_audio(
    vocals_path: Path,
    background_path: Path,
    output_path: Path,
    runner: ProcessRunner,
    background_volume: float = 0.5,
    timeout_s: int | None = None,
) -> Path:
    """Mixes a vocal track with a background track."""

    # We use amix filter to combine them.
    # amix by default scales volume by 1/N. We use volume filter on background.

    tmp_path = output_path.with_suffix(".tmp")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(vocals_path),
        "-i",
        str(background_path),
        "-filter_complex",
        f"[1:a]volume={background_volume}[bg];[0:a][bg]amix=inputs=2:duration=longest[out]",
        "-map",
        "[out]",
        "-ac",
        "2",
        "-ar",
        "44100",
        str(tmp_path),
    ]

    await runner.run(cmd, timeout_s=timeout_s, check=True)

    if tmp_path.exists():
        tmp_path.replace(output_path)

    if not output_path.exists():
        raise ArtifactError(f"Mixing failed. Expected artifact at {output_path}")

    return output_path
