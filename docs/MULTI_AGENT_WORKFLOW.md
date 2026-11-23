# Multi-Agent & Reviewer Workflow (Generic Template)

Large ROM localization projects benefit from separating **authoring**, **independent binary/text review**, and **release integration** into clear lanes:

## Recommended Role Separation
1. **Builder / Integrator**
   - Owns the base ROM pin, active build scripts, final patch generation, and CI gates.
   - Runs all pre-build (`text_diff`, `terminology`, `width`) and post-build (`gfx_pointers`, `strcpy_safety`, `rom_header`) gates before tagging any candidate.
2. **Translators / Specialists**
   - Work in isolated sandbox/inbox directories with strict read-only access to the base ROM.
   - Deliver self-contained unified diffs + machine-verifiable receipts (SHA-256 hashes, pixel widths, negative controls).
3. **Independent Reviewer (Second Pair of Eyes)**
   - Verifies diffs apply with zero fuzz on a clean checkout, checks terminology consistency, disassembles any custom Thumb hooks, and validates both positive and negative controls.
4. **Release / Hygiene Guard**
   - Runs `glyphwerk secret-scan .` and checks git history before publishing any public tool or documentation repository so zero ROMs, saves, credentials, or local machine paths ever leak.

## Minimal Handoff Contract
Every submitted fix bundle should include:
- Exact input ROM checksums (MD5/SHA-256)
- One clean unified diff per target source file (zero overlapping diffs)
- Positive proof (bug fixed) **and** negative control (adjacent data/behavior untouched)
- Reproducible verification command returning exit code `0`
