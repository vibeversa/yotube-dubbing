from unittest.mock import AsyncMock

import pytest

from youtube_dub.media.mixing import mix_audio
from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner


@pytest.fixture
def fake_runner():
    runner = ProcessRunner()
    runner.run = AsyncMock()  # type: ignore
    return runner


@pytest.mark.asyncio
async def test_mix_audio(fake_runner, tmp_path):
    vocals = tmp_path / "v.wav"
    bg = tmp_path / "b.wav"
    out = tmp_path / "o.wav"

    async def mock_run(*args, **kwargs):
        out.write_text("mixed")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    await mix_audio(vocals, bg, out, fake_runner, background_volume=0.3)

    cmd = fake_runner.run.call_args[0][0]
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "volume=0.3" in filter_arg
    assert "amix" in filter_arg
