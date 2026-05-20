#!/usr/bin/env python3
"""Bump the version in pyproject.toml and .claude-plugin/plugin.json in sync."""

import json
import re
import sys
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
PLUGIN_JSON = Path(".claude-plugin/plugin.json")


def read_version() -> str:
    text = PYPROJECT.read_text()
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    if not match:
        sys.exit("Could not find version in pyproject.toml")
    return match.group(1)


def bump(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    sys.exit(f"Unknown part: {part!r} — use major, minor, or patch")


def set_version(new_version: str) -> None:
    # pyproject.toml
    text = PYPROJECT.read_text()
    text = re.sub(r'^(version = ")[^"]+(")', rf'\g<1>{new_version}\2', text, flags=re.MULTILINE)
    PYPROJECT.write_text(text)

    # plugin.json
    data = json.loads(PLUGIN_JSON.read_text())
    data["version"] = new_version
    PLUGIN_JSON.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    current = read_version()
    new = bump(current, part)
    set_version(new)
    print(f"{current} → {new}")


if __name__ == "__main__":
    main()
