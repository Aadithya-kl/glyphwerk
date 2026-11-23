"""Detect ARMv4T Thumb table-base literals mistaken for single text pointers.

When Thumb code loads a struct-table base via ``ldr rB, =L`` and adds a scaled
index (``lsls`` / ``muls`` / ``adds``), retargeting ``L`` to a single relocated
string corrupts every subsequent entry in the table.

Uses Capstone when installed, with a built-in pure-Python Thumb decoder fallback
so safety checks and unit tests always work out of the box.
"""
from __future__ import annotations

import struct
from collections.abc import Iterable

try:
    from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

    _CAPSTONE = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
except ImportError:
    _CAPSTONE = None

ROM_BASE = 0x08000000


def _ldr_pc_sites(rom: bytes | bytearray, literal_offset: int) -> list[tuple[int, int]]:
    """Find Thumb ``ldr rD, [pc, #imm8*4]`` instructions loading ``literal_offset``."""
    sites: list[tuple[int, int]] = []
    start = max(0, literal_offset - 1020)
    for addr in range(start, literal_offset, 2):
        hw = struct.unpack_from("<H", rom, addr)[0]
        if (hw >> 11) == 0b01001:
            target = ((addr + 4) & ~3) + (hw & 0xFF) * 4
            if target == literal_offset:
                reg = (hw >> 8) & 7
                sites.append((addr, reg))
    return sites


def _detect_pure_thumb(rom: bytes | bytearray, ldr_addr: int, rb: int) -> str | None:
    """Lightweight pure-Python Thumb pattern check for scaled-index table arithmetic."""
    scaled: set[int] = set()
    # Look back up to 8 halfwords for lsls / muls / subs
    for a in range(max(0, ldr_addr - 16), ldr_addr, 2):
        hw = struct.unpack_from("<H", rom, a)[0]
        if (hw >> 11) == 0b00000 and ((hw >> 6) & 0x1F) != 0:  # lsls rD, rM, #imm5
            scaled.add(hw & 7)
        elif (hw >> 6) == 0b0100001101:  # muls rD, rM
            scaled.add(hw & 7)

    # Look forward up to 10 halfwords after ldr rB, [pc, #imm]
    for a in range(ldr_addr + 2, min(len(rom) - 1, ldr_addr + 22), 2):
        hw = struct.unpack_from("<H", rom, a)[0]
        # lsls rD, rM, #imm5
        if (hw >> 11) == 0b00000 and ((hw >> 6) & 0x1F) != 0:
            rd = hw & 7
            if rd != rb:
                scaled.add(rd)
            continue
        # muls rD, rM
        if (hw >> 6) == 0b0100001101:
            rd = hw & 7
            if rd != rb:
                scaled.add(rd)
            continue
        # adds rD, rN, rM  (0001100 mmm nnn ddd)
        if (hw >> 9) == 0b0001100:
            rd = hw & 7
            rn = (hw >> 3) & 7
            rm = (hw >> 6) & 7
            if (rn == rb and rm in scaled) or (rm == rb and rn in scaled):
                return f"table_base+scaled_index @0x{a:X}"
            if rd != rb and (rn in scaled or rm in scaled):
                scaled.add(rd)
                continue
        # add rD/h, rM/h  (01000100 D M mmm ddd) — low regs only here
        if (hw >> 8) == 0b01000100:
            rd = (hw & 7) | (((hw >> 7) & 1) << 3)
            rm = ((hw >> 3) & 7) | (((hw >> 6) & 1) << 3)
            if (rd == rb and rm in scaled) or (rm == rb and rd in scaled):
                return f"table_base+scaled_index @0x{a:X}"
        # adds rB, #imm8 (field offset)
        if (hw >> 11) == 0b00110 and ((hw >> 8) & 7) == rb:
            continue
        # branch / return / pop terminates basic block
        if (hw >> 12) in (0xD, 0xE, 0xF) or (hw >> 8) in (0x47, 0xBD):
            break
    return None


def _detect_capstone(rom: bytes | bytearray, ldr_addr: int, rb_name: str) -> str | None:
    assert _CAPSTONE is not None
    lo = max(0, ldr_addr - 16)
    before = list(_CAPSTONE.disasm(bytes(rom[lo:ldr_addr]), ROM_BASE + lo))
    after = list(_CAPSTONE.disasm(bytes(rom[ldr_addr + 2 : ldr_addr + 22]), ROM_BASE + ldr_addr + 2))

    def _ops(ins) -> list[str]:
        return [x.strip() for x in ins.op_str.replace("[", "").replace("]", "").split(",") if x.strip()]

    scaled: set[str] = {
        _ops(ins)[0]
        for ins in before
        if ins.mnemonic in ("lsls", "muls", "subs") and len(_ops(ins)) >= 2
    }
    for ins in after:
        ops = _ops(ins)
        if ins.mnemonic in ("adds", "add") and len(ops) == 3 and rb_name in ops[1:]:
            if (set(ops[1:]) - {rb_name}) & scaled:
                return f"table_base+scaled_index @0x{ins.address - ROM_BASE:X}"
        if ins.mnemonic in ("adds", "add") and len(ops) == 2 and rb_name in ops:
            other = ops[1] if ops[0] == rb_name else ops[0]
            if other in scaled:
                return f"table_base+scaled_index @0x{ins.address - ROM_BASE:X}"
        if ins.mnemonic in ("lsls", "muls") and len(ops) >= 2 and ops[0] != rb_name:
            scaled.add(ops[0])
            continue
        if ins.mnemonic in ("adds", "add") and len(ops) == 3 and ops[0] != rb_name and (set(ops[1:]) & scaled):
            scaled.add(ops[0])
            continue
        if ins.mnemonic in ("adds", "add") and len(ops) == 2 and ops[0] == rb_name and ops[1].startswith("#"):
            continue
        if (ops and ops[0] == rb_name) or ins.mnemonic in ("bl", "bx", "pop", "b"):
            break
    return None


def detect_table_base_literals(
    rom: bytes | bytearray,
    literal_offsets: Iterable[int],
) -> dict[int, str]:
    """Identify which 4B literal offsets act as struct-table bases (MUST NOT be retargeted)."""
    found: dict[int, str] = {}
    for lit in literal_offsets:
        for ldr_addr, reg in _ldr_pc_sites(rom, lit):
            reason = (
                _detect_capstone(rom, ldr_addr, f"r{reg}")
                if _CAPSTONE is not None
                else _detect_pure_thumb(rom, ldr_addr, reg)
            )
            if reason is not None:
                found[lit] = reason
                break
    return found
