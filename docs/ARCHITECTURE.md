# Glyphwerk Architecture

Glyphwerk enforces a **safety-first, profile-driven localization pipeline** for GBA Gen-3 projects. Every transformation is guarded by explicit binary invariants before and after patching.

## Pipeline Layers

1. **Profile Layer (`glyphwerk.profile`, `profiles/*.json`)**
   Separates all ROM-specific offsets (`rom_base_addr`, `strcpy_addr`, `script_banks`, `reserved_ranges`, `windows`, `wram_bpre`) from generic Python code.

2. **Codec & Width Layer (`glyphwerk.codec`)**
   - `pcs.py`: Lossless Gen-3 Western PCS encoder/decoder with `FC` argument-length awareness, `FD`/`F7`/`F8`/`F9` control tokens, `\p` vs. `\pk\mn` disambiguation, and `[#HHHH]` raw-byte escapes.
   - `width.py`: Measures pixel widths per visual line using BPRE glyph advance tables (`font_widths_bpre.json`) and worst-case buffer expansion (`FD xx`).

3. **ROM Pointer & Relocation Layer (`glyphwerk.rom`)**
   - **In-Place-First:** Fixed-stride tables (items, abilities, species, berries, trainer classes) are patched strictly in-place with an EN-byte guard and `0xFF` padding. Pointers to struct arrays are NEVER retargeted.
   - **Pool Allocator (`PoolAllocator`):** Best-fit allocation over verified `0xFF` runs with a `+2 B` preceding-terminator guard, explicit `reserved_ranges`, and live pointer-chain protection.
   - **Graphic Lock (`graphic_lock_ranges`):** Validates all referenced GBA BIOS Type-`0x10` LZ77 streams so pointer-like words inside compressed tile/palette payloads are never touched.
   - **Table-Base Guard (`table_guard.py`):** Detects Thumb `ldr rB, =L` + scaled index (`lsls`/`muls`/`adds`) so struct-table base literals are never mistaken for single text pointers.
   - **Full Pointer Coverage (`pointers.py`):** Finds both 4-byte-aligned pointers AND unaligned XSE script operands (`loadpointer`, `msgbox`, `bufferstring`, `trainerbattle`), filtered through a fail-closed `PointerBlocklist`.

4. **Version-Porting & Graphics Layer (`glyphwerk.porter`, `glyphwerk.gfx`)**
   - `anchor_match.py`: Maps translations from ROM v1 to ROM v2 using exact PCS matches + surrounding byte context disambiguation (refusing to guess on unresolved duplicates).
   - `dex_wrap.py`: Optimal balanced N-line word wrapper (e.g. `<= 230 px`, `<= 3 lines`, zero `\l`/`\p`), leaving already-valid entries untouched.
   - `lz77.py` & `tiles.py`: Pure-Python GBA BIOS `0x10` LZ77 codec and 4bpp tile remapper/auditor.
   - `bps.py`: External CLI wrapper for user-installed `flips` (GPLv3 kept strictly external).

5. **Hard Quality Gates (`glyphwerk.gates`)**
   Every build passes `text_diff`, `terminology`, `gfx_pointers`, `strcpy_safety`, `rom_header`, and `secret_scan` before release.

6. **Deterministic Bot Harness (`glyphwerk.bot`)**
   Flag-aware BFS world router (`WorldGraph` + `LiveFlags` + fail-closed verified `ScriptWarp`) paired with a BPRE mGBA `explorer.lua` runtime logger.
