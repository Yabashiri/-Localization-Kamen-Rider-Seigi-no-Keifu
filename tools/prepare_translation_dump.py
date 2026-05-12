"""Prepare an English translation working dump from the Japanese JSON dump.

The output mirrors ``dump_jp`` into ``translation_en`` and keeps only the
fields needed by translators:

* ``idx``
* ``text_jp``
* ``text_en``

Existing ``text_en`` values are preserved by ``idx`` when the script is rerun,
unless ``--overwrite`` is passed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from font_mapping import project_path


DEFAULT_INPUT_ROOT = Path("dump_jp")
DEFAULT_OUTPUT_ROOT = Path("translation_en")


def iter_json_paths(input_root: Path) -> list[Path]:
    """Return source JSON files in stable relative order."""

    root = project_path(input_root)
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def output_path_for_json(path: Path, input_root: Path, output_root: Path) -> Path:
    """Return the translation JSON output path for a source dump path."""

    relative = path.relative_to(project_path(input_root))
    return project_path(output_root) / relative


def load_existing_text_en(path: Path) -> dict[int, str]:
    """Load existing English strings by idx so reruns do not erase work."""

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    existing: dict[int, str] = {}
    for record in records:
        if not isinstance(record, dict) or "idx" not in record:
            continue
        text_en = record.get("text_en")
        if isinstance(text_en, str) and text_en:
            existing[int(record["idx"])] = text_en
    return existing


def prepare_records(source_records: list[dict[str, Any]], existing_text: dict[int, str]) -> list[dict[str, object]]:
    """Convert Japanese dump records to translator-facing records."""

    prepared: list[dict[str, object]] = []
    for record in source_records:
        idx = int(record["idx"])
        prepared.append(
            {
                "idx": idx,
                "text_jp": str(record["text_jp"]),
                "text_en": existing_text.get(idx, ""),
            }
        )
    return prepared


def write_json(path: Path, records: list[dict[str, object]]) -> None:
    """Write a readable UTF-8 JSON translation file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT), help="Directory containing Japanese JSON dumps")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory to write translation JSON files")
    parser.add_argument("--overwrite", action="store_true", help="Clear existing text_en values instead of preserving them")
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    json_paths = iter_json_paths(input_root)
    total_entries = 0
    preserved_entries = 0

    for json_path in json_paths:
        output_path = output_path_for_json(json_path, input_root, output_root)
        existing_text = {} if args.overwrite else load_existing_text_en(output_path)

        with json_path.open("r", encoding="utf-8") as file:
            source_records = json.load(file)

        records = prepare_records(source_records, existing_text)
        write_json(output_path, records)
        total_entries += len(records)
        preserved_entries += sum(1 for record in records if record["text_en"])

    print(f"Translation JSON files prepared: {len(json_paths)}")
    print(f"Entries prepared: {total_entries}")
    print(f"Existing translations preserved: {preserved_entries}")
    print(f"Wrote {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
