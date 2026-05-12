"""Dump all DAT-like Japanese text tables to JSON.

The output mirrors paths under ``game_dump/DATA`` into ``dump_jp`` and stores
    each DAT entry as ``idx``, ``text_jp``, an empty ``text_en`` placeholder,
    and raw ``codes`` for exact Japanese round-trip rebuilds.
Control codes are decoded as:

* ``0x8000`` -> ``{END}``
* ``0x8100`` -> newline
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from font_mapping import decode_codes, find_dat_like_files, project_path, read_dat_entries


CORRECTED_FONT_MAP_PATH = Path("localization/font_maps/font_map_corrected.json")
DEFAULT_ROOT = Path("game_dump/DATA")
DEFAULT_OUTPUT_ROOT = Path("dump_jp")


def load_corrected_font_map(path: Path = CORRECTED_FONT_MAP_PATH) -> dict[int, str]:
    """Load the reviewed ``code -> char`` map used by localization tools."""

    with project_path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)
    return {int(code, 16): char for code, char in data.items()}


def output_path_for_dat(path: str, root: Path, output_root: Path) -> Path:
    """Return the JSON output path for a source DAT path."""

    root_path = project_path(root)
    relative = project_path(path).relative_to(root_path.parent)
    return project_path(output_root) / relative.with_suffix(".json")


def dump_dat(path: str, code_to_char: Mapping[int, str]) -> tuple[list[dict[str, object]], int]:
    """Decode one DAT-like file into JSON-ready records."""

    records: list[dict[str, object]] = []
    unknown_entries = 0
    for idx, codes in read_dat_entries(path):
        text, unknown_count = decode_codes(codes, code_to_char)
        if unknown_count:
            unknown_entries += 1
        records.append(
            {
                "idx": idx,
                "text_jp": text,
                "text_en": "",
                "codes": [f"{code:04X}" for code in codes],
            }
        )
    return records, unknown_entries


def write_json(path: Path, records: list[dict[str, object]]) -> None:
    """Write a compact, readable UTF-8 JSON text dump."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Root directory to scan for DAT-like files")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory to write JSON dumps")
    parser.add_argument("--font-map", default=str(CORRECTED_FONT_MAP_PATH), help="Corrected code -> char JSON map")
    args = parser.parse_args()

    root = Path(args.root)
    output_root = Path(args.output_root)
    code_to_char = load_corrected_font_map(Path(args.font_map))
    dat_paths = find_dat_like_files(root)
    total_entries = 0
    unknown_entries = 0

    for dat_path in dat_paths:
        records, file_unknown_entries = dump_dat(dat_path, code_to_char)
        write_json(output_path_for_dat(dat_path, root, output_root), records)
        total_entries += len(records)
        unknown_entries += file_unknown_entries

    print(f"DAT-like files dumped: {len(dat_paths)}")
    print(f"Entries dumped: {total_entries}")
    print(f"Entries with unknown glyphs: {unknown_entries}")
    print(f"Wrote {output_root}")

    return 1 if unknown_entries else 0


if __name__ == "__main__":
    raise SystemExit(main())
