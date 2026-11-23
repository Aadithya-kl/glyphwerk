"""Unit tests for glyphwerk.codec.width (pixel-width linter)."""
from glyphwerk.codec.width import lint_text, measure_lines


def test_measure_basic_dialog_lines():
    widths = measure_lines("Hallo Welt!\\nDas passt.")
    assert len(widths) == 2
    assert all(0 < w < 100 for w in widths)


def test_buffer_worst_case_expansion_catches_overflow():
    # With 60px default buffer expansion for [#FD02], a near-full line must overflow 208 px
    text = "Wenn mein [#FD02] sehr lange ueber die gesamte Dialogbox hinausgeht"
    rep = lint_text(text, max_line_px=208, expand_buffers=True)
    assert not rep.ok
    assert rep.overflow_lines


def test_color_codes_contribute_zero_pixels():
    plain = measure_lines("Test")
    colored = measure_lines("[#FC0106]Test[#FC0108]")
    assert plain == colored


def test_max_lines_enforced():
    rep = lint_text("Z1\\nZ2\\nZ3\\nZ4", max_line_px=230, max_lines=3)
    assert not rep.ok
    assert rep.line_count == 4
