from youtube_dub.domain.enums import PipelineStage


def test_stage_order():
    # Verify the order as specified in the architecture document
    stages = list(PipelineStage)
    expected_order = [
        PipelineStage.SOURCE_READY,
        PipelineStage.TRANSCRIBED,
        PipelineStage.SEGMENTED,
        PipelineStage.TRANSLATED,
        PipelineStage.TTS_PARTIAL,
        PipelineStage.ALIGNED,
        PipelineStage.TIMED,
        PipelineStage.MIXED,
        PipelineStage.RENDERED,
        PipelineStage.COMPLETED,
    ]
    assert stages == expected_order
