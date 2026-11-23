"""End-to-end synthetic version-port & quality-gate integration test (zero real ROMs)."""
import struct

from glyphwerk.codec.pcs import decode, encode
from glyphwerk.gates.gfx_pointers import check_gfx_pointers
from glyphwerk.gates.rom_header import check_rom_header_pointers
from glyphwerk.gates.strcpy_safety import check_strcpy_safety
from glyphwerk.gates.terminology import check_terminology
from glyphwerk.gates.text_diff import check_text_entry
from glyphwerk.porter.anchor_match import match_by_anchors
from glyphwerk.porter.tables import TableEntry, apply_table_entries
from glyphwerk.rom.pointers import find_all_pointers
from glyphwerk.rom.relocate import PoolAllocator, graphic_lock_ranges, relocate_string


def test_full_synthetic_v1_to_v2_port_and_all_gates(synthetic_rom):
    v1_rom = bytes(synthetic_rom.rom)
    # Build v2_rom by shifting the dialog string by +0x40 bytes inside a fresh copy
    v2_base = bytearray(v1_rom)
    old_off = synthetic_rom.dialog_str_offset
    new_off = old_off + 0x40
    en_dlg = "Hello [#FD01]!"
    raw_en, _ = encode(en_dlg, terminate=True)
    # Clear old location and place string at shifted v2 offset + update pointers
    v2_base[old_off : old_off + len(raw_en)] = b"\x00" * len(raw_en)
    v2_base[new_off : new_off + len(raw_en)] = raw_en
    for p in (synthetic_rom.dialog_aligned_ptr, synthetic_rom.dialog_xse_ptr):
        struct.pack_into("<I", v2_base, p, 0x08000000 + new_off)

    # 1. Anchor-match v1 offset -> v2 offset
    matches = match_by_anchors(v1_rom, v2_base, [{"offset": old_off, "en": en_dlg}])
    assert len(matches) == 1
    assert matches[0].status == "unique"
    assert matches[0].new_offset == new_off

    # 2. Text & terminology pre-build gates
    tr_dlg = "Hallo [#FD01], gute Reise!"
    assert check_text_entry(en_dlg, tr_dlg) == []
    assert check_text_entry("A\\lB", "A\\llist B")[0].code == "DOUBLE_SCROLL_TYPO"
    assert check_text_entry("A\\lB", "A\\llieber B") == []  # Negative control: \l + lieber!
    assert check_text_entry("[#FD01] with", "[#FD01]mit")[0].code == "GLUED_BUFFER"
    assert check_terminology("Im Supermarkt", [{"blocked": "Supermarkt", "preferred": "Markt"}])

    # 3. Build patched v2 ROM: fixed table in-place + dialog relocated (4B + XSE pointers)
    v2_patched = bytearray(v2_base)
    alloc = PoolAllocator(v2_patched, min_run=64)
    gfx_locks = graphic_lock_ranges(v2_base)

    tbl_report = apply_table_entries(
        v2_patched,
        [
            TableEntry(synthetic_rom.table_base, 12, "CHERI", "AMRENA"),
            TableEntry(synthetic_rom.table_base + 12, 12, "ORAN", "SINEL"),
            TableEntry(synthetic_rom.table_base + 24, 12, "LUM", "PRUNUS"),
        ],
    )
    assert tbl_report.ok and tbl_report.applied == 3

    ptrs = [h.offset for h in find_all_pointers(v2_base, new_off)]
    tr_raw, _ = encode(tr_dlg, terminate=True)
    rel = relocate_string(v2_patched, new_off, tr_raw, ptrs, alloc, gfx_locks=gfx_locks)
    assert len(rel.pointers_updated) == 2

    # 4. Run ALL binary safety gates on v2_base vs v2_patched -> 100% GREEN!
    assert check_gfx_pointers(v2_base, v2_patched) == []
    assert check_rom_header_pointers(v2_base, v2_patched) == []
    assert check_strcpy_safety(v2_base, v2_patched, strcpy_addr=synthetic_rom.strcpy_addr) == []

    # 5. Roundtrip readback from patched ROM
    assert decode(v2_patched[synthetic_rom.table_base : synthetic_rom.table_base + 12]) == "AMRENA"
    assert decode(v2_patched[rel.target_offset : rel.target_offset + 64]) == tr_dlg
