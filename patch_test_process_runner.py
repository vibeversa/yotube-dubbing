import re

with open("tests/test_process_runner.py", "r") as f:
    content = f.read()

redaction_test = """def test_cmd_redaction(runner):
    cmd = ["ffmpeg", "-i", "input.mp4", "-y", "output.mp4"]
    redacted = runner._redact_cmd(cmd)
    assert redacted == cmd

    cmd2 = ["python", "script.py", "--api-key", "secret123"]
    assert runner._redact_cmd(cmd2) == ["python", "script.py", "--api-key", "***"]

    cmd3 = ["tool", "key=abcde"]
    assert runner._redact_cmd(cmd3) == ["tool", "key=***"]"""

content = re.sub(
    r"def test_cmd_redaction\(runner\):.*?assert redacted == cmd.*?# currently an identity function per initial spec",
    redaction_test,
    content,
    flags=re.DOTALL,
)

with open("tests/test_process_runner.py", "w") as f:
    f.write(content)
