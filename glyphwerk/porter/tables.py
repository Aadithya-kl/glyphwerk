"""EN-guarded fixed-stride and pointer-table patcher."""
from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass

from glyphwerk.codec.pcs import TERMINATOR, encode
from glyphwerk.rom.relocate import PoolAllocator, write_inplace

ROM_BASE = 0x08000000


@dataclass(frozen=True)
class TableEntry:
    offset: int
    slot_bytes: int
    en: str
    de: str
    mode: str = "inplace"  # "inplace" | "reloc_ptr"
    pointers: tuple[int, ...] = ()


@dataclass(frozen=True)
class TablePatchReport:
    applied: int
    relocated: int
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def apply_table_entries(
    rom: bytearray,
    entries: Iterable[TableEntry],
    *,
    allocator: PoolAllocator | None = None,
    rom_base: int = ROM_BASE,
) -> TablePatchReport:
    """Apply EN-guarded table entries in-place (or via exact pointer relocation)."""
    applied = 0
    relocated = 0
    errors: list[str] = []

    for item in entries:
        en_raw, bad_en = encode(item.en, terminate=True)
        de_raw, bad_de = encode(item.de, terminate=True)
        if bad_en or bad_de:
            errors.append(f"0x{item.offset:07X}: unencodable PCS chars en={bad_en} de={bad_de}")
            continue

        if item.mode == "inplace":
            if len(de_raw) > item.slot_bytes:
                errors.append(
                    f"0x{item.offset:07X}: translation {len(de_raw)}B exceeds slot {item.slot_bytes}B"
                )
                continue
            try:
                ok = write_inplace(
                    rom,
                    item.offset,
                    de_raw,
                    slot_bytes=item.slot_bytes,
                    expected_old=en_raw,
                    pad_byte=TERMINATOR,
                )
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if ok:
                applied += 1
        elif item.mode == "reloc_ptr":
            if allocator is None or not item.pointers:
                errors.append(f"0x{item.offset:07X}: reloc_ptr requires allocator and explicit pointers")
                continue
            expected_ptr = (rom_base + item.offset) & 0xFFFFFFFF
            if any(struct.unpack_from("<I", rom, p)[0] != expected_ptr for p in item.pointers):
                errors.append(f"0x{item.offset:07X}: pointer guard mismatch")
                continue
            dst = allocator.alloc(len(de_raw), align=1)
            rom[dst : dst + len(de_raw)] = de_raw
            new_ptr = (rom_base + dst) & 0xFFFFFFFF
            for p in item.pointers:
                struct.pack_into("<I", rom, p, new_ptr)
            applied += 1
            relocated += 1
        else:
            errors.append(f"0x{item.offset:07X}: unknown mode {item.mode!r}")

    return TablePatchReport(applied=applied, relocated=relocated, errors=errors)
