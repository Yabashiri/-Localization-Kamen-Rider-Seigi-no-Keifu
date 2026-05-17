"""Report TXD native texture entries and matching exported PNG files."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path
from typing import Any

from font_mapping import project_path
from txd_inspect import inspect_txd, texture_summaries


PNG_COLOR_TYPES = {
    0: "grayscale",
    2: "rgb",
    3: "indexed",
    4: "grayscale_alpha",
    6: "rgba",
}


def read_png_ihdr(path: Path) -> dict[str, Any]:
    data = path.read_bytes()[:33]
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG file: {path}")
    chunk_len = struct.unpack_from(">I", data, 8)[0]
    chunk_type = data[12:16]
    if chunk_type != b"IHDR" or chunk_len != 13:
        raise ValueError(f"Unexpected PNG IHDR in {path}")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack_from(">IIBBBBB", data, 16)
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": PNG_COLOR_TYPES.get(color_type, str(color_type)),
        "compression": compression,
        "filter": filter_method,
        "interlace": interlace,
    }


def normalize_texture_name(name: str) -> str:
    return name.lower()


def find_exported_png(relative_txd: Path, texture: str, export_root: Path) -> Path | None:
    export_dir = export_root / relative_txd.parent
    if not export_dir.is_dir():
        return None
    expected = f"{relative_txd.stem}_{texture}.png".lower()
    for path in export_dir.glob("*.png"):
        if path.name.lower() == expected:
            return path
    prefix = f"{relative_txd.stem}_".lower()
    texture_key = normalize_texture_name(texture)
    matches = [
        path
        for path in export_dir.glob("*.png")
        if path.name.lower().startswith(prefix) and path.stem.lower().endswith(texture_key)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def report_rows(source_root: Path, export_root: Path) -> list[dict[str, Any]]:
    source_root = project_path(source_root)
    export_root = project_path(export_root)
    rows: list[dict[str, Any]] = []
    for txd_path in sorted(source_root.rglob("*.TXD")):
        relative_txd = txd_path.relative_to(source_root)
        report = inspect_txd(txd_path)
        for texture in texture_summaries(report):
            png_path = find_exported_png(relative_txd, texture["texture"], export_root)
            png_info = read_png_ihdr(png_path) if png_path else {}
            rows.append(
                {
                    "txd": Path("DATA", relative_txd).as_posix(),
                    "texture": texture["texture"],
                    "width": texture["width"],
                    "height": texture["height"],
                    "bpp": texture["bpp"],
                    "data_size": texture["data_size"],
                    "png": Path("DATA", png_path.relative_to(export_root)).as_posix() if png_path else "",
                    "png_width": png_info.get("width", ""),
                    "png_height": png_info.get("height", ""),
                    "png_bit_depth": png_info.get("bit_depth", ""),
                    "png_color_type": png_info.get("color_type", ""),
                    "dimension_match": bool(
                        png_info
                        and texture["width"] == png_info["width"]
                        and texture["height"] == png_info["height"]
                    ),
                }
            )
    return rows


def print_tsv(rows: list[dict[str, Any]]) -> None:
    headers = [
        "txd",
        "texture",
        "width",
        "height",
        "bpp",
        "data_size",
        "png",
        "png_width",
        "png_height",
        "png_bit_depth",
        "png_color_type",
        "dimension_match",
    ]
    print("\t".join(headers))
    for row in rows:
        print("\t".join(str(row[header]) for header in headers))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default="game_dump/DATA")
    parser.add_argument("--export-root", default="dump_jp/EXPORT_TXD")
    parser.add_argument("--check", action="store_true", help="Fail on missing PNGs or dimension mismatches")
    args = parser.parse_args()

    rows = report_rows(Path(args.source_root), Path(args.export_root))
    print_tsv(rows)
    missing = [row for row in rows if not row["png"]]
    mismatched = [row for row in rows if row["png"] and not row["dimension_match"]]
    if args.check:
        if missing:
            print(f"Missing PNG matches: {len(missing)}")
        if mismatched:
            print(f"Dimension mismatches: {len(mismatched)}")
        if missing or mismatched:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
