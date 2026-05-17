# Translation cleanup plan

Updated: 2026-05-16

## Current priority

Continue manual translation of non-EV `translation_en/DATA/SCREVENT/MSG/*.json` placeholder strings.

## Rules to preserve while translating

- Preserve the Japanese message geometry: keep the same number of visible lines as `text_jp` whenever possible.
- Keep short one-line object messages as one line; do not expand them into explanatory two-line prose.
- Keep two-line Japanese messages as two-line English messages unless the game text becomes unreadable.
- Preserve UI choice formatting with arrow selection. Do not use `Select` as the visible choice marker.
- Use the real arrow glyph `→`; do not use ASCII `->` because `>` is not encodable in the current font map.
- Keep translated choice rows close to the Japanese layout, especially files like `R01B.json`.
- Do not mechanically normalize `\n` line breaks while doing the formatting pass; English wrapping is already adapted separately.
- Audit Japanese visual indentation beyond choice rows: leading/trailing fullwidth spaces, centered titles, padded menu/HINT pages, stretched shout lines, and plus/minus selectors. Recreate the same visual intent in `text_en` with encodable ASCII spaces, then verify through `tools/encode_all_text.py`.
- Current scan found no literal tab characters in `translation_en/DATA`; treat "tabs" as large visual spacing/padding unless a real `\t` appears later.
- For Yes/No choice rows, keep the arrow marker and review whether the visible English should use compact `Yes`/`No` or Russian `Да`/`Нет`; do not leave `Select`.
- Preserve visible continuation/end glyph records: when `text_jp` is `↓{END}` (usually `idx: 1000`), `text_en` must also be `↓{END}`, not `v{END}` or `End`.
- Avoid placeholder-like generic English such as `Check this place`, `Nothing useful here`, and `There is a device here...` unless the Japanese really says that.

## Known issues to fix/check

- Review all current uncommitted non-EV changes for line-count drift between `text_jp` and `text_en`.
- Re-check choice rows changed from `Select Yes   No` / `Yes   Select No` so they render with arrow selection and stable spacing.
- Re-check non-choice padded layout rows, especially `translation_en/DATA/MENU/HINT.json`, `MEMCARD.json`, centered EV title/shout rows, and `R19DENJIROCK.json` plus/minus selector rows.
- Replace translated `v{END}` continuation glyph rows with the original down arrow `↓{END}` wherever the Japanese row is `↓{END}`.
- Re-run the placeholder report after the current translation pass; the existing `reports/remaining_placeholders.tsv` is stale and still lists old `Select`/placeholder rows.
- Run `tools/encode_all_text.py` after cleanup to catch unencodable characters before committing.
- Commit clean translation/report chunks without push when the batch is verified.
