import asyncio

import pytest

from youtube_dub.domain.errors import (
    ProcessCancelledError,
    ProcessExitCodeError,
    ProcessTimeoutError,
)
from youtube_dub.media.process_runner import ProcessRunner


@pytest.fixture
def runner():
    return ProcessRunner()


@pytest.mark.asyncio
async def test_successful_command(runner):
    cmd = ["echo", "hello world"]
    result = await runner.run(cmd)

    assert result.returncode == 0
    assert result.stdout.strip() == b"hello world"
    assert result.stderr == b""


@pytest.mark.asyncio
async def test_nonzero_exit_check_true(runner):
    cmd = ["ls", "/nonexistent/path/for/test"]
    with pytest.raises(ProcessExitCodeError, match="returned non-zero exit status"):
        await runner.run(cmd, check=True)


@pytest.mark.asyncio
async def test_nonzero_exit_check_false(runner):
    cmd = ["ls", "/nonexistent/path/for/test"]
    result = await runner.run(cmd, check=False)

    assert result.returncode != 0
    assert (
        b"No such file or directory" in result.stderr
        or b"cannot access" in result.stderr
    )


@pytest.mark.asyncio
async def test_timeout(runner):
    cmd = ["sleep", "10"]
    with pytest.raises(ProcessTimeoutError, match="Process timed out after 1s"):
        await runner.run(cmd, timeout_s=1)


@pytest.mark.asyncio
async def test_cancellation(runner):
    cmd = ["sleep", "10"]

    async def run_and_cancel():
        task = asyncio.create_task(runner.run(cmd))
        await asyncio.sleep(0.5)
        task.cancel()
        await task

    with pytest.raises(ProcessCancelledError, match="Process cancelled: sleep 10"):
        await run_and_cancel()


@pytest.mark.asyncio
async def test_stderr_capture(runner):
    cmd = ["sh", "-c", "echo 'error message' >&2; exit 0"]
    result = await runner.run(cmd)

    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr.strip() == b"error message"


def test_cmd_redaction(runner):
    cmd = ["ffmpeg", "-i", "input.mp4", "-y", "output.mp4"]
    redacted = runner._redact_cmd(cmd)
    assert redacted == cmd

    cmd2 = ["python", "script.py", "--api-key", "secret123"]
    assert runner._redact_cmd(cmd2) == ["python", "script.py", "--api-key", "***"]

    cmd3 = ["tool", "key=abcde"]
    assert runner._redact_cmd(cmd3) == ["tool", "key=***"]
