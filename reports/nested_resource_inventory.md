# Nested resource inventory

Date: 2026-05-21

This note records a follow-up audit after comparing the old `game_dump` with a
fresh ISO root dump.  The file dump itself is complete, but many game resources
are still nested inside already extracted files.

## Scope

The current texture workspace covers only direct TXD files:

```text
game_dump/DATA/**/*.TXD
```

Current direct TXD coverage:

```text
direct TXD files: 83
direct TXD texture entries: 283
exported PNGs under dump_jp/EXPORT_TXD: 283
```

Those 83 TXD files are not the whole texture set.

## Main finding

`RSC` and `TRA` are resource containers.  They contain additional RenderWare
TXD and DFF payloads that are not represented in the current
`dump_jp/EXPORT_TXD` PNG export.

Recursive scan totals:

```text
embedded TXD payloads: 2949 total, 2832 unique
embedded DFF payloads: 2282 total, 1691 unique
unique embedded TXD texture entries: 13154
```

No unique embedded TXD payload matched any of the 83 direct TXD files by hash,
so these are additional texture dictionaries, not duplicate coverage of the
current export.

## Embedded TXD and DFF locations

```text
RSC containers:
  DATA root   261 TXD, 489 DFF
  ESCENE      150 TXD, 1058 DFF
  MAP          19 TXD, 33 DFF
  MENU         57 TXD, 95 DFF

TRA containers:
  TSCENE     2373 TXD
  CHAR         89 TXD, 470 DFF
  BIKE              137 DFF
```

Unique embedded TXD payloads by source:

```text
RSC DATA root   251
RSC ESCENE       65
RSC MAP           6
RSC MENU         57
TRA CHAR         80
TRA TSCENE     2373
```

## Embedded texture layout

Unique embedded TXD texture rows by native bit depth:

```text
8bpp:   1249
16bpp: 11865
24bpp:    40
```

Most common dimensions:

```text
256x256 16bpp: 11865
256x256 8bpp:    957
128x128 8bpp:    225
256x256 24bpp:    40
64x64 8bpp:       36
512x256 8bpp:     14
32x32 8bpp:       10
```

## RSC container notes

`RSC` uses a `HEAD` header followed by one or more `RSRC` entries.  Entries can
themselves be nested `RSC` containers.  The scan found 7617 resource entries.

Entry extensions seen inside RSC:

```text
DATA root: .anm, .bin, .dff, .njl, .njm, .rsc, .txd
ESCENE:    .anm, .dff, .njc, .njl, .njm, .txd
MAP:       .bin, .dff, .txd
MENU:      .anm, .bin, .dff, .rsc, .txd
```

Useful examples:

```text
EFFSET01.RSC
  effect/effset01.txd
  effect/*.bin

FEV_011.RSC
  FEV_011_TEX.rsc
    FEV_011_TEX.Txd
  FEV_011_DFF.rsc
    FEV011_00.dff
  FEV_011_ANM.rsc
    FEV011_00.anm

MENU/ECAT_A.RSC
  ECAT_A.Txd

ESCENE/PC01.RSC
  PE01.Txd
  PE01ED*.dff

MAP/BK00_SKY.RSC
  skydome.txd
  Sky_Bike*.dff
```

## TRA container notes

All 3444 `.TRA` files parsed as table-based containers.  The table points to
payload sections, and some payload sections are nested TRA containers.

Recursive TRA content summary from the audit:

```text
TXD payloads: 2462
DFF payloads: 607
nested TRA payloads: 506
raw/other payloads: 13682
```

Typical examples:

```text
TSCENE/AB/R01A0000.TRA
  table header
  embedded TXD at 0x60

BIKE/MODEL_AA.TRA
  embedded DFF payloads

CHAR/*_DATA.TRA
  nested TRA and character TXD/DFF payloads
```

## Non-container checks

The audit also scanned non-`RSC`/`TRA` files for valid RenderWare TXD/DFF
payloads.  No precise valid RenderWare payloads were found outside the known
direct TXD/DFF files and the `RSC`/`TRA` containers.

Notes:

```text
.ADX  audio, false-positive byte patterns only
.PSS  video
.ANM  standalone RenderWare animation chunks
.ADO  ADS scripts/control data
.BIN/.DAT/.CLI  mostly script/control/data tables, no valid TXD/DFF payloads found
```

## Known localization candidates found after audit

The 2026-05-29 embedded TXD visual pass found these production candidates:

```text
DATA/TSCENE/EV126_00.TRA .. DATA/TSCENE/EV131_00.TRA
  Chapter/interstitial title cards.
  Embedded TXD offset: 0x40.
  Five 256x256 16bpp tiles per file.

DATA/MENU/SUB_ST_A.RSC .. DATA/MENU/SUB_ST_E.RSC
  Status/upgrade UI labels.

DATA/KFI_*.RSC and DATA/KFI_KIJIN_01.RSC .. DATA/KFI_KIJIN_50.RSC
  Museum record pages, especially tex_kfi_tx_* texture entries.
```

Detailed candidate notes and diagnostic contact-sheet paths are tracked in
`reports/texture_localization_candidates.md`.

## Future work

1. Add tools to recursively list and extract `RSC` entries without modifying
   the original container.
2. Add tools to recursively list and extract `TRA` payloads.
3. Export embedded TXD payloads to a separate workspace, for example:

```text
dump_jp/EXPORT_EMBEDDED_TXD/
```

4. Continue visual contact-sheet review for embedded TXDs; chapter title cards,
   `SUB_ST_*`, and `KFI_*` are already recorded as candidates.
5. Keep replacement work separate from direct TXD replacement.  Repacking
   embedded TXDs requires writing them back into their owning `RSC` or `TRA`
   container, then staging the rebuilt container file.

## Important distinction

The old `game_dump` is a complete file dump.  The missing work is nested
resource extraction, not missing files from the disc.
