"""MCP server for Claude Session Inspector."""

from datetime import datetime, timezone
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from claude_session_inspector.formatting import format_conversation
from claude_session_inspector.inspection import inspect_session as inspect_session_impl
from claude_session_inspector.search import SearchMatch, search_sessions as _search_sessions_impl
from claude_session_inspector.sessions import (
    SessionInfo,
    UserMessage,
    discover_sessions,
    find_session_file,
    load_session,
    resolve_project_name,
)

mcp = FastMCP(
    "claude-session-inspector",
    instructions=(
        "Use these tools to see the user's work history across Claude Code projects, "
        "retrieve context from prior sessions, or answer questions about past Claude Code conversations. "
        "list_sessions discovers recent activity across all projects. "
        "search_sessions finds sessions by keyword or topic. "
        "view_session_messages reads the raw transcript of a session. "
        "inspect_session uses AI to summarise or answer a specific question about a session."
    ),
)


def _format_timestamp(dt: datetime | None) -> str:
    """Format a datetime for display, or return 'unknown' if None."""
    if dt is None:
        return "unknown"
    # Format as: 2026-05-16 10:30 UTC
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _format_sessions_table(sessions: list[SessionInfo]) -> str:
    """Format a list of sessions as a pipe-separated table."""
    header = "session_id | project | branch | last_active | started | size_kb | first_prompt"
    rows = [header]
    for s in sessions:
        branch = s.git_branch or "unknown"
        last_active = _format_timestamp(s.last_timestamp)
        started = _format_timestamp(s.first_timestamp)
        size_kb = round(s.file_size_bytes / 1024, 1)
        prompt = (s.first_prompt or "").replace("|", " ").replace("\n", " ").strip()
        if len(prompt) > 300:
            prompt = prompt[:300] + "..."
        rows.append(
            f"{s.session_id} | {s.project_name} | {branch} | {last_active} | {started}"
            f" | {size_kb} | {prompt}"
        )
    return "\n".join(rows)


def _format_search_result(match: SearchMatch) -> str:
    """Format a single search match as a block."""
    first_prompt = match.first_prompt if match.first_prompt else "(empty)"
    result = f"""Session: {match.session_id}
Project: {match.project_name}
Matches: {match.match_count}
First prompt: {first_prompt}"""
    if match.snippets:
        snippets_text = "\n".join(f"  > {s}" for s in match.snippets)
        result += f"\n\nMatching snippets:\n{snippets_text}"
    return result


@mcp.tool()
def list_sessions(
    project: Annotated[
        str | None,
        Field(description="Project name filter (case-insensitive substring match)."),
    ] = None,
    max_results: Annotated[
        int,
        Field(
            description=(
                "Maximum sessions to return (default: 20). If the limit is reached there "
                "may be more — narrow with project= or use search_sessions to find sessions "
                "matching a specific topic."
            )
        ),
    ] = 20,
) -> str:
    """Browse recent Claude Code sessions sorted by last activity.

    Use this whenever you need to discover what the user has been working on or survey recent
    Claude agent activity across projects. Returns a table of sessions with metadata including
    project, branch, timestamps, file size, and the opening prompt.

    To search session *content* for a specific keyword, function name, or error message, use
    the search_sessions tool instead.
    """
    sessions, total = discover_sessions(project_filter=project, limit=max_results)

    if not sessions:
        if project:
            return f"No sessions found matching '{project}'."
        return "No sessions found."

    header = f"Showing {len(sessions)} of {total} sessions (most recent first):\n"
    table = _format_sessions_table(sessions)

    suffix = ""
    if total > max_results:
        suffix = (
            f"\n\n[Results truncated at {max_results}. Use the project= filter to narrow by "
            f"project name, or use search_sessions to find sessions matching a specific topic.]"
        )

    return header + table + suffix


@mcp.tool()
def search_sessions(
    query: Annotated[
        str,
        Field(
            description=(
                "String or pattern to search for across all session content. Use concrete "
                "identifiers likely to appear verbatim — e.g. 'AuthMiddleware', 'migration 0042', "
                "'TypeError: cannot read'. Treated as a fixed string by default (safe for natural "
                "language, function names, error messages). Set use_regex=True for patterns."
            )
        ),
    ],
    project: Annotated[
        str | None,
        Field(description="Project name filter (case-insensitive substring match)."),
    ] = None,
    max_results: Annotated[
        int,
        Field(description="Maximum matching sessions to return (default: 20)."),
    ] = 20,
    use_regex: Annotated[
        bool,
        Field(
            description=(
                "If False (default), treat query as a fixed string. If True, enable Rust regex "
                "syntax for patterns like `initializ(e|ation)` or case-insensitive flags (`(?i)search`)."
            )
        ),
    ] = False,
) -> str:
    """Search Claude Code session content for a specific string or pattern using ripgrep.

    Use this to answer "have I worked on X before?" or to retrieve context from a prior session
    before continuing related work. Returns matching sessions with snippets showing where the
    query was found. Use list_sessions instead when you just want to browse recent activity
    without a specific keyword in mind.
    """
    try:
        matches = _search_sessions_impl(
            query, project=project, max_results=max_results, use_regex=use_regex
        )
    except RuntimeError as err:
        return str(err)

    if not matches:
        return f'No matches found for "{query}".'

    count = len(matches)
    count_text = "session" if count == 1 else "sessions"
    header = f'Found "{query}" in {count} {count_text}:\n'

    blocks = [_format_search_result(m) for m in matches]
    separator = "\n" + "─" * 34 + "\n"

    return header + separator + separator.join(blocks) + "\n" + "─" * 34


_VALID_MESSAGE_TYPES = {"user", "assistant", "tool_calls", "tool_results"}


@mcp.tool()
def view_session_messages(
    session_id: Annotated[str, Field(description="Session UUID (from list_sessions).")],
    start_index: Annotated[
        int | None,
        Field(
            description=(
                "Start of message slice (0-based, negative ok: -1 = last message). "
                "None = from beginning."
            )
        ),
    ] = None,
    end_index: Annotated[
        int | None,
        Field(
            description="End of message slice (exclusive, negative ok). None = to end.",
        ),
    ] = None,
    message_type: Annotated[
        list[str] | None,
        Field(
            description=(
                "Filter messages before slicing. Allowed values: 'user', 'assistant', "
                "'tool_calls' (assistant messages with tool calls), "
                "'tool_results' (user messages with tool results). "
                "Multiple values = OR. None = no filter."
            )
        ),
    ] = None,
    max_tool_result_length: Annotated[
        int,
        Field(
            description=(
                "Max characters of tool result content to include per result (default: 200). "
                "Set to 0 to omit content entirely — tool call indicators are always shown."
            )
        ),
    ] = 200,
) -> str:
    """Read the conversation messages from a specific Claude Code session.

    Use this to retrieve the actual content of a session once you have its ID (from
    list_sessions). Supports Python-style index slicing (negative indices ok) and filtering
    by message type. For example, start_index=-3 to get the last 3 messages, or
    message_type=['user'] to see only user messages. Prefer inspect_session when you want
    an AI summary rather than the raw transcript.
    """
    if message_type is not None:
        invalid = [t for t in message_type if t not in _VALID_MESSAGE_TYPES]
        if invalid:
            valid_list = ", ".join(sorted(_VALID_MESSAGE_TYPES))
            return (
                f"Error: Invalid message_type value(s): {', '.join(repr(t) for t in invalid)}. "
                f"Valid values: {valid_list}"
            )

    session_file = find_session_file(session_id)
    if session_file is None:
        return f"Error: Session '{session_id}' not found."

    try:
        messages = load_session(session_file)
    except OSError as err:
        return f"Error: Could not read session '{session_id}': {err}"

    if not messages:
        return f"Session '{session_id}' has no messages."

    project_name = resolve_project_name(session_file.parent.name)

    git_branch: str | None = None
    for msg in messages:
        if isinstance(msg, UserMessage) and msg.git_branch:
            git_branch = msg.git_branch
            break

    return format_conversation(
        messages,
        session_id,
        project_name,
        git_branch,
        start_index=start_index,
        end_index=end_index,
        message_type=message_type,
        max_tool_result_length=max_tool_result_length,
    )


@mcp.tool()
async def inspect_session(
    session_id: Annotated[str, Field(description="Session UUID (from list_sessions).")],
    question: Annotated[
        str | None,
        Field(
            description=(
                "Question to ask about the session. If omitted, returns a comprehensive summary "
                "covering topics discussed, decisions made, problems solved, and current status."
            )
        ),
    ] = None,
) -> str:
    """Ask a natural-language question about a Claude Code session, or get an AI summary.

    Use this when you want a synthesised answer about a session rather than reading the raw
    transcript yourself — for example, "what was decided about the auth approach?", "what
    files were changed?", "what is the current status of this work?", or just omit the question
    to get a comprehensive summary. Internally sends the session to Claude Haiku for analysis,
    so it handles long sessions well and returns a focused answer. Prefer view_session_messages
    if you need the verbatim conversation content; prefer this tool when you need a quick
    understanding of what happened or want to extract a specific piece of information efficiently.

    Requires the claude CLI to be installed and authenticated.
    """
    return await inspect_session_impl(session_id, question)


def main() -> None:
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
