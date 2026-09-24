import shutil
from pathlib import Path
from typing import Protocol

from youtube_dub.domain.errors import ArtifactError
from youtube_dub.media.process_runner import ProcessRunner


class VocalSeparator(Protocol):
    async def separate(
        self, audio_path: Path, output_dir: Path, runner: ProcessRunner
    ) -> tuple[Path, Path]:
        """Returns (vocals_path, background_path)"""
        ...


class PassThroughVocalSeparator(VocalSeparator):
    """A separator that just uses the original audio for both (or muted background)."""

    async def separate(
        self, audio_path: Path, output_dir: Path, runner: ProcessRunner
    ) -> tuple[Path, Path]:

        output_dir.mkdir(parents=True, exist_ok=True)
        vocals_path = output_dir / "vocals.wav"
        bg_path = output_dir / "background.wav"

        shutil.copy2(audio_path, vocals_path)

        # for a true passthrough, we'll just create a dummy background by copying it
        # or we could make it silent using ffmpeg. For simplicity, we just copy.
        shutil.copy2(audio_path, bg_path)

        return vocals_path, bg_path


class DemucsVocalSeparator(VocalSeparator):
    """Uses Demucs to separate vocals from background."""

    async def separate(
        self, audio_path: Path, output_dir: Path, runner: ProcessRunner
    ) -> tuple[Path, Path]:

        output_dir.mkdir(parents=True, exist_ok=True)

        # Demucs places outputs in a predictable hierarchy based on model name and input name
        # We specify two stems output directly
        cmd = [
            "demucs",
            "--two-stems=vocals",
            "-n",
            "htdemucs",  # Use standard fast model
            "-o",
            str(output_dir),
            str(audio_path),
        ]

        await runner.run(cmd, check=True)

        # Find outputs
        model_dir = output_dir / "htdemucs" / audio_path.stem
        vocals_path = model_dir / "vocals.wav"
        bg_path = model_dir / "no_vocals.wav"

        if not vocals_path.exists() or not bg_path.exists():
            raise ArtifactError(
                "Demucs separation completed but artifacts are missing."
            )

        # Move them to the requested output_dir root for stability
        final_vocals = output_dir / "vocals.wav"
        final_bg = output_dir / "background.wav"

        shutil.move(str(vocals_path), str(final_vocals))
        shutil.move(str(bg_path), str(final_bg))

        return final_vocals, final_bg
