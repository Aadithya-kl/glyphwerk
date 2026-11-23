# Glyphwerk (GBA)

**Safety-first localization, version-porting, quality-gate, and deterministic QA-bot toolkit for Game Boy Advance (Gen-3 engine) ROM projects.**

> **Deutsch:** Siehe [README.de.md](README.de.md) für die vollständige deutsche Dokumentation.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](pyproject.toml)

---

## Why Glyphwerk?

Translating large GBA Gen-3 projects (vanilla FireRed/LeafGreen or expanded CFRU-based builds) quickly runs into subtle binary hazards that simple text injectors miss:
- **Accidental pointer retargeting inside LZ77 graphics or map borders** causing silent tile corruption
- **Table-base literals mistaken for text pointers** (`ldr rB, =sTable` + `lsls`/`adds`), breaking entire struct arrays
- **`libc strcpy` stopping on `0x00` (Gen-3 space)** when a translation shifts where the first space appears
- **Unaligned XSE script pointers (`loadpointer`, `msgbox`, `bufferstring`, `trainerbattle`)** missed by 4-byte-aligned scanners
- **Pixel-width box overflows** in 208 px dialog boxes or 230 px Pokédex frames
- **Painful version ports** when upstream releases a new base ROM build

Glyphwerk packages the **codec, profile-driven relocator, version-porting matcher, binary safety gates, LZ77 tile tools, and deterministic mGBA QA-bot router** into one zero-dependency MIT-licensed Python toolkit.

---

## Core Architecture

```
Translation JSON/CSV + Game Profile (profiles/*.json)
          │
          ▼
 ┌──────────────────────┐    ┌──────────────────────────┐
 │ glyphwerk.codec      │───▶│ glyphwerk.gates          │
 │ PCS codec + px width │    │ text_diff, terminology   │
 └──────────┬───────────┘    └──────────────────────────┘
            ▼
 ┌──────────────────────┐    ┌──────────────────────────┐
 │ glyphwerk.rom        │───▶│ glyphwerk.gates (binary) │
 │ in-place-first, pool │    │ gfx_pointers, strcpy,    │
 │ alloc, table_guard,  │    │ rom_header, secret_scan  │
 │ 4B + XSE ptrs, locks │    └──────────────────────────┘
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐    ┌──────────────────────────┐
 │ glyphwerk.porter     │    │ glyphwerk.bot            │
 │ anchor_match,        │    │ Flag-aware BFS router +  │
 │ dex_wrap, tables,    │    │ mGBA explorer.lua        │
 │ external flips BPS   │    └──────────────────────────┘
 └──────────────────────┘
```

## Quickstart (Zero Real ROMs Required)

```bash
pip install -e ".[dev]"

# Run all 10 synthetic unit & integration test suites
pytest -v

# Run the self-contained 64-KB synthetic ROM build + safety-gate demo
python examples/minimal_synthetic_demo/run_demo.py

# Encode/decode Gen-3 PCS strings & measure pixel widths from the CLI
glyphwerk encode "Pokéball-Größe\nZeile 2"
glyphwerk width "Hallo Welt!\nDas passt sauber." --max-px 208
glyphwerk secret-scan .
```

## Key Features
- **Zero-Dependency Gen-3 PCS Codec (`glyphwerk.codec.pcs`)**: Full EN/DE/FR/IT/ES character map, `FC` argument-length awareness, `FD`/`F7`/`F8`/`F9` tokens, `\p` vs `\pk\mn` protection, `[#HHHH]` lossless raw-byte roundtrip.
- **Pixel-Accurate Width Linter & Balanced Wrapper (`glyphwerk.codec.width`, `glyphwerk.porter.dex_wrap`)**: Uses BPRE advance widths + worst-case buffer expansion (`FD xx`), plus optimal balanced N-line wrapping (e.g. `<= 230 px` for Pokédex boxes).
- **In-Place-First Relocator with Graphic & Table Guards (`glyphwerk.rom`)**: Protects preceding `0xFF` terminators (`+2 B`), locks all referenced GBA BIOS `0x10` LZ77 streams (`graphic_lock_ranges`), detects Thumb `ldr`+`lsls`/`adds` table-base literals (`table_guard`), tracks both 4B-aligned and unaligned XSE script pointers, and supports fail-closed pointer lock lists.
- **Hard Binary Quality Gates (`glyphwerk.gates`)**:
  - `gfx_pointers`: zero retargeted pointer-like words inside LZ77 graphic blocks
  - `strcpy_safety`: Thumb `BL strcpy` literal-source scanner catching `0x00` space-length shifts
  - `rom_header`: zero modified pointers referencing `0x08000000..0x080001FF`
  - `text_diff` & `terminology`: control-code parity, `\ll` scroll typos, glued buffers, blocklist enforcement
  - `secret_scan`: prevents committing ROMs, saves, credentials, or local machine paths
- **External BPS Wrapper (`glyphwerk.porter.bps`)**: Calls user-installed `flips` externally without vendoring GPLv3 code.
- **Deterministic Bot Harness (`glyphwerk.bot`)**: Flag-aware BFS world router (`LiveFlags` + fail-closed verified script warps) + BPRE mGBA `explorer.lua`.

## Documentation
- [Architecture (EN)](docs/ARCHITECTURE.md) · [Architektur (DE)](docs/ARCHITECTURE.de.md)
- [Game Profile Schema](docs/GAME_PROFILE_SCHEMA.md)
- [Engineering Lessons Learned (DE/EN)](docs/ERKENNTNISSE.md)
- [Bot Harness Guide](docs/BOT_HARNESS.md)
- [Multi-Agent Review Workflow](docs/MULTI_AGENT_WORKFLOW.md)
- [Legal Notice](LEGAL_NOTICE.md)

## License
MIT — see [LICENSE](LICENSE) and [LEGAL_NOTICE.md](LEGAL_NOTICE.md).
