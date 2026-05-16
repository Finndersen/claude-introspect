"""Tests for the inspection module."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_session_inspector.inspection import (
    DEFAULT_SUMMARY_QUESTION,
    inspect_session,
)
from claude_session_inspector.sessions import AssistantMessage, UserMessage


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        UserMessage(
            uuid="user-1",
            timestamp=datetime(2026, 5, 16, 10, 0, 0),
            text="What is the weather?",
            tool_results=[],
            is_sidechain=False,
            cwd="/home/user",
            git_branch="main",
            session_id="test-session",
        ),
        AssistantMessage(
            uuid="asst-1",
            timestamp=datetime(2026, 5, 16, 10, 0, 5),
            text="I don't have access to real-time weather data.",
            tool_calls=[],
            model="claude-opus",
            is_sidechain=False,
        ),
    ]


@pytest.mark.asyncio
async def test_inspect_session_with_default_question(sample_messages):
    """Test inspect_session uses default question when none provided."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"Session summary here.", b"")
        )
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        result = await inspect_session("test-session-id")

        assert result == "Session summary here."
        # Verify the prompt contains the default question
        call_args = mock_process.communicate.call_args
        prompt = call_args[0][0].decode("utf-8")
        assert DEFAULT_SUMMARY_QUESTION in prompt


@pytest.mark.asyncio
async def test_inspect_session_with_custom_question(sample_messages):
    """Test inspect_session uses custom question when provided."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"Answer to custom question.", b"")
        )
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        custom_q = "What was the main issue discussed?"
        result = await inspect_session("test-session-id", question=custom_q)

        assert result == "Answer to custom question."
        call_args = mock_process.communicate.call_args
        prompt = call_args[0][0].decode("utf-8")
        assert custom_q in prompt
        assert DEFAULT_SUMMARY_QUESTION not in prompt


@pytest.mark.asyncio
async def test_inspect_session_formats_conversation(sample_messages):
    """Test that the formatted conversation is passed to claude."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"response", b""))
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        await inspect_session("test-session-id")

        call_args = mock_process.communicate.call_args
        prompt = call_args[0][0].decode("utf-8")

        # Verify prompt structure
        assert "<conversation>" in prompt
        assert "</conversation>" in prompt
        assert "=== Session: test-session-id ===" in prompt


@pytest.mark.asyncio
async def test_inspect_session_session_not_found():
    """Test that FileNotFoundError is raised when session not found."""
    with patch("claude_session_inspector.inspection.find_session_file") as mock_find:
        mock_find.return_value = None

        with pytest.raises(FileNotFoundError, match="Session not found"):
            await inspect_session("nonexistent-session-id")


@pytest.mark.asyncio
async def test_inspect_session_claude_not_found(sample_messages):
    """Test that FileNotFoundError is raised when claude command not found."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"
        mock_create.side_effect = FileNotFoundError("claude not found")

        with pytest.raises(FileNotFoundError, match="claude command not found"):
            await inspect_session("test-session-id")


@pytest.mark.asyncio
async def test_inspect_session_timeout(sample_messages):
    """Test that TimeoutError is raised when command times out."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()
        mock_create.return_value = mock_process

        with pytest.raises(TimeoutError, match="timed out after 60 seconds"):
            await inspect_session("test-session-id")

        # Verify process was killed
        mock_process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_inspect_session_command_failure(sample_messages):
    """Test that RuntimeError is raised on non-zero exit code."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error message from claude")
        )
        mock_process.returncode = 1
        mock_create.return_value = mock_process

        with pytest.raises(RuntimeError, match="exit code 1"):
            await inspect_session("test-session-id")


@pytest.mark.asyncio
async def test_inspect_session_respects_max_messages(sample_messages):
    """Test that max_messages parameter is passed to formatting function."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch(
            "claude_session_inspector.inspection.format_conversation_for_inspection"
        ) as mock_format,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"
        mock_format.return_value = "formatted conversation"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"response", b""))
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        await inspect_session("test-session-id", max_messages=50)

        # Verify format_conversation_for_inspection was called with max_messages=50
        mock_format.assert_called_once()
        call_kwargs = mock_format.call_args[1]
        assert call_kwargs["max_messages"] == 50


@pytest.mark.asyncio
async def test_inspect_session_calls_find_session_file(sample_messages):
    """Test that find_session_file is called with the session_id."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"response", b""))
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        test_session_id = "my-test-session-id"
        await inspect_session(test_session_id)

        mock_find.assert_called_once_with(test_session_id)


@pytest.mark.asyncio
async def test_inspect_session_calls_load_session():
    """Test that load_session is called with the session file."""
    session_file = Path("/test/session.jsonl")

    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = session_file
        mock_load.return_value = []
        mock_project.return_value = "TestProject"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"response", b""))
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        await inspect_session("test-session-id")

        mock_load.assert_called_once_with(session_file)


@pytest.mark.asyncio
async def test_inspect_session_subprocess_args(sample_messages):
    """Test that subprocess is called with correct arguments."""
    with (
        patch("claude_session_inspector.inspection.find_session_file") as mock_find,
        patch("claude_session_inspector.inspection.load_session") as mock_load,
        patch(
            "claude_session_inspector.inspection.resolve_project_name"
        ) as mock_project,
        patch("claude_session_inspector.inspection.asyncio.create_subprocess_exec") as mock_create,
    ):
        mock_find.return_value = Path("/test/session.jsonl")
        mock_load.return_value = sample_messages
        mock_project.return_value = "TestProject"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"response", b""))
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        await inspect_session("test-session-id")

        mock_create.assert_called_once()
        call_args = mock_create.call_args

        # Check positional args
        assert call_args[0] == (
            "claude",
            "-p",
            "--model",
            "claude-haiku-4",
        )

        # Check keyword args
        assert call_args[1]["stdin"] == asyncio.subprocess.PIPE
        assert call_args[1]["stdout"] == asyncio.subprocess.PIPE
        assert call_args[1]["stderr"] == asyncio.subprocess.PIPE
