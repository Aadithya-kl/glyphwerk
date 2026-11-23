"""Unit tests for 4B + unaligned XSE pointer discovery and fail-closed PointerBlocklist."""
from glyphwerk.rom.pointers import (
    PointerBlocklist,
    find_aligned_pointers,
    find_all_pointers,
    find_unaligned_xse_pointers,
)

ROM_BASE = 0x08000000


def test_aligned_and_unaligned_xse_pointer_discovery(synthetic_rom):
    aligned = find_aligned_pointers(synthetic_rom.rom, synthetic_rom.dialog_str_offset)
    assert synthetic_rom.dialog_aligned_ptr in aligned
    assert synthetic_rom.dialog_xse_ptr not in aligned  # 0x5003 is unaligned!

    xse = find_unaligned_xse_pointers(synthetic_rom.rom, synthetic_rom.dialog_str_offset)
    assert any(h.offset == synthetic_rom.dialog_xse_ptr and h.kind == "xse_loadpointer" for h in xse)

    union = find_all_pointers(synthetic_rom.rom, synthetic_rom.dialog_str_offset)
    offs = {h.offset for h in union}
    assert {synthetic_rom.dialog_aligned_ptr, synthetic_rom.dialog_xse_ptr}.issubset(offs)


def test_blocklist_verifies_pinned_original_word(synthetic_rom):
    good = PointerBlocklist({synthetic_rom.header_ptr_site: (ROM_BASE + 0xA0, "header_const")})
    assert good.verify_against_rom(synthetic_rom.rom) == []
    assert good.filter_mutable([synthetic_rom.header_ptr_site, synthetic_rom.dialog_aligned_ptr]) == [
        synthetic_rom.dialog_aligned_ptr
    ]

    stale = PointerBlocklist({synthetic_rom.header_ptr_site: (ROM_BASE + 0xDEAD, "wrong_version")})
    errs = stale.verify_against_rom(synthetic_rom.rom)
    assert len(errs) == 1
    assert "0x0000400" in errs[0]
