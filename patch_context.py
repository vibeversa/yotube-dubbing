with open("src/youtube_dub/pipeline/context.py", "r") as f:
    content = f.read()

# Add separation import and separator property
if "VocalSeparator" not in content:
    content = content.replace(
        "from youtube_dub.storage.artifacts import JobArtifactStore",
        "from youtube_dub.storage.artifacts import JobArtifactStore\nfrom youtube_dub.media.separation import VocalSeparator",
    )
    content = content.replace(
        "tts_provider: TTSProvider | None = None",
        "tts_provider: TTSProvider | None = None\n    separator: VocalSeparator | None = None",
    )

with open("src/youtube_dub/pipeline/context.py", "w") as f:
    f.write(content)
