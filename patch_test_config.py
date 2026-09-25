with open("tests/test_config.py", "r") as f:
    content = f.read()

content = content.replace(
    'tts_model="model",\n            api_keys=["k"],',
    'tts_model="model",\n            separation_model="passthrough",\n            api_keys=["k"],',
)

with open("tests/test_config.py", "w") as f:
    f.write(content)
