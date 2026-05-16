"""Tests for the formatting module."""

from datetime import datetime, timezone

import pytest

from claude_session_inspector.formatting import (
    _format_for_inspection,
    format_conversation,
    format_conversation_for_inspection,
    format_single_message,
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
# Fixtures — for inspection format (_format_for_inspection)
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

    assert '[Tool: Read(file_path="/foo/bar.py")]' in result
    assert '[Tool: Write(file_path="/foo/baz.py", content="x=1")]' in result


# ---------------------------------------------------------------------------
# format_conversation — Filtering and limits
# ---------------------------------------------------------------------------


def test_format_conversation_user_only_filter(user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2):
    """user_only=True should exclude assistant messages."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", user_only=True)

    # Only user messages should be present
    assert "What is Python?" in result
    assert "Can you show me the file?" in result
    # Assistant messages should not be present
    assert "Python is a popular" not in result
    assert "Here is the file" not in result
    # Message count should reflect filtering
    assert "Message count: 2" in result


def test_format_conversation_max_messages_limit(user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2):
    """max_messages should limit to most recent N."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main", max_messages=2)

    # Only the last 2 messages should be present
    assert "Can you show me the file?" in result
    assert "Here is the file" in result
    # First messages should not be present
    assert "What is Python?" not in result
    assert "Python is a popular" not in result
    # Message count should reflect the limit
    assert "Message count: 2" in result


def test_format_conversation_max_messages_after_filter(
    user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2
):
    """max_messages should apply after user_only filtering."""
    messages = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
    # Filter to user_only, then limit to 1 message
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", max_messages=1, user_only=True
    )

    # Only the most recent user message should be present
    assert "Can you show me the file?" in result
    assert "What is Python?" not in result
    assert "Message count: 1" in result


# ---------------------------------------------------------------------------
# format_conversation — Tool results handling
# ---------------------------------------------------------------------------


def test_format_conversation_tool_results_excluded_by_default(user_msg_2):
    """Tool results should be excluded by default."""
    messages = [user_msg_2]
    result = format_conversation(messages, "sess-abc", "MyProject", "main")

    # The message text should be present
    assert "Can you show me the file?" in result
    # But tool results should not be visible
    assert "very long file content" not in result


def test_format_conversation_tool_results_included_when_flag_set(user_msg_2):
    """Tool results should be included when include_tool_results=True."""
    messages = [user_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", include_tool_results=True
    )

    # The message text should be present
    assert "Can you show me the file?" in result
    # Tool results header should be present
    assert "Tool Results:" in result
    # Content should be truncated (max 200 chars)
    assert "This is a very long file content" in result
    # But the full long content should not be present (it exceeds 200 chars)
    assert len(result.split("Tool Results:")[-1]) < 1000  # Should be much shorter


def test_format_conversation_tool_results_truncated_to_200_chars(user_msg_2):
    """Tool results should be truncated to 200 characters."""
    messages = [user_msg_2]
    result = format_conversation(
        messages, "sess-abc", "MyProject", "main", include_tool_results=True
    )

    # Find the tool results section
    parts = result.split("Tool Results:")
    assert len(parts) == 2
    results_part = parts[1]

    # The result should include truncation indicator
    assert "..." in results_part or "et dolore" in results_part

    # Extract just the result text line (should be after "Tool Results:" and before next separator)
    lines = results_part.strip().split("\n")
    result_line = lines[0]
    # Should be around 200 chars (plus ellipsis)
    assert len(result_line) <= 210  # 200 + "..." + some margin


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
# format_single_message
# ---------------------------------------------------------------------------


def test_format_single_message_user_message(user_msg_1):
    """Should format user message correctly."""
    result = format_single_message(user_msg_1, "sess-abc", "MyProject", "recent_prompt")

    assert "Session: sess-abc" in result
    assert "Project: MyProject" in result
    assert "Mode: recent_prompt" in result
    assert "[USER]" in result
    assert "What is Python?" in result
    assert "2024-06-01T10:00:00" in result


def test_format_single_message_assistant_message(assistant_msg_1):
    """Should format assistant message correctly."""
    result = format_single_message(assistant_msg_1, "sess-abc", "MyProject", "latest_response")

    assert "Session: sess-abc" in result
    assert "Project: MyProject" in result
    assert "Mode: latest_response" in result
    assert "[ASSISTANT]" in result
    assert "Python is a popular programming language." in result


def test_format_single_message_output_format(user_msg_1):
    """Output should have correct structure with separators."""
    result = format_single_message(user_msg_1, "sess-abc", "MyProject", "first_prompt")

    # Should have dashes as separators (38 dashes based on spec)
    assert "──────────────────────────────────" in result

    # Should have proper line structure
    lines = result.split("\n")
    assert lines[0] == "Session: sess-abc"
    assert lines[1] == "Project: MyProject"
    assert lines[2] == "Mode: first_prompt"


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

    assert "[Tool: DoSomething()]" in result


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
    result = format_conversation([user_msg], "sess-abc", "MyProject", "main", include_tool_results=True)

    # Should be truncated
    assert "..." in result
    # Should not include the full 500 chars
    assert long_content not in result


# ---------------------------------------------------------------------------
# _format_for_inspection — Header
# ---------------------------------------------------------------------------


def test_format_for_inspection_header_basic(user_message_1: UserMessage):
    messages = [user_message_1]
    result = _format_for_inspection(messages, "sess-abc", "MyProject")

    assert "=== Session: sess-abc ===" in result
    assert "Project: MyProject" in result
    assert "Branch: main" in result
    assert "Messages: 1" in result


def test_format_for_inspection_header_no_branch():
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
    result = _format_for_inspection([msg], "sess-abc", "MyProject")

    assert "=== Session: sess-abc ===" in result
    assert "Project: MyProject" in result
    assert "Branch:" not in result


def test_format_for_inspection_period(
    user_message_1: UserMessage, assistant_message_1: AssistantMessage
):
    messages = [user_message_1, assistant_message_1]
    result = _format_for_inspection(messages, "sess-abc", "MyProject")

    assert "2024-06-01 10:00:00" in result
    assert "2024-06-01 10:00:05" in result
    assert "→" in result


# ---------------------------------------------------------------------------
# _format_for_inspection — User Messages
# ---------------------------------------------------------------------------


def test_format_for_inspection_user_message(user_message_1: UserMessage):
    messages = [user_message_1]
    result = _format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[USER]" in result
    assert "Hello, Claude!" in result
    assert "2024-06-01 10:00:00" in result


# ---------------------------------------------------------------------------
# _format_for_inspection — Assistant Messages
# ---------------------------------------------------------------------------


def test_format_for_inspection_assistant_message(assistant_message_1: AssistantMessage):
    messages = [assistant_message_1]
    result = _format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[ASSISTANT]" in result
    assert "Hello! How can I help?" in result
    assert "2024-06-01 10:00:05" in result


def test_format_for_inspection_tool_calls_condensed(
    assistant_message_1: AssistantMessage,
):
    messages = [assistant_message_1]
    result = _format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[Tool: Read(file_path=/foo/bar.py)]" in result
    assert "[Tool: Bash(command=ls -la /home)]" in result


def test_format_for_inspection_tool_call_truncation():
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
    result = _format_for_inspection([msg], "sess-abc", "MyProject")

    assert "[Tool: Bash(command=" in result
    assert "xxxxxxxx)]" in result
    tool_lines = [line for line in result.split("\n") if "[Tool:" in line]
    assert len(tool_lines) > 0
    assert len(tool_lines[0]) <= 110


# ---------------------------------------------------------------------------
# _format_for_inspection — Tool Results
# ---------------------------------------------------------------------------


def test_format_for_inspection_tool_results_excluded_by_default(
    user_message_with_tool_results: UserMessage,
):
    messages = [user_message_with_tool_results]
    result = _format_for_inspection(messages, "sess-abc", "MyProject")

    assert "[ToolResult]" not in result
    assert "def hello()" not in result


def test_format_for_inspection_tool_results_included_when_enabled(
    user_message_with_tool_results: UserMessage,
):
    messages = [user_message_with_tool_results]
    result = _format_for_inspection(
        messages, "sess-abc", "MyProject", include_tool_results=True
    )

    assert "[ToolResult]" in result
    assert "def hello():" in result


def test_format_for_inspection_tool_result_truncation():
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
    result = _format_for_inspection(
        [msg],
        "sess-abc",
        "MyProject",
        include_tool_results=True,
        max_tool_result_length=100,
    )

    assert "[ToolResult]" in result
    assert "... (truncated)" in result
    assert long_content not in result


# ---------------------------------------------------------------------------
# _format_for_inspection — Message Separation
# ---------------------------------------------------------------------------


def test_format_for_inspection_message_separation(
    user_message_1: UserMessage, assistant_message_1: AssistantMessage
):
    messages = [user_message_1, assistant_message_1]
    result = _format_for_inspection(messages, "sess-abc", "MyProject")
    lines = result.split("\n")

    user_idx = next(i for i, line in enumerate(lines) if "[USER]" in line)
    asst_idx = next(i for i, line in enumerate(lines) if "[ASSISTANT]" in line)

    assert asst_idx > user_idx
    assert lines[user_idx + 2] == ""


# ---------------------------------------------------------------------------
# _format_for_inspection — Empty Messages
# ---------------------------------------------------------------------------


def test_format_for_inspection_empty_messages():
    result = _format_for_inspection([], "sess-abc", "MyProject")
    assert "No messages." in result
    assert "=== Session: sess-abc ===" in result


# ---------------------------------------------------------------------------
# _format_for_inspection — Edge Cases
# ---------------------------------------------------------------------------


def test_format_for_inspection_timezone_naive():
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
    result = _format_for_inspection([msg], "sess-abc", "MyProject")

    assert "2024-06-01 10:00:00" in result


def test_format_for_inspection_assistant_no_tool_calls():
    msg = AssistantMessage(
        uuid="a-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Just text",
        tool_calls=[],
        model="claude-3-haiku",
        is_sidechain=False,
    )
    result = _format_for_inspection([msg], "sess-abc", "MyProject")

    assert "Just text" in result
    assert "[Tool:" not in result


def test_format_for_inspection_assistant_empty_tool_input():
    msg = AssistantMessage(
        uuid="a-001",
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        text="Calling tool",
        tool_calls=[{"id": "t1", "name": "Wait", "input": {}}],
        model="claude-3-haiku",
        is_sidechain=False,
    )
    result = _format_for_inspection([msg], "sess-abc", "MyProject")

    assert "[Tool: Wait()]" in result


# ---------------------------------------------------------------------------
# format_conversation_for_inspection — No Limiting
# ---------------------------------------------------------------------------


def test_format_conversation_for_inspection_no_limiting():
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
    result = format_conversation_for_inspection(
        messages, "sess-abc", "MyProject", max_messages=100
    )

    assert "[Note:" not in result
    assert "Message 1" in result
    assert "Message 2" in result


# ---------------------------------------------------------------------------
# format_conversation_for_inspection — Message Limiting
# ---------------------------------------------------------------------------


def test_format_conversation_for_inspection_limiting():
    messages = [
        UserMessage(
            uuid=f"u-{i:03d}",
            timestamp=datetime(2024, 6, 1, 10, i // 60, i % 60, tzinfo=timezone.utc),
            text=f"Message {i}",
            tool_results=[],
            is_sidechain=False,
            cwd="/home",
            git_branch="main",
            session_id="sess-abc",
        )
        for i in range(150)
    ]
    result = format_conversation_for_inspection(
        messages, "sess-abc", "MyProject", max_messages=50
    )

    assert "[Note: Showing last 50 of 150 messages]" in result
    assert "Message 149" in result
    assert "Message 0" not in result
    assert "Message 99" not in result


# ---------------------------------------------------------------------------
# format_conversation_for_inspection — Tool Results Always Excluded
# ---------------------------------------------------------------------------


def test_format_conversation_for_inspection_tool_results_excluded(
    user_message_with_tool_results: UserMessage,
):
    messages = [user_message_with_tool_results]
    result = format_conversation_for_inspection(messages, "sess-abc", "MyProject")

    assert "[ToolResult]" not in result
