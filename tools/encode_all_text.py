"""Rebuild DAT-like text tables from Japanese or translation JSON dumps.

The encoder reads JSON files created by ``dump_all_text.py`` or
``prepare_translation_dump.py`` and writes rebuilt DAT files without modifying
``game_dump``. It encodes:

* newline -> ``0x8100``
* ``{END}`` -> ``0x8000``
* ASCII letters/digits/spaces/punctuation -> available fullwidth equivalents

If a JSON string has no ``{END}``, the encoder appends one automatically. When
``text_en`` is empty and a record has ``codes`` from the Japanese dump, those
raw codes are used to preserve exact original glyph choices.
"""

from __future__ import annotations

import argparse
import json
import struct
import textwrap
from pathlib import Path
from typing import Iterable

from font_mapping import CONTROL_END, CONTROL_NEWLINE, project_path


CORRECTED_FONT_MAP_PATH = Path("localization/font_maps/font_map_corrected.json")
DEFAULT_INPUT_ROOT = Path("dump_jp")
DEFAULT_OUTPUT_ROOT = Path("rebuilt_jp")

ASCII_PUNCTUATION_FALLBACKS = {
    " ": "　",
    "+": "＋",
    "%": "％",
    ".": "．",
    ",": "、",
    "!": "！",
    "?": "？",
    ":": "：",
    ";": "；",
    "-": "ー",
    "(": "（",
    ")": "）",
    "/": "／",
    '"': "“",
}
ASCII_DIRECT_FONT_CODES = {
    **{str(digit): digit for digit in range(10)},
    **{chr(ord("A") + index): 0x0037 + index for index in range(26)},
    **{chr(ord("a") + index): 0x0100 + index for index in range(26)},
    " ": 0x000A,
    "+": 0x000B,
    "-": 0x000C,
    ":": 0x000D,
    ",": 0x000E,
    ".": 0x0010,
    "?": 0x0012,
    "!": 0x0013,
    '"': 0x0018,
    "'": 0x0019,
    "’": 0x0019,
    "‘": 0x0019,
    "`": 0x0019,
    "(": 0x001A,
    ")": 0x001B,
    "%": 0x0022,
    "<": 0x0020,
    ">": 0x0021,
    ";": 0x002D,
    "/": 0x002F,
    "$": 0x0031,
    "=": 0x0036,
}

DEFAULT_WRAP_COLUMNS = 0

WRAP_PROFILES = {
    "none": (),
    "game": (
        # Menu option/help text is drawn in fixed rows; injected newlines make
        # different records overlap. Keep these single-line unless a string is
        # manually broken in translation_en.
        ("DATA/MENU/CONFIG_MSG.json", 0),
        ("DATA/MENU/FIELD_NAME.json", 0),
        ("DATA/MENU/ITEM_GET_MSG.json", 0),
        # Item/status descriptions have dedicated text areas and can tolerate
        # controlled wrapping better than option rows.
        ("DATA/MENU/ITEM_MSG.json", 22),
        ("DATA/MENU/STATUS_MSG.json", 22),
        # Cutscene/event subtitles need an ELF-side X/start-position fix.
        # Keep this only as a guard against very long single lines; do not use
        # aggressive wrapping to hide the renderer bug.
        ("DATA/SCREVENT/MSG/EV", 48),
        ("DATA/SCREVENT/MSG/", 32),
        ("DATA/MEMCARD.json", 24),
    ),
}


def wrap_translation_text(text: str, columns: int) -> str:
    """Wrap English text before encoding so fixed-width message boxes fit."""

    if columns <= 0:
        return text

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    suffix = ""
    if normalized.endswith("{END}"):
        normalized = normalized[: -len("{END}")]
        suffix = "{END}"

    wrapped_lines: list[str] = []
    for line in normalized.split("\n"):
        if not line or len(line) <= columns:
            wrapped_lines.append(line)
            continue
        wrapped_lines.extend(
            textwrap.wrap(
                line,
                width=columns,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [line]
        )
    return "\n".join(wrapped_lines) + suffix


def wrap_columns_for_path(relative_path: Path, wrap_columns: int, wrap_profile: str) -> int:
    """Pick a wrap width for one JSON file.

    A single global width is not valid for this game: menu help strings,
    field names, item descriptions, and cutscene subtitles are drawn in
    different windows with different anchoring. Explicit ``--wrap-columns``
    keeps the old force-wrap behavior for experiments; profiles are safer.
    """

    if wrap_columns > 0:
        return wrap_columns

    relative_text = relative_path.as_posix()
    for prefix, columns in WRAP_PROFILES[wrap_profile]:
        if relative_text == prefix or relative_text.startswith(prefix):
            return columns
    return 0


def load_reverse_font_map(path: Path = CORRECTED_FONT_MAP_PATH) -> dict[str, int]:
    """Load the reviewed font map as ``char -> lowest DAT code``."""

    with project_path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    char_to_code: dict[str, int] = {}
    for code_text, char in sorted(data.items(), key=lambda item: int(item[0], 16)):
        char_to_code.setdefault(char, int(code_text, 16))
    char_to_code.update(ASCII_DIRECT_FONT_CODES)
    return char_to_code


def normalize_ascii_char_for_font(char: str, char_to_code: dict[str, int]) -> str:
    """Convert one prototype ASCII translation character to an in-game glyph."""

    if char in ASCII_DIRECT_FONT_CODES and char in char_to_code:
        return char

    replacement = char
    if "A" <= char <= "Z":
        replacement = chr(ord(char) + 0xFEE0)
    elif "a" <= char <= "z":
        replacement = char
    elif "0" <= char <= "9":
        replacement = chr(ord(char) + 0xFEE0)
    elif char in ASCII_PUNCTUATION_FALLBACKS:
        replacement = ASCII_PUNCTUATION_FALLBACKS[char]

    if replacement != char and replacement not in char_to_code:
        return char
    return replacement


def iter_json_paths(input_root: Path) -> list[Path]:
    """Return all dump JSON files in stable relative order."""

    root = project_path(input_root)
    return sorted(
        path
        for path in root.rglob("*.json")
        if path.is_file() and path.name.upper() != "HINT.JSON"
    )


def encode_text(text: str, char_to_code: dict[str, int], source_label: str) -> list[int]:
    """Encode one dump string into DAT u16 codes."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    codes: list[int] = []
    pos = 0
    while pos < len(normalized):
        if normalized.startswith("{END}", pos):
            codes.append(CONTROL_END)
            pos += len("{END}")
            continue

        char = normalized[pos]
        if char == "\n":
            codes.append(CONTROL_NEWLINE)
        else:
            char = normalize_ascii_char_for_font(char, char_to_code)
            if char in char_to_code:
                codes.append(char_to_code[char])
            else:
                raise ValueError(f"{source_label}: cannot encode character {char!r} at position {pos}")
        pos += 1

    if CONTROL_END not in codes:
        codes.append(CONTROL_END)
    return codes


def parse_raw_codes(raw_codes: object, source_label: str) -> list[int]:
    """Parse JSON raw code strings emitted by ``dump_all_text.py``."""

    if not isinstance(raw_codes, list):
        raise ValueError(f"{source_label}: codes must be a list")

    codes: list[int] = []
    for raw_code in raw_codes:
        if not isinstance(raw_code, str):
            raise ValueError(f"{source_label}: raw code must be a hex string")
        code = int(raw_code, 16)
        if not 0 <= code <= 0xFFFF:
            raise ValueError(f"{source_label}: raw code out of u16 range: {raw_code}")
        codes.append(code)
    return codes


def output_path_for_json(path: Path, input_root: Path, output_root: Path) -> Path:
    """Return rebuilt DAT output path for a dump JSON path."""

    relative = path.relative_to(project_path(input_root))
    return project_path(output_root) / relative.with_suffix(".DAT")


def build_dat(entries: Iterable[tuple[int, list[int]]]) -> bytes:
    """Build the DAT table bytes from encoded entries."""

    entry_list = list(entries)
    count = len(entry_list)
    table_size = 4 + count * 8
    string_data = bytearray()
    table = bytearray()

    for idx, codes in entry_list:
        if not 0 <= idx <= 0xFFFF:
            raise ValueError(f"idx out of u16 range: {idx}")
        if len(codes) > 0xFFFF:
            raise ValueError(f"entry {idx} length out of u16 range: {len(codes)}")

        offset = table_size + len(string_data)
        table += struct.pack("<HHI", idx, len(codes), offset)
        for code in codes:
            string_data += struct.pack("<H", code)

    return struct.pack("<I", count) + table + string_data


def encode_json_file(
    path: Path,
    input_root: Path,
    output_root: Path,
    char_to_code: dict[str, int],
    wrap_columns: int,
    wrap_profile: str,
) -> int:
    """Encode one dump JSON file and return the number of entries written."""

    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    relative_path = path.relative_to(project_path(input_root))
    file_wrap_columns = wrap_columns_for_path(relative_path, wrap_columns, wrap_profile)
    entries: list[tuple[int, list[int]]] = []
    for record_number, record in enumerate(records, start=1):
        idx = int(record["idx"])
        label = f"{relative_path} record {record_number} idx {idx}"
        text_en = str(record.get("text_en") or "")
        if text_en:
            text_en = wrap_translation_text(text_en, file_wrap_columns)
            codes = encode_text(text_en, char_to_code, label)
        elif "codes" in record:
            codes = parse_raw_codes(record["codes"], label)
        else:
            codes = encode_text(str(record["text_jp"]), char_to_code, label)
        entries.append((idx, codes))

    output_path = output_path_for_json(path, input_root, output_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(build_dat(entries))
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT), help="Directory containing JSON dumps")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory to write rebuilt DAT files")
    parser.add_argument("--font-map", default=str(CORRECTED_FONT_MAP_PATH), help="Corrected code -> char JSON map")
    parser.add_argument(
        "--wrap-columns",
        type=int,
        default=DEFAULT_WRAP_COLUMNS,
        help="Force word-wrap for all non-empty text_en; use 0 for profile/default behavior",
    )
    parser.add_argument(
        "--wrap-profile",
        choices=sorted(WRAP_PROFILES),
        default="none",
        help="Optional layout-aware wrap profile; ignored when --wrap-columns is greater than 0",
    )
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    char_to_code = load_reverse_font_map(Path(args.font_map))
    json_paths = iter_json_paths(input_root)
    total_entries = 0

    for json_path in json_paths:
        total_entries += encode_json_file(
            json_path,
            input_root,
            output_root,
            char_to_code,
            args.wrap_columns,
            args.wrap_profile,
        )

    print(f"JSON files encoded: {len(json_paths)}")
    print(f"Entries encoded: {total_entries}")
    print(f"Wrote {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
