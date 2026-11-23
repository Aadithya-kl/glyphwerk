"""Unified CLI entry point for Glyphwerk (GBA)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from glyphwerk import __version__
from glyphwerk.codec.pcs import decode, encode
from glyphwerk.codec.width import lint_text
from glyphwerk.gates.gfx_pointers import check_gfx_pointers
from glyphwerk.gates.rom_header import check_rom_header_pointers
from glyphwerk.gates.secret_scan import scan_directory
from glyphwerk.gates.strcpy_safety import check_strcpy_safety
from glyphwerk.porter.bps import apply_bps, create_bps
from glyphwerk.porter.dex_wrap import wrap_balanced
from glyphwerk.profile import load_profile


def _cmd_encode(args: argparse.Namespace) -> int:
    raw, bad = encode(args.text, terminate=args.terminate)
    print(json.dumps({"hex": raw.hex(" ").upper(), "bytes": len(raw), "unencodable": bad}))
    return 1 if bad else 0


def _cmd_decode(args: argparse.Namespace) -> int:
    raw = bytes.fromhex(args.hex.replace(" ", ""))
    print(decode(raw))
    return 0


def _cmd_width(args: argparse.Namespace) -> int:
    rep = lint_text(args.text, max_line_px=args.max_px, max_lines=args.max_lines)
    print(
        json.dumps(
            {
                "ok": rep.ok,
                "line_widths": rep.line_widths,
                "max_line_px": rep.max_line_px,
                "overflow_lines": rep.overflow_lines,
                "unencodable": rep.unencodable,
            }
        )
    )
    return 0 if rep.ok else 1


def _cmd_dex_wrap(args: argparse.Namespace) -> int:
    res = wrap_balanced(args.text, max_line_px=args.max_px, max_lines=args.max_lines)
    print(json.dumps({"ok": res.ok, "changed": res.changed, "line_widths": res.line_widths, "text": res.text}))
    return 0 if res.ok else 1


def _cmd_gate(args: argparse.Namespace) -> int:
    base = Path(args.base).read_bytes()
    patched = Path(args.patched).read_bytes()
    prof = load_profile(args.profile) if args.profile else None
    rc = 0

    gfx = check_gfx_pointers(base, patched)
    print(f"[gate:gfx_pointers] findings={len(gfx)} -> {'RED' if gfx else 'GREEN'}")
    if gfx:
        rc = 1

    hdr_end = prof.header_guard_end if prof else 0x200
    hdr = check_rom_header_pointers(base, patched, header_guard_end=hdr_end)
    print(f"[gate:rom_header] findings={len(hdr)} -> {'RED' if hdr else 'GREEN'}")
    if hdr:
        rc = 1

    strcpy_addr = args.strcpy_addr or (prof.strcpy_addr if prof else None)
    if strcpy_addr is not None:
        sc = check_strcpy_safety(base, patched, strcpy_addr=strcpy_addr)
        print(f"[gate:strcpy_safety] findings={len(sc)} -> {'RED' if sc else 'GREEN'}")
        if sc:
            rc = 1
    return rc


def _cmd_bps(args: argparse.Namespace) -> int:
    if args.action == "create":
        create_bps(args.base, args.second, args.out, flips_bin=args.flips_bin)
    else:
        apply_bps(args.base, args.second, args.out, flips_bin=args.flips_bin)
    print(f"OK: {args.out}")
    return 0


def _cmd_secret_scan(args: argparse.Namespace) -> int:
    findings = scan_directory(args.path, extra_banned_substrings=args.ban or ())
    for f in findings:
        print(f"RED [{f.rule}] {f.path}: {f.detail}")
    print(f"[secret-scan] path={args.path} findings={len(findings)} -> {'RED' if findings else 'GREEN'}")
    return 1 if findings else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="glyphwerk", description=f"Glyphwerk GBA Toolkit v{__version__}")
    p.add_argument("--version", action="version", version=f"glyphwerk {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("encode", help="Encode source notation into Gen-3 PCS hex bytes")
    pe.add_argument("text")
    pe.add_argument("--terminate", action="store_true")
    pe.set_defaults(func=_cmd_encode)

    pd = sub.add_parser("decode", help="Decode Gen-3 PCS hex bytes to source notation")
    pd.add_argument("hex")
    pd.set_defaults(func=_cmd_decode)

    pw = sub.add_parser("width", help="Measure line pixel widths and check overflow")
    pw.add_argument("text")
    pw.add_argument("--max-px", type=int, default=208)
    pw.add_argument("--max-lines", type=int, default=None)
    pw.set_defaults(func=_cmd_width)

    px = sub.add_parser("dex-wrap", help="Rewrap text into balanced N lines <= max-px")
    px.add_argument("text")
    px.add_argument("--max-px", type=int, default=230)
    px.add_argument("--max-lines", type=int, default=3)
    px.set_defaults(func=_cmd_dex_wrap)

    pg = sub.add_parser("gate", help="Run binary safety gates comparing base and patched ROM")
    pg.add_argument("--base", required=True)
    pg.add_argument("--patched", required=True)
    pg.add_argument("--profile", default=None)
    pg.add_argument("--strcpy-addr", type=lambda s: int(s, 0), default=None)
    pg.set_defaults(func=_cmd_gate)

    pb = sub.add_parser("bps", help="Create or apply BPS patch via external flips binary")
    pb.add_argument("action", choices=["create", "apply"])
    pb.add_argument("base")
    pb.add_argument("second", help="patched ROM (create) or .bps patch (apply)")
    pb.add_argument("out")
    pb.add_argument("--flips-bin", default=None)
    pb.set_defaults(func=_cmd_bps)

    ps = sub.add_parser("secret-scan", help="Scan directory for ROMs, secrets, and private paths")
    ps.add_argument("path", default=".", nargs="?")
    ps.add_argument("--ban", action="append", default=[])
    ps.set_defaults(func=_cmd_secret_scan)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
