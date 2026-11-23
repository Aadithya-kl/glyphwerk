"""Pure-Python GBA BIOS LZ77 (Type 0x10) compressor and decompressor."""
from __future__ import annotations


def decompress_lz77(data: bytes | bytearray, offset: int = 0) -> tuple[bytes, int]:
    """Decompress a GBA BIOS Type-0x10 LZ77 stream starting at ``offset``.

    Returns ``(decompressed_bytes, compressed_byte_length)``.
    """
    if offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError(f"Not a GBA Type-0x10 LZ77 header at 0x{offset:X}")
    target_len = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    out = bytearray()
    pos = offset + 4
    n = len(data)
    while len(out) < target_len:
        if pos >= n:
            raise ValueError("Truncated LZ77 stream")
        flags = data[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= target_len:
                break
            if flags & (0x80 >> bit):
                if pos + 1 >= n:
                    raise ValueError("Truncated LZ77 backreference")
                b1, b2 = data[pos], data[pos + 1]
                pos += 2
                length = (b1 >> 4) + 3
                disp = (((b1 & 0x0F) << 8) | b2) + 1
                if disp > len(out):
                    raise ValueError(f"Invalid LZ77 backreference disp={disp} > out={len(out)}")
                for _ in range(length):
                    out.append(out[-disp])
            else:
                if pos >= n:
                    raise ValueError("Truncated LZ77 literal")
                out.append(data[pos])
                pos += 1
    return bytes(out[:target_len]), pos - offset


def compress_lz77(raw: bytes | bytearray, *, vram_safe: bool = True) -> bytes:
    """Compress ``raw`` into a valid GBA BIOS Type-0x10 LZ77 stream.

    ``vram_safe=True`` enforces ``disp >= 2`` (required by GBA BIOS ``LZ77UnCompVram``).
    """
    src = bytes(raw)
    n = len(src)
    if n >= (1 << 24):
        raise ValueError("Input exceeds 24-bit GBA LZ77 header limit")
    out = bytearray([0x10, n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF])
    min_disp = 2 if vram_safe else 1
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len = 0
            best_disp = 0
            win_lo = max(0, i - 0x1000)
            max_len = min(18, n - i)
            if max_len >= 3:
                for start in range(i - min_disp, win_lo - 1, -1):
                    if src[start] != src[i]:
                        continue
                    cur = 0
                    while cur < max_len and src[start + cur] == src[i + cur]:
                        cur += 1
                    if cur > best_len:
                        best_len = cur
                        best_disp = i - start
                        if best_len == max_len:
                            break
            if best_len >= 3:
                flags |= 0x80 >> bit
                disp_enc = best_disp - 1
                out.append(((best_len - 3) << 4) | ((disp_enc >> 8) & 0x0F))
                out.append(disp_enc & 0xFF)
                i += best_len
            else:
                out.append(src[i])
                i += 1
        out[flag_pos] = flags
    return bytes(out)
