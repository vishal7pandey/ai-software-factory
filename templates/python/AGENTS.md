# {{name}}

## Commands

```bash
uv sync                        # install deps
uv run pytest -q               # tests
uv run ruff check .            # lint
uv run ruff format --check .   # format check (use `uv run ruff format .` to fix)
uv run python -m {{package}}.main
```

## Conventions

* Python 3.12+, `src/{{package}}/` layout, tests in `tests/` named `test_*.py`.
* Type-hint public functions; keep pure logic separate from I/O so it is unit-testable.
* No new dependency without asking. Dependencies go in `pyproject.toml`; commit `uv.lock`.
* Config from environment variables; document them in `.env.example`. Never commit `.env`.
