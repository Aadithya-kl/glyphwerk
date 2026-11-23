"""Binary, textual, terminology, and repository-hygiene quality gates."""

from glyphwerk.gates.gfx_pointers import GfxPointerFinding, check_gfx_pointers
from glyphwerk.gates.rom_header import check_rom_header_pointers
from glyphwerk.gates.secret_scan import SecretFinding, scan_directory
from glyphwerk.gates.strcpy_safety import StrcpyFinding, check_strcpy_safety
from glyphwerk.gates.terminology import TermFinding, check_terminology
from glyphwerk.gates.text_diff import TextFinding, check_text_entry

__all__ = [
    "GfxPointerFinding",
    "check_gfx_pointers",
    "StrcpyFinding",
    "check_strcpy_safety",
    "check_rom_header_pointers",
    "TextFinding",
    "check_text_entry",
    "TermFinding",
    "check_terminology",
    "SecretFinding",
    "scan_directory",
]
