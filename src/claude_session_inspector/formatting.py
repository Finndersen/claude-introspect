"""Formatting and output rendering for session data."""

from datetime import datetime

from claude_session_inspector.sessions import AssistantMessage, SessionMessage, UserMessage


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


def _condense_tool_call(tool_call: dict, tool_content_length: int = 200) -> str:
    name = tool_call.get("name", "unknown")
    tool_id = tool_call.get("id", "")
    input_dict = tool_call.get("input", {})

    if not input_dict or tool_content_length == 0:
        params = ""
    else:
        pairs = list(input_dict.items())[:2]
        params = ", ".join(f'{k}="{_truncate_text(str(v), tool_content_length)}"' for k, v in pairs)

    id_part = f" | id={tool_id}" if tool_id else ""
    return f"[Tool: {name}({params}){id_part}]"


def format_conversation(
    messages: list[SessionMessage],
    session_id: str,
    project_name: str,
    git_branch: str | None,
    start_index: int | None = None,
    end_index: int | None = None,
    tool_content_length: int = 200,
) -> str:
    total = len(messages)
    sliced = messages[start_index:end_index]

    if not sliced:
        return f"""Session: {session_id}
Project: {project_name}
Branch: {git_branch or "unknown"}

No messages to display."""

    first_ts = _format_timestamp_iso(sliced[0].timestamp)
    last_ts = _format_timestamp_iso(sliced[-1].timestamp)

    slice_note = ""
    if start_index is not None or end_index is not None:
        actual_start = (
            0
            if start_index is None
            else (
                max(0, total + start_index)
                if start_index < 0
                else min(start_index, total)
            )
        )
        actual_end = (
            total
            if end_index is None
            else (
                max(0, total + end_index)
                if end_index < 0
                else min(end_index, total)
            )
        )
        slice_note = f"\n[Note: Showing messages {actual_start}–{actual_end} of {total}]"

    header = f"""Session: {session_id}
Project: {project_name}
Branch: {git_branch or "unknown"}
Time range: {first_ts} to {last_ts}
Message count: {len(sliced)}{slice_note}

"""

    formatted_msgs = []
    for msg in sliced:
        if isinstance(msg, UserMessage):
            timestamp = _format_timestamp_iso(msg.timestamp)
            body_parts = []
            if msg.text:
                body_parts.append(msg.text)
            for result in msg.tool_results:
                tool_use_id = result.get("tool_use_id", "")
                status = "error" if result.get("is_error", False) else "ok"
                content_part = ""
                if tool_content_length > 0:
                    result_text = result.get("content", "")
                    if not isinstance(result_text, str):
                        result_text = str(result_text)
                    content_part = f" {_truncate_text(result_text, tool_content_length)}"
                body_parts.append(f"[ToolResult: {tool_use_id} | {status}]{content_part}")
            block = f"[USER] ({timestamp})\n" + "\n".join(body_parts)
            formatted_msgs.append(block)

        elif isinstance(msg, AssistantMessage):
            timestamp = _format_timestamp_iso(msg.timestamp)
            body_parts = []
            if msg.text:
                body_parts.append(msg.text)
            if msg.tool_calls:
                condensed = ", ".join(_condense_tool_call(tc, tool_content_length) for tc in msg.tool_calls)
                body_parts.append(condensed)
            block = f"[ASSISTANT] ({timestamp})\n" + "\n\n".join(body_parts)
            formatted_msgs.append(block)

    return header + "\n\n".join(formatted_msgs)
