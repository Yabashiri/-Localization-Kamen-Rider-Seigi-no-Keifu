# Menu Smoke Test

Date: 2026-05-12

ISO: `build/out/kamen_rider_text_smoke.iso`

Injected DAT:

- `DATA/MENU/CONFIG_MSG.DAT`: `930 -> 1240`
- `DATA/MENU/ITEM_GET_MSG.DAT`: `1566 -> 1942`
- `DATA/MENU/ITEM_MSG.DAT`: `3222 -> 4884`

Build checks:

- `build/stage/DATA.iso` built from staged DATA tree.
- `build/stage/DATA.CVM` built with `cvm_tool mkcvm`.
- `build/stage/DATA.CVM` opens with `cvm_tool info` and has `CVMH`/`ROFS`.
- `build/out/kamen_rider_text_smoke.iso` built with Cygwin `mkisofs`.
- `isoinfo` reads the final ISO root and `MODULES/`.

PCSX2:

- Launch: pending.
- Crash/hang: pending.
- English glyph visibility: pending.
- Window overflow: pending.
- Line wrapping issues: pending.
- Screenshots: pending.
