"""Gate: pure-Python Thumb ``BL strcpy`` scanner catching Gen-3 ``0x00`` (space) copy-length shifts.

In Gen-3 GBA games, byte ``0x00`` is the PCS space character, whereas C ``libc strcpy``
terminates on ``0x00``. If native code accidentally calls ``strcpy`` on a PCS string into
a small stack buffer, moving the first space further back in a translation causes a stack
buffer overflow.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

ROM_BASE = 0x08000000


@dataclass(frozen=True)
class StrcpyFinding:
    bl_offset: int
    source_offset: int
    base_len: int | None
    patched_len: int | None


def find_thumb_bl_sites(
    rom: bytes | bytearray,
    target_addr: int,
    *,
    rom_base: int = ROM_BASE,
) -> list[int]:
    """Return all Thumb ``BL`` offsets calling ``target_addr`` (pure Python, no NumPy)."""
    out: list[int] = []
    n = len(rom) // 2
    if n < 2:
        return out
    halfwords = struct.unpack_from(f"<{n}H", rom, 0)
    for i in range(n - 1):
        h1 = halfwords[i]
        if (h1 & 0xF800) != 0xF000:
            continue
        h2 = halfwords[i + 1]
        if (h2 & 0xF800) != 0xF800:
            continue
        off = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
        if off & 0x400000:
            off -= 0x800000
        tgt = rom_base + i * 2 + 4 + off
        if tgt == target_addr:
            out.append(i * 2)
    return out


def _literal_r1_before(rom: bytes | bytearray, bl_offset: int) -> int | None:
    """Look back up to 12 halfwords for ``ldr r1, [pc, #imm8*4]`` (0x49xx)."""
    for k in range(1, 13):
        o = bl_offset - 2 * k
        if o < 0:
            break
        hw = struct.unpack_from("<H", rom, o)[0]
        if (hw & 0xFF00) == 0x4900:
            lit = ((o + 4) & ~3) + (hw & 0xFF) * 4
            if lit + 4 <= len(rom):
                return struct.unpack_from("<I", rom, lit)[0]
    return None


def _cstr_len(rom: bytes | bytearray, offset: int, limit: int = 400) -> int | None:
    j = rom.find(b"\x00", offset, min(len(rom), offset + limit))
    return (j - offset + 1) if j >= 0 else None


def check_strcpy_safety(
    base_rom: bytes | bytearray,
    patched_rom: bytes | bytearray,
    *,
    strcpy_addr: int,
    rom_base: int = ROM_BASE,
    only_longer: bool = False,
) -> list[StrcpyFinding]:
    """Compare C-string (``0x00``-terminated) lengths at every ``BL strcpy`` literal source."""
    findings: list[StrcpyFinding] = []
    limit = rom_base + len(base_rom)
    for bl_off in find_thumb_bl_sites(base_rom, strcpy_addr, rom_base=rom_base):
        src_ptr = _literal_r1_before(base_rom, bl_off)
        if src_ptr is None or not (rom_base <= src_ptr < limit):
            continue
        src_off = src_ptr - rom_base
        le = _cstr_len(base_rom, src_off)
        ld = _cstr_len(patched_rom, src_off)
        if le != ld:
            if only_longer and le is not None and ld is not None and ld <= le:
                continue
            findings.append(StrcpyFinding(bl_off, src_off, le, ld))
    return findings
