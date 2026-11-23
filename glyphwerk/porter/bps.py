"""External Flips (BPS) wrapper — never bundles GPLv3 binaries inside Glyphwerk."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def find_flips(explicit: str | Path | None = None) -> Path:
    """Locate an externally installed ``flips`` executable."""
    if explicit is not None:
        p = Path(explicit)
        if p.is_file():
            return p
        raise FileNotFoundError(f"Configured flips binary not found: {p}")
    for candidate in ("flips", "flips.exe"):
        found = shutil.which(candidate)
        if found:
            return Path(found)
    raise FileNotFoundError(
        "External 'flips' binary not found on PATH. Install Floating IPS separately "
        "(https://github.com/Alcaro/Flips) or pass --flips-bin <path>."
    )


def create_bps(
    base_rom: str | Path,
    patched_rom: str | Path,
    out_bps: str | Path,
    *,
    flips_bin: str | Path | None = None,
) -> Path:
    """Create a BPS patch using the external ``flips`` executable."""
    exe = find_flips(flips_bin)
    out = Path(out_bps)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(exe), "--create", "--bps", str(base_rom), str(patched_rom), str(out)],
        check=True,
    )
    return out


def apply_bps(
    base_rom: str | Path,
    patch_bps: str | Path,
    out_rom: str | Path,
    *,
    flips_bin: str | Path | None = None,
) -> Path:
    """Apply a BPS patch using the external ``flips`` executable."""
    exe = find_flips(flips_bin)
    out = Path(out_rom)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(exe), "--apply", str(patch_bps), str(base_rom), str(out)],
        check=True,
    )
    return out
