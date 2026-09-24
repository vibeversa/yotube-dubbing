import asyncio
import logging
import os
import subprocess
import sys

from youtube_dub.domain.errors import (
    ProcessCancelledError,
    ProcessError,
    ProcessExitCodeError,
    ProcessTimeoutError,
)

logger = logging.getLogger(__name__)


class CompletedProcess:
    def __init__(self, args: list[str], returncode: int, stdout: bytes, stderr: bytes):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ProcessRunner:
    @staticmethod
    def _redact_cmd(cmd: list[str]) -> list[str]:
        # Basic redaction strategy for logs.
        # In the future, this can be expanded to redact specific API keys if they are passed as args.
        # For now, just return a copy.
        return list(cmd)

    @staticmethod
    def _terminate_process(process: asyncio.subprocess.Process) -> None:
        """Platform-aware process termination."""
        if process.returncode is not None:
            return

        try:
            if sys.platform == "win32":
                # Use taskkill for Windows tree termination
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                # POSIX termination
                process.terminate()
        except OSError as e:
            logger.debug(f"Error terminating process {process.pid}: {e}")

    @staticmethod
    def _kill_process(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return

        try:
            if sys.platform != "win32":
                process.kill()
        except OSError as e:
            logger.debug(f"Error killing process {process.pid}: {e}")

    async def run(
        self,
        cmd: list[str],
        *,
        job_id: str | None = None,
        timeout_s: int | None = None,
        check: bool = True,
    ) -> CompletedProcess:

        redacted_cmd = self._redact_cmd(cmd)
        cmd_str = " ".join(redacted_cmd)

        logger.info(f"process_started: {cmd_str} (job_id: {job_id})")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Create a new process group for POSIX to help with tree termination if needed
            preexec_fn=os.setsid if sys.platform != "win32" else None,
        )

        stdout_data = b""
        stderr_data = b""

        try:
            if timeout_s is not None:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(), timeout=timeout_s
                )
            else:
                stdout_data, stderr_data = await process.communicate()

        except TimeoutError:
            logger.error(f"process_timeout: {cmd_str}")
            self._terminate_process(process)

            # Wait a moment for termination to complete
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except TimeoutError:
                self._kill_process(process)
                await process.wait()

            raise ProcessTimeoutError(
                f"Process timed out after {timeout_s}s: {cmd_str}"
            )

        except asyncio.CancelledError:
            logger.warning(f"process_cancelled: {cmd_str}")
            self._terminate_process(process)
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except TimeoutError:
                self._kill_process(process)
                await process.wait()
            raise ProcessCancelledError(f"Process cancelled: {cmd_str}")

        except Exception as e:
            logger.error(f"process_failed (unexpected): {e}")
            self._terminate_process(process)
            raise ProcessError(f"Unexpected error running process: {e}")

        finally:
            if process.returncode is None:
                self._terminate_process(process)

        if check and process.returncode != 0:
            logger.error(f"process_failed: {cmd_str} (exit code {process.returncode})")
            logger.debug(f"stderr: {stderr_data.decode(errors='replace')}")
            raise ProcessExitCodeError(
                f"Command '{cmd_str}' returned non-zero exit status {process.returncode}."
            )

        logger.info(f"process_finished: {cmd_str} (exit code {process.returncode})")

        return CompletedProcess(
            args=cmd,
            returncode=process.returncode, # type: ignore
            stdout=stdout_data,
            stderr=stderr_data,
        )
