"""4-byte aligned & unaligned XSE script pointer discovery + fail-closed locklist."""
from __future__ import annotations

import json
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROM_BASE = 0x08000000


@dataclass(frozen=True)
class PointerHit:
    offset: int
    aligned: bool
    kind: str  # "aligned_4b" | "xse_loadpointer" | "xse_msgbox" | "xse_bufferstring" | "xse_trainerbattle"


def find_aligned_pointers(
    rom: bytes | bytearray,
    target_offset: int,
    *,
    rom_base: int = ROM_BASE,
) -> list[int]:
    """Return all 4-byte-aligned ROM offsets holding little-endian ``rom_base + target_offset``."""
    needle = struct.pack("<I", (rom_base + target_offset) & 0xFFFFFFFF)
    out: list[int] = []
    start = 0
    while True:
        idx = rom.find(needle, start)
        if idx < 0:
            break
        if (idx & 3) == 0:
            out.append(idx)
        start = idx + 1
    return out


def _classify_xse_context(rom: bytes | bytearray, ptr_offset: int) -> str | None:
    """Identify whether a 4-byte ROM address at ``ptr_offset`` is an XSE script text operand."""
    if ptr_offset >= 2:
        op2 = rom[ptr_offset - 2]
        arg = rom[ptr_offset - 1]
        if op2 == 0x0F and arg <= 0x03:
            return "xse_loadpointer"
        if op2 == 0x85 and arg <= 0x03:
            return "xse_bufferstring"
    if ptr_offset >= 1 and rom[ptr_offset - 1] == 0x67:
        return "xse_msgbox"
    # trainerbattle (0x5C <type:1> <id:2> <flags:2> <introPtr:4> <defeatPtr:4> ...)
    for delta in (6, 10, 14):
        if ptr_offset >= delta and rom[ptr_offset - delta] == 0x5C:
            return "xse_trainerbattle"
    return None


def find_unaligned_xse_pointers(
    rom: bytes | bytearray,
    target_offset: int,
    *,
    script_banks: Iterable[tuple[int, int]] | None = None,
    rom_base: int = ROM_BASE,
) -> list[PointerHit]:
    """Find XSE script text pointers (both aligned and unaligned) targeting ``target_offset``."""
    needle = struct.pack("<I", (rom_base + target_offset) & 0xFFFFFFFF)
    ranges = list(script_banks) if script_banks else [(0, len(rom))]
    hits: list[PointerHit] = []
    seen: set[int] = set()
    for lo, hi in ranges:
        lo_c = max(0, lo)
        hi_c = min(len(rom), hi)
        pos = lo_c
        while True:
            idx = rom.find(needle, pos, hi_c)
            if idx < 0:
                break
            if idx not in seen:
                kind = _classify_xse_context(rom, idx)
                if kind is not None:
                    seen.add(idx)
                    hits.append(PointerHit(offset=idx, aligned=(idx & 3) == 0, kind=kind))
            pos = idx + 1
    return hits


def find_all_pointers(
    rom: bytes | bytearray,
    target_offset: int,
    *,
    script_banks: Iterable[tuple[int, int]] | None = None,
    rom_base: int = ROM_BASE,
) -> list[PointerHit]:
    """Return deduplicated union of 4B-aligned and unaligned XSE script pointers."""
    by_off: dict[int, PointerHit] = {}
    for off in find_aligned_pointers(rom, target_offset, rom_base=rom_base):
        by_off[off] = PointerHit(offset=off, aligned=True, kind="aligned_4b")
    for hit in find_unaligned_xse_pointers(rom, target_offset, script_banks=script_banks, rom_base=rom_base):
        if hit.offset not in by_off:
            by_off[hit.offset] = hit
    return [by_off[k] for k in sorted(by_off)]


class PointerBlocklist:
    """Fail-closed locklist of pointer sites that MUST NEVER be retargeted.

    Each entry binds a ROM pointer offset to its expected original 32-bit word
    so a stale locklist entry for a different ROM version fails loudly.
    """

    def __init__(self, entries: dict[int, tuple[int | None, str]]) -> None:
        self._entries = dict(entries)

    @classmethod
    def load(cls, path: str | Path) -> PointerBlocklist:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        entries: dict[int, tuple[int | None, str]] = {}
        items = raw.get("locked_pointers", raw) if isinstance(raw, dict) else raw
        if isinstance(items, dict):
            for k, v in items.items():
                off = int(k, 0)
                if isinstance(v, dict):
                    word = int(v["original_word"], 0) if "original_word" in v else None
                    reason = str(v.get("reason", ""))
                else:
                    word, reason = None, str(v)
                entries[off] = (word, reason)
        elif isinstance(items, list):
            for item in items:
                off = int(item["offset"], 0)
                word = int(item["original_word"], 0) if item.get("original_word") is not None else None
                entries[off] = (word, str(item.get("reason", "")))
        return cls(entries)

    def is_locked(self, ptr_offset: int) -> bool:
        return ptr_offset in self._entries

    def reason(self, ptr_offset: int) -> str | None:
        entry = self._entries.get(ptr_offset)
        return entry[1] if entry is not None else None

    def verify_against_rom(self, base_rom: bytes | bytearray) -> list[str]:
        """Verify every locked offset still carries its pinned ``original_word`` in ``base_rom``."""
        mismatches: list[str] = []
        for off, (expected_word, reason) in sorted(self._entries.items()):
            if off + 4 > len(base_rom):
                mismatches.append(f"0x{off:07X}: out of bounds ({reason})")
                continue
            if expected_word is not None:
                actual = struct.unpack_from("<I", base_rom, off)[0]
                if actual != expected_word:
                    mismatches.append(
                        f"0x{off:07X}: expected 0x{expected_word:08X}, got 0x{actual:08X} ({reason})"
                    )
        return mismatches

    def filter_mutable(self, offsets: Iterable[int]) -> list[int]:
        return [o for o in offsets if o not in self._entries]
