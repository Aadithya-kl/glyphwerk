# Glyphwerk-Architektur

Glyphwerk setzt eine **sicherheitsorientierte, profilgesteuerte Lokalisierungs-Pipeline** für GBA-Gen-3-Projekte um. Jede Binäränderung wird vor und nach dem Schreiben durch harte Invarianten abgesichert.

## Schichtenmodell

1. **Profil-Schicht (`glyphwerk.profile`, `profiles/*.json`)**
   Trennt alle spielspezifischen Adressen (`rom_base_addr`, `strcpy_addr`, `script_banks`, `reserved_ranges`, `windows`, `wram_bpre`) vollständig vom generischen Code.

2. **Codec- & Breiten-Schicht (`glyphwerk.codec`)**
   - `pcs.py`: Verlustfreier Gen-3-PCS-Encoder/Decoder mit `FC`-Argumentlängen, `FD`/`F7`/`F8`/`F9`-Steuerbytes, `\p`-vs.-`\pk\mn`-Schutz und `[#HHHH]`-Rohbytes.
   - `width.py`: Misst reale Pixelbreiten je Zeile auf Basis der BPRE-Vorschubtabelle (`font_widths_bpre.json`) inkl. Worst-Case-Pufferschätzung (`FD xx`).

3. **ROM-Zeiger- & Relokations-Schicht (`glyphwerk.rom`)**
   - **In-Place-First:** Festbreiten-Tabellen (Items, Fähigkeiten, Arten, Beeren, Trainerklassen) werden ausschließlich in-place mit EN-Byte-Guard und `0xFF`-Padding gepatcht.
   - **Pool-Allokator (`PoolAllocator`):** Best-Fit über geprüfte `0xFF`-Blöcke mit `+2 B`-Terminatorschutz, `reserved_ranges` und Schutz lebender Zeigerketten.
   - **Grafiksperre (`graphic_lock_ranges`):** Erkennt alle referenzierten GBA-BIOS-`0x10`-LZ77-Ströme, sodass zeigerähnliche Wörter in Kachel-/Palettendaten niemals umgebogen werden.
   - **Tabellenbasis-Wächter (`table_guard.py`):** Erkennt Thumb-Muster `ldr rB, =L` + skalierter Index (`lsls`/`muls`/`adds`) und schützt Struct-Tabellenbasen vor Verwechslung mit Einzeltextzeigern.
   - **Vollständige Zeigererfassung (`pointers.py`):** Findet sowohl 4B-ausgerichtete Zeiger als auch unausgerichtete XSE-Skriptoperanden (`loadpointer`, `msgbox`, `bufferstring`, `trainerbattle`), gefiltert durch eine fail-closed `PointerBlocklist`.

4. **Porting- & Grafik-Schicht (`glyphwerk.porter`, `glyphwerk.gfx`)**
   - `anchor_match.py`: Überträgt Übersetzungen per exaktem PCS-Anker + Nachbar-Kontextabgleich auf neue ROM-Versionen (ohne blindes Raten bei Mehrdeutigkeit).
   - `dex_wrap.py`: Optimal balancierter N-Zeilen-Umbruch (`<= 230 px`, `<= 3` Zeilen), der bereits saubere Einträge byte-identisch unangetastet lässt.
   - `lz77.py` / `tiles.py`: Reiner Python-LZ77-Codec (`0x10`) und 4bpp-Kachel-Audit.
   - `bps.py`: Externer CLI-Wrapper für lokal installiertes `flips` (strikt ohne GPLv3-Binärdatei im Repository).

5. **Harte Quality Gates (`glyphwerk.gates`)**
   `text_diff`, `terminology`, `gfx_pointers`, `strcpy_safety`, `rom_header` und `secret_scan`.

6. **Deterministischer Bot-Harness (`glyphwerk.bot`)**
   Flag-bewusster BFS-Weltrouter (`WorldGraph` + `LiveFlags` + fail-closed geprüfte `ScriptWarp`s) zusammen mit dem BPRE-mGBA-Skript `explorer.lua`.
