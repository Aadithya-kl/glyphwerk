"""Gen-3 PCS text codec and pixel-width measurement tools."""

from glyphwerk.codec.pcs import FC_ARGS, TERMINATOR, decode, encode, encoded_length
from glyphwerk.codec.width import FontWidths, WidthReport, lint_text, measure_lines

__all__ = [
    "FC_ARGS",
    "TERMINATOR",
    "encode",
    "decode",
    "encoded_length",
    "FontWidths",
    "WidthReport",
    "measure_lines",
    "lint_text",
]
