import math
from unittest.mock import AsyncMock

import pytest

from youtube_dub.media.process_runner import CompletedProcess, ProcessRunner
from youtube_dub.media.timing import apply_timing_fit, calculate_atempo_chain


def test_calculate_atempo_chain():
    # Inside range
    assert calculate_atempo_chain(1.0) == [1.0]
    assert calculate_atempo_chain(1.5) == [1.5]
    assert calculate_atempo_chain(0.5) == [0.5]
    assert calculate_atempo_chain(2.0) == [2.0]

    # Above range
    assert calculate_atempo_chain(2.5) == [2.0, 1.25]
    assert calculate_atempo_chain(4.0) == [2.0, 2.0]
    assert calculate_atempo_chain(5.0) == [2.0, 2.0, 1.25]

    # Below range
    assert calculate_atempo_chain(0.25) == [0.5, 0.5]

    chain = calculate_atempo_chain(0.2)
    assert len(chain) == 3
    assert chain[0] == 0.5
    assert chain[1] == 0.5
    assert math.isclose(chain[2], 0.8)

    with pytest.raises(ValueError, match="Ratio must be > 0"):
        calculate_atempo_chain(0)


@pytest.fixture
def fake_runner():
    runner = ProcessRunner()
    runner.run = AsyncMock()  # type: ignore
    return runner


@pytest.mark.asyncio
async def test_apply_timing_fit_noop(fake_runner, tmp_path):
    in_path = tmp_path / "in.wav"
    in_path.write_text("audio")
    out_path = tmp_path / "out.wav"

    res = await apply_timing_fit(in_path, out_path, fake_runner, 1.0)

    assert res == out_path
    assert out_path.read_text() == "audio"
    fake_runner.run.assert_not_called()


@pytest.mark.asyncio
async def test_apply_timing_fit_ffmpeg(fake_runner, tmp_path):
    in_path = tmp_path / "in.wav"
    out_path = tmp_path / "out.wav"

    async def mock_run(*args, **kwargs):
        out_path.write_text("timed")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    await apply_timing_fit(in_path, out_path, fake_runner, 3.0)

    cmd = fake_runner.run.call_args[0][0]
    assert "-filter:a" in cmd
    filter_arg = cmd[cmd.index("-filter:a") + 1]
    assert filter_arg == "atempo=2.0000,atempo=1.5000"
