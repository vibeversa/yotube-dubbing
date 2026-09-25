with open("src/youtube_dub/factory.py", "r") as f:
    content = f.read()

# Fix mypy error by typing separator variable
content = content.replace(
    "separator = DemucsVocalSeparator()",
    "separator: VocalSeparator = DemucsVocalSeparator()",
)

with open("src/youtube_dub/factory.py", "w") as f:
    f.write(content)
