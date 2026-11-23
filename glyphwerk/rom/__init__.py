"""ROM pointer discovery, fail-closed locklists, pool relocation, and table-base guards."""

from glyphwerk.rom.byte_scan import find_free_runs, read_pcs_at, scan_bytes
from glyphwerk.rom.pointers import (
    PointerBlocklist,
    find_aligned_pointers,
    find_all_pointers,
    find_unaligned_xse_pointers,
)
from glyphwerk.rom.relocate import (
    PoolAllocator,
    graphic_lock_ranges,
    lz77_stream_length,
    relocate_string,
    write_inplace,
)
from glyphwerk.rom.table_guard import detect_table_base_literals

__all__ = [
    "find_free_runs",
    "read_pcs_at",
    "scan_bytes",
    "PointerBlocklist",
    "find_aligned_pointers",
    "find_unaligned_xse_pointers",
    "find_all_pointers",
    "PoolAllocator",
    "lz77_stream_length",
    "graphic_lock_ranges",
    "write_inplace",
    "relocate_string",
    "detect_table_base_literals",
]
