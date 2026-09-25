import re

with open("src/youtube_dub/media/timing.py", "r") as f:
    content = f.read()

# Add validation for ratio
if "if ratio > 10.0 or ratio < 0.1:" not in content:
    content = content.replace(
        "def calculate_atempo_chain(ratio: float) -> list[float]:",
        '''def calculate_atempo_chain(ratio: float) -> list[float]:
    """Calculates the ffmpeg atempo filter chain required to achieve a speed ratio.
    ffmpeg atempo filter only supports ratios between 0.5 and 2.0.
    For ratios outside this range, we must chain multiple filters.
    """
    if ratio <= 0.0:
        raise ValueError("Ratio must be > 0")
    if ratio > 10.0 or ratio < 0.1:
        raise ValueError(f"Extreme stretching ratio not supported: {ratio}")''',
    )

    content = re.sub(
        r'    """Calculates the ffmpeg atempo filter chain required to achieve a speed ratio\.\n    ffmpeg atempo filter only supports ratios between 0\.5 and 2\.0\.\n    For ratios outside this range, we must chain multiple filters\.\n    """\n    if ratio <= 0\.0:\n        raise ValueError\("Ratio must be > 0"\)\n',
        "",
        content,
        count=1,
    )

with open("src/youtube_dub/media/timing.py", "w") as f:
    f.write(content)
