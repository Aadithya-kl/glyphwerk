"""Version-porting anchor matching, balanced Pokédex wrapping, fixed-table patching, and external BPS."""

from glyphwerk.porter.anchor_match import AnchorMatch, match_by_anchors
from glyphwerk.porter.bps import apply_bps, create_bps, find_flips
from glyphwerk.porter.dex_wrap import WrapResult, wrap_balanced
from glyphwerk.porter.tables import TableEntry, TablePatchReport, apply_table_entries

__all__ = [
    "AnchorMatch",
    "match_by_anchors",
    "WrapResult",
    "wrap_balanced",
    "TableEntry",
    "TablePatchReport",
    "apply_table_entries",
    "find_flips",
    "create_bps",
    "apply_bps",
]
