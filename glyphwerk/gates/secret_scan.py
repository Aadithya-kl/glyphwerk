"""Gate: repository hygiene & secret/ROM-artifact scanner."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

BANNED_EXTENSIONS = frozenset({
    ".gba", ".gbc", ".gb", ".sav", ".ss0", ".ss1", ".ss2", ".ss3", ".ss4",
    ".bps", ".ips", ".ups", ".xdelta", ".exe", ".dll", ".pem", ".key",
})

DEFAULT_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("GENERIC_API_KEY", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("WINDOWS_USER_PATH", re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+")),
    ("TAILSCALE_IP", re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b")),
    ("PRIVATE_KEY_HEADER", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)

TEXT_EXTENSIONS = frozenset({
    ".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".lua", ".sh", ".csv", ".tsv", ".ini", ".cfg",
})


@dataclass(frozen=True)
class SecretFinding:
    path: str
    rule: str
    detail: str


def scan_directory(
    root: str | Path,
    *,
    extra_banned_substrings: Iterable[str] = (),
    ignore_dirs: Iterable[str] = (".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"),
) -> list[SecretFinding]:
    """Scan ``root`` recursively for banned binary extensions, secrets, and private paths."""
    root_path = Path(root).resolve()
    ignored = set(ignore_dirs)
    extra = [s.lower() for s in extra_banned_substrings if s]
    findings: list[SecretFinding] = []

    for item in sorted(root_path.rglob("*")):
        rel = item.relative_to(root_path)
        if any(part in ignored for part in rel.parts):
            continue
        if not item.is_file():
            continue
        ext = item.suffix.lower()
        rel_str = rel.as_posix()
        if ext in BANNED_EXTENSIONS:
            findings.append(SecretFinding(rel_str, "BANNED_EXTENSION", f"Forbidden file type: {ext}"))
            continue
        if ext not in TEXT_EXTENSIONS and item.name not in ("LICENSE", ".gitignore"):
            continue
        try:
            content = item.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Do not flag regex definitions inside secret_scan.py itself
        if rel_str.endswith("gates/secret_scan.py"):
            continue
        for rule_name, rx in DEFAULT_SECRET_PATTERNS:
            m = rx.search(content)
            if m:
                findings.append(SecretFinding(rel_str, rule_name, m.group(0)[:60]))
        low = content.lower()
        for sub in extra:
            if sub in low:
                findings.append(SecretFinding(rel_str, "BANNED_SUBSTRING", sub))

    return findings
