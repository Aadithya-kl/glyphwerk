"""Unit tests for glyphwerk.porter.dex_wrap (balanced <=230px / <=3-line wrapper)."""
from glyphwerk.porter.dex_wrap import wrap_balanced


def test_overlong_dex_entry_rewrapped_cleanly_under_230px():
    # Line 1 intentionally exceeds 230 px (324 px) while the whole text fits in 3 lines <= 230 px
    overlong = (
        "Dieses Wesen wandert bei Vollmond über hohe Bergkämme und\\n"
        "sammelt leuchtende Kristalle tief im Tal."
    )
    res = wrap_balanced(overlong, max_line_px=230, max_lines=3)
    assert res.ok
    assert res.changed
    assert len(res.line_widths) <= 3
    assert all(w <= 230 for w in res.line_widths)
    assert "\\l" not in res.text and "\\p" not in res.text


def test_text_too_long_for_three_lines_is_reported_not_forced():
    # About 743 px of words cannot fit into 3 x 230 px: the wrapper must refuse and leave the text untouched
    too_long = (
        "Dieses seltene Wesen wandert bei Vollmond ueber hohe Bergkämme und\\n"
        "sammelt leuchtende Kristalle in einem verborgenen Nest tief im Tal."
    )
    res = wrap_balanced(too_long, max_line_px=230, max_lines=3)
    assert not res.ok
    assert not res.changed
    assert res.text == too_long


def test_negative_control_already_clean_entry_untouched():
    already_clean = "Ein kleines Wesen aus dem Wald.\\nEs liebt warme Sonnenstrahlen."
    res = wrap_balanced(already_clean, max_line_px=230, max_lines=3)
    assert res.ok
    assert not res.changed
    assert res.text == already_clean


def test_scroll_code_triggers_rewrap():
    with_scroll = "Erste Zeile.\\lZweite Zeile."
    res = wrap_balanced(with_scroll, max_line_px=230, max_lines=3)
    assert res.ok
    assert res.changed
    assert "\\l" not in res.text
