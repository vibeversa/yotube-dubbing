from unittest.mock import AsyncMock

import pytest

from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner
from youtube_dub.media.separation import DemucsVocalSeparator, PassThroughVocalSeparator


@pytest.fixture
def fake_runner():
    runner = ProcessRunner()
    runner.run = AsyncMock()  # type: ignore
    return runner


@pytest.mark.asyncio
async def test_passthrough_separator(fake_runner, tmp_path):
    audio_file = tmp_path / "input.wav"
    audio_file.write_text("audio")
    out_dir = tmp_path / "out"

    async def mock_run(*args, **kwargs):
        out = out_dir / "background.wav"
        out.write_text("silent bg")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    sep = PassThroughVocalSeparator()
    v, b = await sep.separate(audio_file, out_dir, fake_runner)

    assert v.name == "vocals.wav"
    assert b.name == "background.wav"
    assert v.exists()
    assert b.exists()

    cmd = fake_runner.run.call_args[0][0]
    assert "ffmpeg" in cmd
    assert "volume=0" in cmd


@pytest.mark.asyncio
async def test_demucs_separator(fake_runner, tmp_path):
    audio_file = tmp_path / "input.wav"
    audio_file.write_text("audio")
    out_dir = tmp_path / "out"

    sep = DemucsVocalSeparator()

    async def mock_run(*args, **kwargs):
        # Simulate demucs file creation
        model_dir = out_dir / "htdemucs" / "input"
        model_dir.mkdir(parents=True)
        (model_dir / "vocals.wav").write_text("v")
        (model_dir / "no_vocals.wav").write_text("b")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    v, b = await sep.separate(audio_file, out_dir, fake_runner)

    assert v.name == "vocals.wav"
    assert b.name == "background.wav"
    assert v.exists()
    assert b.exists()

    cmd = fake_runner.run.call_args[0][0]
    assert "demucs" in cmd
    assert "--two-stems=vocals" in cmd
