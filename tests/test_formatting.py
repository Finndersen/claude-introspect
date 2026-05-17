"""Tests for the formatting module."""

from datetime import datetime, timezone

import pytest

from claude_session_inspector.formatting import (
    format_conversation,
    format_for_inspection,
)
from claude_session_inspector.sessions import AssistantMessage, UserMessage


# ---------------------------------------------------------------------------
# Fixtures — for format_conversation (view_session_messages format)
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
# Fixtures — for inspection format (format_for_inspection)
# ---------------------------------------------------------------------------


@pytest.fixture
def user_message_1() -> UserMessage:
    return UserMessage(
        uuid="u-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Hello, Claude!",
        tool_results=[],
        is_sidechain=False,
        cwd="/home/user/project",
        git_branch="main",
        session_id="sess-abc",
    )


@pytest.fixture
def assistant_message_1() -> AssistantMessage:
    return AssistantMessage(
        uuid="a-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 5, tzinfo=timezone.utc),
        text="Hello! How can I help?",
        tool_calls=[
            {
                "id": "tool-1",
                "name": "Read",
                "input": {"file_path": "/foo/bar.py"},
            },
            {
                "id": "tool-2",
                "name": "Bash",
                "input": {"command": "ls -la /home"},
            },
        ],
        model="claude-3-opus",
        is_sidechain=False,
    )


@pytest.fixture
def user_message_with_tool_results() -> UserMessage:
    return UserMessage(
        uuid="u-002",
        timestamp=datetime(2024, 6, 1, 10, 0, 10, tzinfo=timezone.utc),
        text="What's in that file?",
        tool_results=[
            {
                "type": "tool_result",
                "tool_use_id": "tool-1",
                "content": "def hello():\n    print('Hello')",
            },
            {
                "type": "tool_result",
                "tool_use_id": "tool-2",
                "content": "total 1234\ndrwxr-xr-x  5 user  staff    160 Jun  1 10:00 Desktop",
            },
        ],
        is_sidechain=False,
        cwd="/home/user/project",
        git_branch="main",
        session_id="sess-abc",
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
# format_conversation — Filtering and limits
# ---------------------------------------------------------------------------


def test_format_conversation_message_type_user_filter(
    user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2
):
    """message_type=['user'] should exclude assistant messages."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", message_type=["user"])

    assert "What is Python?" in result
    assert "Can you show me the file?" in result
    assert "Python is a popular" not in result
    assert "Here is the file" not in result
    assert "Message count: 2" in result


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


def test_format_conversation_slice_applied_after_type_filter(
    user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2
):
    """message_type filter then start_index=-1 should give last filtered message."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", message_type=["user"], start_index=-1
    )

    assert "Can you show me the file?" in result
    assert "What is Python?" not in result
    assert "Message count: 1" in result


# ---------------------------------------------------------------------------
# format_conversation — Tool results handling
# ---------------------------------------------------------------------------


def test_format_conversation_tool_results_included_by_default(user_msg_2):
    messages = [user_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    assert "Can you show me the file?" in result
    assert "[ToolResult:" in result
    assert "This is a very long file content" in result


def test_format_conversation_tool_results_content_excluded_when_max_length_zero(user_msg_2):
    messages = [user_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", max_tool_result_length=0
    )

    assert "Can you show me the file?" in result
    assert "[ToolResult:" in result
    assert "very long file content" not in result


def test_format_conversation_tool_results_truncated(user_msg_2):
    messages = [user_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", max_tool_result_length=50
    )

    assert "[ToolResult:" in result
    assert "..." in result
    assert "Lorem ipsum" not in result


# ---------------------------------------------------------------------------
# format_conversation — Timestamp handling
# ---------------------------------------------------------------------------


def test_format_conversation_timestamp_range(user_msg_1, assistant_msg_1, user_msg_2):
    """Should show correct timestamp range."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    # Should show time range from first to last message
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
    # Should still have timestamp (formatted as ISO string)
    assert "2024-06-01" in result


# ---------------------------------------------------------------------------
# format_conversation — Index slicing
# ---------------------------------------------------------------------------


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
# format_conversation — message_type filtering
# ---------------------------------------------------------------------------


def test_format_conversation_message_type_user(user_msg_2):
    """message_type=['user'] renders text only, suppresses tool_results."""
    messages = [user_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", message_type=["user"])

    assert "[USER]" in result
    assert "Can you show me the file?" in result
    assert "[ToolResult:" not in result


def test_format_conversation_message_type_tool_results(user_msg_1, user_msg_2):
    """message_type=['tool_results'] renders tool_results only; messages without tool_results are omitted."""
    messages = [user_msg_1, user_msg_2]  # user_msg_1 has no tool_results
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", message_type=["tool_results"]
    )

    assert "[ToolResult:" in result
    assert "What is Python?" not in result  # user_msg_1 omitted; user_msg_2 text suppressed
    assert "Can you show me the file?" not in result  # text suppressed


def test_format_conversation_message_type_assistant(assistant_msg_1):
    """message_type=['assistant'] renders text only, suppresses tool_calls."""
    messages = [assistant_msg_1]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", message_type=["assistant"]
    )

    assert "[ASSISTANT]" in result
    assert "Python is a popular programming language." in result
    assert "[Tool:" not in result


def test_format_conversation_message_type_tool_calls(assistant_msg_1, assistant_msg_2):
    """message_type=['tool_calls'] renders tool_calls only; messages without tool_calls are omitted."""
    messages = [assistant_msg_1, assistant_msg_2]  # assistant_msg_2 has no tool_calls
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", message_type=["tool_calls"]
    )

    assert "[Tool:" in result
    assert "Python is a popular" not in result  # text suppressed
    assert "Here is the file" not in result  # assistant_msg_2 omitted


def test_format_conversation_message_type_user_and_tool_results(user_msg_2):
    """message_type=['user','tool_results'] renders both text and tool_results."""
    messages = [user_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", message_type=["user", "tool_results"]
    )

    assert "Can you show me the file?" in result
    assert "[ToolResult:" in result


def test_format_conversation_message_type_multiple_cross(
    user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2
):
    """message_type=['user','assistant'] shows text of both, no tool parts."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", message_type=["user", "assistant"]
    )

    assert "What is Python?" in result
    assert "Python is a popular programming language." in result
    assert "[Tool:" not in result
    assert "[ToolResult:" not in result


def test_format_conversation_message_omitted_when_no_renderable_parts(assistant_msg_2):
    """AssistantMessage with no tool_calls filtered by ['tool_calls'] is omitted entirely."""
    messages = [assistant_msg_2]  # has no tool_calls
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", message_type=["tool_calls"]
    )

    assert "No messages to display" in result


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

    assert "[ToolResult: t1]" in result
    assert "..." in result
    assert long_content not in result


# ---------------------------------------------------------------------------
# format_for_inspection — Header
# ---------------------------------------------------------------------------


def testformat_for_inspection_header_basic(user_message_1: UserMessage):
    messages = [user_message_1]
    result = format_for_inspection(messages, "sess-abc", "MyProject")

    assert "=== Session: sess-abc ===" in result
    assert "Project: MyProject" in result
    assert "Branch: main" in result
    assert "Messages: 1" in result


def testformat_for_inspection_header_no_branch():
    msg = UserMessage(
        uuid="u-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Hello",
        tool_results=[],
        is_sidechain=False,
        cwd="/home",
        git_branch=None,
        session_id="sess-abc",
    )
    result = format_for_inspection([msg], "sess-abc", "MyProject")

    assert "=== Session: sess-abc ===" in result
    assert "Project: MyProject" in result
    assert "Branch:" not in result


def testformat_for_inspection_period(
    user_message_1: UserMessage, assistant_message_1: AssistantMessage
):
    messages = [user_message_1, assistant_message_1]
    result = format_for_inspection(messages, "sess-abc", "MyProject")

    assert "2024-06-01 10:00:00" in result
    assert "2024-06-01 10:00:05" in result
    assert "→" in result


# ---------------------------------------------------------------------------
# format_for_inspection — User Messages
# ---------------------------------------------------------------------------


def testformat_for_inspection_user_message(user_message_1: UserMessage):
    messages = [user_message_1]
    result = format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[USER]" in result
    assert "Hello, Claude!" in result
    assert "2024-06-01 10:00:00" in result


# ---------------------------------------------------------------------------
# format_for_inspection — Assistant Messages
# ---------------------------------------------------------------------------


def testformat_for_inspection_assistant_message(assistant_message_1: AssistantMessage):
    messages = [assistant_message_1]
    result = format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[ASSISTANT]" in result
    assert "Hello! How can I help?" in result
    assert "2024-06-01 10:00:05" in result


def testformat_for_inspection_tool_calls_condensed(
    assistant_message_1: AssistantMessage,
):
    messages = [assistant_message_1]
    result = format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[Tool: Read(file_path=/foo/bar.py) | id=tool-1]" in result
    assert "[Tool: Bash(command=ls -la /home) | id=tool-2]" in result


def testformat_for_inspection_tool_call_truncation():
    long_command = "x" * 100
    msg = AssistantMessage(
        uuid="a-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Running command",
        tool_calls=[
            {
                "id": "t1",
                "name": "Bash",
                "input": {"command": long_command},
            }
        ],
        model="claude-3-opus",
        is_sidechain=False,
    )
    result = format_for_inspection([msg], "sess-abc", "MyProject")

    assert "[Tool: Bash(command=" in result
    assert "xxxxxxxx) | id=t1]" in result
    tool_lines = [line for line in result.split("\n") if "[Tool:" in line]
    assert len(tool_lines) > 0
    assert len(tool_lines[0]) <= 110


# ---------------------------------------------------------------------------
# format_for_inspection — Tool Results
# ---------------------------------------------------------------------------


def testformat_for_inspection_tool_results_included_by_default(
    user_message_with_tool_results: UserMessage,
):
    messages = [user_message_with_tool_results]
    result = format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[ToolResult: tool-1]" in result
    assert "[ToolResult: tool-2]" in result
    assert "def hello():" in result


def testformat_for_inspection_tool_results_content_excluded_when_max_length_zero(
    user_message_with_tool_results: UserMessage,
):
    messages = [user_message_with_tool_results]
    result = format_for_inspection(messages, "sess-abc", "MyProject", max_tool_result_length=0)

    assert "[ToolResult: tool-1]" in result
    assert "[ToolResult: tool-2]" in result
    assert "def hello()" not in result


def testformat_for_inspection_tool_result_truncation():
    long_content = "x" * 500
    msg = UserMessage(
        uuid="u-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Check this",
        tool_results=[
            {
                "type": "tool_result",
                "tool_use_id": "t1",
                "content": long_content,
            }
        ],
        is_sidechain=False,
        cwd="/home",
        git_branch="main",
        session_id="sess-abc",
    )
    result = format_for_inspection([msg], "sess-abc", "MyProject", max_tool_result_length=100)

    assert "[ToolResult: t1]" in result
    assert "... (truncated)" in result
    assert long_content not in result


# ---------------------------------------------------------------------------
# format_for_inspection — Message Separation
# ---------------------------------------------------------------------------


def testformat_for_inspection_message_separation(
    user_message_1: UserMessage, assistant_message_1: AssistantMessage
):
    messages = [user_message_1, assistant_message_1]
    result = format_for_inspection(messages, "sess-abc", "MyProject")
    lines = result.split("\n")

    user_idx = next(i for i, line in enumerate(lines) if "[USER]" in line)
    asst_idx = next(i for i, line in enumerate(lines) if "[ASSISTANT]" in line)

    assert asst_idx > user_idx
    assert lines[user_idx + 2] == ""


# ---------------------------------------------------------------------------
# format_for_inspection — Empty Messages
# ---------------------------------------------------------------------------


def testformat_for_inspection_empty_messages():
    result = format_for_inspection([], "sess-abc", "MyProject")
    assert "No messages." in result
    assert "=== Session: sess-abc ===" in result


# ---------------------------------------------------------------------------
# format_for_inspection — Edge Cases
# ---------------------------------------------------------------------------


def testformat_for_inspection_timezone_naive():
    msg = UserMessage(
        uuid="u-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0),
        text="Hello",
        tool_results=[],
        is_sidechain=False,
        cwd="/home",
        git_branch="main",
        session_id="sess-abc",
    )
    result = format_for_inspection([msg], "sess-abc", "MyProject")

    assert "2024-06-01 10:00:00" in result


def testformat_for_inspection_assistant_no_tool_calls():
    msg = AssistantMessage(
        uuid="a-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Just text",
        tool_calls=[],
        model="claude-3-haiku",
        is_sidechain=False,
    )
    result = format_for_inspection([msg], "sess-abc", "MyProject")

    assert "Just text" in result
    assert "[Tool:" not in result


def testformat_for_inspection_assistant_empty_tool_input():
    msg = AssistantMessage(
        uuid="a-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Calling tool",
        tool_calls=[{"id": "t1", "name": "Wait", "input": {}}],
        model="claude-3-haiku",
        is_sidechain=False,
    )
    result = format_for_inspection([msg], "sess-abc", "MyProject")

    assert "[Tool: Wait() | id=t1]" in result


# ---------------------------------------------------------------------------
# format_for_inspection — No Limiting
# ---------------------------------------------------------------------------


def test_format_for_inspection_no_limiting():
    messages = [
        UserMessage(
            uuid="u-001",
            timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
            text="Message 1",
            tool_results=[],
            is_sidechain=False,
            cwd="/home",
            git_branch="main",
            session_id="sess-abc",
        ),
        UserMessage(
            uuid="u-002",
            timestamp=datetime(2024, 6, 1, 10, 0, 1, tzinfo=timezone.utc),
            text="Message 2",
            tool_results=[],
            is_sidechain=False,
            cwd="/home",
            git_branch="main",
            session_id="sess-abc",
        ),
    ]
    result = format_for_inspection(messages, "sess-abc", "MyProject")

    assert "Message 1" in result
    assert "Message 2" in result


