# Reverse Engineering Notes

## ELF symbols

Main game ELF:

- `game_dump/SLPS_253.02`

The ELF contains a `.symtab`, so many function and global variable names are
available directly from the game binary.

Useful examples:

- `avGameSave`
- `g_Wk`
- `afCharacterSetLife`
- `afItem*`
- `afMenuItem*`

## Inventory / save data

`avGameSave` is a global game-save/progress structure in RAM, not an emulator
save state.

- `avGameSave = 0x0041f110`
- size: `0xd008`

Known candidate inventory/item fields:

- `0x00424c86 = avGameSave + 0x5b76`
- `0x00424d5e = avGameSave + 0x5c4e`

Both addresses are inside `avGameSave`. They are not function addresses.

Notes:

- These addresses are not 32-bit aligned.
- They are plausibly byte or 16-bit fields.
- Direct fixed-offset references were not found in the quick check, so the game
  may access them through computed pointers/indexes.

### Key item IDs

Observed key-item slot values match `ITEM_GET_MSG.json` indices directly.

Sources:

- `translation_en/DATA/MENU/ITEM_GET_MSG.json` contains short item names.
- `translation_en/DATA/MENU/ITEM_MSG.json` contains item descriptions.

For the main key-item range:

- slot value `0x03e8` equals decimal `1000`, matching `ITEM_GET_MSG[1000]`
- corresponding description is usually `ITEM_MSG[1]`
- in general for this range: `ITEM_MSG index = ITEM_GET_MSG index - 999`

Known key-item values:

```text
0x03e8 | Lever
0x03e9 | Plant ID Card LV2
0x03ea | Plant ID Card LV1
0x03eb | Elevator Start Key
0x03ec | Shocker Card
0x03ed | Shocker Card
0x03ee | Gas Room Key
0x03ef | Shocker Card
0x03f0 | Elevator Start Key
0x03f1 | Unlock Key / Central Control Room
0x03f2 | Unlock Key / Substation Room
0x03f3 | Unlock Key / A6
0x03f4 | Power Routing Key
0x03f5 | Bulkhead Key
0x03f6 | Escape Key
0x03f7 | Jumper Cable
0x03f8 | Turbine Room Key
0x03f9 | Red Punch Card
0x03fa | Blue Punch Card
0x03fb | Green Punch Card
0x03fc | Magnetic Key
0x03fd | Tape Recorder
0x03fe | Cassette Recorder
0x03ff | Small Cassette Recorder
0x0400 | IC Recorder
0x0401 | Passcode Blank
0x0402 | Passcode Failed
0x0403 | Barcode Key
0x0404 | IC Chip Card
0x0405 | Data Stick
0x0406 | Gold Plate
0x0407 | Green Plate
0x0408 | Black Plate
0x0409 | Shocker Medal
0x040a | Machine Key
0x040b | Plant ID Card LV1
0x040c | Gravity Stop Card
0x040d | Gold Plate
0x040e | Shocker Key
```

Other inventory-like value ranges seen in `ITEM_GET_MSG.json`:

```text
0x07d1 | Life Pack L
0x07d2 | Rider Energy S
0x07d3 | Rider Energy L
0x07d4 | Life Pack S
0x0bb8 | Hint File
0x0bb9 | File Folder
0x0bba | Operation Orders
0x0bbb | Operation Orders
0x0fa0 | Monster File
0x0fa1 | Monster File
```

## Character life / health

The game appears to name health as `Life`.

Relevant symbols:

- `afCharacterSetLife`
- `g_iCombatantLifeTable`
- `RiderBikeLife`
- `afGaugeDrawPlayer`
- `afGaugeDrawBoss`
- `afGaugeDrawBike`

`afCharacterSetLife`:

- function address: `0x001c0600`
- file offset in `game_dump/SLPS_253.02`: `0x0c0680`
- size: `0x30`

Confirmed logic from `afCharacterSetLife`:

```asm
0x001c0600: lw  v0, 0x6378(a0)   ; max life
0x001c0610: sw  v0, 0x6374(a0)   ; clamp current life to max
0x001c0620: sw  a1, 0x6374(a0)   ; set current life
```

Confirmed fields:

- `character_base + 0x6374 = current life`
- `character_base + 0x6378 = max life`

Observed player/work address:

- `0x0044bae4 = g_Wk + 0x6374 = current life`
- `0x0044bae8 = g_Wk + 0x6378 = max life`
- `g_Wk = 0x00445770`

This means the observed health address is inside global `g_Wk`, not a random
heap allocation.

## Quick workflow for future addresses

For a runtime address:

1. Check which ELF symbol range contains it.
2. Compute `address - symbol_base`.
3. Search code for nearby field offsets.
4. If a setter/getter exists, inspect its load/store offsets.
5. For data fields, record address, size, suspected meaning, and base symbol.

For code addresses:

- Prefer 32-bit aligned addresses.

For data addresses:

- Exact address is useful.
- Also note the value size when known: byte, 16-bit, or 32-bit.
