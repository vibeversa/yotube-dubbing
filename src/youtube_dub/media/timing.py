from pathlib import Path

from youtube_dub.domain.errors import ArtifactError
from youtube_dub.media.process_runner import ProcessRunner


def calculate_atempo_chain(ratio: float) -> list[float]:
    """Calculates the ffmpeg atempo filter chain required to achieve a speed ratio.
    ffmpeg atempo filter only supports ratios between 0.5 and 2.0.
    For ratios outside this range, we must chain multiple filters.
    """
    if ratio <= 0.0:
        raise ValueError("Ratio must be > 0")
    if ratio > 10.0 or ratio < 0.1:
        raise ValueError(f"Extreme stretching ratio not supported: {ratio}")

    chain = []

    # Handle speeding up (ratio > 2.0)
    while ratio > 2.0:
        chain.append(2.0)
        ratio /= 2.0

    # Handle slowing down (ratio < 0.5)
    while ratio < 0.5:
        chain.append(0.5)
        ratio /= 0.5

    # Append the remainder if it's not exactly 1.0 (to avoid useless filters)
    # We use a small epsilon to account for float math
    if abs(ratio - 1.0) > 1e-4:
        chain.append(ratio)

    if not chain:
        return [1.0]

    return chain


async def apply_timing_fit(
    input_path: Path,
    output_path: Path,
    runner: ProcessRunner,
    ratio: float,
    timeout_s: int | None = None,
) -> Path:

    chain = calculate_atempo_chain(ratio)

    tmp_path = output_path.with_suffix(".tmp")

    if len(chain) == 1 and abs(chain[0] - 1.0) < 1e-4:
        # No modification needed, just copy
        import shutil

        shutil.copy2(input_path, tmp_path)
        tmp_path.replace(output_path)
        return output_path

    # Build filter string
    filter_str = ",".join([f"atempo={r:.4f}" for r in chain])

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-filter:a",
        filter_str,
        str(tmp_path),
    ]

    await runner.run(cmd, timeout_s=timeout_s, check=True)

    if tmp_path.exists():
        tmp_path.replace(output_path)

    if not output_path.exists():
        raise ArtifactError(f"Timing fit failed. Artifact missing at {output_path}")

    return output_path
