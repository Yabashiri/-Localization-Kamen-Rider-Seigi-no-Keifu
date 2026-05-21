# TXD localization plan

## Current status

The project now has a trusted narrow PNG -> PS2 TXD importer for linear 16bpp
textures.  It has been used successfully for the title-screen background
textures in `DATA/TITLE.TXD`.

Indexed 4bpp/8bpp texture replacement is still a separate future task because
those texture payloads need PS2/native swizzle and CLUT handling.

Existing PNGs under `dump_jp/EXPORT_TXD` were extracted with an external GUI
tool and are treated as Japanese reference assets.

Important scope note: `dump_jp/EXPORT_TXD` currently covers only the 83 direct
`game_dump/DATA/**/*.TXD` files.  A later audit found many additional TXD/DFF
payloads nested inside `RSC` and `TRA` containers.  See
`reports/nested_resource_inventory.md` before starting any broad texture
coverage work.

Original TXD files stay in `game_dump/DATA`.  Localized or test rebuilt TXD
files should be written to `rebuilt_en/DATA/...` so the existing DATA.CVM/ISO
pipeline can stage them without touching the original dump.

## Working folders

```text
dump_jp/EXPORT_TXD/          Japanese reference PNG export
textures_en/EXPORT_TXD/      editable localized PNG workspace
localization/textures_manifest.json
rebuilt_en/DATA/.../*.TXD    rebuilt TXD files ready for staging
```

`textures_en` is a workspace for image editing and experiments.  Keep
`dump_jp/EXPORT_TXD` unchanged so visual regressions can be compared against the
original export.

## Completed title-screen texture localization

Status: completed and promoted out of draft/test work.

In-game verification: passed.  The finalized title-screen texture set was
checked in-game by the project owner multiple times on 2026-05-21 and should be
treated as accepted work.

The localized title-screen background is finalized as five trackable PNG tiles:

```text
textures_en/EXPORT_TXD/TITLE_title_00_00.png
textures_en/EXPORT_TXD/TITLE_title_00_01.png
textures_en/EXPORT_TXD/TITLE_title_00_02.png
textures_en/EXPORT_TXD/TITLE_title_00_03.png
textures_en/EXPORT_TXD/TITLE_title_00_04.png
```

The only retained full-size source/backup image for this title background is:

```text
textures_en/EXPORT_TXD/59b2d66b-922e-49e1-b4cf-16cbf4a38c45.png
```

All draft folders, diagnostic previews, temporary TXD import folders, and
scratch backups from the title-screen iteration were intentionally removed.

Important `TITLE_title_00_04.png` detail:

```text
left half, x=0..127     -> screen strip x=512..639, y=0..255
right half, x=128..255  -> screen strip x=512..639, y=256..511
```

This is not a normal full 256x256 screen tile.  The game draws it as two
128-pixel-wide vertical strips on the right side of the title background.

Final verified build:

```text
2026-05-17
Imported TITLE_title_00_00..00_04 into rebuilt_en/DATA/TITLE.TXD.
Built build/out/kamen_rider_full_translation.iso.
Verified embedded ELF patch bytes: 6041033c.
Verified ISO size: 3915405312 bytes.
```

Future work should treat the title-screen background tiles as production assets,
not as draft textures still needing the earlier crop/packing investigation.

## Commands

Create workspace folders:

```text
python tools\txd_manifest.py init-workspace
```

Regenerate the manifest from the current game dump and exported PNGs:

```text
python tools\txd_manifest.py build
```

Check what is still missing:

```text
python tools\txd_manifest.py validate
```

Inspect TXD RenderWare chunk structure:

```text
python tools\txd_inspect.py game_dump\DATA\MENU\TEX_K_IT_001.TXD
python tools\txd_inspect.py --textures game_dump\DATA\MENU\TEX_K_IT_001.TXD
```

Run a byte-identical no-op RenderWare round-trip:

```text
python tools\txd_roundtrip.py --check
```

Compare TXD texture entries against exported PNG dimensions:

```text
python tools\txd_texture_report.py --check
```

Import a PNG into a linear 16bpp TXD texture entry:

```text
python tools\txd_import_png.py --input-txd game_dump\DATA\TITLE.TXD --texture title_00_03 --png textures_en\EXPORT_TXD\TITLE_title_00_03.png --output-txd rebuilt_en\DATA\TITLE.TXD
```

Confirmed smoke test:

```text
2026-05-17
DATA/TITLE.TXD title_00_03
Imported from textures_en/EXPORT_TXD/MENU/TITLE_title_00_03.png
Built into build/out/kamen_rider_full_translation.iso
PCSX2/in-game result: replacement texture is visible on the title screen.
```

Stage rebuilt text and texture files:

```text
python tools\stage_rebuilt_text.py
```

The staging script overlays `.DAT`, `.BIN`, and `.TXD` files from
`rebuilt_en/DATA`.

## Safe test order

1. Copy one small original TXD, for example
   `game_dump/DATA/MENU/TEX_K_IT_001.TXD`, to
   `rebuilt_en/DATA/MENU/TEX_K_IT_001.TXD`.
2. Run `python tools\stage_rebuilt_text.py` and confirm the TXD is reported as
   replaced with the same size.
3. Build the ISO with the usual CVM/ISO pipeline and verify the game still
   loads.
4. Only after that, try saving the copied TXD in an external editor with no
   visual changes.
5. If the no-op save works in PCSX2, replace one exported PNG with an obvious
   test label and verify it in-game.

If a no-op editor save breaks rendering, the next task is a custom PS2
RenderWare TXD importer/round-trip tool rather than more image editing.

## TXD structure findings

All 83 current `game_dump/DATA/**/*.TXD` files parse as RenderWare texture
dictionaries with version `0x1005ffff`.

Observed structure:

```text
Texture Dictionary
  Struct                  texture count
  Texture Native
    Struct                platform = "PS2"
    String                texture name
    String                alpha/mask name, usually empty
    Struct                PS2 native payload
      Struct              64-byte raster header
      Struct              raster/CLUT data payload
    Extension
  Extension
```

Examples:

```text
DATA/MENU/TEX_K_IT_001.TXD
  texture_count = 1
  tex_k_it_001 = 128x128 8bpp

DATA/MENU/TELOP_A_TEX.TXD
  texture_count = 2
  tex_te_01_2 = 256x256 8bpp
  tex_te_01_1 = 256x256 8bpp

DATA/FONT.TXD
  texture_count = 14
  font_13..font_00 = 256x256 4bpp
```

This confirms that the next importer task is PS2 indexed texture replacement:
preserve the RenderWare chunk tree, texture names, extensions, and native
header values, then replace the raster/CLUT payload in-place for matching
dimensions and bit depth.

Current validation:

```text
python tools\txd_roundtrip.py --check
  Processed TXD files: 83
  all rebuilt outputs byte-identical

python tools\txd_texture_report.py --check
  texture rows: 283
  all exported PNGs found
  all exported PNG dimensions match TXD native headers
  native layouts:
    14 rows:  4bpp, header 0xc0, CLUT 0x40
    169 rows: 8bpp, header 0xa0, CLUT 0x400
    4 rows:   8bpp, header 0xa0, CLUT 0x200
    95 rows:  16bpp, header 0x50, no CLUT
    1 row:    32bpp, header 0x50, no CLUT
```

Nested resource audit:

```text
2026-05-21
Direct TXD coverage is not complete texture coverage.
RSC/TRA containers contain 2949 embedded TXD payloads, 2832 unique.
Those embedded TXDs contain 13154 texture entries and are not exported yet.
Details: reports/nested_resource_inventory.md
```

For indexed textures, the exported PNG dimensions and palette type match the
native headers, but the PNG index stream is not always byte-identical to the
native pixel region.  A direct check on `TEX_K_IT_001` matched 14434 of 16384
positions, so importer work must handle PS2/native swizzle or the external
exporter's unswizzle behavior instead of copying PNG scanlines directly.

The `TEX_K_IT_001` CLUT comparison confirms the usual PS2 8bpp palette order
inside each 32-color block:

```text
PNG order -> native CLUT order:
0..7, 16..23, 8..15, 24..31
```

Converting native alpha from PS2's 0..128 range to PNG 0..255 with
`round(alpha * 255 / 128)` makes the native and PNG palette sets match, but
palette remapping alone does not make native pixels equal PNG scanlines.  The
pixel region needs its own swizzle/deswizzle mapping.
