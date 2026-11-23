"""Generic ROM byte scanner, PCS string reader, and free-space mapper."""
from __future__ import annotations

from glyphwerk.codec.pcs import TERMINATOR, decode


def read_pcs_at(rom: bytes | bytearray, offset: int, *, max_len: int = 2048) -> tuple[str, int]:
    """Decode PCS string at ``offset``; returns ``(decoded_text, byte_len_including_0xFF)``."""
    end = rom.find(bytes([TERMINATOR]), offset, min(len(rom), offset + max_len))
    if end < 0:
        raise ValueError(f"Unterminated PCS string at 0x{offset:07X}")
    return decode(rom[offset:end]), (end - offset) + 1


def scan_bytes(rom: bytes | bytearray, needle: bytes) -> list[int]:
    """Return every ROM offset matching ``needle``."""
    if not needle:
        return []
    out: list[int] = []
    pos = 0
    while True:
        idx = rom.find(needle, pos)
        if idx < 0:
            break
        out.append(idx)
        pos = idx + 1
    return out


def find_free_runs(
    rom: bytes | bytearray,
    *,
    fill_byte: int = 0xFF,
    min_len: int = 64,
) -> list[tuple[int, int]]:
    """Return all ``[start, end)`` intervals of ``fill_byte`` of length ``>= min_len``."""
    runs: list[tuple[int, int]] = []
    i = 0
    n = len(rom)
    while i < n:
        if rom[i] == fill_byte:
            j = i
            while j < n and rom[j] == fill_byte:
                j += 1
            if j - i >= min_len:
                runs.append((i, j))
            i = j
        else:
            i += 1
    return runs
