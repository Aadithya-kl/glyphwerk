# Contributing to Glyphwerk

Thank you for helping improve Glyphwerk!

## Core Rules
1. **Zero Copyrighted Game Data:** Never commit GBA ROMs (`.gba`), saves (`.sav`), savestates (`.ss0`), patch files (`.bps`/`.ips`/`.ups`), or extracted commercial game scripts/text dumps.
2. **Synthetic Tests Only:** Every bug fix or new quality gate must include a deterministic unit test under `tests/` running against small generated binary fixtures (see `tests/conftest.py`).
3. **Profile-Driven Design:** Never hardcode game-specific ROM offsets in `glyphwerk/`. Put structural offsets into a JSON profile under `profiles/` matching `docs/GAME_PROFILE_SCHEMA.md`.
4. **License Compatibility:** Contributions must be compatible with the MIT License. Keep GPL/AGPL binaries (such as `flips`) external via CLI wrappers.

## Local Workflow
```bash
pip install -e ".[dev]"
ruff check glyphwerk tests examples
pytest -v
glyphwerk secret-scan .
```
