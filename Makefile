.PHONY: install test lint

install:
	uv sync --extra dev
	git config core.hooksPath .githooks

test:
	uv run pytest

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
