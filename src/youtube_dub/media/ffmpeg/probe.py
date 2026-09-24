import json
from dataclasses import dataclass, field
from pathlib import Path

from youtube_dub.domain.errors import ProcessError
from youtube_dub.media.process_runner import ProcessRunner


@dataclass
class MediaStream:
    index: int
    codec_name: str
    codec_type: str
    sample_rate: str | None = None
    channels: int | None = None


@dataclass
class MediaProbeInfo:
    duration_s: float
    container: str
    video_streams: list[MediaStream] = field(default_factory=list)
    audio_streams: list[MediaStream] = field(default_factory=list)


async def probe_media(file_path: Path, runner: ProcessRunner) -> MediaProbeInfo:
    """Probes media using ffprobe and returns structured metadata."""

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(file_path),
    ]

    try:
        result = await runner.run(cmd, check=True)
    except Exception as e:
        raise ProcessError(f"Failed to probe media {file_path}: {e}")

    try:
        data = json.loads(result.stdout.decode("utf-8"))

        format_info = data.get("format", {})
        duration = float(format_info.get("duration", 0.0))
        container = format_info.get("format_name", "unknown")

        video_streams = []
        audio_streams = []

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            s = MediaStream(
                index=stream.get("index", 0),
                codec_name=stream.get("codec_name", "unknown"),
                codec_type=codec_type,
            )

            if codec_type == "video":
                video_streams.append(s)
            elif codec_type == "audio":
                s.sample_rate = stream.get("sample_rate")
                s.channels = stream.get("channels")
                audio_streams.append(s)

        return MediaProbeInfo(
            duration_s=duration,
            container=container,
            video_streams=video_streams,
            audio_streams=audio_streams,
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        raise ProcessError(f"Failed to parse ffprobe output for {file_path}: {e}")
