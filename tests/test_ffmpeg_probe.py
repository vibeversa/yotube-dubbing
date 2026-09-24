import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from youtube_dub.domain.errors import ProcessError
from youtube_dub.media.ffmpeg.probe import probe_media
from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner


@pytest.fixture
def fake_runner():
    runner = ProcessRunner()
    runner.run = AsyncMock()  # type: ignore
    return runner


@pytest.mark.asyncio
async def test_probe_media_success(fake_runner):
    mock_data = {
        "format": {"duration": "120.5", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264"},
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "44100",
                "channels": 2,
            },
        ],
    }

    fake_runner.run.return_value = CompletedProcess(
        args=[], returncode=0, stdout=json.dumps(mock_data).encode("utf-8"), stderr=b""
    )

    info = await probe_media(Path("test.mp4"), fake_runner)

    assert info.duration_s == 120.5
    assert "mp4" in info.container
    assert len(info.video_streams) == 1
    assert info.video_streams[0].codec_name == "h264"
    assert len(info.audio_streams) == 1
    assert info.audio_streams[0].codec_name == "aac"
    assert info.audio_streams[0].sample_rate == "44100"
    assert info.audio_streams[0].channels == 2


@pytest.mark.asyncio
async def test_probe_media_failure(fake_runner):
    fake_runner.run.side_effect = ProcessError("ffprobe failed")

    with pytest.raises(ProcessError, match="Failed to probe media test.mp4"):
        await probe_media(Path("test.mp4"), fake_runner)


@pytest.mark.asyncio
async def test_probe_media_malformed_json(fake_runner):
    fake_runner.run.return_value = CompletedProcess(
        args=[], returncode=0, stdout=b"not json", stderr=b""
    )

    with pytest.raises(ProcessError, match="Failed to parse ffprobe output"):
        await probe_media(Path("test.mp4"), fake_runner)
