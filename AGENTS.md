# Working on the factory

Read `docs/ARCHITECTURE.md` first — it is the contract. If your change disagrees with it, change the
document in the same commit, deliberately.

## Commands

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run factory lint        # validates skills + kit manifest
```

On this Windows machine Application Control blocks `pytest.exe`; use `uv run python -m pytest -q`.

## Rules

* Python ≥ 3.12, stdlib + PyYAML only. No new dependency without an ADR.
* The package is `swfactory`, never `factory` (collides with factory_boy).
* Skills must be executable by an agent with only git + file access; the CLI is optional.
* `verify.py` must stay standalone (stdlib + PyYAML) — it is copied into projects.
* Write files with `\n` newlines; tests must pass on Windows and Linux.
* Scope check before adding anything: "has a real project needed this yet?" If not, put it in
  `docs/ROADMAP.md` instead.
* Never commit machine paths (`registry/local.yaml` is gitignored) or secrets.
