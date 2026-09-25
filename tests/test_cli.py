from unittest.mock import MagicMock, patch

from youtube_dub.cli import main


@patch("youtube_dub.cli.create_studio_application")
@patch("sys.argv", ["youtube-dub", "create", "--source", "en", "--target", "fr"])
def test_cli_create(mock_create_studio, capsys):
    mock_studio = MagicMock()
    mock_studio.create_job.return_value = MagicMock(job_id="test-123")
    mock_create_studio.return_value = mock_studio

    main()

    out, _ = capsys.readouterr()
    assert "Created job test-123" in out
    mock_studio.create_job.assert_called_with("en", "fr")


@patch("youtube_dub.cli.create_studio_application")
@patch("sys.argv", ["youtube-dub", "run", "--job-id", "test-123"])
def test_cli_run(mock_create_studio, capsys):
    import asyncio

    mock_studio = MagicMock()
    mock_task = asyncio.Future()
    mock_task.set_result(None)
    mock_studio._active_tasks = {"test-123": mock_task}

    mock_create_studio.return_value = mock_studio

    main()

    out, _ = capsys.readouterr()
    assert "Job test-123 started" in out
    mock_studio.run_job.assert_called_with("test-123")
