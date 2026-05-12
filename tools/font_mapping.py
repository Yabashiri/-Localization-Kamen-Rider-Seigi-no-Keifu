"""Shared font-code mapping helpers for Kamen Rider DAT text tools.

The DAT text format stores glyph references as little-endian ``u16`` codes.
Diagnostics showed that these codes are *not* dense indices into ``FONT.TXT``:

* ``0x0000..0x00ff`` map directly to page 0 from ``DATA/FONT.TXT``.
* ``0x0100..`` map as ``page * 0x100 + local_index`` using rows from
  ``DATA/EXPORT_TXD/FONT_data.json`` for pages 1 and later.

This module centralizes that confirmed hybrid mapping so decoders, encoders,
audits, and dump tools can all use the same table.
"""

from __future__ import annotations

import json
import os
import struct
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple


FONT_TXT_PATH = Path("game_dump/DATA/FONT.TXT")
FONT_JSON_PATH = Path("game_dump/DATA/EXPORT_TXD/FONT_data.json")


def project_root() -> Path:
    """Return repository/game extraction root from either root/ or tools/."""

    module_dir = Path(__file__).resolve().parent
    if (module_dir / "DATA").exists():
        return module_dir
    return module_dir.parent


def project_path(path: os.PathLike[str] | str) -> Path:
    """Resolve project-relative paths while preserving absolute paths."""

    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return project_root() / path_obj

CONTROL_END = 0x8000
CONTROL_NEWLINE = 0x8100
CONTROL_CODES = {
    CONTROL_END: "{END}",
    CONTROL_NEWLINE: "\n",
}


def load_font_txt(path: os.PathLike[str] | str = FONT_TXT_PATH) -> List[str]:
    """Load characters from ``DATA/FONT.TXT`` using Shift-JIS.

    Line breaks are file formatting, not glyphs, so they are removed.
    """

    raw = project_path(path).read_bytes()
    text = raw.decode("shift_jis", errors="replace")
    return [char for char in text if char not in "\r\n"]


def load_font_json_rows(
    path: os.PathLike[str] | str = FONT_JSON_PATH,
) -> Mapping[str, List[List[str]]]:
    """Load exported OCR/manual glyph rows from ``FONT_data.json``."""

    with project_path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def _iter_json_page_numbers(data: Mapping[str, object]) -> Iterable[int]:
    """Yield numeric page ids present as ``FONT_font_XX`` keys."""

    prefix = "FONT_font_"
    for key in data:
        if key.startswith(prefix):
            suffix = key[len(prefix) :]
            if suffix.isdigit():
                yield int(suffix)


def load_font_map(
    font_txt_path: os.PathLike[str] | str = FONT_TXT_PATH,
    font_json_path: os.PathLike[str] | str = FONT_JSON_PATH,
) -> Dict[int, str]:
    """Build the confirmed hybrid ``DAT code -> character`` map.

    Page 0 comes from the first 256 characters of ``FONT.TXT``. Pages 1+ come
    from ``FONT_data.json`` as page-local sequential indices:
    ``code = page * 0x100 + local_index``.
    """

    font_chars = load_font_txt(font_txt_path)
    font_json = load_font_json_rows(font_json_path)

    code_to_char: Dict[int, str] = {
        code: char for code, char in enumerate(font_chars[:0x100])
    }

    for page in sorted(_iter_json_page_numbers(font_json)):
        if page == 0:
            continue
        local_index = 0
        for row in font_json.get(f"FONT_font_{page:02d}", []):
            for char in row:
                code_to_char[page * 0x100 + local_index] = char
                local_index += 1

    return code_to_char


def load_char_map(
    font_txt_path: os.PathLike[str] | str = FONT_TXT_PATH,
    font_json_path: os.PathLike[str] | str = FONT_JSON_PATH,
) -> Dict[str, int]:
    """Build a reverse ``character -> DAT code`` map for future encoders.

    Some glyphs are intentionally duplicated in the game font table. For stable
    encoding, the first/lowest code is kept for each character.
    """

    char_to_code: Dict[str, int] = {}
    for code, char in sorted(load_font_map(font_txt_path, font_json_path).items()):
        char_to_code.setdefault(char, code)
    return char_to_code


def find_dat_like_files(root: os.PathLike[str] | str = "game_dump/DATA") -> List[str]:
    """Find DAT/BIN files that match the known text table structure."""

    paths: List[str] = []
    scan_root = project_path(root)
    base_root = project_root()
    for dirpath, _, filenames in os.walk(scan_root):
        for filename in filenames:
            if not filename.lower().endswith((".dat", ".bin")):
                continue

            path = Path(dirpath) / filename
            try:
                data = path.read_bytes()
                if len(data) < 12:
                    continue

                count = struct.unpack_from("<I", data, 0)[0]
                if not (0 < count < 10000 and 4 + count * 8 <= len(data)):
                    continue

                checked = min(count, 20)
                valid = 0
                for index in range(checked):
                    _, length, offset = struct.unpack_from("<HHI", data, 4 + index * 8)
                    if offset < len(data) and offset + length * 2 <= len(data):
                        valid += 1

                if valid >= max(1, checked // 2):
                    try:
                        paths.append(str(path.relative_to(base_root)))
                    except ValueError:
                        paths.append(str(path))
            except Exception:
                # Keep discovery tolerant: unrelated binary files may resemble
                # text tables partially or be unreadable during extraction work.
                continue

    return sorted(paths)


def read_dat_entries(path: os.PathLike[str] | str) -> List[Tuple[int, List[int]]]:
    """Read raw ``(idx, [u16 codes])`` entries from a DAT-like text file."""

    data = project_path(path).read_bytes()
    count = struct.unpack_from("<I", data, 0)[0]
    entries: List[Tuple[int, List[int]]] = []

    for index in range(count):
        idx, length, offset = struct.unpack_from("<HHI", data, 4 + index * 8)
        codes: List[int] = []
        for char_index in range(length):
            pos = offset + char_index * 2
            if pos + 2 > len(data):
                break
            codes.append(struct.unpack_from("<H", data, pos)[0])
        entries.append((idx, codes))

    return entries


def collect_used_codes(paths: Iterable[os.PathLike[str] | str]) -> Tuple[Counter, Counter]:
    """Collect glyph-code and control-code usage from DAT-like files."""

    glyph_codes: Counter[int] = Counter()
    control_codes: Counter[int] = Counter()

    for path in paths:
        for _, codes in read_dat_entries(path):
            for code in codes:
                if code >= 0x8000:
                    control_codes[code] += 1
                else:
                    glyph_codes[code] += 1

    return glyph_codes, control_codes


def decode_codes(codes: Iterable[int], code_to_char: Mapping[int, str]) -> Tuple[str, int]:
    """Decode raw DAT codes for diagnostics, returning ``(text, unknown_count)``."""

    output: List[str] = []
    unknown_count = 0
    for code in codes:
        if code in CONTROL_CODES:
            output.append(CONTROL_CODES[code])
        elif code in code_to_char:
            output.append(code_to_char[code])
        else:
            output.append(f"[0x{code:04X}]")
            unknown_count += 1
    return "".join(output), unknown_count
