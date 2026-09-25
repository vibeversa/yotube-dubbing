with open("tests/test_stages_part2.py", "r") as f:
    content = f.read()

if "def test_mix_stage" not in content:
    content += """
from youtube_dub.pipeline.stages.mix import MixStage

@pytest.mark.asyncio
async def test_mix_stage_negative_start_ms(fake_context):
    timing_path = fake_context.artifact_store.path_for(fake_context.job_id, "timing")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timing_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "timed_artifact": "seg-1.wav"}], f)

    translations_path = fake_context.artifact_store.path_for(fake_context.job_id, "translations")
    translations_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translations_path, "w") as f:
        json.dump([{"segment_id": "seg-1", "start_ms": -100, "end_ms": 1000}], f)

    source_audio = fake_context.artifact_store.path_for(fake_context.job_id, "source_audio")
    source_audio.parent.mkdir(parents=True, exist_ok=True)
    source_audio.touch()

    timed_audio = fake_context.artifact_store.path_for(fake_context.job_id, "timing", "seg-1")
    timed_audio.parent.mkdir(parents=True, exist_ok=True)
    timed_audio.touch()

    async def mock_run(cmd, **kwargs):
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch()
        return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

    fake_context.process_runner.run.side_effect = mock_run

    stage = MixStage()
    res = await stage.run(fake_context)

    assert res.status == StageStatus.FAILED
    assert "Invalid start_ms < 0" in res.error
"""

with open("tests/test_stages_part2.py", "w") as f:
    f.write(content)
