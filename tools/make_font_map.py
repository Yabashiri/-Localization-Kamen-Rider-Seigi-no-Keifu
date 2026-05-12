"""Generate and verify the hybrid Kamen Rider DAT font map."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from font_mapping import collect_used_codes, find_dat_like_files, load_font_map, project_path


GENERATED_PATH = Path("localization/font_maps/font_map.generated.json")
CORRECTED_PATH = Path("localization/font_maps/font_map_corrected.json")


def write_font_map(path: Path, code_to_char: dict[int, str]) -> None:
    """Write ``code -> char`` map as fixed-width uppercase hex JSON keys."""

    output_path = project_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {f"{code:04X}": code_to_char[code] for code in sorted(code_to_char)}
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(serializable, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="game_dump/DATA", help="Root directory to scan for DAT-like files")
    parser.add_argument(
        "--overwrite-corrected",
        action="store_true",
        help="Overwrite localization/font_maps/font_map_corrected.json with the generated map",
    )
    args = parser.parse_args()

    code_to_char = load_font_map()
    write_font_map(GENERATED_PATH, code_to_char)
    print(f"Wrote {GENERATED_PATH} ({len(code_to_char)} glyph mappings)")

    generated_path = project_path(GENERATED_PATH)
    corrected_path = project_path(CORRECTED_PATH)
    if corrected_path.exists() and not args.overwrite_corrected:
        print(f"Kept existing {CORRECTED_PATH} (use --overwrite-corrected to replace)")
    else:
        corrected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(generated_path, corrected_path)
        print(f"Wrote {CORRECTED_PATH} from generated map")

    dat_paths = find_dat_like_files(args.root)
    used_codes, control_codes = collect_used_codes(dat_paths)
    missing_codes = {code: count for code, count in used_codes.items() if code not in code_to_char}

    print()
    print("=== DAT-like coverage audit ===")
    print(f"DAT-like files: {len(dat_paths)}")
    print(f"Used glyph codes: {len(used_codes)}")
    if used_codes:
        print(f"min code: 0x{min(used_codes):04X}")
        print(f"max code: 0x{max(used_codes):04X}")
    print("Control codes:")
    if control_codes:
        for code, count in control_codes.most_common():
            print(f"  0x{code:04X}: {count}")
    else:
        print("  none")
    print(f"Missing glyph codes: {len(missing_codes)}")

    if missing_codes:
        print("Top missing:")
        for code, count in sorted(missing_codes.items(), key=lambda item: (-item[1], item[0]))[:30]:
            print(f"  0x{code:04X}: {count}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

