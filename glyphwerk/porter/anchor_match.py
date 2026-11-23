"""Version-to-version string anchor matcher for porting translations across ROM updates."""
from __future__ import annotations

from dataclasses import dataclass

from glyphwerk.codec.pcs import encode
from glyphwerk.rom.byte_scan import scan_bytes


@dataclass(frozen=True)
class AnchorMatch:
    old_offset: int
    new_offset: int | None
    status: str  # "unique" | "context_resolved" | "ambiguous" | "missing"
    candidates: tuple[int, ...]


def match_by_anchors(
    old_rom: bytes | bytearray,
    new_rom: bytes | bytearray,
    entries: list[dict],
    *,
    context_bytes: int = 16,
) -> list[AnchorMatch]:
    """Locate each ``entries`` item's exact EN PCS string inside ``new_rom``.

    When multiple identical EN strings exist in ``new_rom``, disambiguates using
    preceding/following neighbor bytes from ``old_rom``. Never guesses blindly:
    unresolved duplicates stay ``ambiguous``.
    """
    results: list[AnchorMatch] = []
    for item in entries:
        old_off = int(item["offset"], 0) if isinstance(item["offset"], str) else int(item["offset"])
        en_text = str(item["en"])
        raw, bad = encode(en_text, terminate=True)
        if bad:
            raise ValueError(f"Unencodable EN text at 0x{old_off:07X}: {bad}")
        cands = scan_bytes(new_rom, raw)
        if not cands:
            results.append(AnchorMatch(old_off, None, "missing", ()))
            continue
        if len(cands) == 1:
            results.append(AnchorMatch(old_off, cands[0], "unique", (cands[0],)))
            continue

        # Context disambiguation around old_off
        pre_lo = max(0, old_off - context_bytes)
        pre_old = bytes(old_rom[pre_lo:old_off])
        post_old = bytes(old_rom[old_off + len(raw) : old_off + len(raw) + context_bytes])
        best_score = -1
        best_cands: list[int] = []
        for c in cands:
            c_pre = bytes(new_rom[max(0, c - len(pre_old)) : c])
            c_post = bytes(new_rom[c + len(raw) : c + len(raw) + len(post_old)])
            # strict=False on purpose: near the ROM start/end the candidate context can be shorter than the old one
            score = sum(1 for a, b in zip(reversed(pre_old), reversed(c_pre), strict=False) if a == b)
            score += sum(1 for a, b in zip(post_old, c_post, strict=False) if a == b)
            if score > best_score:
                best_score = score
                best_cands = [c]
            elif score == best_score:
                best_cands.append(c)

        if len(best_cands) == 1 and best_score >= 4:
            results.append(AnchorMatch(old_off, best_cands[0], "context_resolved", tuple(cands)))
        else:
            results.append(AnchorMatch(old_off, None, "ambiguous", tuple(cands)))
    return results
