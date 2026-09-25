with open("src/youtube_dub/pipeline/stages/time_fit.py", "r") as f:
    content = f.read()

# Add validation for segment duration
if 'if s["end_ms"] <= s["start_ms"]:' not in content:
    validation = """                if s["start_ms"] < 0:
                    return StageResult(StageStatus.FAILED, f"Invalid start_ms < 0 for segment {seg_id}")
                if s["end_ms"] <= s["start_ms"]:
                    return StageResult(StageStatus.FAILED, f"Invalid duration for segment {seg_id}")
"""
    content = content.replace(
        'if s.get("status") != SegmentStatus.SYNTHESIZED.value:',
        validation
        + '                if s.get("status") != SegmentStatus.SYNTHESIZED.value:',
    )

with open("src/youtube_dub/pipeline/stages/time_fit.py", "w") as f:
    f.write(content)
