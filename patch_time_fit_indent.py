with open("src/youtube_dub/pipeline/stages/time_fit.py", "r") as f:
    content = f.read()

content = content.replace(
    '                                if s["start_ms"] < 0:',
    '                if s["start_ms"] < 0:',
)

with open("src/youtube_dub/pipeline/stages/time_fit.py", "w") as f:
    f.write(content)
