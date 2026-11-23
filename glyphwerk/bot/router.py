"""Deterministic BFS world router with Live-RAM flag awareness & fail-closed script warps.

Design guarantees:
1. Flag-aware NPC blocking: an NPC event on tile ``(bank, map, x, y)`` with
   ``flag_id != 0`` blocks traversal ONLY while that flag is unset (0 = visible).
   Once the live RAM bit flips to 1, the tile becomes passable. When ``flags=None``,
   falls back to conservative static blocking (every NPC blocks).
2. Fail-closed verified script warps: only explicitly proven static script warps
   whose destination ``(dest_bank, dest_map)`` is known and non-``(0, 0)`` are
   accepted. Dynamic runtime targets ``(0, 0)`` and unproven/open opcode paths
   are rejected fail-closed.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

DIRS: dict[str, tuple[int, int]] = {"D": (0, 1), "U": (0, -1), "L": (-1, 0), "R": (1, 0)}


@dataclass(frozen=True)
class ScriptWarp:
    bank: int
    map_id: int
    x: int
    y: int
    dest_bank: int
    dest_map: int
    dest_x: int
    dest_y: int
    proven: bool = True
    open_opcode_path: bool = False


@dataclass(frozen=True)
class RouteStep:
    kind: str  # "walk" | "warp" | "script_warp" | "connection"
    direction: str
    dest: tuple[int, int, int, int]  # (bank, map, x, y)


class LiveFlags:
    """Decode live GBA Gen-3 flag bitsets (base WRAM save block + optional extended flags)."""

    def __init__(
        self,
        base_hex: str = "",
        ext_hex: str = "",
        *,
        ext_flag_start: int = 0x900,
        overrides: dict[int, bool] | None = None,
    ) -> None:
        self.base = bytes.fromhex(base_hex) if base_hex else b""
        self.ext = bytes.fromhex(ext_hex) if ext_hex else b""
        self.ext_flag_start = ext_flag_start
        self.overrides = dict(overrides or {})

    def is_set(self, flag_id: int) -> bool:
        """Return ``True`` iff ``flag_id != 0`` and its live bit is set (1)."""
        if not flag_id:
            return False
        if flag_id in self.overrides:
            return bool(self.overrides[flag_id])
        if flag_id < self.ext_flag_start:
            idx = flag_id >> 3
            return idx < len(self.base) and bool((self.base[idx] >> (flag_id & 7)) & 1)
        rel = flag_id - self.ext_flag_start
        idx = rel >> 3
        return idx < len(self.ext) and bool((self.ext[idx] >> (rel & 7)) & 1)


class WorldGraph:
    """Deterministic grid + warp + connection router for GBA overworld maps."""

    def __init__(
        self,
        maps: dict[tuple[int, int], list[str]],
        *,
        npc_flags: dict[tuple[int, int, int, int], list[int]] | None = None,
        warps: dict[tuple[int, int, int, int], tuple[int, int, int, int]] | None = None,
        connections: dict[tuple[int, int], list[tuple[str, int, int, int]]] | None = None,
        script_warps: Iterable[ScriptWarp] = (),
        flags: LiveFlags | None = None,
    ) -> None:
        """Create a router graph.

        ``maps`` maps ``(bank, map_id)`` to a list of row strings where ``'.'`` is
        walkable and any other character (e.g. ``'#'``) is blocked.
        """
        self.maps = {k: list(rows) for k, rows in maps.items()}
        self.npc_flags = dict(npc_flags or {})
        self.flags = flags

        # Filter warps fail-closed (never accept dynamic 0.0 placeholder destinations)
        self.warps: dict[tuple[int, int, int, int], tuple[int, int, int, int]] = {}
        for src, dst in (warps or {}).items():
            if (dst[0], dst[1]) == (0, 0) or (dst[0], dst[1]) not in self.maps:
                continue
            self.warps[src] = dst

        self.connections: dict[tuple[int, int], list[tuple[str, int, int, int]]] = dict(connections or {})

        # Fail-closed ingestion of verified static script warps
        self.script_warps: dict[tuple[int, int, int, int], tuple[int, int, int, int]] = {}
        self.rejected_script_warps: list[ScriptWarp] = []
        for sw in script_warps:
            if (
                (not sw.proven)
                or sw.open_opcode_path
                or (sw.dest_bank == 0 and sw.dest_map == 0)
                or (sw.dest_bank, sw.dest_map) not in self.maps
            ):
                self.rejected_script_warps.append(sw)
                continue
            self.script_warps[(sw.bank, sw.map_id, sw.x, sw.y)] = (
                sw.dest_bank,
                sw.dest_map,
                sw.dest_x,
                sw.dest_y,
            )

    def is_npc_blocking(self, bank: int, map_id: int, x: int, y: int) -> bool:
        fids = self.npc_flags.get((bank, map_id, x, y))
        if not fids:
            return False
        if self.flags is None:
            return True
        return any(fid == 0 or not self.flags.is_set(fid) for fid in fids)

    def is_walkable(self, bank: int, map_id: int, x: int, y: int) -> bool:
        rows = self.maps.get((bank, map_id))
        if not rows or y < 0 or y >= len(rows) or x < 0 or x >= len(rows[y]):
            return False
        return rows[y][x] == "." and not self.is_npc_blocking(bank, map_id, x, y)

    def neighbors(self, state: tuple[int, int, int, int]) -> list[RouteStep]:
        b, m, x, y = state
        rows = self.maps.get((b, m))
        if not rows:
            return []
        h = len(rows)
        w = len(rows[0]) if h else 0
        out: list[RouteStep] = []
        for d_key, (dx, dy) in DIRS.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                if (b, m, nx, ny) in self.warps:
                    out.append(RouteStep("warp", d_key, self.warps[(b, m, nx, ny)]))
                elif (b, m, nx, ny) in self.script_warps:
                    out.append(RouteStep("script_warp", d_key, self.script_warps[(b, m, nx, ny)]))
                elif self.is_walkable(b, m, nx, ny):
                    out.append(RouteStep("walk", d_key, (b, m, nx, ny)))
            else:
                for c_dir, c_off, db, dm in self.connections.get((b, m), ()):
                    if c_dir != d_key or (db, dm) not in self.maps:
                        continue
                    d_rows = self.maps[(db, dm)]
                    dh, dw = len(d_rows), len(d_rows[0])
                    if d_key == "U":
                        tx, ty = x - c_off, dh - 1
                    elif d_key == "D":
                        tx, ty = x - c_off, 0
                    elif d_key == "L":
                        tx, ty = dw - 1, y - c_off
                    else:
                        tx, ty = 0, y - c_off
                    if self.is_walkable(db, dm, tx, ty):
                        out.append(RouteStep("connection", d_key, (db, dm, tx, ty)))
        return out

    def find_path(
        self,
        start: tuple[int, int, int, int],
        goal: tuple[int, int, int, int],
        *,
        max_nodes: int = 50_000,
    ) -> list[RouteStep] | None:
        """Shortest-path BFS from ``start`` to ``goal``; returns ``None`` if blocked."""
        if start == goal:
            return []
        q: deque[tuple[int, int, int, int]] = deque([start])
        parent: dict[tuple[int, int, int, int], tuple[tuple[int, int, int, int], RouteStep]] = {}
        visited = {start}
        expanded = 0

        while q and expanded < max_nodes:
            cur = q.popleft()
            expanded += 1
            for step in self.neighbors(cur):
                nxt = step.dest
                if nxt in visited:
                    continue
                visited.add(nxt)
                parent[nxt] = (cur, step)
                if nxt == goal:
                    path: list[RouteStep] = []
                    node = goal
                    while node != start:
                        prev, st = parent[node]
                        path.append(st)
                        node = prev
                    path.reverse()
                    return path
                q.append(nxt)
        return None
