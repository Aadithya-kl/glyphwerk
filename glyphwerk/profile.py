"""Game profile loader and schema validator."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _parse_int(val: Any) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        return int(val, 0)
    raise ValueError(f"Expected integer or hex string, got {val!r}")


@dataclass(frozen=True)
class WindowSpec:
    max_line_px: int
    max_lines: int = 2


@dataclass(frozen=True)
class GameProfile:
    profile_id: str
    title: str
    rom_base_addr: int = 0x08000000
    rom_max_size: int = 0x02000000
    header_guard_end: int = 0x200
    strcpy_addr: int | None = None
    font_widths_table: int | None = None
    fill_byte: int = 0xFF
    min_run_bytes: int = 64
    terminator_guard_bytes: int = 2
    reserved_ranges: tuple[tuple[int, int], ...] = ()
    script_banks: tuple[tuple[int, int], ...] = ()
    windows: dict[str, WindowSpec] = field(default_factory=dict)
    buffer_max_px: dict[str, int] = field(default_factory=lambda: {"FD01": 42, "FD06": 42, "default": 60})
    wram_bpre: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameProfile:
        if data.get("schema_version") != 1:
            raise ValueError(f"Unsupported profile schema_version: {data.get('schema_version')!r}")
        fs = data.get("free_space", {})
        reserved = tuple(
            (_parse_int(lo), _parse_int(hi)) for lo, hi in fs.get("reserved_ranges", [])
        )
        banks = tuple(
            (_parse_int(lo), _parse_int(hi)) for lo, hi in data.get("script_banks", [])
        )
        windows = {
            name: WindowSpec(
                max_line_px=int(spec["max_line_px"]),
                max_lines=int(spec.get("max_lines", 2)),
            )
            for name, spec in data.get("windows", {}).items()
        }
        buf_px = {str(k): int(v) for k, v in data.get("buffer_max_px", {"default": 60}).items()}
        return cls(
            profile_id=str(data["profile_id"]),
            title=str(data.get("title", data["profile_id"])),
            rom_base_addr=_parse_int(data.get("rom_base_addr", 0x08000000)),
            rom_max_size=_parse_int(data.get("rom_max_size", 0x02000000)),
            header_guard_end=_parse_int(data.get("header_guard_end", 0x200)),
            strcpy_addr=_parse_int(data["strcpy_addr"]) if data.get("strcpy_addr") is not None else None,
            font_widths_table=_parse_int(data["font_widths_table"]) if data.get("font_widths_table") is not None else None,
            fill_byte=_parse_int(fs.get("fill_byte", 0xFF)),
            min_run_bytes=int(fs.get("min_run_bytes", 64)),
            terminator_guard_bytes=int(fs.get("terminator_guard_bytes", 2)),
            reserved_ranges=reserved,
            script_banks=banks,
            windows=windows,
            buffer_max_px=buf_px,
            wram_bpre=dict(data.get("wram_bpre", {})),
        )


def load_profile(path: str | Path) -> GameProfile:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return GameProfile.from_dict(raw)
