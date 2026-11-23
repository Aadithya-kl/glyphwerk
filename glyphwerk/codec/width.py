"""Pixel-accurate line width measurement and box-overflow linting for Gen-3 GBA."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from glyphwerk.codec.pcs import FC_ARGS, TERMINATOR, encode

DEFAULT_WIDTHS_PATH = Path(__file__).resolve().parent / "font_widths_bpre.json"


@dataclass(frozen=True)
class WidthReport:
    line_widths: list[int]
    max_line_px: int
    line_count: int
    overflow_lines: list[tuple[int, int]]
    unencodable: list[str]
    ok: bool


class FontWidths:
    """Glyph advance widths (in pixels) indexed by PCS byte value (0x00..0xFF)."""

    def __init__(
        self,
        width_by_byte: dict[int, int],
        buffer_max_px: dict[str, int] | None = None,
    ) -> None:
        self.width_by_byte = dict(width_by_byte)
        self.buffer_max_px = dict(buffer_max_px or {"FD01": 42, "FD06": 42, "default": 60})

    @classmethod
    def load(cls, path: str | Path = DEFAULT_WIDTHS_PATH) -> FontWidths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        wmap = {int(k, 16): int(v) for k, v in data["width_by_byte"].items()}
        bmap = {str(k): int(v) for k, v in data.get("buffer_max_px", {}).items()}
        return cls(wmap, bmap)

    def buffer_width(self, buf_id: int) -> int:
        key = f"FD{buf_id:02X}"
        if key in self.buffer_max_px:
            return self.buffer_max_px[key]
        return self.buffer_max_px.get("default", 60)

    def measure_bytes(self, raw: bytes | bytearray, *, expand_buffers: bool = True) -> list[int]:
        """Measure pixel width of each visual line in a PCS byte string."""
        lines: list[int] = [0]
        i = 0
        n = len(raw)
        while i < n:
            b = raw[i]
            if b == TERMINATOR:
                break
            if b in (0xFE, 0xFA, 0xFB):
                lines.append(0)
                i += 1
            elif b == 0xFC:
                sub = raw[i + 1] if i + 1 < n else 0
                i += 2 + FC_ARGS.get(sub, 1)
            elif b == 0xFD:
                buf_id = raw[i + 1] if i + 1 < n else 0
                if expand_buffers:
                    lines[-1] += self.buffer_width(buf_id)
                i += 2
            elif b in (0xF7, 0xF8, 0xF9):
                lines[-1] += 6
                i += 2
            else:
                lines[-1] += self.width_by_byte.get(b, 6)
                i += 1
        return lines


_DEFAULT_FONTS: FontWidths | None = None


def _get_default_fonts() -> FontWidths:
    global _DEFAULT_FONTS
    if _DEFAULT_FONTS is None:
        _DEFAULT_FONTS = FontWidths.load()
    return _DEFAULT_FONTS


def measure_lines(
    text: str,
    *,
    fonts: FontWidths | None = None,
    expand_buffers: bool = True,
) -> list[int]:
    """Return pixel widths for every line in ``text``."""
    fw = fonts or _get_default_fonts()
    raw, _ = encode(text)
    return fw.measure_bytes(raw, expand_buffers=expand_buffers)


def lint_text(
    text: str,
    *,
    max_line_px: int = 208,
    max_lines: int | None = None,
    fonts: FontWidths | None = None,
    expand_buffers: bool = True,
) -> WidthReport:
    """Validate PCS encodability, line widths, and optional max line count."""
    fw = fonts or _get_default_fonts()
    raw, bad = encode(text)
    widths = fw.measure_bytes(raw, expand_buffers=expand_buffers)
    overflows = [(idx + 1, px) for idx, px in enumerate(widths) if px > max_line_px]
    too_many = max_lines is not None and len(widths) > max_lines
    ok = (not bad) and (not overflows) and (not too_many)
    return WidthReport(
        line_widths=widths,
        max_line_px=max(widths) if widths else 0,
        line_count=len(widths),
        overflow_lines=overflows,
        unencodable=bad,
        ok=ok,
    )
