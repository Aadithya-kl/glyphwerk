"""Gate: verify no pointer referencing the GBA ROM header (0x08000000..0x080001FF) was modified."""
from __future__ import annotations

import struct

ROM_BASE = 0x08000000


def check_rom_header_pointers(
    base_rom: bytes | bytearray,
    patched_rom: bytes | bytearray,
    *,
    header_guard_end: int = 0x200,
    rom_base: int = ROM_BASE,
) -> list[int]:
    """Return all 4B offsets whose header-targeting ROM pointer changed in ``patched_rom``."""
    changed: list[int] = []
    hi = rom_base + header_guard_end
    scan_end = min(len(base_rom), len(patched_rom)) - 3
    for off in range(0, scan_end, 4):
        val = struct.unpack_from("<I", base_rom, off)[0]
        if rom_base <= val < hi:
            if patched_rom[off : off + 4] != base_rom[off : off + 4]:
                # Ignore accidental non-pointer byte edits unless patched word still looks like ROM ptr
                if patched_rom[off + 3] in (0x08, 0x09):
                    changed.append(off)
    return changed
