# Legal Notice & Clean-Room Policy

1. **No Copyrighted Game Data:**
   This repository contains **only original software tools, documentation, structural profile schemas, and synthetic test fixtures**. It does **not** contain, distribute, or link to any GBA ROM images, BIOS dumps, save files, game scripts, proprietary text strings, or copyrighted graphics/audio assets.
2. **Independent Software:**
   Glyphwerk is an independent open-source localization and quality-assurance toolkit for Game Boy Advance (Gen-3 engine) projects. Game Boy Advance and Pokémon are registered trademarks of Nintendo, Creatures Inc., and GAME FREAK inc. This project is not affiliated with, endorsed by, or sponsored by any trademark holder.
3. **External Patching Tools (License Separation):**
   Glyphwerk itself is licensed under the **MIT License** (`LICENSE`). For BPS patch generation and verification, `glyphwerk.porter.bps` invokes an **external, user-installed** `flips` (Floating IPS, GPLv3) executable via subprocess. No GPLv3 binaries or source files are vendored in this repository.
4. **User Responsibility:**
   Users must supply their own legally obtained ROM images and translation sources locally. All automated tests in this repository run exclusively on generated 64-KB synthetic binary fixtures.
