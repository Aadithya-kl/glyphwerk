"""4bpp GBA 8x8 tile utilities (palette index remapping & pixel-diff audit)."""
from __future__ import annotations

TILE_BYTES_4BPP = 32


def remap_4bpp_tile(tile: bytes | bytearray, index_map: dict[int, int]) -> bytes:
    """Remap 4-bit palette indices inside a single 32-byte 4bpp GBA tile."""
    if len(tile) != TILE_BYTES_4BPP:
        raise ValueError(f"Expected 32-byte 4bpp tile, got {len(tile)}")
    out = bytearray(TILE_BYTES_4BPP)
    for idx, b in enumerate(tile):
        lo = index_map.get(b & 0x0F, b & 0x0F) & 0x0F
        hi = index_map.get((b >> 4) & 0x0F, (b >> 4) & 0x0F) & 0x0F
        out[idx] = lo | (hi << 4)
    return bytes(out)


def diff_4bpp_tiles(before: bytes | bytearray, after: bytes | bytearray) -> dict[int, int]:
    """Return ``{tile_index: changed_pixel_count}`` comparing two 4bpp tilesets."""
    if len(before) != len(after) or (len(before) % TILE_BYTES_4BPP) != 0:
        raise ValueError("Tilesets must have identical lengths divisible by 32")
    changed: dict[int, int] = {}
    n_tiles = len(before) // TILE_BYTES_4BPP
    for t in range(n_tiles):
        base = t * TILE_BYTES_4BPP
        px_diff = 0
        for off in range(TILE_BYTES_4BPP):
            b0, b1 = before[base + off], after[base + off]
            if (b0 & 0x0F) != (b1 & 0x0F):
                px_diff += 1
            if (b0 >> 4) != (b1 >> 4):
                px_diff += 1
        if px_diff:
            changed[t] = px_diff
    return changed
