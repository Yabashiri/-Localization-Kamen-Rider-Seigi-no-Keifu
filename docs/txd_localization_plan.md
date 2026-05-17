# TXD localization plan

## Current status

The project has no trusted PNG -> PS2 TXD importer yet.  Existing PNGs under
`dump_jp/EXPORT_TXD` were extracted with an external GUI tool and are treated as
Japanese reference assets.

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
```
