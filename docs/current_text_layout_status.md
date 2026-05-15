# Current text layout status

Date: 2026-05-15

## Short version

Resolved. Do not continue trying to fix the cutscene / lower message-box bug
with more word-wrap changes.

The active fix is the ELF-side scenario centering clamp in
`tools/patch_elf_text_spacing.py`. Long English lines now start inside the
visible lower textbox instead of being pushed off the left side.

Tested working in PCSX2 on 2026-05-15 with:

```text
build/out/kamen_rider_full_translation.iso
```

Observed fixed lines include:

```text
That feeling right now... What
was it?

Kamen Rider, soon we will show
you our true power.
```

## What worked

- Per-DAT wrap profiles fixed the menu regression caused by one global wrap.
- Menu option/help rows must stay unwrapped:
  - `DATA/MENU/CONFIG_MSG.json`: 0
  - `DATA/MENU/FIELD_NAME.json`: 0
  - `DATA/MENU/ITEM_GET_MSG.json`: 0
- Item/status descriptions can still use controlled wrapping:
  - `DATA/MENU/ITEM_MSG.json`: 22
  - `DATA/MENU/STATUS_MSG.json`: 22

## What failed

- Global wrap did not fix the lower textbox start position.
- Aggressive wrap for `DATA/SCREVENT/MSG/` made things worse. A test with wrap
  16 caused missing/fragmented cutscene lines and did not address the left-edge
  start-position bug.
- `DATA/SCREVENT/MSG/` is back to 32 columns only as a guard for very long
  strings. Do not reduce this again as a "fix" for the current bug.

## Evidence

- The same left clipping reproduced in a diagnostic ISO without the Latin
  spacing patch.
- Diagnostic no-spacing ELF byte at the known advance patch location was:
  `e041033c`.
- Full Latin-spacing patch changes that same location to:
  `6041033c`.
- Because the no-spacing diagnostic still clipped the left side, the lower
  textbox issue is not caused only by `tools/patch_elf_text_spacing.py
  --advance 14`.
- A temporary ELF-only diagnostic ISO used original `game_dump/DATA.CVM`; that
  image has no translation and should not be used to verify translated text.
- The confirmed working image was rebuilt from `translation_en` with
  `--wrap-profile game` and the patched ELF.

## Root cause found

The lower textbox renderer computes an X centering correction in
`afScenarioMsgKind`:

```text
x += (18 - maxLineLen) * 14
```

This worked for short Japanese lines. For English lines longer than 18 glyphs,
the correction becomes negative and pushes the text start off the left side of
the lower message box.

`tools/patch_elf_text_spacing.py` now also patches this scenario centering code.
The replacement keeps the original centering for short lines but clamps the
correction to zero for long lines:

```text
x += max(18 - maxLineLen, 0) * 14
```

The patch starts at vaddr `0x171180`, file offset `0x71200`.

Item/status descriptions use a different path. `afMenuItemMessageDraw` and
`afMenuStatusMessageDraw` call `afMsgDraw` with fixed coordinates around
X=`108`, Y=`326`; they do not use the `afScenarioMsgKind` centering correction.
If those descriptions overflow their boxes, handle them with item/status wrap
profiles or manual line breaks instead of changing the scenario anchor patch.

Known ELF investigation notes:

- Central text draw-ish function appears near vaddr `0x169b20`.
- Current Latin advance patch touches file offset `0x69ffc`, vaddr `0x169f7c`.
- Original `lui`/float-28 pattern `e041033c` appears at nearby offsets:
  `0x69f88`, `0x69fb0`, `0x69ffc`.
- Other occurrences include:
  `0x69770`, `0x717c0`, `0x1e4ab8`, `0x213a44`, `0x213a70`,
  `0x213ad0`, `0x213b6c`.
- Calls to vaddr `0x169b20` were seen near bottom-message-looking code around:
  `0x71758`, `0x717d8`, `0x71800`, `0x20fef8`, `0x20ff30`,
  `0x20ff78`, `0x20ffb4`, `0x210054`, `0x21008c`, `0x2100c4`,
  `0x213a64`, `0x213a90`, `0x213ac4`, `0x213af0`.

## Next useful work

1. Keep `--wrap-profile game` for full translated builds.
2. Leave wrap alone for the lower textbox.
3. If item/status descriptions still misplace text, treat that as a separate
   renderer path; do not change the scenario patch to compensate.

## Build caveat

The current known-good translated ISO was built on 2026-05-15:

```text
python tools\encode_all_text.py --input-root translation_en --output-root rebuilt_en --wrap-profile game
python tools\hint_bin.py build
python tools\stage_rebuilt_text.py
python tools\build_data_iso.py
python tools\build_data_cvm.py
python tools\patch_elf_text_spacing.py --advance 14
python tools\build_patched_iso.py --patched-elf build/stage/SLPS_253.02 --output-iso build/out/kamen_rider_full_translation.iso
```

Final verification:

```text
iso_size 3915411456
advance_14 6041033c OK
scenario_anchor_clamp 232085002a0880000019040023186400231864000b180100000883446008804606080046 OK
```
