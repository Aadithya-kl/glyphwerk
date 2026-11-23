"""Standalone lossless Gen-3 GBA (PCS) text encoder & decoder.

Supports:
- Full Gen-3 Western character map (EN/DE/FR/IT/ES incl. umlauts, ß, accented letters)
- Escape sequences: \\n (0xFE), \\l (0xFA), \\p (0xFB), \\. (0xB0), \\qo (0xB1), \\qc (0xB2)
- Protection against longest-prefix bug: \\p is ALWAYS 0xFB (page break) unless exact \\pk\\mn
- Curly/bracket macro aliases ({PLAYER}, [player], {BUFFER1..3}, {RIVAL}, {COLOR ...})
- Lossless raw-byte escapes [#HH..] for arbitrary FC/FD/F7/F8/F9 control codes
- Exact FC argument-length table so decode() never misreads control-code arguments as text
"""
from __future__ import annotations

import re

TERMINATOR = 0xFF

# Standard Gen-3 GBA (BPRE/Western) single-byte character table
PCS_BYTE_TO_CHAR: dict[int, str] = {
    0x00: " ", 0x01: "À", 0x02: "Á", 0x03: "Â", 0x04: "Ç", 0x05: "È", 0x06: "É", 0x07: "Ê",
    0x08: "Ë", 0x09: "Ì", 0x0B: "Î", 0x0C: "Ï", 0x0D: "Ò", 0x0E: "Ó", 0x0F: "Ô", 0x10: "Œ",
    0x11: "Ù", 0x12: "Ú", 0x13: "Û", 0x14: "Ñ", 0x15: "ß", 0x16: "à", 0x17: "á", 0x19: "ç",
    0x1A: "è", 0x1B: "é", 0x1C: "ê", 0x1D: "ë", 0x1E: "ì", 0x20: "î", 0x21: "ï", 0x22: "ò",
    0x23: "ó", 0x24: "ô", 0x25: "œ", 0x26: "ù", 0x27: "ú", 0x28: "û", 0x29: "ñ", 0x2A: "º",
    0x2B: "ª", 0x2D: "&", 0x2E: "+", 0x35: "=", 0x36: ";", 0x51: "¿", 0x52: "¡",
    0x5A: "Í", 0x5B: "%", 0x5C: "(", 0x5D: ")", 0x68: "â", 0x6F: "í",
    0xA1: "0", 0xA2: "1", 0xA3: "2", 0xA4: "3", 0xA5: "4", 0xA6: "5", 0xA7: "6", 0xA8: "7",
    0xA9: "8", 0xAA: "9", 0xAB: "!", 0xAC: "?", 0xAD: ".", 0xAE: "-", 0xAF: "·", 0xB0: "…",
    0xB1: "“", 0xB2: "”", 0xB3: "‘", 0xB4: "’", 0xB5: "♂", 0xB6: "♀", 0xB7: "$", 0xB8: ",",
    0xB9: "×", 0xBA: "/",
    **{0xBB + i: chr(ord("A") + i) for i in range(26)},
    **{0xD5 + i: chr(ord("a") + i) for i in range(26)},
    0xEF: "▶", 0xF0: ":",
    0xF1: "Ä", 0xF2: "Ö", 0xF3: "Ü", 0xF4: "ä", 0xF5: "ö", 0xF6: "ü",
}

CHAR_TO_PCS: dict[str, int] = {}
for _b, _ch in PCS_BYTE_TO_CHAR.items():
    CHAR_TO_PCS.setdefault(_ch, _b)
# Common Unicode punctuation aliases
CHAR_TO_PCS.setdefault("'", 0xB4)
CHAR_TO_PCS.setdefault('"', 0xB1)
CHAR_TO_PCS.setdefault("*", 0xB9)
CHAR_TO_PCS.setdefault("‧", 0xAF)

# Argument byte count after 0xFC <subcmd>
FC_ARGS: dict[int, int] = {
    0x01: 1, 0x02: 1, 0x03: 1, 0x04: 3, 0x05: 1, 0x06: 1, 0x07: 0, 0x08: 1,
    0x09: 0, 0x0A: 0, 0x0B: 2, 0x0C: 1, 0x0D: 1, 0x0E: 1, 0x0F: 0, 0x10: 2,
    0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x15: 0, 0x16: 0, 0x17: 0, 0x18: 0,
}

_MULTI_TOKENS: list[tuple[str, bytes]] = sorted(
    [
        ("\\pk\\mn", b"\x53\x54"),
        ("\\n", b"\xFE"),
        ("\\l", b"\xFA"),
        ("\\p", b"\xFB"),
        ("\\.", b"\xB0"),
        ("\\qo", b"\xB1"),
        ("\\qc", b"\xB2"),
        ("[player]", b"\xFD\x01"),
        ("[buffer1]", b"\xFD\x02"),
        ("[buffer2]", b"\xFD\x03"),
        ("[buffer3]", b"\xFD\x04"),
        ("[rival]", b"\xFD\x06"),
        ("{PLAYER}", b"\xFD\x01"),
        ("{BUFFER1}", b"\xFD\x02"),
        ("{BUFFER2}", b"\xFD\x03"),
        ("{BUFFER3}", b"\xFD\x04"),
        ("{RIVAL}", b"\xFD\x06"),
        ("{COLOR GREEN}", b"\xFC\x01\x06"),
        ("{COLOR TRANSPARENT}", b"\xFC\x01\x08"),
        ("{COLOR RED}", b"\xFC\x01\x04"),
        ("{COLOR BLUE}", b"\xFC\x01\x08"),
        ("{COLOR WHITE}", b"\xFC\x01\x02"),
    ],
    key=lambda kv: -len(kv[0]),
)

_RAW_RE = re.compile(r"\[#([0-9A-Fa-f]{2,})\]")
_SPECIAL_SINGLE = {0xB0: "\\.", 0xB1: "\\qo", 0xB2: "\\qc"}
_LINE_CTRL = {0xFE: "\\n", 0xFA: "\\l", 0xFB: "\\p"}


def encode(text: str, *, terminate: bool = False) -> tuple[bytes, list[str]]:
    """Encode human-readable source notation into Gen-3 PCS bytes.

    Returns ``(encoded_bytes, unencodable_chars)``. Literal CR/LF are ignored
    as formatting whitespace; use ``\\n``, ``\\l``, ``\\p`` for in-game breaks.
    """
    out = bytearray()
    bad: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        rm = _RAW_RE.match(text, i)
        if rm:
            hex_part = rm.group(1)
            if len(hex_part) % 2 != 0:
                bad.append(rm.group(0))
            else:
                out.extend(bytes.fromhex(hex_part))
            i = rm.end()
            continue

        # Guard: \p is ALWAYS page-break 0xFB except the exact \pk\mn ligature
        if text.startswith("\\p", i) and not text.startswith("\\pk\\mn", i):
            out.append(0xFB)
            i += 2
            continue

        matched = False
        for tok, raw in _MULTI_TOKENS:
            if text.startswith(tok, i):
                out.extend(raw)
                i += len(tok)
                matched = True
                break
        if matched:
            continue

        ch = text[i]
        if ch in ("\r", "\n"):
            i += 1
            continue
        b = CHAR_TO_PCS.get(ch)
        if b is None:
            bad.append(ch)
        else:
            out.append(b)
        i += 1

    if terminate:
        out.append(TERMINATOR)
    return bytes(out), bad


def encoded_length(text: str, *, terminate: bool = False) -> int:
    """Return byte length of ``encode(text, terminate=terminate)[0]``."""
    return len(encode(text, terminate=terminate)[0])


def decode(raw: bytes | bytearray | memoryview) -> str:
    """Losslessly decode Gen-3 PCS bytes back to source notation.

    Stops at the first ``0xFF`` terminator byte. Guarantees ``encode(decode(b))[0] == b``
    for every valid terminator-free PCS byte sequence.
    """
    data = bytes(raw)
    out: list[str] = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == TERMINATOR:
            break
        if b in _LINE_CTRL:
            out.append(_LINE_CTRL[b])
            i += 1
        elif b in (0xF7, 0xF8, 0xF9, 0xFD):
            chunk = data[i : min(i + 2, n)]
            out.append(f"[#{chunk.hex().upper()}]")
            i += len(chunk)
        elif b == 0xFC:
            sub = data[i + 1] if i + 1 < n else 0
            length = 2 + FC_ARGS.get(sub, 1)
            chunk = data[i : min(i + length, n)]
            out.append(f"[#{chunk.hex().upper()}]")
            i += len(chunk)
        elif b in _SPECIAL_SINGLE:
            out.append(_SPECIAL_SINGLE[b])
            i += 1
        elif b in PCS_BYTE_TO_CHAR:
            out.append(PCS_BYTE_TO_CHAR[b])
            i += 1
        else:
            out.append(f"[#{b:02X}]")
            i += 1
    return "".join(out)
