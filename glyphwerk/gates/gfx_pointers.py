"""Gate: detect retargeted pointer-like words inside LZ77 graphic payloads."""
from __future__ import annotations

import bisect
import struct
from collections.abc import Iterable
from dataclasses import dataclass

from glyphwerk.rom.relocate import graphic_lock_ranges

ROM_BASE = 0x08000000


@dataclass(frozen=True)
class GfxPointerFinding:
    offset: int
    base_word: int
    patched_word: int


def check_gfx_pointers(
    base_rom: bytes | bytearray,
    patched_rom: bytes | bytearray,
    *,
    allowed_ranges: Iterable[tuple[int, int]] = (),
    rom_base: int = ROM_BASE,
) -> list[GfxPointerFinding]:
    """Fail if any 4B word inside a referenced LZ77 stream was retargeted like a ROM pointer."""
    locks = graphic_lock_ranges(base_rom, rom_base=rom_base)
    if not locks:
        return []
    starts = [s for s, _ in locks]
    allowed = list(allowed_ranges)
    limit = rom_base + max(len(base_rom), len(patched_rom))
    findings: list[GfxPointerFinding] = []
    scan_end = min(len(base_rom), len(patched_rom)) - 3
    for p in range(0, scan_end, 4):
        if base_rom[p : p + 4] == patched_rom[p : p + 4]:
            continue
        k = bisect.bisect_right(starts, p) - 1
        if k < 0 or p >= locks[k][1]:
            continue
        v = struct.unpack_from("<I", base_rom, p)[0]
        w = struct.unpack_from("<I", patched_rom, p)[0]
        if rom_base <= v < limit and rom_base <= w < limit:
            if any(lo <= p < hi for lo, hi in allowed):
                continue
            findings.append(GfxPointerFinding(offset=p, base_word=v, patched_word=w))
    return findings
