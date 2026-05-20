"""Tests for the formatting module."""

from datetime import datetime, timezone

import pytest

from claude_session_inspector.formatting import format_conversation
from claude_session_inspector.sessions import AssistantMessage, UserMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_msg_1() -> UserMessage:
    """First user message."""
    return UserMessage(
        uuid="u-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:00.000Z"),
        text="What is Python?",
        tool_results=[],
        is_sidechain=False,
        cwd="/home/user/project",
        git_branch="main",
        session_id="sess-abc",
    )


@pytest.fixture
def assistant_msg_1() -> AssistantMessage:
    """First assistant message with tool calls."""
    return AssistantMessage(
        uuid="a-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:05.000Z"),
        text="Python is a popular programming language.",
        tool_calls=[
            {"id": "tool-1", "name": "Read", "input": {"file_path": "/foo/bar.py"}},
            {"id": "tool-2", "name": "Write", "input": {"file_path": "/foo/baz.py", "content": "x=1"}},
        ],
        model="claude-3-opus",
        is_sidechain=False,
    )


@pytest.fixture
def user_msg_2() -> UserMessage:
    """Second user message with tool results."""
    return UserMessage(
        uuid="u-002",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:10.000Z"),
        text="Can you show me the file?",
        tool_results=[
            {
                "type": "tool_result",
                "tool_use_id": "tool-1",
                "content": "This is a very long file content that should be truncated to 200 characters because it exceeds the limit. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            }
        ],
        is_sidechain=False,
        cwd="/home/user/project",
        git_branch="main",
        session_id="sess-abc",
    )


@pytest.fixture
def assistant_msg_2() -> AssistantMessage:
    """Second assistant message without tool calls."""
    return AssistantMessage(
        uuid="a-002",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:15.000Z"),
        text="Here is the file content.",
        tool_calls=[],
        model="claude-3-opus",
        is_sidechain=False,
    )


# ---------------------------------------------------------------------------
# format_conversation — Basic functionality
# ---------------------------------------------------------------------------


def test_format_conversation_empty_list():
    """Empty message list should still have header."""
    result = format_conversation([], "sess-abc", "MyProject", "main")
    assert "Session: sess-abc" in result
    assert "Project: MyProject" in result
    assert "No messages to display" in result


def test_format_conversation_mixed_messages(user_msg_1, assistant_msg_1, user_msg_2):
    """Mixed user/assistant messages should format correctly."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    # Check header
    assert "Session: sess-abc" in result
    assert "Project: MyProject" in result
    assert "Branch: main" in result
    assert "Message count: 3" in result

    # Check messages are present
    assert "[USER]" in result
    assert "[ASSISTANT]" in result
    assert "What is Python?" in result
    assert "Python is a popular programming language." in result
    assert "Can you show me the file?" in result


def test_format_conversation_with_assistant_tool_calls(user_msg_1, assistant_msg_1):
    """Tool calls should be condensed with key=value pairs."""
    messages = [user_msg_1, assistant_msg_1]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    assert '[Tool: Read(file_path="/foo/bar.py") | id=tool-1]' in result
    assert '[Tool: Write(file_path="/foo/baz.py", content="x=1") | id=tool-2]' in result


# ---------------------------------------------------------------------------
# format_conversation — Index slicing
# ---------------------------------------------------------------------------


def test_format_conversation_start_index_negative(
    user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2
):
    """start_index=-2 should return the last 2 messages."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", start_index=-2)

    assert "Can you show me the file?" in result
    assert "Here is the file" in result
    assert "What is Python?" not in result
    assert "Python is a popular" not in result
    assert "Message count: 2" in result


def test_format_conversation_start_index(user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2):
    """start_index=2 should return messages from index 2 onwards."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", start_index=2)

    assert "Can you show me the file?" in result
    assert "Here is the file" in result
    assert "What is Python?" not in result
    assert "Message count: 2" in result


def test_format_conversation_end_index(user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2):
    """end_index=2 should return only first 2 messages."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", end_index=2)

    assert "What is Python?" in result
    assert "Python is a popular" in result
    assert "Can you show me the file?" not in result
    assert "Message count: 2" in result


def test_format_conversation_negative_start_index(
    user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2
):
    """start_index=-1 should return only the last message."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", start_index=-1)

    assert "Here is the file" in result
    assert "What is Python?" not in result
    assert "Can you show me the file?" not in result
    assert "Python is a popular" not in result
    assert "Message count: 1" in result


def test_format_conversation_negative_end_index(
    user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2
):
    """end_index=-1 should exclude the last message."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", end_index=-1)

    assert "What is Python?" in result
    assert "Python is a popular" in result
    assert "Can you show me the file?" in result
    assert "Here is the file" not in result
    assert "Message count: 3" in result


def test_format_conversation_start_and_end(user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2):
    """start_index=1, end_index=3 should return messages at index 1 and 2."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", start_index=1, end_index=3
    )

    assert "Python is a popular" in result
    assert "Can you show me the file?" in result
    assert "What is Python?" not in result
    assert "Here is the file" not in result
    assert "Message count: 2" in result


def test_format_conversation_slice_note_shown(user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2):
    """A slice note should appear when start_index or end_index is provided."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", end_index=2)

    assert "[Note: Showing messages" in result
    assert "of 4" in result


def test_format_conversation_no_note_when_no_slice(user_msg_1, assistant_msg_1):
    """No slice note should appear when both start_index and end_index are None."""
    messages = [user_msg_1, assistant_msg_1]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    assert "[Note:" not in result


# ---------------------------------------------------------------------------
# format_conversation — Tool results handling
# ---------------------------------------------------------------------------


def test_format_conversation_tool_results_included_by_default(user_msg_2):
    messages = [user_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    assert "Can you show me the file?" in result
    assert "[ToolResult:" in result
    assert "This is a very long file content" in result


def test_format_conversation_tool_results_content_excluded_when_length_zero(user_msg_2):
    messages = [user_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", tool_content_length=0
    )

    assert "Can you show me the file?" in result
    assert "[ToolResult:" in result
    assert "very long file content" not in result


def test_format_conversation_tool_results_truncated(user_msg_2):
    messages = [user_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", tool_content_length=50
    )

    assert "[ToolResult:" in result
    assert "..." in result
    assert "Lorem ipsum" not in result


def test_format_conversation_tool_result_ok_status():
    """Tool result without is_error should show | ok status."""
    user_msg = UserMessage(
        uuid="u-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:00.000Z"),
        text="",
        tool_results=[{"type": "tool_result", "tool_use_id": "t1", "content": "result"}],
        is_sidechain=False,
        cwd=None,
        git_branch=None,
        session_id=None,
    )
    result = format_conversation([user_msg], "sess-abc", "MyProject", "main")
    assert "[ToolResult: t1 | ok]" in result


def test_format_conversation_tool_result_error_status():
    """Tool result with is_error=True should show | error status."""
    user_msg = UserMessage(
        uuid="u-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:00.000Z"),
        text="",
        tool_results=[
            {
                "type": "tool_result",
                "tool_use_id": "t2",
                "content": "something went wrong",
                "is_error": True,
            }
        ],
        is_sidechain=False,
        cwd=None,
        git_branch=None,
        session_id=None,
    )
    result = format_conversation([user_msg], "sess-abc", "MyProject", "main")
    assert "[ToolResult: t2 | error]" in result


def test_format_conversation_tool_call_params_omitted_when_length_zero(assistant_msg_1):
    """tool_content_length=0 should suppress tool call params but keep name and id."""
    messages = [assistant_msg_1]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", tool_content_length=0)

    assert "[Tool: Read() | id=tool-1]" in result
    assert "file_path" not in result


# ---------------------------------------------------------------------------
# format_conversation — Timestamp handling
# ---------------------------------------------------------------------------


def test_format_conversation_timestamp_range(user_msg_1, assistant_msg_1, user_msg_2):
    """Should show correct timestamp range."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    assert "2024-06-01T10:00:00" in result or "2024-06-01" in result
    assert "2024-06-01T10:00:10" in result or "2024-06-01" in result


def test_format_conversation_timestamp_format_with_naive_datetime():
    """Naive datetimes should be treated as UTC."""
    msg = UserMessage(
        uuid="u-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0),  # Naive datetime
        text="Test",
        tool_results=[],
        is_sidechain=False,
        cwd=None,
        git_branch=None,
        session_id=None,
    )
    result = format_conversation([msg], "sess-abc", "MyProject", "main")
    assert "2024-06-01" in result


# ---------------------------------------------------------------------------
# format_conversation edge cases
# ---------------------------------------------------------------------------


def test_format_conversation_git_branch_none():
    """Should handle None git_branch."""
    msg = UserMessage(
        uuid="u-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:00.000Z"),
        text="Test",
        tool_results=[],
        is_sidechain=False,
        cwd=None,
        git_branch=None,
        session_id=None,
    )
    result = format_conversation([msg], "sess-abc", "MyProject", None)

    assert "Branch: unknown" in result


def test_format_conversation_assistant_no_tool_calls(user_msg_1):
    """Assistant message without tool calls should format correctly."""
    asst_msg = AssistantMessage(
        uuid="a-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:05.000Z"),
        text="Just text, no tools.",
        tool_calls=[],
        model="claude-3-opus",
        is_sidechain=False,
    )
    messages = [user_msg_1, asst_msg]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    assert "Just text, no tools." in result
    assert "[ASSISTANT]" in result


def test_format_conversation_empty_message_text():
    """Empty message text should still format."""
    msg = UserMessage(
        uuid="u-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:00.000Z"),
        text="",
        tool_results=[],
        is_sidechain=False,
        cwd=None,
        git_branch=None,
        session_id=None,
    )
    result = format_conversation([msg], "sess-abc", "MyProject", "main")

    assert "[USER]" in result
    assert "Message count: 1" in result


def test_format_conversation_tool_call_with_no_input():
    """Tool call without input should format as name()."""
    asst_msg = AssistantMessage(
        uuid="a-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:05.000Z"),
        text="Calling a tool.",
        tool_calls=[{"id": "tool-1", "name": "DoSomething", "input": {}}],
        model="claude-3-opus",
        is_sidechain=False,
    )
    messages = [asst_msg]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    assert "[Tool: DoSomething() | id=tool-1]" in result


def test_format_conversation_long_tool_result_content():
    """Tool result with very long content should be truncated."""
    long_content = "x" * 500
    user_msg = UserMessage(
        uuid="u-001",
        timestamp=datetime.fromisoformat("2024-06-01T10:00:00.000Z"),
        text="Test",
        tool_results=[{"type": "tool_result", "tool_use_id": "t1", "content": long_content}],
        is_sidechain=False,
        cwd=None,
        git_branch=None,
        session_id=None,
    )
    result = format_conversation([user_msg], "sess-abc", "MyProject", "main")

    assert "[ToolResult: t1 | ok]" in result
    assert "..." in result
    assert long_content not in result
