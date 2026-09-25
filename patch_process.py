import re

with open("src/youtube_dub/media/process_runner.py", "r") as f:
    content = f.read()

redact_method = """    @staticmethod
    def _redact_cmd(cmd: list[str]) -> list[str]:
        redacted = list(cmd)

        # Redact common key indicators
        for i, arg in enumerate(redacted):
            if "key" in arg.lower() and "=" in arg:
                parts = arg.split("=", 1)
                redacted[i] = f"{parts[0]}=***"
            elif arg in ("-k", "--key", "--api-key") and i + 1 < len(redacted):
                redacted[i+1] = "***"
        return redacted"""

content = re.sub(
    r"    @staticmethod\n    def _redact_cmd\(cmd: list\[str\]\) -> list\[str\]:.*?return list\(cmd\)",
    redact_method,
    content,
    flags=re.DOTALL,
)

with open("src/youtube_dub/media/process_runner.py", "w") as f:
    f.write(content)
