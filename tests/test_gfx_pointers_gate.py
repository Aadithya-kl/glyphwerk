"""Unit tests for glyphwerk.gates.gfx_pointers and glyphwerk.gfx.lz77/tiles."""
import struct

from glyphwerk.gates.gfx_pointers import check_gfx_pointers
from glyphwerk.gfx.lz77 import compress_lz77, decompress_lz77
from glyphwerk.gfx.tiles import diff_4bpp_tiles, remap_4bpp_tile

ROM_BASE = 0x08000000


def test_lz77_roundtrip_and_tile_remap():
    tiles = bytes([0x12] * 32 + [0x34] * 32)
    comp = compress_lz77(tiles)
    unpacked, comp_len = decompress_lz77(comp)
    assert unpacked == tiles
    assert comp_len == len(comp)

    remapped_t0 = remap_4bpp_tile(tiles[:32], {1: 7, 2: 7})
    changed = diff_4bpp_tiles(tiles, remapped_t0 + tiles[32:])
    assert changed == {0: 64}


def test_gfx_pointers_gate_catches_corrupted_word_inside_lz77(synthetic_rom):
    base = bytes(synthetic_rom.rom)
    # Find the aligned offset inside the LZ77 stream that looks like a ROM pointer
    hit_off = None
    for off in range(synthetic_rom.lz77_offset, synthetic_rom.lz77_offset + synthetic_rom.lz77_len - 3, 4):
        w = struct.unpack_from("<I", base, off)[0]
        if ROM_BASE <= w < ROM_BASE + len(base):
            hit_off = off
            break
    # Even if compressed displacement shifted alignment, force an aligned ROM-like word in a clean copy
    if hit_off is None:
        base_mut = bytearray(base)
        hit_off = (synthetic_rom.lz77_offset + 8) & ~3
        struct.pack_into("<I", base_mut, hit_off, ROM_BASE + synthetic_rom.dialog_str_offset)
        base = bytes(base_mut)

    patched = bytearray(base)
    assert check_gfx_pointers(base, patched) == []

    # Retargeting the pointer-like word inside LZ77 MUST trigger RED
    struct.pack_into("<I", patched, hit_off, ROM_BASE + synthetic_rom.free_pool_start + 4)
    findings = check_gfx_pointers(base, patched)
    assert len(findings) == 1
    assert findings[0].offset == hit_off

    # Allowing that explicitly manifested graphic asset range turns gate back to GREEN
    assert check_gfx_pointers(base, patched, allowed_ranges=[(synthetic_rom.lz77_offset, synthetic_rom.lz77_offset + synthetic_rom.lz77_len)]) == []
