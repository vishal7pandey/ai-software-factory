# {{name}}

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Test and lint

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

## Run

```bash
uv run python -m {{package}}.main
```

Work is tracked as work items in `docs/work/`; see `AGENTS.md`.
