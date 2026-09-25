with open("src/youtube_dub/config/loader.py", "r") as f:
    content = f.read()

# Add separation_model to AppConfig
content = content.replace(
    "    tts_model: str", "    tts_model: str\n    separation_model: str"
)
content = content.replace(
    "    tts_model=tts_model,",
    '    tts_model=tts_model,\n        separation_model=os.environ.get("DUB_SEPARATION_MODEL", "passthrough"),',
)

with open("src/youtube_dub/config/loader.py", "w") as f:
    f.write(content)
