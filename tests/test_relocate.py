"""Unit tests for glyphwerk.rom.relocate (pool allocator, +2B guard, LZ77 lock)."""
import struct

import pytest

from glyphwerk.codec.pcs import decode, encode
from glyphwerk.rom.pointers import PointerBlocklist
from glyphwerk.rom.relocate import PoolAllocator, graphic_lock_ranges, relocate_string, write_inplace

ROM_BASE = 0x08000000


def test_pool_protects_preceding_terminator(synthetic_rom):
    alloc = PoolAllocator(synthetic_rom.rom, min_run=64, terminator_guard=2)
    dst = alloc.alloc(32)
    # Must start at least 2 bytes AFTER 0xC000 so preceding string's 0xFF terminator stays intact!
    assert dst >= synthetic_rom.free_pool_start + 2
    assert synthetic_rom.rom[synthetic_rom.free_pool_start] == 0xFF


def test_relocate_respects_blocklist_and_retargets_safe_pointers(synthetic_rom):
    rom = bytearray(synthetic_rom.rom)
    alloc = PoolAllocator(rom, min_run=64)
    locks = graphic_lock_ranges(rom)
    assert any(lo <= synthetic_rom.lz77_offset < hi for lo, hi in locks)

    bl = PointerBlocklist({synthetic_rom.dialog_aligned_ptr: (ROM_BASE + synthetic_rom.dialog_str_offset, "test_lock")})
    new_bytes, _ = encode("Hallo [#FD01], willkommen in der Demo!", terminate=True)
    res = relocate_string(
        rom,
        synthetic_rom.dialog_str_offset,
        new_bytes,
        [synthetic_rom.dialog_aligned_ptr, synthetic_rom.dialog_xse_ptr],
        alloc,
        blocklist=bl,
        gfx_locks=locks,
    )
    assert res.pointers_updated == [synthetic_rom.dialog_xse_ptr]
    assert res.pointers_skipped == [synthetic_rom.dialog_aligned_ptr]
    # Aligned ptr untouched, XSE ptr retargeted to new string
    assert struct.unpack_from("<I", rom, synthetic_rom.dialog_aligned_ptr)[0] == ROM_BASE + synthetic_rom.dialog_str_offset
    new_target = struct.unpack_from("<I", rom, synthetic_rom.dialog_xse_ptr)[0] - ROM_BASE
    assert decode(rom[new_target : new_target + 64]) == "Hallo [#FD01], willkommen in der Demo!"


def test_inplace_guard_rejects_mismatched_original(synthetic_rom):
    rom = bytearray(synthetic_rom.rom)
    bad_old, _ = encode("WRONG", terminate=True)
    new_b, _ = encode("SINEL", terminate=True)
    with pytest.raises(ValueError, match="EN guard mismatch"):
        write_inplace(rom, synthetic_rom.table_base, new_b, slot_bytes=12, expected_old=bad_old)
