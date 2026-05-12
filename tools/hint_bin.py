"""Dump and rebuild DATA/MENU/HINT.BIN Shift-JIS strings.

HINT.BIN is not a DAT glyph-code table. It is a CSVS container with tables of
file-relative string pointers and a Shift-JIS string pool. Pointer values are
stored as ``string_offset - 8``; the first CSVS size field points to the start of
the following ROPS payload, which must be preserved.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from font_mapping import project_path


DEFAULT_INPUT = Path("game_dump/DATA/MENU/HINT.BIN")
DEFAULT_JSON = Path("translation_en/DATA/MENU/HINT.json")
DEFAULT_OUTPUT = Path("rebuilt_en/DATA/MENU/HINT.BIN")
STRING_POINTER_BIAS = 8


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def write_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def looks_like_text(data: bytes, offset: int, limit: int) -> bool:
    if offset <= 0 or offset >= limit:
        return False
    end = data.find(b"\x00", offset, limit)
    if end <= offset:
        return False
    try:
        text = data[offset:end].decode("shift_jis")
    except UnicodeDecodeError:
        return False
    return all((char == "\n") or (char == "\t") or (ord(char) >= 0x20) for char in text)


def find_string_start(data: bytes, csv_size: int) -> int:
    starts: list[int] = []
    for offset in range(0, csv_size - 3, 4):
        candidate = read_u32(data, offset) + STRING_POINTER_BIAS
        if candidate >= 0xE00 and looks_like_text(data, candidate, csv_size):
            starts.append(candidate)
    if not starts:
        raise ValueError("Could not locate HINT.BIN string pool")
    return min(starts)


def iter_strings(data: bytes, start: int, end: int) -> list[tuple[int, str]]:
    strings: list[tuple[int, str]] = []
    offset = start
    while offset < end:
        terminator = data.find(b"\x00", offset, end)
        if terminator < 0:
            break
        raw = data[offset:terminator]
        if raw:
            strings.append((offset, raw.decode("shift_jis").replace("\\n", "\n")))
        offset = terminator + 1
    return strings


def dump_hint(input_bin: Path, output_json: Path) -> None:
    data = input_bin.read_bytes()
    if data[:4] != b"CSVS":
        raise ValueError(f"Unexpected HINT.BIN magic: {data[:4]!r}")

    csv_size = read_u32(data, 4)
    string_start = find_string_start(data, csv_size)
    records = [
        {
            "offset": f"0x{offset:04X}",
            "text_jp": text,
            "text_en": "",
        }
        for offset, text in iter_strings(data, string_start, csv_size)
    ]

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with output_json.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Dumped {len(records)} HINT.BIN strings to {output_json}")


def build_hint(input_bin: Path, input_json: Path, output_bin: Path) -> None:
    data = input_bin.read_bytes()
    if data[:4] != b"CSVS":
        raise ValueError(f"Unexpected HINT.BIN magic: {data[:4]!r}")

    csv_size = read_u32(data, 4)
    string_start = find_string_start(data, csv_size)
    tail = data[csv_size:]
    prefix = bytearray(data[:string_start])

    records = json.loads(input_json.read_text(encoding="utf-8"))
    offset_map: dict[int, int] = {}
    string_pool = bytearray()
    for record in records:
        old_offset = int(str(record["offset"]), 16)
        text = str(record.get("text_en") or record["text_jp"]).replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\n", "\\n")
        new_offset = string_start + len(string_pool)
        offset_map[old_offset] = new_offset
        string_pool += text.encode("shift_jis")
        string_pool += b"\x00"

    for offset in range(0, len(prefix) - 3, 4):
        pointer = read_u32(prefix, offset)
        old_string_offset = pointer + STRING_POINTER_BIAS
        if old_string_offset in offset_map:
            write_u32(prefix, offset, offset_map[old_string_offset] - STRING_POINTER_BIAS)

    new_csv_size = len(prefix) + len(string_pool)
    write_u32(prefix, 4, new_csv_size)

    output_bin.parent.mkdir(parents=True, exist_ok=True)
    output_bin.write_bytes(bytes(prefix) + bytes(string_pool) + tail)
    print(f"Built HINT.BIN: {output_bin} ({len(data)} -> {output_bin.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    dump_parser = subparsers.add_parser("dump")
    dump_parser.add_argument("--input-bin", default=str(DEFAULT_INPUT))
    dump_parser.add_argument("--output-json", default=str(DEFAULT_JSON))

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--input-bin", default=str(DEFAULT_INPUT))
    build_parser.add_argument("--input-json", default=str(DEFAULT_JSON))
    build_parser.add_argument("--output-bin", default=str(DEFAULT_OUTPUT))

    args = parser.parse_args()
    if args.command == "dump":
        dump_hint(project_path(args.input_bin), project_path(args.output_json))
    elif args.command == "build":
        build_hint(project_path(args.input_bin), project_path(args.input_json), project_path(args.output_bin))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
