import re

with open("tests/test_separation.py", "r") as f:
    content = f.read()

replacement = """@pytest.mark.asyncio
async def test_passthrough_separator(fake_runner, tmp_path):
    audio_file = tmp_path / "input.wav"
    audio_file.write_text("audio")
    out_dir = tmp_path / "out"

    async def mock_run(*args, **kwargs):
        out = out_dir / "background.wav"
        out.write_text("silent bg")
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_runner.run.side_effect = mock_run

    sep = PassThroughVocalSeparator()
    v, b = await sep.separate(audio_file, out_dir, fake_runner)

    assert v.name == "vocals.wav"
    assert b.name == "background.wav"
    assert v.exists()
    assert b.exists()

    cmd = fake_runner.run.call_args[0][0]
    assert "ffmpeg" in cmd
    assert "volume=0" in cmd"""

content = re.sub(
    r"@pytest.mark.asyncio\nasync def test_passthrough_separator.*?assert b\.exists\(\)",
    replacement,
    content,
    flags=re.DOTALL,
)

with open("tests/test_separation.py", "w") as f:
    f.write(content)
