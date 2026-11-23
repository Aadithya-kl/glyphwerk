"""Unit tests for glyphwerk.rom.table_guard (Thumb table-base literal detection)."""
from glyphwerk.rom.table_guard import detect_table_base_literals


def test_detects_thumb_table_base_literal_and_ignores_plain_pointer(synthetic_rom):
    # 0x200C is loaded by `ldr r1, [pc, #8]` followed by `adds r0, r1, r0` after `lsls r0, r0, #2`
    # 0x5040 is just a plain data pointer, NOT loaded by Thumb scaled-index code
    found = detect_table_base_literals(
        synthetic_rom.rom,
        [synthetic_rom.table_literal_site, synthetic_rom.dialog_aligned_ptr],
    )
    assert synthetic_rom.table_literal_site in found
    assert synthetic_rom.dialog_aligned_ptr not in found
