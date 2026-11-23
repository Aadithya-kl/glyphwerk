# Glyphwerk (GBA)

**Sicherheitsorientiertes Lokalisierungs-, Versions-Port-, Quality-Gate- und deterministisches QA-Bot-Toolkit für Game-Boy-Advance-Projekte (Gen-3-Engine).**

> **English:** See [README.md](README.md) for the English documentation.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](pyproject.toml)

---

## Warum Glyphwerk?

Bei großen GBA-Gen-3-Übersetzungen (klassisches FireRed/LeafGreen oder erweiterte CFRU-Projekte) treten Binärfehler auf, die einfache Text-Injektoren übersehen:
- **Zufällige Zeiger-Umbiegungen in LZ77-Grafikströmen oder Kartenrändern** (stille Kachel-Korruption)
- **Tabellenbasis-Literale als Textzeiger verkannt** (`ldr rB, =sTable` + `lsls`/`adds`), wodurch ganze Struct-Tabellen zerbrechen
- **`libc strcpy` stoppt am ersten `0x00`-Byte (Gen-3-Leerzeichen)** und verursacht Stack-Überläufe, sobald eine Übersetzung das erste Leerzeichen verschiebt
- **Unausgerichtete XSE-Skriptzeiger (`loadpointer`, `msgbox`, `bufferstring`, `trainerbattle`)**, die reine 4-Byte-Scanner übersehen
- **Pixelbreiten-Überläufe** in Dialogboxen (`208 px`) oder Pokédex-Rahmen (`230 px`)
- **Aufwendige Versions-Ports** bei neuen Upstream-ROM-Ständen

Glyphwerk bündelt **PCS-Codec, profilgesteuerten Relokator, Versions-Port-Matcher, Binär-Gates, LZ77-Kachelwerkzeuge und den deterministischen mGBA-QA-Bot-Router** in einem MIT-lizenzierten Python-Toolkit ohne Pflicht-Abhängigkeiten.

## Schnellstart (ohne echte ROMs)

```bash
pip install -e ".[dev]"

# Alle 10 synthetischen Unit- und Integrationstest-Suiten ausfuehren
pytest -v

# Eigenstaendige 64-KB-Synthetik-ROM-Demo inkl. aller Safety-Gates starten
python examples/minimal_synthetic_demo/run_demo.py

# CLI-Werkzeuge nutzen
glyphwerk encode "Pokéball-Größe\nZeile 2"
glyphwerk width "Hallo Welt!\nDas passt sauber." --max-px 208
glyphwerk secret-scan .
```

## Kernmodule
- **`glyphwerk.codec`**: Verlustfreier Gen-3-PCS-Encoder/Decoder (`\p` vs. `\pk\mn`, `FC`-Argumentlängen, `FD`/`F7`/`F8`/`F9`, `[#HHHH]`) + pixelgenauer Breiten-Linter (`font_widths_bpre.json`).
- **`glyphwerk.rom`**: 4B- & unausgerichteter XSE-Zeigerscanner, fail-closed Zeigersperrliste, `0xFF`-Pool-Relokator (`+2 B`-Terminatorschutz, LZ77-`graphic_lock_ranges`, Zeigerketten-Schutz) und Thumb-Tabellenbasis-Wächter (`table_guard`).
- **`glyphwerk.porter`**: Versions-Anker-Matcher (`anchor_match`), optimal balancierter N-Zeilen-Umbruch (`dex_wrap`), EN-geguardeter Tabellen-Patcher (`tables`) und externer `flips`-BPS-Wrapper (`bps`, ohne GPLv3-Binärdatei im Repo).
- **`glyphwerk.gfx`**: Reiner Python-LZ77-Codec (GBA BIOS Typ `0x10`) und 4bpp-Kachel-Audit.
- **`glyphwerk.gates`**: `gfx_pointers`, `strcpy_safety`, `rom_header`, `text_diff`, `terminology`, `secret_scan`.
- **`glyphwerk.bot`**: Deterministischer BFS-Weltrouter mit **Live-RAM-Flag-Auswertung (`LiveFlags`)** und fail-closed Skript-Warps + konfigurierbares BPRE-`explorer.lua` für mGBA.

## Dokumentation
- [Architektur (DE)](docs/ARCHITECTURE.de.md) · [Architecture (EN)](docs/ARCHITECTURE.md)
- [Spielprofil-Schema](docs/GAME_PROFILE_SCHEMA.md)
- [Gesammelte Erkenntnisse & Fehlerklassen](docs/ERKENNTNISSE.md)
- [Bot-Harness-Anleitung](docs/BOT_HARNESS.md)
- [Multi-Agent-Review-Workflow](docs/MULTI_AGENT_WORKFLOW.md)
- [Rechtlicher Hinweis (Clean-Room)](LEGAL_NOTICE.md)

## Lizenz
MIT — siehe [LICENSE](LICENSE) und [LEGAL_NOTICE.md](LEGAL_NOTICE.md).
