"""Safety-first in-place writer, free-space pool allocator, and LZ77 graphic lock."""
from __future__ import annotations

import bisect
import struct
from collections.abc import Iterable
from dataclasses import dataclass

from glyphwerk.codec.pcs import TERMINATOR
from glyphwerk.rom.pointers import PointerBlocklist

ROM_BASE = 0x08000000


def lz77_stream_length(rom: bytes | bytearray, offset: int) -> int | None:
    """Validate GBA BIOS LZ77 (type 0x10) stream at ``offset`` and return compressed length."""
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        return None
    unpacked = rom[offset + 1] | (rom[offset + 2] << 8) | (rom[offset + 3] << 16)
    if not (32 <= unpacked <= 0x10000) or (unpacked % 32) != 0:
        return None
    produced = 0
    pos = offset + 4
    n = len(rom)
    while produced < unpacked:
        if pos >= n:
            return None
        flags = rom[pos]
        pos += 1
        for bit in range(8):
            if produced >= unpacked:
                break
            if flags & (0x80 >> bit):
                if pos + 1 >= n:
                    return None
                disp = (((rom[pos] & 0x0F) << 8) | rom[pos + 1]) + 1
                if disp > produced:
                    return None
                produced += (rom[pos] >> 4) + 3
                pos += 2
            else:
                if pos >= n:
                    return None
                produced += 1
                pos += 1
    return pos - offset


def graphic_lock_ranges(rom: bytes | bytearray, *, rom_base: int = ROM_BASE) -> list[tuple[int, int]]:
    """Find all referenced GBA BIOS 0x10 LZ77 graphic blocks as merged ``[start, end)`` ranges.

    4-byte words inside these ranges are compressed tile/tilemap/palette payloads,
    NEVER text pointers, even if they happen to match ``0x08xxxxxx`` by coincidence.
    """
    n_words = len(rom) // 4
    limit = rom_base + len(rom)
    targets: set[int] = set()
    for (val,) in struct.iter_unpack("<I", bytes(rom[: n_words * 4])):
        if rom_base <= val < limit:
            off = val - rom_base
            if rom[off] == 0x10:
                targets.add(off)

    raw_ranges: list[tuple[int, int]] = []
    for t in sorted(targets):
        ln = lz77_stream_length(rom, t)
        if ln is not None:
            raw_ranges.append((t, t + ln))

    if not raw_ranges:
        return []
    merged: list[tuple[int, int]] = [raw_ranges[0]]
    for lo, hi in raw_ranges[1:]:
        p_lo, p_hi = merged[-1]
        if lo <= p_hi:
            merged[-1] = (p_lo, max(p_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


def _subtract_ranges(
    pool: list[list[int]],
    excluded: Iterable[tuple[int, int]],
) -> list[list[int]]:
    ex_list = list(excluded)
    if not ex_list:
        return pool
    out: list[list[int]] = []
    for s, e in pool:
        segs = [(s, e)]
        for rs, re_ in ex_list:
            nxt: list[tuple[int, int]] = []
            for a, b in segs:
                if re_ <= a or rs >= b:
                    nxt.append((a, b))
                else:
                    if a < rs:
                        nxt.append((a, rs))
                    if re_ < b:
                        nxt.append((re_, b))
            segs = nxt
        out.extend([list(x) for x in segs if x[1] > x[0]])
    return out


def _is_rom_ptr(rom: bytes | bytearray, off: int, rom_base: int = ROM_BASE) -> bool:
    if off < 0 or off + 4 > len(rom):
        return False
    val = struct.unpack_from("<I", rom, off)[0]
    return rom_base <= val < rom_base + len(rom)


def live_pointer_target_guards(
    rom: bytes | bytearray,
    pool: list[list[int]],
    *,
    chain_min: int = 3,
    rom_base: int = ROM_BASE,
) -> list[tuple[int, int]]:
    """Protect free-byte runs that are live targets of aligned pointer tables."""
    if not pool:
        return []
    starts = [s for s, _ in pool]
    guards: list[tuple[int, int]] = []
    for q in range(0, len(rom) - 3, 4):
        val = struct.unpack_from("<I", rom, q)[0]
        if not (rom_base <= val < rom_base + len(rom)):
            continue
        t = val - rom_base
        if (t & 3) != 0:
            continue
        k = bisect.bisect_right(starts, t + 2) - 1
        if k < 0 or not (pool[k][0] - 2 <= t < pool[k][1]):
            continue
        # Count contiguous aligned pointer chain around q
        lo = hi = q
        while _is_rom_ptr(rom, lo - 4, rom_base):
            lo -= 4
        while _is_rom_ptr(rom, hi + 4, rom_base):
            hi += 4
        chain_len = (hi - lo) // 4 + 1
        if chain_len >= chain_min:
            guards.append((max(0, t - 2), pool[k][1]))
    return guards


class PoolAllocator:
    """Best-fit allocator over verified free ``0xFF`` ROM blocks."""

    def __init__(
        self,
        rom: bytes | bytearray,
        *,
        min_run: int = 64,
        fill_byte: int = 0xFF,
        terminator_guard: int = 2,
        reserved_ranges: Iterable[tuple[int, int]] = (),
        protect_pointer_chains: bool = True,
    ) -> None:
        raw_pool: list[list[int]] = []
        i = 0
        n = len(rom)
        while i < n:
            if rom[i] == fill_byte:
                j = i
                while j < n and rom[j] == fill_byte:
                    j += 1
                if j - i >= min_run:
                    # Guard preceding string terminator (first 0xFF) + safety pad
                    start = i + terminator_guard
                    if start < j:
                        raw_pool.append([start, j])
                i = j
            else:
                i += 1
        ex = list(reserved_ranges)
        if protect_pointer_chains:
            ex.extend(live_pointer_target_guards(rom, raw_pool))
        self.blocks: list[list[int]] = _subtract_ranges(raw_pool, ex)

    @property
    def free_bytes(self) -> int:
        return sum(e - s for s, e in self.blocks)

    def alloc(self, size: int, *, align: int = 1) -> int:
        """Allocate ``size`` bytes using best-fit strategy; raises ``MemoryError`` if exhausted."""
        if size <= 0:
            raise ValueError("Allocation size must be > 0")
        best_idx = -1
        best_waste = 1 << 60
        best_addr = -1
        for idx, (s, e) in enumerate(self.blocks):
            aligned = (s + align - 1) & ~(align - 1)
            if aligned + size <= e:
                waste = (e - aligned) - size
                if waste < best_waste:
                    best_waste = waste
                    best_idx = idx
                    best_addr = aligned
        if best_idx < 0:
            raise MemoryError(f"No free pool block can fit {size} bytes (align={align})")
        s, e = self.blocks[best_idx]
        after = best_addr + size
        new_segs: list[list[int]] = []
        if best_addr > s:
            new_segs.append([s, best_addr])
        if after < e:
            new_segs.append([after, e])
        self.blocks[best_idx : best_idx + 1] = new_segs
        return best_addr


@dataclass(frozen=True)
class RelocateResult:
    mode: str  # "inplace" | "relocated"
    target_offset: int
    pointers_updated: list[int]
    pointers_skipped: list[int]


def write_inplace(
    rom: bytearray,
    offset: int,
    new_bytes: bytes,
    *,
    slot_bytes: int,
    expected_old: bytes | None = None,
    pad_byte: int = TERMINATOR,
) -> bool:
    """Write ``new_bytes + 0xFF`` in-place with strict slot and EN-guard checks."""
    payload = new_bytes if new_bytes.endswith(bytes([TERMINATOR])) else new_bytes + bytes([TERMINATOR])
    if len(payload) > slot_bytes:
        return False
    if expected_old is not None:
        exp = expected_old if expected_old.endswith(bytes([TERMINATOR])) else expected_old + bytes([TERMINATOR])
        if bytes(rom[offset : offset + len(exp)]) != exp:
            raise ValueError(f"EN guard mismatch at 0x{offset:07X}")
    rom[offset : offset + slot_bytes] = payload + bytes([pad_byte]) * (slot_bytes - len(payload))
    return True


def relocate_string(
    rom: bytearray,
    orig_offset: int,
    new_bytes: bytes,
    pointer_offsets: Iterable[int],
    allocator: PoolAllocator,
    *,
    blocklist: PointerBlocklist | None = None,
    gfx_locks: Iterable[tuple[int, int]] = (),
    rom_base: int = ROM_BASE,
) -> RelocateResult:
    """Relocate ``new_bytes + 0xFF`` into ``allocator`` and retarget safe pointers only."""
    payload = new_bytes if new_bytes.endswith(bytes([TERMINATOR])) else new_bytes + bytes([TERMINATOR])
    locks = sorted(gfx_locks)
    lock_starts = [s for s, _ in locks]

    def _in_gfx_lock(p: int) -> bool:
        k = bisect.bisect_right(lock_starts, p) - 1
        return k >= 0 and p < locks[k][1]

    safe_ptrs: list[int] = []
    skipped: list[int] = []
    expected_word = (rom_base + orig_offset) & 0xFFFFFFFF
    for p in pointer_offsets:
        if (blocklist is not None and blocklist.is_locked(p)) or _in_gfx_lock(p):
            skipped.append(p)
            continue
        if struct.unpack_from("<I", rom, p)[0] != expected_word:
            skipped.append(p)
            continue
        safe_ptrs.append(p)

    if not safe_ptrs:
        raise ValueError(f"No mutable pointers left to relocate 0x{orig_offset:07X}")

    dst = allocator.alloc(len(payload), align=1)
    rom[dst : dst + len(payload)] = payload
    new_word = (rom_base + dst) & 0xFFFFFFFF
    for p in safe_ptrs:
        struct.pack_into("<I", rom, p, new_word)

    return RelocateResult(
        mode="relocated",
        target_offset=dst,
        pointers_updated=safe_ptrs,
        pointers_skipped=skipped,
    )
