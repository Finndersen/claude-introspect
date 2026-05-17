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
    name = tool_call.get("name", "unknown")
    tool_id = tool_call.get("id", "")
    input_dict = tool_call.get("input", {})

    if not input_dict:
        params = ""
    else:
        pairs = list(input_dict.items())[:2]
        params = ", ".join(f'{k}="{_truncate_text(str(v), 80)}"' for k, v in pairs)

    id_part = f" | id={tool_id}" if tool_id else ""
    return f"[Tool: {name}({params}){id_part}]"


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
    name = tool_call.get("name", "unknown")
    tool_id = tool_call.get("id", "")
    input_data = tool_call.get("input", {})

    if not input_data or not isinstance(input_data, dict):
        params = ""
    else:
        first_key = next(iter(input_data.keys()))
        value_str = _clip_string(str(input_data[first_key]), 80)
        params = f"{first_key}={value_str}"

    id_part = f" | id={tool_id}" if tool_id else ""
    return f"[Tool: {name}({params}){id_part}]"


# ── format_conversation helpers ────────────────────────────────────────────


def _filter_eligible(
    messages: list[SessionMessage], message_type: list[str] | None
) -> list[SessionMessage]:
    """Return messages that have at least one renderable part given the filter."""
    if message_type is None:
        return list(messages)
    result = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            if "user" in message_type or (
                "tool_results" in message_type and msg.tool_results
            ):
                result.append(msg)
        elif isinstance(msg, AssistantMessage):
            if "assistant" in message_type or (
                "tool_calls" in message_type and msg.tool_calls
            ):
                result.append(msg)
    return result


def _should_render_text(msg: SessionMessage, message_type: list[str] | None) -> bool:
    if message_type is None:
        return True
    if isinstance(msg, UserMessage):
        return "user" in message_type
    if isinstance(msg, AssistantMessage):
        return "assistant" in message_type
    return False


def _should_render_tool_parts(msg: SessionMessage, message_type: list[str] | None) -> bool:
    if message_type is None:
        return True
    if isinstance(msg, UserMessage):
        return "tool_results" in message_type
    if isinstance(msg, AssistantMessage):
        return "tool_calls" in message_type
    return False


# ── format_conversation — used by view_session_messages ───────────────────


def format_conversation(
    messages: list[SessionMessage],
    session_id: str,
    project_name: str,
    git_branch: str | None,
    start_index: int | None = None,
    end_index: int | None = None,
    message_type: list[str] | None = None,
    max_tool_result_length: int = 200,
) -> str:
    # Apply message_type filter, then slice
    filtered = _filter_eligible(messages, message_type)
    total_after_filter = len(filtered)
    sliced = filtered[start_index:end_index]

    if not sliced:
        return f"""Session: {session_id}
Project: {project_name}
Branch: {git_branch or "unknown"}

No messages to display."""

    # Calculate timestamp range
    first_ts = _format_timestamp_iso(sliced[0].timestamp)
    last_ts = _format_timestamp_iso(sliced[-1].timestamp)

    # Build slice note if a slice was explicitly requested
    slice_note = ""
    if start_index is not None or end_index is not None:
        actual_start = (
            0
            if start_index is None
            else (
                max(0, total_after_filter + start_index)
                if start_index < 0
                else min(start_index, total_after_filter)
            )
        )
        actual_end = (
            total_after_filter
            if end_index is None
            else (
                max(0, total_after_filter + end_index)
                if end_index < 0
                else min(end_index, total_after_filter)
            )
        )
        slice_note = f"\n[Note: Showing messages {actual_start}–{actual_end} of {total_after_filter}]"

    header = f"""Session: {session_id}
Project: {project_name}
Branch: {git_branch or "unknown"}
Time range: {first_ts} to {last_ts}
Message count: {len(sliced)}{slice_note}

{'─' * 78}
"""

    # Format each message, respecting render flags
    formatted_msgs = []
    for msg in sliced:
        render_text = _should_render_text(msg, message_type)
        render_tool_parts = _should_render_tool_parts(msg, message_type)

        if isinstance(msg, UserMessage):
            timestamp = _format_timestamp_iso(msg.timestamp)
            body_parts = []
            if render_text:
                body_parts.append(msg.text)
            if render_tool_parts:
                for result in msg.tool_results:
                    tool_use_id = result.get("tool_use_id", "")
                    content_part = ""
                    if max_tool_result_length > 0:
                        result_text = result.get("content", "")
                        if not isinstance(result_text, str):
                            result_text = str(result_text)
                        content_part = f" {_truncate_text(result_text, max_tool_result_length)}"
                    body_parts.append(f"[ToolResult: {tool_use_id}]{content_part}")
            block = f"[USER] ({timestamp})\n" + "\n".join(body_parts)
            formatted_msgs.append(block)

        elif isinstance(msg, AssistantMessage):
            timestamp = _format_timestamp_iso(msg.timestamp)
            body_parts = []
            if render_text:
                body_parts.append(msg.text)
            if render_tool_parts and msg.tool_calls:
                condensed = ", ".join(_condense_tool_call(tc) for tc in msg.tool_calls)
                body_parts.append(condensed)
            block = f"[ASSISTANT] ({timestamp})\n" + "\n\n".join(body_parts)
            formatted_msgs.append(block)

    separator = "\n" + "─" * 78 + "\n"
    return header + separator.join(formatted_msgs) + "\n" + "─" * 78


# ── Inspection format ───────────────────────────────────────────────────────


def format_for_inspection(
    messages: list[SessionMessage],
    session_id: str,
    project_name: str,
    max_tool_result_length: int = 200,
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

    messages_label = f"Messages: {len(messages)}"

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

            for result in msg.tool_results:
                tool_use_id = result.get("tool_use_id", "")
                content_part = ""
                if max_tool_result_length > 0:
                    text = _extract_tool_result_text(result.get("content", ""))
                    if text is not None:
                        truncated = _clip_string(text, max_tool_result_length)
                        if len(text) > max_tool_result_length:
                            truncated += " ... (truncated)"
                        content_part = f" {truncated}"
                lines.append(f"[ToolResult: {tool_use_id}]{content_part}")

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


