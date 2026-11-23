"""Unit tests for glyphwerk.gates.strcpy_safety (0x00 space-shift stack overflow gate)."""
from glyphwerk.codec.pcs import encode
from glyphwerk.gates.strcpy_safety import check_strcpy_safety


def test_strcpy_gate_green_on_unchanged_and_red_on_shifted_space(synthetic_rom):
    base = bytes(synthetic_rom.rom)
    # Identical ROM -> GREEN
    assert check_strcpy_safety(base, base, strcpy_addr=synthetic_rom.strcpy_addr) == []

    # Replacing "Go back now" (space at index 2 -> len 3) with "Zurueckgehen" (no space -> longer copy!)
    # MUST be flagged RED!
    patched = bytearray(base)
    long_word, _ = encode("Zurueckgehen", terminate=True)
    patched[synthetic_rom.strcpy_str_offset : synthetic_rom.strcpy_str_offset + len(long_word)] = long_word
    findings = check_strcpy_safety(base, patched, strcpy_addr=synthetic_rom.strcpy_addr)
    assert len(findings) == 1
    assert findings[0].bl_offset == synthetic_rom.strcpy_bl_site
    assert findings[0].source_offset == synthetic_rom.strcpy_str_offset
    assert findings[0].base_len == 3
    assert findings[0].patched_len != 3
