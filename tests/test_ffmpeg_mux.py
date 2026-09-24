from unittest.mock import AsyncMock

import pytest

from youtube_dub.media.ffmpeg.mux import mux_media
from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner


@pytest.fixture
def fake_runner():
    runner = ProcessRunner()
    runner.run = AsyncMock()  # type: ignore
    return runner


@pytest.mark.asyncio
async def test_mux_media_copy(fake_runner, tmp_path):
    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "audio.wav"
    out_path = tmp_path / "output.mp4"

    async def mock_run(*args, **kwargs):
        out_path.write_text("muxed")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    await mux_media(
        video_path, audio_path, out_path, fake_runner, allow_stream_copy=True
    )

    cmd = fake_runner.run.call_args[0][0]
    assert "-c:v" in cmd
    assert "copy" in cmd
    assert "-shortest" in cmd


@pytest.mark.asyncio
async def test_mux_media_reencode(fake_runner, tmp_path):
    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "audio.wav"
    out_path = tmp_path / "output.mp4"

    async def mock_run(*args, **kwargs):
        out_path.write_text("muxed")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    await mux_media(
        video_path, audio_path, out_path, fake_runner, allow_stream_copy=False
    )

    cmd = fake_runner.run.call_args[0][0]
    assert "libx264" in cmd
