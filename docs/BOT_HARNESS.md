# Deterministic mGBA Bot Harness (`glyphwerk.bot`)

Glyphwerk includes a lightweight, deterministic QA playtest architecture built around **normal GBA key inputs only** (no teleport cheats, no flag injection):

## Components
1. **World Router (`glyphwerk.bot.router`)**
   - `WorldGraph`: Shortest-path BFS over map collision grids, warps, map connections, and statically verified `ScriptWarp` transitions.
   - `LiveFlags`: Decodes base WRAM save-block flags (and optional extended flag arrays) exported from mGBA so NPCs whose visibility flag is set (`1` = hidden) automatically unblock their tiles.
   - **Fail-Closed Safety:** Dynamic placeholder warps (`0.0`) and unproven/open script opcode paths are explicitly rejected so the router never invents impossible paths.

2. **mGBA Explorer Script (`glyphwerk/bot/explorer.lua`)**
   - Reads standard BPRE WRAM addresses (overridable via `BOT_WRAM` from your `profiles/*.json`).
   - Logs every encountered in-game PCS string (`T <hex>`) directly from `gStringVar4`, enabling automated detection of untranslated strings, overflow lines, or control-code glitches during unattended runs.
   - Exports live player coordinates and raw flag hex dumps (`req_<n>.txt`) whenever a plan finishes, an edge is blocked, or a cutscene shifts position, then hot-loads the newly planned route (`plan_<n>.lua`).
   - Always emits deterministic termination artifacts: `events.tsv`, `end.ss0`, `end.png`, and `DONE`.

## Usage Pattern
1. Export map grids, warps, connections, and NPC `(x, y, flag_id)` metadata from your target ROM into your local database or JSON.
2. Instantiate `WorldGraph(..., flags=LiveFlags(base_hex, ext_hex))` on each `req_<n>.txt` request.
3. Write the resulting `RouteStep` sequence to `plan_<n>.lua` and let `explorer.lua` drive mGBA via real directional + `A`/`B` button presses.
