import glob

for filename in glob.glob("tests/*.py"):
    with open(filename, "r") as f:
        content = f.read()

    if "AppConfig(" in content:
        content = content.replace(
            'tts_model="m3",\n        api_keys=["k"],',
            'tts_model="m3",\n        separation_model="passthrough",\n        api_keys=["k"],',
        )
        content = content.replace(
            'tts_model="model",\n        api_keys=["k"],',
            'tts_model="model",\n        separation_model="passthrough",\n        api_keys=["k"],',
        )

        with open(filename, "w") as f:
            f.write(content)
