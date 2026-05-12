"""Audit real DAT glyph usage against the current corrected font map.

The report is intended for manual proofreading of OCR/manual glyph-table
mistakes.  For every actually used glyph code it lists the current character,
usage count, and a handful of decoded context examples.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Iterable, Mapping

from font_mapping import (
    CONTROL_CODES,
    collect_used_codes,
    decode_codes,
    find_dat_like_files,
    load_font_map,
    project_path,
    read_dat_entries,
)


CORRECTED_FONT_MAP_PATH = Path("localization/font_maps/font_map_corrected.json")
DEFAULT_OUTPUT_PATH = Path("reports/font_usage.tsv")


def load_corrected_font_map() -> dict[int, str]:
    """Load corrected ``code -> char`` map, falling back to generated sources."""

    path = project_path(CORRECTED_FONT_MAP_PATH)
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return {int(code, 16): char for code, char in data.items()}
    return load_font_map()


def shorten_example(text: str, limit: int) -> str:
    """Make decoded text safe for one-line TSV output and trim long samples."""

    one_line = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\n")
    one_line = one_line.replace("\t", " ")
    if len(one_line) <= limit:
        return one_line
    if limit <= 1:
        return "…"[:limit]
    return one_line[: limit - 1].rstrip() + "…"


def add_examples_for_codes(
    examples: DefaultDict[int, list[str]],
    codes: Iterable[int],
    label: str,
    max_examples: int,
) -> None:
    """Attach a decoded entry label to each glyph code seen in that entry."""

    for code in sorted({code for code in codes if code < 0x8000}):
        code_examples = examples[code]
        if len(code_examples) >= max_examples or label in code_examples:
            continue
        code_examples.append(label)


def write_usage_report(
    output_path: Path,
    code_to_char: Mapping[int, str],
    used_codes: Counter[int],
    examples: Mapping[int, list[str]],
) -> None:
    """Write glyph usage rows sorted by code as a TSV file."""

    resolved_output_path = project_path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

    with resolved_output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter="\t", lineterminator="\n")
        writer.writerow(["code", "char", "count", "examples"])
        for code in sorted(used_codes):
            writer.writerow(
                [
                    f"{code:04X}",
                    code_to_char.get(code, f"[0x{code:04X}]"),
                    used_codes[code],
                    " | ".join(examples.get(code, [])),
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="game_dump/DATA", help="Root directory to scan for DAT-like files")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="TSV report path to write")
    parser.add_argument("--max-examples", type=int, default=5, help="Maximum examples to keep per glyph code")
    parser.add_argument("--example-limit", type=int, default=160, help="Maximum characters per example")
    args = parser.parse_args()

    code_to_char = load_corrected_font_map()
    dat_paths = find_dat_like_files(args.root)
    used_codes, control_codes = collect_used_codes(dat_paths)
    missing_codes = {code: count for code, count in used_codes.items() if code not in code_to_char}
    examples: DefaultDict[int, list[str]] = defaultdict(list)
    unknown_entries = 0

    for path in dat_paths:
        for idx, codes in read_dat_entries(path):
            decoded, unknown_count = decode_codes(codes, code_to_char)
            if unknown_count:
                unknown_entries += 1
            label = f"{path}[{idx}]: {shorten_example(decoded, args.example_limit)}"
            add_examples_for_codes(examples, codes, label, args.max_examples)

    write_usage_report(Path(args.output), code_to_char, used_codes, examples)

    print(f"DAT-like files: {len(dat_paths)}")
    print(f"Used glyph codes: {len(used_codes)}")
    print("Control codes:")
    if control_codes:
        for code, count in sorted(control_codes.items()):
            name = CONTROL_CODES.get(code, "")
            suffix = f" {name!r}" if name else ""
            print(f"  0x{code:04X}: {count}{suffix}")
    else:
        print("  none")
    print(f"Missing glyph codes: {len(missing_codes)}")
    print(f"Entries with unknown glyphs: {unknown_entries}")
    print(f"Wrote {Path(args.output)}")

    if missing_codes:
        print("Top missing:")
        for code, count in sorted(missing_codes.items(), key=lambda item: (-item[1], item[0]))[:30]:
            print(f"  0x{code:04X}: {count}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())