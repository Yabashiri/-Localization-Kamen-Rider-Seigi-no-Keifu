# Current text layout status

Date: 2026-05-13

## Short version

Do not continue trying to fix the current cutscene / lower message-box bug with
more word-wrap changes.

The active blocker is the text start X / anchoring of the lower textbox
renderer. Long English lines begin off the left side of the screen. Short lines
can look fine because centering/anchoring hides the issue for small strings.

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

## Current suspicion

The lower textbox renderer likely computes X from a center/right anchor or from
string width in a way that worked for Japanese but pushes long English strings
off-screen.

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

1. Leave wrap alone for the lower textbox.
2. Identify the call site or branch used by cutscene/field lower messages.
3. Patch or clamp the start X for that renderer so the first glyph starts
   inside the visible textbox.
4. Build a targeted diagnostic ISO for that ELF X/start-position patch only.

## Build caveat

The last interrupted build sequence only re-encoded `rebuilt_en`; it did not
finish staging DATA.CVM or rebuilding `build/out/kamen_rider_full_translation.iso`.
If the existing ISO was created during the failed wrap-16 test, it may still be
bad and should not be treated as a fresh baseline.
