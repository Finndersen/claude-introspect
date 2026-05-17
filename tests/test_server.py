"""Tests for the MCP server and list_sessions tool."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from claude_session_inspector.search import SearchMatch
from claude_session_inspector.server import (
    inspect_session,
    list_sessions,
    search_sessions,
    view_session_messages,
)
from claude_session_inspector.sessions import AssistantMessage, SessionInfo, UserMessage


def mock_session(
    session_id: str = "abc123",
    project_name: str = "TestProject",
    project_dir: str = "/path/to/project",
    first_prompt: str = "Help me implement a feature",
    first_timestamp: datetime | None = datetime(
        2026, 5, 16, 9, 15, tzinfo=timezone.utc
    ),
    last_timestamp: datetime | None = datetime(
        2026, 5, 16, 10, 30, tzinfo=timezone.utc
    ),
    git_branch: str | None = "main",
    cwd: str | None = "/path/to/project",
    file_size_bytes: int = 4096,
) -> SessionInfo:
    """Create a mock SessionInfo for testing."""
    return SessionInfo(
        session_id=session_id,
        project_name=project_name,
        project_dir=project_dir,
        file_path=Path(f"/tmp/{session_id}.jsonl"),
        first_prompt=first_prompt,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
        git_branch=git_branch,
        cwd=cwd,
        file_size_bytes=file_size_bytes,
    )


def test_sessions_browse_empty_no_filter():
    """Test empty results without filter."""
    with patch("claude_session_inspector.server.discover_sessions", return_value=([], 0)):
        result = list_sessions()
        assert result == "No sessions found."


def test_sessions_browse_empty_with_filter():
    """Test empty results with filter."""
    with patch("claude_session_inspector.server.discover_sessions", return_value=([], 0)):
        result = list_sessions(project="NonExistent")
        assert result == "No sessions found matching 'NonExistent'."


def test_sessions_browse_single():
    """Test output with a single session."""
    session = mock_session(session_id="abc123")
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=([session], 1)
    ):
        result = list_sessions()
        assert "Showing 1 of 1 sessions" in result
        assert "abc123" in result
        assert "TestProject" in result
        assert "main" in result
        assert "2026-05-16 10:30 UTC" in result
        assert "2026-05-16 09:15 UTC" in result


def test_sessions_browse_multiple():
    """Test output with multiple sessions."""
    sessions = [
        mock_session(session_id="aaa", project_name="Project1"),
        mock_session(session_id="bbb", project_name="Project2"),
        mock_session(session_id="ccc", project_name="Project3"),
    ]
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=(sessions, 3)
    ):
        result = list_sessions()
        assert "Showing 3 of 3 sessions" in result
        assert "aaa" in result
        assert "bbb" in result
        assert "ccc" in result


def test_sessions_browse_plural_vs_singular():
    """Test header line shows correct counts."""
    with patch(
        "claude_session_inspector.server.discover_sessions",
        return_value=([mock_session()], 1),
    ):
        result = list_sessions()
        assert "Showing 1 of 1 sessions" in result

    sessions = [mock_session(session_id=f"id{i}") for i in range(2)]
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=(sessions, 2)
    ):
        result = list_sessions()
        assert "Showing 2 of 2 sessions" in result


def test_sessions_browse_with_project_filter():
    """Test that project filter and limit are passed to discover_sessions."""
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=([], 0)
    ) as mock_discover:
        list_sessions(project="MyProject")
        mock_discover.assert_called_once_with(project_filter="MyProject", limit=20)


def test_sessions_browse_none_timestamps():
    """Test handling of None timestamps."""
    session = mock_session(first_timestamp=None, last_timestamp=None)
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=([session], 1)
    ):
        result = list_sessions()
        assert result.count("unknown") >= 2


def test_sessions_browse_none_branch():
    """Test handling of None git_branch."""
    session = mock_session(git_branch=None)
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=([session], 1)
    ):
        result = list_sessions()
        assert "unknown" in result


def test_sessions_browse_first_prompt_truncated():
    """Test that first_prompt longer than 300 chars is truncated in table output."""
    prompt = "x" * 400
    session = mock_session(first_prompt=prompt)
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=([session], 1)
    ):
        result = list_sessions()
        assert "x" * 300 + "..." in result
        assert "x" * 400 not in result


def test_sessions_browse_table_columns():
    """Test that table header contains expected columns."""
    session = mock_session()
    with patch(
        "claude_session_inspector.server.discover_sessions", return_value=([session], 1)
    ):
        result = list_sessions()
        assert "session_id" in result
        assert "project" in result
        assert "branch" in result
        assert "last_active" in result
        assert "started" in result
        assert "size_kb" in result
        assert "first_prompt" in result


# ─────────────────────────────────────────────────────────────────────────
# search_sessions tests
# ─────────────────────────────────────────────────────────────────────────


def test_sessions_search_empty_results():
    """Test search with no matches."""
    with patch("claude_session_inspector.server._search_sessions_impl", return_value=[]):
        result = search_sessions("nonexistent")
        assert 'No matches found for "nonexistent"' in result


def test_sessions_search_single_result():
    """Test search with a single match."""
    match = SearchMatch(
        session_id="abc123",
        project_name="TestProject",
        match_count=5,
        snippets=["first match", "second match"],
        first_prompt="Help me implement a feature",
    )
    with patch("claude_session_inspector.server._search_sessions_impl", return_value=[match]):
        result = search_sessions("test")
        assert 'Found "test" in 1 session' in result
        assert "Session: abc123" in result
        assert "Project: TestProject" in result
        assert "Matches: 5" in result
        assert "First prompt: Help me implement a feature" in result
        assert "first match" in result
        assert "second match" in result


def test_sessions_search_multiple_results():
    """Test search with multiple matches."""
    matches = [
        SearchMatch(
            session_id="session1",
            project_name="Project1",
            match_count=10,
            snippets=["match1"],
            first_prompt="prompt1",
        ),
        SearchMatch(
            session_id="session2",
            project_name="Project2",
            match_count=5,
            snippets=["match2"],
            first_prompt="prompt2",
        ),
    ]
    with patch("claude_session_inspector.server._search_sessions_impl", return_value=matches):
        result = search_sessions("test")
        assert 'Found "test" in 2 sessions' in result
        assert "Session: session1" in result
        assert "Session: session2" in result


def test_sessions_search_plural_vs_singular():
    """Test correct singular/plural in count header."""
    with patch(
        "claude_session_inspector.server._search_sessions_impl",
        return_value=[SearchMatch("s", "P", 1, [], "")],
    ):
        result = search_sessions("test")
        assert "in 1 session" in result

    with patch(
        "claude_session_inspector.server._search_sessions_impl",
        return_value=[SearchMatch("s1", "P", 1, [], ""), SearchMatch("s2", "P", 1, [], "")],
    ):
        result = search_sessions("test")
        assert "in 2 sessions" in result


def test_sessions_search_with_project_filter():
    """Test that project filter is passed to _search_sessions_impl."""
    with patch(
        "claude_session_inspector.server._search_sessions_impl", return_value=[]
    ) as mock_search:
        search_sessions("test", project="MyProject")
        mock_search.assert_called_once_with("test", project="MyProject", max_results=20, use_regex=False)


def test_sessions_search_with_max_results():
    """Test that max_results parameter is passed."""
    with patch(
        "claude_session_inspector.server._search_sessions_impl", return_value=[]
    ) as mock_search:
        search_sessions("test", max_results=5)
        mock_search.assert_called_once_with("test", project=None, max_results=5, use_regex=False)


def test_sessions_search_with_use_regex():
    """Test that use_regex=True is passed through to the impl."""
    with patch(
        "claude_session_inspector.server._search_sessions_impl", return_value=[]
    ) as mock_search:
        search_sessions("initializ(e|ation)", use_regex=True)
        mock_search.assert_called_once_with(
            "initializ(e|ation)", project=None, max_results=20, use_regex=True
        )


def test_sessions_search_rg_not_found_error():
    """Test handling of RuntimeError from ripgrep not being installed."""
    with patch("claude_session_inspector.server._search_sessions_impl") as mock_search:
        mock_search.side_effect = RuntimeError(
            "ripgrep (rg) is not installed. Please install ripgrep to use search_sessions."
        )
        result = search_sessions("test")
        assert "ripgrep (rg) is not installed" in result


def test_sessions_search_empty_first_prompt():
    """Test handling of empty first_prompt."""
    match = SearchMatch(
        session_id="s",
        project_name="P",
        match_count=1,
        snippets=["match"],
        first_prompt="",
    )
    with patch("claude_session_inspector.server._search_sessions_impl", return_value=[match]):
        result = search_sessions("test")
        assert "First prompt: (empty)" in result


def test_sessions_search_all_fields_present():
    """Test that all expected fields are in the output."""
    match = SearchMatch(
        session_id="abc",
        project_name="TestProject",
        match_count=3,
        snippets=["snippet1", "snippet2"],
        first_prompt="Test prompt",
    )
    with patch("claude_session_inspector.server._search_sessions_impl", return_value=[match]):
        result = search_sessions("query")
        required_fields = [
            "Session:",
            "Project:",
            "Matches:",
            "First prompt:",
            "Matching snippets:",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────────────────
# view_session_messages tests
# ─────────────────────────────────────────────────────────────────────────


def mock_user_message(
    text: str = "Hello, help me with this",
    timestamp: datetime | None = None,
    git_branch: str | None = "main",
) -> UserMessage:
    """Create a mock UserMessage for testing."""
    if timestamp is None:
        timestamp = datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc)
    return UserMessage(
        uuid="user-1",
        timestamp=timestamp,
        text=text,
        tool_results=[],
        is_sidechain=False,
        cwd="/path/to/project",
        git_branch=git_branch,
        session_id="test-session",
    )


def mock_assistant_message(
    text: str = "Here is the response",
    timestamp: datetime | None = None,
) -> AssistantMessage:
    """Create a mock AssistantMessage for testing."""
    if timestamp is None:
        timestamp = datetime(2026, 5, 16, 10, 5, tzinfo=timezone.utc)
    return AssistantMessage(
        uuid="assistant-1",
        timestamp=timestamp,
        text=text,
        tool_calls=[],
        model="claude-opus",
        is_sidechain=False,
    )


def test_view_session_messages_delegates_to_format_conversation():
    """Test view_session_messages delegates to format_conversation with correct args."""
    messages = [
        mock_user_message("Hello", timestamp=datetime(2026, 5, 16, 9, 0, tzinfo=timezone.utc)),
        mock_assistant_message(timestamp=datetime(2026, 5, 16, 9, 5, tzinfo=timezone.utc)),
        mock_user_message("Follow up", timestamp=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc)),
    ]

    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load, patch("claude_session_inspector.server.resolve_project_name") as mock_resolve, patch(
        "claude_session_inspector.server.format_conversation"
    ) as mock_format:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = messages
        mock_resolve.return_value = "TestProject"
        mock_format.return_value = "Formatted conversation"

        result = view_session_messages("test-session", max_tool_result_length=500)

        assert result == "Formatted conversation"
        mock_format.assert_called_once()
        call_args = mock_format.call_args
        assert call_args[0][0] == messages
        assert call_args[0][1] == "test-session"
        assert call_args[0][2] == "TestProject"
        assert call_args[1]["max_tool_result_length"] == 500
        assert call_args[1]["start_index"] is None
        assert call_args[1]["end_index"] is None
        assert call_args[1]["message_type"] is None


def test_view_session_messages_session_not_found():
    """Test error when session file not found."""
    with patch("claude_session_inspector.server.find_session_file", return_value=None):
        result = view_session_messages("nonexistent-id")

        assert "Error: Session" in result
        assert "nonexistent-id" in result
        assert "not found" in result


def test_view_session_messages_empty_session():
    """Test error when session has no messages."""
    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = []

        result = view_session_messages("test-session")

        assert "no messages" in result


def test_view_session_messages_extracts_git_branch():
    """Test that git_branch is extracted from first user message."""
    messages = [
        mock_user_message("First", git_branch="feature-branch"),
        mock_assistant_message(),
    ]

    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load, patch("claude_session_inspector.server.resolve_project_name") as mock_resolve, patch(
        "claude_session_inspector.server.format_conversation"
    ) as mock_format:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = messages
        mock_resolve.return_value = "TestProject"
        mock_format.return_value = "Formatted"

        view_session_messages("test-session")

        call_args = mock_format.call_args
        assert call_args[0][3] == "feature-branch"


def test_view_session_messages_git_branch_none_fallback():
    """Test that None git_branch is handled."""
    messages = [
        mock_user_message("First", git_branch=None),
        mock_assistant_message(),
    ]

    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load, patch("claude_session_inspector.server.resolve_project_name") as mock_resolve, patch(
        "claude_session_inspector.server.format_conversation"
    ) as mock_format:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = messages
        mock_resolve.return_value = "TestProject"
        mock_format.return_value = "Formatted"

        view_session_messages("test-session")

        call_args = mock_format.call_args
        assert call_args[0][3] is None


def test_view_session_messages_start_end_index():
    """Test that start_index and end_index are forwarded to format_conversation."""
    messages = [mock_user_message("Msg"), mock_assistant_message()]

    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load, patch("claude_session_inspector.server.resolve_project_name") as mock_resolve, patch(
        "claude_session_inspector.server.format_conversation"
    ) as mock_format:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = messages
        mock_resolve.return_value = "TestProject"
        mock_format.return_value = "Sliced"

        view_session_messages("test-session", start_index=1, end_index=3)

        call_args = mock_format.call_args
        assert call_args[1]["start_index"] == 1
        assert call_args[1]["end_index"] == 3


def test_view_session_messages_negative_index():
    """start_index=-1 returns only the last message."""
    messages = [
        mock_user_message("First", timestamp=datetime(2026, 5, 16, 9, 0, tzinfo=timezone.utc)),
        mock_assistant_message(timestamp=datetime(2026, 5, 16, 9, 5, tzinfo=timezone.utc)),
        mock_user_message("Last", timestamp=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc)),
    ]

    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load, patch("claude_session_inspector.server.resolve_project_name") as mock_resolve:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = messages
        mock_resolve.return_value = "TestProject"

        result = view_session_messages("test-session", start_index=-1)

        assert "Last" in result
        assert "First" not in result
        assert "Message count: 1" in result


def test_view_session_messages_message_type_filter():
    """message_type=['user'] filters to user messages only."""
    messages = [
        mock_user_message("User prompt"),
        mock_assistant_message("Assistant reply"),
    ]

    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load, patch("claude_session_inspector.server.resolve_project_name") as mock_resolve:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = messages
        mock_resolve.return_value = "TestProject"

        result = view_session_messages("test-session", message_type=["user"])

        assert "User prompt" in result
        assert "Assistant reply" not in result


def test_view_session_messages_invalid_message_type():
    """Invalid message_type value returns an error before touching the session."""
    result = view_session_messages("test-session", message_type=["invalid_type"])

    assert "Error" in result
    assert "invalid_type" in result


def test_view_session_messages_combined_slice_and_type():
    """message_type filter is applied before start_index slice."""
    messages = [
        mock_user_message("U1", timestamp=datetime(2026, 5, 16, 9, 0, tzinfo=timezone.utc)),
        mock_assistant_message("A1", timestamp=datetime(2026, 5, 16, 9, 5, tzinfo=timezone.utc)),
        mock_user_message("U2", timestamp=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc)),
    ]

    with patch("claude_session_inspector.server.find_session_file") as mock_find, patch(
        "claude_session_inspector.server.load_session"
    ) as mock_load, patch("claude_session_inspector.server.resolve_project_name") as mock_resolve:
        mock_find.return_value = Path("/tmp/test-session.jsonl")
        mock_load.return_value = messages
        mock_resolve.return_value = "TestProject"

        # Filter to user messages (U1, U2), then take last 1 → U2
        result = view_session_messages("test-session", message_type=["user"], start_index=-1)

        assert "U2" in result
        assert "U1" not in result
        assert "A1" not in result


# ─────────────────────────────────────────────────────────────────────────
# inspect_session tests
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inspect_session_delegates_to_impl():
    """Test that the MCP tool delegates to inspect_session_impl with all args."""
    with patch(
        "claude_session_inspector.server.inspect_session_impl",
        new=AsyncMock(return_value="summary text"),
    ) as mock_impl:
        result = await inspect_session("abc123", question="What happened?")

        assert result == "summary text"
        mock_impl.assert_called_once_with("abc123", "What happened?")


@pytest.mark.asyncio
async def test_inspect_session_default_args():
    """Test that optional args use expected defaults when not provided."""
    with patch(
        "claude_session_inspector.server.inspect_session_impl",
        new=AsyncMock(return_value="default summary"),
    ) as mock_impl:
        result = await inspect_session("abc123")

        assert result == "default summary"
        mock_impl.assert_called_once_with("abc123", None)


@pytest.mark.asyncio
async def test_inspect_session_propagates_errors():
    """Test that errors from impl propagate through the MCP wrapper."""
    with patch(
        "claude_session_inspector.server.inspect_session_impl",
        new=AsyncMock(side_effect=FileNotFoundError("Session not found: abc123")),
    ):
        with pytest.raises(FileNotFoundError, match="Session not found"):
            await inspect_session("abc123")
