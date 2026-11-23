"""Unit tests for glyphwerk.codec.pcs (lossless Gen-3 PCS codec)."""
from glyphwerk.codec.pcs import decode, encode


def test_german_umlauts_and_sharp_s_roundtrip():
    text = "Pokéball-Größe: ÄÖÜ äöüß!\\nZeile 2\\lScroll\\pAbsatz"
    raw, bad = encode(text)
    assert bad == []
    assert decode(raw) == text


def test_page_break_p_not_confused_with_pkmn():
    # \p followed by 'k' or 'n' MUST remain 0xFB + char, NEVER swallowed!
    raw_pk_word, bad1 = encode("Hallo\\pkönnen")
    assert bad1 == []
    assert raw_pk_word[5] == 0xFB
    assert decode(raw_pk_word) == "Hallo\\pkönnen"

    raw_pn_word, bad2 = encode("Hallo\\pnicht")
    assert bad2 == []
    assert raw_pn_word[5] == 0xFB
    assert decode(raw_pn_word) == "Hallo\\pnicht"

    # Exact \pk\mn ligature encodes to 0x53 0x54
    raw_lig, bad3 = encode("\\pk\\mn")
    assert bad3 == []
    assert raw_lig == b"\x53\x54"


def test_control_codes_fc_fd_raw_roundtrip():
    text = "[#FC0106]Wichtig![#FC0108]\\nHallo [#FD01], [#FD04]!"
    raw, bad = encode(text)
    assert bad == []
    assert b"\xFC\x01\x06" in raw
    assert b"\xFD\x01" in raw
    assert decode(raw) == text


def test_unencodable_characters_reported():
    raw, bad = encode("Hallo 🚀 Welt")
    assert "🚀" in bad
    assert decode(raw) == "Hallo  Welt"
