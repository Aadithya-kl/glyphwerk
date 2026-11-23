"""Gate: control-code parity, double-scroll typos (\\ll), and glued-buffer checks."""
from __future__ import annotations

import re
from dataclasses import dataclass

from glyphwerk.codec.pcs import encode

_BUFFER_RE = re.compile(r"\[#FD[0-9A-Fa-f]{2}\]|\[(?:player|rival|buffer\d+)\]|\{(?:PLAYER|RIVAL|BUFFER\d+)\}")
_DOUBLE_SCROLL_RE = re.compile(r"\\ll([A-Za-zÄÖÜäöüß]+)")
_GLUED_BUFFER_RE = re.compile(r"(\[#FD[0-9A-Fa-f]{2}\]|\[(?:player|rival|buffer\d+)\])([A-Za-zÄÖÜäöüß]{2,})")

# Legitimate words starting with 'l' that can follow \l (e.g. \llieber = \l + lieber)
DEFAULT_L_WORD_PREFIXES = (
    "la", "le", "li", "lo", "lu", "lä", "lö", "lü", "ly",
)


@dataclass(frozen=True)
class TextFinding:
    code: str
    message: str


def _extract_buffers(text: str) -> list[str]:
    return sorted(_BUFFER_RE.findall(text))


def check_text_entry(
    en_text: str,
    tr_text: str,
    *,
    allowed_glued_suffixes: tuple[str, ...] = ("s", "x", "m", "cm", "kg"),
) -> list[TextFinding]:
    """Validate a source/translation string pair for structural and control-code regressions."""
    findings: list[TextFinding] = []

    _, bad = encode(tr_text)
    if bad:
        findings.append(TextFinding("UNENCODABLE_PCS", f"Unencodable characters: {bad}"))

    en_bufs = _extract_buffers(en_text)
    tr_bufs = _extract_buffers(tr_text)
    if en_bufs != tr_bufs:
        findings.append(TextFinding("BUFFER_MISMATCH", f"Buffers differ: EN={en_bufs} vs TR={tr_bufs}"))

    for m in _DOUBLE_SCROLL_RE.finditer(tr_text):
        rest = m.group(1)
        word_with_l = "l" + rest.lower()
        # Flag suspicious double \ll where the remainder is a standalone non-l word like 'ist', 'und', 'in'
        if rest.lower() in ("ist", "und", "in", "ich", "erst", "akzeptieren", "einziges", "aber", "auch", "nicht", "das", "die", "der"):
            findings.append(
                TextFinding("DOUBLE_SCROLL_TYPO", f"Likely double scroll typo '\\ll{rest}' (expected '\\l{rest}')")
            )
        elif not word_with_l.startswith(DEFAULT_L_WORD_PREFIXES):
            findings.append(
                TextFinding("DOUBLE_SCROLL_SUSPECT", f"Suspect '\\ll{rest}' (does not form common 'l-' word)")
            )

    for m in _GLUED_BUFFER_RE.finditer(tr_text):
        buf, suffix = m.group(1), m.group(2)
        if suffix.lower() not in allowed_glued_suffixes:
            findings.append(
                TextFinding("GLUED_BUFFER", f"Missing space after buffer token: '{buf}{suffix}'")
            )

    return findings
