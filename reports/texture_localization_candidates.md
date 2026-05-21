# Texture localization candidates

Date: 2026-05-21

This list is a visual inventory of exported TXD PNGs that appear to contain
Japanese text or text-like graphic elements.  It intentionally excludes item
icons and ordinary material textures unless there is visible Japanese text in
the image.

Temporary visual review sheets were generated under:

```text
build/texture_localization_inventory/
```

## Already completed

Title-screen background:

```text
textures_en/EXPORT_TXD/TITLE_title_00_00.png
textures_en/EXPORT_TXD/TITLE_title_00_01.png
textures_en/EXPORT_TXD/TITLE_title_00_02.png
textures_en/EXPORT_TXD/TITLE_title_00_03.png
textures_en/EXPORT_TXD/TITLE_title_00_04.png
```

Status: accepted in-game.  Do not treat these as draft/test targets.

## High-priority candidates

### Warning screen

Japanese disclaimer text split across five 256x256 tiles:

```text
dump_jp/EXPORT_TXD/WARNING_00.png
dump_jp/EXPORT_TXD/WARNING_01.png
dump_jp/EXPORT_TXD/WARNING_02.png
dump_jp/EXPORT_TXD/WARNING_03.png
dump_jp/EXPORT_TXD/WARNING_04.png
```

### Mission / event telops

Large Japanese splash text, likely shown during scenario or objective changes.
These are two-tile 512x256 banners: `_1` is the left half and `_2` is the
right half.

```text
TELOP_A_TEX: tex_te_01_1 + tex_te_01_2
TELOP_B_TEX: tex_te_02_1 + tex_te_02_2
TELOP_C_TEX: tex_te_03_1 + tex_te_03_2
TELOP_D_TEX: tex_te_04_1 + tex_te_04_2
TELOP_E_TEX: tex_te_05_1 + tex_te_05_2
```

Working visual review sheet:

```text
build/texture_localization_inventory/telop_chapter_composed.png
```

Rough visible meanings:

```text
TELOP_A_TEX: Defeat the Shocker biker unit.
TELOP_B_TEX: Break through the Shocker minefield.
TELOP_C_TEX: Annihilate the red combatants.
TELOP_D_TEX: Break through Shocker's trap.
TELOP_E_TEX: Dodge/avoid Shocker's attack and pursue.
```

### Battle telops

Japanese battle-result/objective banners.  These include repeated common
messages such as battle start, victory, and defeat plus one unique objective
per battle telop TXD.

Unlike `TELOP_A_TEX` through `TELOP_E_TEX`, these exported PNGs are already
full 512x256 textures and do not need left/right tile composition.

```text
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_01_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_02_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_03_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_04_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_05_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_06_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_07_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_08_TEX_*.png
dump_jp/EXPORT_TXD/MENU/TELOP_BATTLE_09_TEX_*.png
```

Concrete exported files:

```text
TELOP_BATTLE_01_TEX_telop_battle_01.png
TELOP_BATTLE_01_TEX_telop_battle_02.png
TELOP_BATTLE_01_TEX_telop_battle_03.png
TELOP_BATTLE_01_TEX_telop_battle_04.png
TELOP_BATTLE_02_TEX_telop_battle_01.png
TELOP_BATTLE_02_TEX_telop_battle_02.png
TELOP_BATTLE_02_TEX_telop_battle_03.png
TELOP_BATTLE_02_TEX_telop_battle_05.png
TELOP_BATTLE_03_TEX_telop_battle_01.png
TELOP_BATTLE_03_TEX_telop_battle_02.png
TELOP_BATTLE_03_TEX_telop_battle_03.png
TELOP_BATTLE_03_TEX_telop_battle_06.png
TELOP_BATTLE_04_TEX_telop_battle_01.png
TELOP_BATTLE_04_TEX_telop_battle_02.png
TELOP_BATTLE_04_TEX_telop_battle_03.png
TELOP_BATTLE_04_TEX_telop_battle_07.png
TELOP_BATTLE_05_TEX_telop_battle_01.png
TELOP_BATTLE_05_TEX_telop_battle_02.png
TELOP_BATTLE_05_TEX_telop_battle_03.png
TELOP_BATTLE_05_TEX_telop_battle_08.png
TELOP_BATTLE_06_TEX_telop_battle_01.png
TELOP_BATTLE_06_TEX_telop_battle_02.png
TELOP_BATTLE_06_TEX_telop_battle_03.png
TELOP_BATTLE_06_TEX_telop_battle_09.png
TELOP_BATTLE_07_TEX_telop_battle_01.png
TELOP_BATTLE_07_TEX_telop_battle_02.png
TELOP_BATTLE_07_TEX_telop_battle_03.png
TELOP_BATTLE_07_TEX_telop_battle_10.png
TELOP_BATTLE_08_TEX_telop_battle_01.png
TELOP_BATTLE_08_TEX_telop_battle_02.png
TELOP_BATTLE_08_TEX_telop_battle_03.png
TELOP_BATTLE_08_TEX_telop_battle_11.png
TELOP_BATTLE_09_TEX_telop_battle_01.png
TELOP_BATTLE_09_TEX_telop_battle_02.png
TELOP_BATTLE_09_TEX_telop_battle_03.png
TELOP_BATTLE_09_TEX_telop_battle_12.png
```

Working visual review sheet:

```text
build/texture_localization_inventory/telop_battle_grouped.png
```

Common repeated banners:

```text
telop_battle_01: Battle Start
telop_battle_02: Victory
telop_battle_03: Defeat
```

Unique objective banners:

```text
telop_battle_04: Defeat 100 Shocker combatants.
telop_battle_05: Defeat 10 Shocker scientists.
telop_battle_06: Defeat 30 red combatants.
telop_battle_07: Defeat 50 black combatants.
telop_battle_08: Defeat 70 Gel-Shocker combatants.
telop_battle_09: Defeat 15 Gel-Shocker scientists.
telop_battle_10: Defeat 15 black combatant strengthened forms.
telop_battle_11: Defeat 20 red combatant strengthened forms.
telop_battle_12: Defeat 25 wolf-man test subjects.
```

## Needs project decision

### Staff roll / credits

These contain Japanese staff role labels, names, and company credits.  Whether
to localize them depends on project scope.  If credits localization is in
scope, treat the full `STAF00` through `STAF11` tile sets as candidates:

```text
dump_jp/EXPORT_TXD/STAF00_00.png .. STAF00_04.png
dump_jp/EXPORT_TXD/STAF01_00.png .. STAF01_04.png
dump_jp/EXPORT_TXD/STAF02_00.png .. STAF02_04.png
dump_jp/EXPORT_TXD/STAF03_00.png .. STAF03_04.png
dump_jp/EXPORT_TXD/STAF04_00.png .. STAF04_04.png
dump_jp/EXPORT_TXD/STAF05_00.png .. STAF05_04.png
dump_jp/EXPORT_TXD/STAF06_00.png .. STAF06_04.png
dump_jp/EXPORT_TXD/STAF07_00.png .. STAF07_04.png
dump_jp/EXPORT_TXD/STAF08_00.png .. STAF08_04.png
dump_jp/EXPORT_TXD/STAF09_00.png .. STAF09_04.png
dump_jp/EXPORT_TXD/STAF10_00.png .. STAF10_04.png
dump_jp/EXPORT_TXD/STAF11_00.png .. STAF11_04.png
```

### Environmental sign

Only obvious Japanese text found in the `BIKE` texture sheet:

```text
dump_jp/EXPORT_TXD/BIKE/RESOURCEBC_r33b0074.png
```

Visible text appears to be `セメント`.  This is probably an in-world material or
sign texture, not UI.  Localize only if environmental text localization is in
scope.

## Probably not localization targets

Item icons and item atlas:

```text
dump_jp/EXPORT_TXD/MENU/TEX_IT_000_tex_it_000.png
dump_jp/EXPORT_TXD/MENU/TEX_K_IT_001_tex_k_it_001.png .. TEX_K_IT_039_tex_k_it_039.png
```

Reason: item names/descriptions are handled by text data.  The icons themselves
are mostly objects, cards, files, keys, and devices; several already use English
labels such as `ID CARD`.

Menu/result graphics that are already Latin/rank-only:

```text
dump_jp/EXPORT_TXD/MENU/SUB_RESULT_01_tex_result_01.png
dump_jp/EXPORT_TXD/MENU/TELOP_BIKE_RUNK_TEX_tex_history_02.png
```

Title menu option graphics:

```text
dump_jp/EXPORT_TXD/TITLE_title_01.png
dump_jp/EXPORT_TXD/TITLE_title_02.png
dump_jp/EXPORT_TXD/TITLE_title_03.png
dump_jp/EXPORT_TXD/TITLE_title_04.png
```

Reason: these are already English/rank graphics or non-text menu art.

Middleware/company logo screens:

```text
dump_jp/EXPORT_TXD/LOGO_00_*.png
dump_jp/EXPORT_TXD/LOGO_01_*.png
dump_jp/EXPORT_TXD/LOGO_02_*.png
dump_jp/EXPORT_TXD/LOGO_03_*.png
dump_jp/EXPORT_TXD/LOGO_04_*.png
```

Reason: ADX, RenderWare, Banpresto, Cavia, XAX, and related logos are not
translation targets.

Font atlas:

```text
dump_jp/EXPORT_TXD/FONT_font_00.png .. FONT_font_13.png
```

Reason: this is glyph infrastructure, not authored screen text.  Change only if
the font/glyph pipeline requires it.

Most `BIKE/RESOURCE*`, `BIKE/SKY*`, `SHADOW_kage.png`:

Reason: these are material, sky, shadow, and environment textures without
visible Japanese text, except `BIKE/RESOURCEBC_r33b0074.png` noted above.
