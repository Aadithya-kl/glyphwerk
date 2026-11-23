"""Optimal pixel-aware balanced N-line wrapper (e.g., Pokédex entries <= 230 px / 3 lines)."""
from __future__ import annotations

from dataclasses import dataclass

from glyphwerk.codec.pcs import encode
from glyphwerk.codec.width import FontWidths, _get_default_fonts


@dataclass(frozen=True)
class WrapResult:
    text: str
    changed: bool
    ok: bool
    line_widths: list[int]


def _word_px(word: str, fonts: FontWidths) -> int:
    raw, _ = encode(word)
    return fonts.measure_bytes(raw, expand_buffers=False)[0]


def wrap_balanced(
    text: str,
    *,
    max_line_px: int = 230,
    max_lines: int = 3,
    fonts: FontWidths | None = None,
    forbid_scroll_breaks: bool = True,
) -> WrapResult:
    """Wrap ``text`` into at most ``max_lines`` lines each ``<= max_line_px``.

    - Leaves entries that ALREADY satisfy ``<= max_line_px``, ``<= max_lines``,
      and have no forbidden ``\\l``/``\\p`` codes **byte-identically untouched**.
    - Otherwise finds the balanced word split minimizing ``(max_width, sum_of_squared_slack)``
      so centered box text stays visually balanced and clear of box borders.
    """
    fw = fonts or _get_default_fonts()
    raw, bad = encode(text)
    if bad:
        return WrapResult(text=text, changed=False, ok=False, line_widths=[])

    cur_widths = fw.measure_bytes(raw, expand_buffers=False)
    has_scroll = any(b in (0xFA, 0xFB) for b in raw) if forbid_scroll_breaks else False
    if (not has_scroll) and len(cur_widths) <= max_lines and all(w <= max_line_px for w in cur_widths):
        return WrapResult(text=text, changed=False, ok=True, line_widths=cur_widths)

    # Flatten breaks into spaces while preserving punctuation/control codes
    flat = text.replace("\\n", " ").replace("\\l", " ").replace("\\p", " ")
    words = [w for w in flat.split(" ") if w]
    if not words:
        return WrapResult(text="", changed=(text != ""), ok=True, line_widths=[0])

    space_px = fw.width_by_byte.get(0x00, 6)
    w_px = [_word_px(w, fw) for w in words]
    if any(px > max_line_px for px in w_px):
        return WrapResult(text=text, changed=False, ok=False, line_widths=cur_widths)

    n = len(words)
    # Prefix sums of word widths
    pref = [0] * (n + 1)
    for i, px in enumerate(w_px):
        pref[i + 1] = pref[i] + px

    def seg_width(i: int, j: int) -> int:
        # words[i:j] inclusive-exclusive
        return (pref[j] - pref[i]) + space_px * (j - i - 1)

    best_score: tuple[int, int, int] | None = None
    best_split: list[tuple[int, int]] | None = None

    def search(start: int, lines_left: int, acc: list[tuple[int, int]]) -> None:
        nonlocal best_score, best_split
        if start == n:
            widths = [seg_width(a, b) for a, b in acc]
            mx = max(widths)
            mean = sum(widths) / len(widths)
            variance = int(sum((w - mean) ** 2 for w in widths))
            score = (len(widths), mx, variance)
            if best_score is None or score < best_score:
                best_score = score
                best_split = list(acc)
            return
        if lines_left == 0:
            return
        for end in range(start + 1, n + 1):
            w = seg_width(start, end)
            if w > max_line_px:
                break
            acc.append((start, end))
            search(end, lines_left - 1, acc)
            acc.pop()

    search(0, max_lines, [])
    if best_split is None:
        return WrapResult(text=text, changed=False, ok=False, line_widths=cur_widths)

    new_lines = [" ".join(words[a:b]) for a, b in best_split]
    new_text = "\\n".join(new_lines)
    new_widths = [seg_width(a, b) for a, b in best_split]
    return WrapResult(
        text=new_text,
        changed=(new_text != text),
        ok=True,
        line_widths=new_widths,
    )
