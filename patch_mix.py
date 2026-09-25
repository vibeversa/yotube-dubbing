with open("src/youtube_dub/pipeline/stages/mix.py", "r") as f:
    content = f.read()

# Fix indentation issue in mix.py
content = content.replace(
    """                    start_ms = s["start_ms"]
                if start_ms < 0:
                    return StageResult(StageStatus.FAILED, f"Invalid start_ms < 0 for segment {seg_id}")
                    inputs.extend(["-i", str(timed_audio)])""",
    """                    start_ms = s["start_ms"]
                    if start_ms < 0:
                        return StageResult(StageStatus.FAILED, f"Invalid start_ms < 0 for segment {seg_id}")
                    inputs.extend(["-i", str(timed_audio)])""",
)

with open("src/youtube_dub/pipeline/stages/mix.py", "w") as f:
    f.write(content)
