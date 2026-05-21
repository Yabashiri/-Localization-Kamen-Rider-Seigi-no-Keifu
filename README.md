# Kamen Rider: Seigi no Keifu English Translation Tools

This repository contains my working files, scripts, notes, translated text, and
localized assets for an English localization effort for the PlayStation 2 game
*Kamen Rider: Seigi no Keifu*.

The repository is focused on translation and reverse-engineering support work:
text dumping, text encoding, font mapping, DAT rebuilding, texture localization
experiments, and ISO staging scripts. It does not include original disc images,
raw game dumps, or extracted copyrighted game assets.

## Special for RetroAchievements

This project is made by me, Yabashiri, specifically for RetroAchievements.

- My RetroAchievements profile: <https://retroachievements.org/user/Yabashiri>
- RetroAchievements game page: <https://retroachievements.org/game/31667>

## Repository Layout

```text
docs/             Research notes, pipeline plans, and current implementation status.
localization/     Font maps and localization metadata used by the tools.
reports/          Audits, cleanup notes, and generated review reports that are safe to track.
textures_en/      Localized English texture workspace and trackable texture assets.
tools/            Python scripts for dumping, encoding, rebuilding, patching, and inspection.
translation_en/   English translation JSON files.
```

## Current Text Pipeline

The text pipeline is built around DAT-like files extracted from the game:

```text
original DAT -> Japanese JSON dump -> English JSON -> rebuilt DAT
```

The main scripts are:

```text
python tools\dump_all_text.py
python tools\prepare_translation_dump.py
python tools\encode_all_text.py --input-root translation_en --output-root rebuilt_en --wrap-profile game
python tools\stage_rebuilt_text.py
```

The current known-good full build flow is documented in
`docs/current_text_layout_status.md`. That document also describes the active
ELF-side text layout patch used for English scenario text.

## Texture Work

The title-screen background texture is localized and has a known-good 16bpp
TXD import path. Other indexed texture replacement work is still experimental.
See `docs/txd_localization_plan.md` for the current TXD notes and status.

## Requirements

The tools are plain Python scripts. They are intended to run on a local checkout
that also has a personal dump of the game available in ignored working folders.

This repository does not provide:

- A game ISO.
- Extracted game files.
- Third-party disc or CVM tools.
- Emulator binaries.

## Copyright and License

This repository uses different licenses for code and creative/project content:

- Code and scripts are licensed under the MIT License.
- Translation text, localized texture work, documentation, reports, localization
  metadata, and other non-code project content are licensed under Creative
  Commons Attribution 4.0 International (CC BY 4.0).

These licenses apply only to my original work in this repository.

The game, its assets, names, code, and other copyrighted material remain the
property of their respective rightsholders and are not distributed here. These
licenses do not grant any rights to the original game or any locally dumped game
assets.
