"""Import rebuilt FONT_font_XX PNG pages into DATA/FONT.TXD.

The game's FONT.TXD pages are PS2 4bpp native textures.  The generic TXD
importer intentionally does not handle this format yet, so this tool is scoped
to the font atlas only.  It infers the native nibble order from the original
FONT.TXD plus the already exported reference PNG pages, then applies that order
to a replacement atlas.
"""

from __future__ import annotations

import argparse
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image

from font_mapping import project_path
from txd_inspect import inspect_txd, texture_summaries


FONT_PAGE_COUNT = 14
WIDTH = 256
HEIGHT = 256
PIXEL_REGION_START = 0xC0
PIXEL_REGION_END = 0x8000

FONT_COLORS = {
    0: (0, 0, 0, 255),
    1: (70, 70, 74, 255),
    2: (92, 91, 92, 255),
    3: (109, 109, 109, 255),
    4: (131, 131, 130, 255),
    5: (162, 161, 156, 255),
    6: (178, 177, 170, 255),
    7: (199, 199, 187, 255),
}
COLOR_TO_INDEX = {color: index for index, color in FONT_COLORS.items()}


def nearest_font_index(color: tuple[int, int, int, int]) -> int:
    r, g, b, a = color
    if a < 128 or (r < 8 and g < 8 and b < 8):
        return 0
    if color in COLOR_TO_INDEX:
        return COLOR_TO_INDEX[color]
    return min(
        (index for index in FONT_COLORS if index != 0),
        key=lambda index: sum((color[channel] - FONT_COLORS[index][channel]) ** 2 for channel in range(3)),
    )


def image_indices(path: Path) -> list[int]:
    image = Image.open(path).convert("RGBA")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"{path} size {image.size} does not match {(WIDTH, HEIGHT)}")
    return [nearest_font_index(pixel) for pixel in image.getdata()]


def native_nibbles(payload: bytes) -> list[int]:
    region = payload[PIXEL_REGION_START:PIXEL_REGION_END]
    values: list[int] = []
    for byte in region:
        values.append(byte & 0x0F)
        values.append(byte >> 4)
    return values


def pack_nibbles(values: list[int]) -> bytes:
    if len(values) % 2:
        raise ValueError("Nibble list length must be even")
    data = bytearray()
    for index in range(0, len(values), 2):
        low = values[index]
        high = values[index + 1]
        if not 0 <= low <= 0xF or not 0 <= high <= 0xF:
            raise ValueError(f"Nibble out of range at {index}: {low}, {high}")
        data.append(low | (high << 4))
    return bytes(data)


def font_textures(input_txd: Path) -> dict[int, dict[str, int | str]]:
    textures = texture_summaries(inspect_txd(input_txd))
    by_page: dict[int, dict[str, int | str]] = {}
    for texture in textures:
        name = str(texture["texture"])
        if name.startswith("font_"):
            by_page[int(name[-2:])] = texture
    missing = [page for page in range(FONT_PAGE_COUNT) if page not in by_page]
    if missing:
        raise ValueError(f"Missing font textures in {input_txd}: {missing}")
    return by_page


def infer_native_to_png_map(input_txd: Path, export_root: Path) -> list[int]:
    """Infer native nibble offset -> linear PNG pixel offset for FONT.TXD."""

    texture_by_page = font_textures(input_txd)
    txd_data = input_txd.read_bytes()
    png_vectors: list[list[int]] = []
    native_vectors: list[list[int]] = []

    for page in range(FONT_PAGE_COUNT):
        png_vectors.append(image_indices(export_root / f"FONT_font_{page:02d}.png"))
        texture = texture_by_page[page]
        payload_offset = int(texture["data_payload_offset"])
        data_size = int(texture["data_size"])
        payload = txd_data[payload_offset : payload_offset + data_size]
        native_vectors.append(native_nibbles(payload))

    native_length = len(native_vectors[0])
    png_map: dict[tuple[int, ...], list[int]] = defaultdict(list)
    native_map: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for index in range(WIDTH * HEIGHT):
        png_map[tuple(page_values[index] for page_values in png_vectors)].append(index)
    for index in range(native_length):
        native_map[tuple(page_values[index] for page_values in native_vectors)].append(index)

    native_to_png: list[int | None] = [None] * native_length
    for key, native_positions in native_map.items():
        png_positions = png_map.get(key, [])
        for native_position, png_position in zip(sorted(native_positions), sorted(png_positions)):
            native_to_png[native_position] = png_position

    missing = [index for index, value in enumerate(native_to_png) if value is None]
    if missing:
        raise ValueError(f"Could not infer {len(missing)} native font pixel positions")
    return [int(value) for value in native_to_png]


def import_font_atlas(input_txd: Path, atlas_root: Path, export_root: Path, output_txd: Path) -> None:
    input_txd = project_path(input_txd)
    atlas_root = project_path(atlas_root)
    export_root = project_path(export_root)
    output_txd = project_path(output_txd)

    native_to_png = infer_native_to_png_map(input_txd, export_root)
    texture_by_page = font_textures(input_txd)
    data = bytearray(input_txd.read_bytes())

    for page in range(FONT_PAGE_COUNT):
        png_path = atlas_root / f"FONT_font_{page:02d}.png"
        if not png_path.is_file():
            raise FileNotFoundError(f"Missing atlas page: {png_path}")
        png_indices = image_indices(png_path)
        native_values = [png_indices[png_index] for png_index in native_to_png]
        replacement = pack_nibbles(native_values)

        texture = texture_by_page[page]
        payload_offset = int(texture["data_payload_offset"])
        start = payload_offset + PIXEL_REGION_START
        end = payload_offset + PIXEL_REGION_END
        if len(replacement) != end - start:
            raise ValueError(f"Replacement size mismatch for font_{page:02d}")
        data[start:end] = replacement

    output_txd.parent.mkdir(parents=True, exist_ok=True)
    output_txd.write_bytes(data)
    print(f"Imported font atlas: {atlas_root} -> {output_txd}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-txd", default="game_dump/DATA/FONT.TXD")
    parser.add_argument("--atlas-root", default="textures_en/EXPORT_TXD/font_prototype")
    parser.add_argument("--export-root", default="dump_jp/EXPORT_TXD")
    parser.add_argument("--output-txd", default="rebuilt_en/DATA/FONT.TXD")
    parser.add_argument(
        "--check-roundtrip",
        action="store_true",
        help="Import original exported pages and fail if the result differs from the input TXD",
    )
    args = parser.parse_args()

    atlas_root = Path(args.export_root) if args.check_roundtrip else Path(args.atlas_root)
    output_txd = Path(args.output_txd)
    import_font_atlas(Path(args.input_txd), atlas_root, Path(args.export_root), output_txd)
    if args.check_roundtrip:
        input_txd = project_path(args.input_txd)
        rebuilt_txd = project_path(output_txd)
        if input_txd.read_bytes() != rebuilt_txd.read_bytes():
            raise ValueError(f"FONT.TXD roundtrip differs: {rebuilt_txd}")
        shutil.copy2(input_txd, rebuilt_txd)
        print("FONT.TXD roundtrip: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
