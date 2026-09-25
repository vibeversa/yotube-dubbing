from pathlib import Path

from youtube_dub.domain.errors import ArtifactError
from youtube_dub.media.process_runner import ProcessRunner


async def mux_media(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    runner: ProcessRunner,
    allow_stream_copy: bool = True,
    audio_bitrate: str = "192k",
    timeout_s: int | None = None,
) -> Path:
    """Muxes a new audio track with an existing video track.

    If allow_stream_copy is True, we attempt to copy the video stream directly.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",  # Use first video stream from first input
        "-map",
        "1:a:0",  # Use first audio stream from second input
    ]

    if allow_stream_copy:
        cmd.extend(["-c:v", "copy"])
    else:
        # Simple re-encode fallback
        cmd.extend(["-c:v", "libx264"])

    cmd.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-shortest",  # End when the shortest stream ends
            str(output_path),
        ]
    )

    await runner.run(cmd, timeout_s=timeout_s, check=True)

    if not output_path.exists():
        raise ArtifactError(
            f"Muxing failed. Expected artifact not found at {output_path}"
        )

    return output_path
