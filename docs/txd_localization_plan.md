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
