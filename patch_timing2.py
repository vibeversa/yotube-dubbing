with open("src/youtube_dub/media/timing.py", "r") as f:
    content = f.read()

content = content.replace(
    '''def calculate_atempo_chain(ratio: float) -> list[float]:
    if ratio > 10.0 or ratio < 0.1:
        raise ValueError(f"Extreme stretching ratio not supported: {ratio}")
    """Calculates the ffmpeg atempo filter chain required to achieve a speed ratio.
    ffmpeg atempo filter only supports ratios between 0.5 and 2.0.
    For ratios outside this range, we must chain multiple filters.
    """
    if ratio <= 0.0:
        raise ValueError("Ratio must be > 0")''',
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

with open("src/youtube_dub/media/timing.py", "w") as f:
    f.write(content)
