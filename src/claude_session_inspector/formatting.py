"""Formatting and output rendering for session data."""

from datetime import datetime

from claude_session_inspector.sessions import AssistantMessage, SessionMessage, UserMessage


# ── Helpers for view_session_messages ─────────────────────────────────────


def _format_timestamp_iso(dt: datetime | None) -> str:
    """Format datetime as ISO 8601 string, or 'unknown' if None."""
    if dt is None:
        return "unknown"
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def _truncate_text(text: str, max_len: int) -> str:
    """Truncate text to max_len characters, adding '...' if truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _condense_tool_call(tool_call: dict) -> str:
    """Condense a tool call to [Tool: name(key="value")] format."""
    name = tool_call.get("name", "unknown")
    input_dict = tool_call.get("input", {})

    if not input_dict:
        return f"[Tool: {name}()]"

    # Show first 1-2 key=value pairs, truncating values to 80 chars
    params = list(input_dict.items())[:2]
    param_str = ", ".join(f'{k}="{_truncate_text(str(v), 80)}"' for k, v in params)
    return f"[Tool: {name}({param_str})]"


# ── Helpers for inspection format ─────────────────────────────────────────


def _format_timestamp(ts: datetime) -> str:
    """Format a datetime for display, handling timezone-naive datetimes."""
    if ts.tzinfo is None:
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return ts.strftime("%Y-%m-%d %H:%M:%S %Z")


def _clip_string(s: str, max_len: int) -> str:
    """Hard-truncate a string to max_len characters with no suffix."""
    if len(s) <= max_len:
        return s
    return s[:max_len]


def _extract_tool_result_text(content: str | list) -> str | None:
    """Extract plain text from tool result content (string or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return " ".join(parts) if parts else None
    return None


def _format_tool_call(tool_call: dict) -> str:
    """Format a single tool call as [Tool: name(param=value)]."""
    name = tool_call.get("name", "unknown")
    input_data = tool_call.get("input", {})

    if not input_data or not isinstance(input_data, dict):
        return f"[Tool: {name}()]"

    first_key = next(iter(input_data.keys()))
    first_value = input_data[first_key]
    value_str = _clip_string(str(first_value), 80)

    return f"[Tool: {name}({first_key}={value_str})]"


# ── format_conversation — used by view_session_messages ───────────────────


def format_conversation(
    messages: list[SessionMessage],
    session_id: str,
    project_name: str,
    git_branch: str | None,
    max_messages: int = 50,
    include_tool_results: bool = False,
    user_only: bool = False,
) -> str:
    """Format a conversation as a readable transcript.

    Args:
        messages: List of SessionMessage (UserMessage or AssistantMessage)
        session_id: Session UUID
        project_name: Project name
        git_branch: Git branch (or None)
        max_messages: Max messages to include (default 50) — applied after filtering
        include_tool_results: Include tool result content in output (default False)
        user_only: Only show user messages (default False)

    Returns:
        Formatted conversation string
    """
    # Apply user_only filter first
    if user_only:
        filtered = [msg for msg in messages if isinstance(msg, UserMessage)]
    else:
        filtered = list(messages)

    # Apply max_messages limit (take most recent N)
    if len(filtered) > max_messages:
        filtered = filtered[-max_messages:]

    if not filtered:
        return f"""Session: {session_id}
Project: {project_name}
Branch: {git_branch or "unknown"}

No messages to display."""

    # Calculate timestamp range
    first_ts = _format_timestamp_iso(filtered[0].timestamp)
    last_ts = _format_timestamp_iso(filtered[-1].timestamp)

    # Build header
    header = f"""Session: {session_id}
Project: {project_name}
Branch: {git_branch or "unknown"}
Time range: {first_ts} to {last_ts}
Message count: {len(filtered)}

{'─' * 78}
"""

    # Format each message
    formatted_msgs = []
    for msg in filtered:
        if isinstance(msg, UserMessage):
            timestamp = _format_timestamp_iso(msg.timestamp)
            block = f"[USER] ({timestamp})\n{msg.text}"

            # Include tool results if requested
            if include_tool_results and msg.tool_results:
                results = []
                for result in msg.tool_results:
                    result_text = result.get("content", "")
                    if isinstance(result_text, str):
                        truncated = _truncate_text(result_text, 200)
                    else:
                        truncated = _truncate_text(str(result_text), 200)
                    results.append(truncated)
                if results:
                    block += "\n\nTool Results:\n" + "\n".join(results)

            formatted_msgs.append(block)

        elif isinstance(msg, AssistantMessage):
            timestamp = _format_timestamp_iso(msg.timestamp)
            block = f"[ASSISTANT] ({timestamp})\n{msg.text}"

            # Condense tool calls
            if msg.tool_calls:
                condensed = ", ".join(_condense_tool_call(tc) for tc in msg.tool_calls)
                block += f"\n\n{condensed}"

            formatted_msgs.append(block)

    separator = "\n" + "─" * 78 + "\n"
    return header + separator.join(formatted_msgs) + "\n" + "─" * 78


def format_single_message(
    message: SessionMessage,
    session_id: str,
    project_name: str,
    mode: str,
) -> str:
    """Format a single message for single-message modes.

    Args:
        message: A UserMessage or AssistantMessage
        session_id: Session UUID
        project_name: Project name
        mode: The viewing mode ('first_prompt', 'recent_prompt', 'latest_response', etc.)

    Returns:
        Formatted single message string
    """
    timestamp = _format_timestamp_iso(message.timestamp)

    if isinstance(message, UserMessage):
        role_tag = "[USER]"
        content = message.text
    else:  # AssistantMessage
        role_tag = "[ASSISTANT]"
        content = message.text

    return f"""Session: {session_id}
Project: {project_name}
Mode: {mode}

{'─' * 38}
{role_tag} ({timestamp})
{content}
{'─' * 38}"""


# ── Inspection format — used by format_conversation_for_inspection ─────────


def _format_for_inspection(
    messages: list[SessionMessage],
    session_id: str,
    project_name: str,
    include_tool_results: bool = False,
    max_tool_result_length: int = 200,
    total_messages: int | None = None,
) -> str:
    """Format a conversation in the token-efficient inspection format.

    Uses === headers, human-readable timestamps, and per-line tool calls.
    """
    if not messages:
        return f"=== Session: {session_id} ===\nProject: {project_name}\n\n---\nNo messages."

    first_user_msg = next(
        (msg for msg in messages if isinstance(msg, UserMessage)), None
    )
    git_branch = first_user_msg.git_branch if first_user_msg else None

    first_timestamp = _format_timestamp(messages[0].timestamp)
    last_timestamp = _format_timestamp(messages[-1].timestamp)

    displayed = len(messages)
    total = total_messages if total_messages is not None else displayed
    messages_label = (
        f"Messages: {displayed} (of {total})" if total > displayed else f"Messages: {displayed}"
    )

    lines = [
        f"=== Session: {session_id} ===",
        f"Project: {project_name}",
    ]

    if git_branch:
        lines.append(f"Branch: {git_branch}")

    lines.extend(
        [
            f"Period: {first_timestamp} → {last_timestamp}",
            messages_label,
            "",
            "---",
        ]
    )

    for msg in messages:
        if isinstance(msg, UserMessage):
            timestamp_str = _format_timestamp(msg.timestamp)
            lines.append(f"[USER] ({timestamp_str})")
            lines.append(msg.text)

            if include_tool_results and msg.tool_results:
                for result in msg.tool_results:
                    text = _extract_tool_result_text(result.get("content", ""))
                    if text is not None:
                        truncated = _clip_string(text, max_tool_result_length)
                        if len(text) > max_tool_result_length:
                            truncated += " ... (truncated)"
                        lines.append(f"[ToolResult] {truncated}")

            lines.append("")

        elif isinstance(msg, AssistantMessage):
            timestamp_str = _format_timestamp(msg.timestamp)
            lines.append(f"[ASSISTANT] ({timestamp_str})")
            lines.append(msg.text)

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    lines.append(_format_tool_call(tool_call))

            lines.append("")

    return "\n".join(lines)


def format_conversation_for_inspection(
    messages: list[SessionMessage],
    session_id: str,
    project_name: str,
    max_messages: int = 100,
) -> str:
    """Format a conversation for inspection, with optional message limiting.

    Args:
        messages: List of messages to format.
        session_id: Session identifier.
        project_name: Friendly project name.
        max_messages: Maximum number of recent messages to include.

    Returns:
        Formatted conversation string, optionally with a note about truncation.
    """
    total = len(messages)

    if total > max_messages:
        messages_to_format = messages[-max_messages:]
        result = _format_for_inspection(
            messages_to_format,
            session_id,
            project_name,
            include_tool_results=False,
            total_messages=total,
        )
        note = f"[Note: Showing last {max_messages} of {total} messages]\n\n"
        return note + result
    else:
        return _format_for_inspection(
            messages,
            session_id,
            project_name,
            include_tool_results=False,
        )
