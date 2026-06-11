"""Search and filtering across sessions."""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from claude_session_inspector.sessions import (
    _normalize_path_filter,
    get_session_metadata,
    get_sessions_dir,
)


# JSONL attachment/content types that are infrastructure noise, not conversation content.
# deferred_tools_delta: tool availability announcements injected as system attachments.
# tool_reference: tool schema references in tool_result content blocks.
_EXCLUDED_LINE_PATTERNS: tuple[str, ...] = (
    '"deferred_tools_delta"',
    '"tool_reference"',
)

_SNIPPET_CONTEXT = 80  # characters to show on each side of a match


def _windowed_snippet(line: str, match_start: int) -> str:
    """Extract text centred around match_start rather than from the line beginning.

    JSONL lines are full JSON objects — the matched term is often buried hundreds of
    characters in. Slicing from the start would never show it.
    """
    start = max(0, match_start - _SNIPPET_CONTEXT)
    end = min(len(line), match_start + _SNIPPET_CONTEXT)
    snippet = line[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(line):
        snippet = snippet + "…"
    return snippet


@dataclass
class SearchMatch:
    """A session matching a search query."""

    session_id: str
    working_dir: str | None
    match_count: int
    snippets: list[str]
    first_prompt: str
    session_summary: str | None = None
    git_branch: str | None = None
    last_active: datetime | None = None
    started: datetime | None = None
    last_assistant_snippet: str | None = None


def search_sessions(
    query: str,
    project: str | None = None,
    max_results: int = 10,
    use_regex: bool = False,
) -> list[SearchMatch]:
    """Search across Claude Code sessions for a text string using ripgrep.

    Args:
        query: Search string to find across sessions.
        project: Optional working directory filter (case-insensitive substring match).
        max_results: Maximum number of matching sessions to return.
        use_regex: If False (default), use fixed-string matching (--fixed-strings flag).
                   If True, enable Rust regex syntax (omits --fixed-strings).

    Returns:
        List of SearchMatch objects sorted by match count descending, limited to max_results.

    Raises:
        RuntimeError: If ripgrep is not installed or other search errors occur.
    """
    sessions_dir = get_sessions_dir()

    if not sessions_dir.exists():
        return []

    try:
        normalized = _normalize_path_filter(project) if project else None
        # Use */*.jsonl (one level deep) to match session files but not subagent files
        # nested at project_dir/session_id/subagents/*.jsonl. Running rg with cwd=sessions_dir
        # and "." as the search path makes ripgrep apply the glob against relative paths
        # (e.g. "project_dir/session.jsonl"), which * can match across — unlike absolute paths
        # where * never crosses a path separator.
        glob_pattern = f"*{normalized}*/*.jsonl" if normalized else "*/*.jsonl"
        cmd = ["rg", "--json"]
        if not use_regex:
            cmd.append("--fixed-strings")
        cmd += [
            "--iglob",
            glob_pattern,
            query,
            ".",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(sessions_dir),
        )
    except FileNotFoundError as err:
        raise RuntimeError("ripgrep (rg) is not installed. Please install ripgrep to use search_sessions.") from err

    if result.returncode not in (0, 1):
        raise RuntimeError(f"ripgrep error: {result.stderr}")

    if result.returncode == 1:
        return []

    matches_by_file: dict[str, list[str]] = {}

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("type") != "match":
            continue

        file_path = entry.get("data", {}).get("path", {}).get("text", "")
        match_text = entry.get("data", {}).get("lines", {}).get("text", "")

        if not file_path or not match_text:
            continue

        if any(p in match_text for p in _EXCLUDED_LINE_PATTERNS):
            continue

        submatches = entry.get("data", {}).get("submatches", [])
        match_start = submatches[0].get("start", 0) if submatches else 0

        if file_path not in matches_by_file:
            matches_by_file[file_path] = []

        matches_by_file[file_path].append(_windowed_snippet(match_text, match_start))

    # Sort by match count descending and slice before opening any files.
    ranked = sorted(matches_by_file.items(), key=lambda item: len(item[1]), reverse=True)
    top_candidates = ranked[:max_results]

    search_results: list[SearchMatch] = []

    for file_path_str, snippets in top_candidates:
        file_path = Path(file_path_str)
        if not file_path.is_absolute():
            file_path = sessions_dir / file_path

        if not file_path.exists():
            continue

        session_id = file_path.stem
        project_dir = file_path.parent.name

        metadata = get_session_metadata(file_path, project_dir)
        if metadata is None:
            continue

        truncated_snippets = snippets[:3]

        search_results.append(
            SearchMatch(
                session_id=session_id,
                working_dir=metadata.cwd,
                match_count=len(snippets),
                snippets=truncated_snippets,
                first_prompt=metadata.first_prompt,
                session_summary=metadata.session_summary,
                git_branch=metadata.git_branch,
                last_active=metadata.last_timestamp,
                started=metadata.first_timestamp,
                last_assistant_snippet=metadata.last_assistant_snippet,
            )
        )

    return search_results
