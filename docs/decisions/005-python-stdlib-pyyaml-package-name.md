# ADR-005 — Python, stdlib + PyYAML, package named `swfactory`

**Status:** accepted · 2026-10-04

**Decision.** CLI in Python ≥ 3.12 (the user's stack; uv-managed), argparse, PyYAML as the only dependency.
Import package is `swfactory`, command is `factory`. A package named `factory` would collide with
`factory_boy` in any project that uses it.

**Consequences.** + No framework upgrades to chase; `verify.py` can ship standalone. − argparse is
verbose; acceptable for ~13 commands. Adding a dependency requires a new ADR.
