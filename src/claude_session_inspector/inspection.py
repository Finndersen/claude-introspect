"""Session inspection via Claude Haiku."""

import asyncio

from claude_session_inspector.formatting import format_conversation_for_inspection
from claude_session_inspector.sessions import (
    find_session_file,
    load_session,
    resolve_project_name,
)

DEFAULT_SUMMARY_QUESTION = (
    "Provide a comprehensive summary of this conversation, including: "
    "the main topics discussed, key decisions made, problems solved, "
    "and the current status/outcome."
)


async def inspect_session(
    session_id: str,
    question: str | None = None,
    max_messages: int = 100,
) -> str:
    """Ask a question about a Claude Code session, or get a summary.

    Loads the session conversation, formats it, and sends it to Claude Haiku for analysis.

    Args:
        session_id: Session UUID to inspect.
        question: Question to ask about the session. If omitted, provides a comprehensive summary.
        max_messages: Maximum messages to include in context (default: 100, takes most recent).

    Returns:
        The LLM response as a string.

    Raises:
        FileNotFoundError: If session not found or claude command not available.
        TimeoutError: If claude command times out.
        RuntimeError: If claude command exits with non-zero status.
    """
    # Find session file
    session_file = find_session_file(session_id)
    if session_file is None:
        raise FileNotFoundError(f"Session not found: {session_id}")

    # Load messages
    messages = load_session(session_file)

    # Get project name from the session file's parent directory name
    project_name = resolve_project_name(session_file.parent.name)

    # Format conversation for inspection
    formatted = format_conversation_for_inspection(
        messages,
        session_id,
        project_name,
        max_messages=max_messages,
    )

    # Build prompt
    question_text = question or DEFAULT_SUMMARY_QUESTION
    prompt = f"""Here is a conversation from a Claude Code session:

<conversation>
{formatted}
</conversation>

{question_text}

Provide a clear, concise answer based only on the conversation content above."""

    # Run claude -p with the prompt via stdin
    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            "--model",
            "claude-haiku-4",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "claude command not found. Make sure it's installed and in PATH."
        ) from e

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(prompt.encode("utf-8")),
            timeout=60,
        )
    except asyncio.TimeoutError as e:
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        raise TimeoutError("claude command timed out after 60 seconds.") from e

    if process.returncode != 0:
        error_msg = (
            stderr.decode("utf-8", errors="replace") if stderr else "(no error output)"
        )
        raise RuntimeError(
            f"claude command failed with exit code {process.returncode}: {error_msg}"
        )

    return stdout.decode("utf-8", errors="replace")
