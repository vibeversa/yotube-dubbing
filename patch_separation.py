import re

with open("src/youtube_dub/media/separation.py", "r") as f:
    content = f.read()

replacement = """        shutil.copy2(audio_path, vocals_path)

        # Create a muted background using ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-filter:a",
            "volume=0",
            str(bg_path),
        ]
        await runner.run(cmd, check=True)

        if not bg_path.exists():
            raise ArtifactError("Failed to create muted background.")

        return vocals_path, bg_path"""

content = re.sub(
    r"        shutil\.copy2\(audio_path, vocals_path\)\n\n        # for a true passthrough.*?return vocals_path, bg_path",
    replacement,
    content,
    flags=re.DOTALL,
)

with open("src/youtube_dub/media/separation.py", "w") as f:
    f.write(content)
