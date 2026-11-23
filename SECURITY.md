# Security Policy

## Scope
Glyphwerk operates on local binary ROM images and translation JSON/CSV inputs. Relevant security and integrity issues include:
- Path traversal or unsafe file overwrites in CLI/patcher commands
- Arbitrary code execution when loading untrusted profiles or translation inputs
- False negatives in `glyphwerk.gates.secret_scan` that could leak local paths, credentials, or binary ROM artifacts
- Silent binary corruption bypassing EN-byte or pointer safety guards

## Reporting a Vulnerability
Please report suspected vulnerabilities privately via GitHub Security Advisories on this repository rather than opening a public issue. Include a minimal reproduction using a synthetic binary fixture (never attach copyrighted ROMs or private credentials).
