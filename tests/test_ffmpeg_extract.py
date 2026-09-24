from unittest.mock import AsyncMock

import pytest

from youtube_dub.domain.errors import ArtifactError
from youtube_dub.media.ffmpeg.extract import extract_audio
from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner


@pytest.fixture
def fake_runner():
    runner = ProcessRunner()
    runner.run = AsyncMock()  # type: ignore
    return runner


@pytest.mark.asyncio
async def test_extract_audio_success(fake_runner, tmp_path):
    in_path = tmp_path / "input.mp4"
    out_path = tmp_path / "output.wav"

    # simulate the file being created
    async def mock_run(*args, **kwargs):
        out_path.write_text("fake wav data")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    result = await extract_audio(in_path, out_path, fake_runner)

    assert result == out_path
    fake_runner.run.assert_called_once()

    # check cmd args
    cmd = fake_runner.run.call_args[0][0]
    assert "-vn" in cmd
    assert "-acodec" in cmd


@pytest.mark.asyncio
async def test_extract_audio_artifact_missing(fake_runner, tmp_path):
    in_path = tmp_path / "input.mp4"
    out_path = tmp_path / "output.wav"

    # Do not create the output file to simulate failure
    fake_runner.run.return_value = CompletedProcess(
        args=[], returncode=0, stdout=b"", stderr=b""
    )

    with pytest.raises(ArtifactError, match="Expected artifact not found"):
        await extract_audio(in_path, out_path, fake_runner)
