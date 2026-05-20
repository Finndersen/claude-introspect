# claude-session-inspector — Development Guide

See `README.md` for installation, MCP tool reference, and sub-agent usage.

## Project layout

```
src/claude_session_inspector/
  server.py       — MCP server entry point; registers all tools
  sessions.py     — session discovery and parsing
  search.py       — ripgrep-backed full-text search
  formatting.py   — conversation transcript formatter
agents/
  session-inspector.md  — sub-agent definition (bundled with the plugin)
.claude-plugin/
  plugin.json     — plugin metadata, including version
  marketplace.json — self-hosted marketplace entry
pyproject.toml    — package metadata, including version
```

## Setup

```sh
make install   # install dev dependencies and activate pre-commit hook
make test      # run tests
make lint      # ruff check + format check
```

## Version bumping

The version lives in two files that must stay in sync: `pyproject.toml` and `.claude-plugin/plugin.json`.

**Bump the version whenever you make functional changes** to the MCP server (`src/`) or the sub-agent definition (`agents/`). Non-functional changes (docs, tests, comments) don't require a bump.

```sh
uv run python bump_version.py          # patch bump (default)
uv run python bump_version.py minor
uv run python bump_version.py major
```

Stage `pyproject.toml` and `.claude-plugin/plugin.json` together with your functional changes in the same commit. The pre-commit hook will block commits that touch `src/` or `agents/` without also staging the version files. Override with `git commit --no-verify` if genuinely not needed.
