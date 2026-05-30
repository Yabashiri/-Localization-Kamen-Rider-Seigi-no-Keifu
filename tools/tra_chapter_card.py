"""Extract or import 640x512 chapter title-card PNGs in TSCENE TRA files.

Chapter cards in DATA/TSCENE/EV126_00.TRA .. EV131_00.TRA are embedded TXDs at
offset 0x40.  Each embedded TXD contains five 256x256 16bpp textures.  The game
draws those textures as a 640x512 screen image:

  _00 -> x=0..255,   y=0..255
  _01 -> x=256..511, y=0..255
  _02 -> x=0..255,   y=256..511
  _03 -> x=256..511, y=256..511
  _04 left half  -> x=512..639, y=0..255
  _04 right half -> x=512..639, y=256..511
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image

from font_mapping import project_path
from txd_import_png import NATIVE_DATA_HEADER_SIZE, encode_rgba5551_pixel
from txd_inspect import parse_children, read_chunk, texture_summaries


DEFAULT_TXD_OFFSET = 0x40
COMPOSITE_SIZE = (640, 512)
TILE_SIZE = 256
TILE_RECTS = {
    "00": (0, 0, 256, 256),
    "01": (256, 0, 512, 256),
    "02": (0, 256, 256, 512),
    "03": (256, 256, 512, 512),
}


def parse_int(text: str) -> int:
    return int(text, 0)


def texture_prefix_from_tra(path: Path) -> str:
    return path.stem.lower()


def embedded_txd_span(tra_data: bytes, txd_offset: int) -> tuple[int, int]:
    chunk = read_chunk(tra_data, txd_offset, len(tra_data))
    if chunk is None:
        raise ValueError(f"No RenderWare chunk found at 0x{txd_offset:x}")
    if chunk.chunk_id != 0x16:
        raise ValueError(f"Expected Texture Dictionary at 0x{txd_offset:x}, found chunk id 0x{chunk.chunk_id:x}")
    return txd_offset, chunk.end_offset


def inspect_txd_bytes(txd_data: bytes, label: str) -> dict:
    return {
        "path": label,
        "size": len(txd_data),
        "chunks": parse_children(txd_data, 0, len(txd_data), 0, None),
    }


def texture_map(txd_data: bytes, label: str) -> dict[str, dict]:
    textures = texture_summaries(inspect_txd_bytes(txd_data, label))
    return {str(texture["texture"]): texture for texture in textures}


def rgba5551_to_rgba(value: int) -> tuple[int, int, int, int]:
    r = value & 0x1F
    g = (value >> 5) & 0x1F
    b = (value >> 10) & 0x1F
    a = 255 if value & 0x8000 else 0
    return (r * 255 // 31, g * 255 // 31, b * 255 // 31, a)


def decode_16bpp_tile(txd_data: bytes, texture: dict) -> Image.Image:
    if texture["bpp"] != 16 or texture["width"] != TILE_SIZE or texture["height"] != TILE_SIZE:
        raise ValueError(
            f"Expected 256x256 16bpp texture, got "
            f"{texture['width']}x{texture['height']} {texture['bpp']}bpp"
        )
    payload_offset = int(texture["data_payload_offset"]) + NATIVE_DATA_HEADER_SIZE[16]
    pixel_count = TILE_SIZE * TILE_SIZE
    payload = txd_data[payload_offset : payload_offset + pixel_count * 2]
    if len(payload) != pixel_count * 2:
        raise ValueError(f"Texture payload is truncated for {texture['texture']}")

    image = Image.new("RGBA", (TILE_SIZE, TILE_SIZE))
    pixels = [rgba5551_to_rgba(value) for (value,) in struct.iter_unpack("<H", payload)]
    image.putdata(pixels)
    return image


def encode_16bpp_tile(image: Image.Image) -> bytes:
    if image.size != (TILE_SIZE, TILE_SIZE):
        raise ValueError(f"Tile size {image.size} does not match {(TILE_SIZE, TILE_SIZE)}")
    return b"".join(encode_rgba5551_pixel(*pixel) for pixel in image.convert("RGBA").getdata())


def compose_tiles(tiles: dict[str, Image.Image]) -> Image.Image:
    composite = Image.new("RGBA", COMPOSITE_SIZE, (0, 0, 0, 255))
    for suffix, rect in TILE_RECTS.items():
        composite.paste(tiles[suffix], rect[:2])
    tile_04 = tiles["04"]
    composite.paste(tile_04.crop((0, 0, 128, 256)), (512, 0))
    composite.paste(tile_04.crop((128, 0, 256, 256)), (512, 256))
    return composite


def split_composite(image: Image.Image) -> dict[str, Image.Image]:
    image = image.convert("RGBA")
    tiles = {suffix: image.crop(rect) for suffix, rect in TILE_RECTS.items()}
    tile_04 = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 255))
    tile_04.paste(image.crop((512, 0, 640, 256)), (0, 0))
    tile_04.paste(image.crop((512, 256, 640, 512)), (128, 0))
    tiles["04"] = tile_04
    return tiles


def normalize_composite(image: Image.Image, fit: str) -> Image.Image:
    image = image.convert("RGBA")
    if image.size == COMPOSITE_SIZE:
        return image
    if fit == "reject":
        raise ValueError(f"PNG size {image.size} does not match {COMPOSITE_SIZE}")
    if fit == "stretch":
        return image.resize(COMPOSITE_SIZE, Image.Resampling.LANCZOS)

    source_w, source_h = image.size
    target_w, target_h = COMPOSITE_SIZE
    scale = min(target_w / source_w, target_h / source_h) if fit == "contain" else max(target_w / source_w, target_h / source_h)
    resized = image.resize((round(source_w * scale), round(source_h * scale)), Image.Resampling.LANCZOS)

    if fit == "contain":
        output = Image.new("RGBA", COMPOSITE_SIZE, (0, 0, 0, 255))
        output.alpha_composite(resized, ((target_w - resized.width) // 2, (target_h - resized.height) // 2))
        return output

    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def load_embedded_txd(tra_path: Path, txd_offset: int) -> tuple[bytearray, int, int, bytes]:
    tra_path = project_path(tra_path)
    tra_data = bytearray(tra_path.read_bytes())
    start, end = embedded_txd_span(tra_data, txd_offset)
    return tra_data, start, end, bytes(tra_data[start:end])


def extract_card(input_tra: Path, output_png: Path, txd_offset: int, texture_prefix: str | None) -> None:
    input_tra = project_path(input_tra)
    output_png = project_path(output_png)
    _, _, _, txd_data = load_embedded_txd(input_tra, txd_offset)

    prefix = texture_prefix or texture_prefix_from_tra(input_tra)
    textures = texture_map(txd_data, f"{input_tra.as_posix()}@0x{txd_offset:x}")
    tiles: dict[str, Image.Image] = {}
    for suffix in ("00", "01", "02", "03", "04"):
        name = f"{prefix}_{suffix}"
        if name not in textures:
            raise ValueError(f"Texture {name!r} not found in embedded TXD")
        tiles[suffix] = decode_16bpp_tile(txd_data, textures[name])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    compose_tiles(tiles).save(output_png)
    print(f"Extracted {input_tra} -> {output_png}")


def import_card(
    input_tra: Path,
    png_path: Path,
    output_tra: Path,
    txd_offset: int,
    texture_prefix: str | None,
    fit: str,
    preview_png: Path | None,
) -> None:
    input_tra = project_path(input_tra)
    png_path = project_path(png_path)
    output_tra = project_path(output_tra)
    preview_png = project_path(preview_png) if preview_png else None

    tra_data, txd_start, txd_end, txd_data_bytes = load_embedded_txd(input_tra, txd_offset)
    txd_data = bytearray(txd_data_bytes)
    prefix = texture_prefix or texture_prefix_from_tra(input_tra)
    textures = texture_map(txd_data, f"{input_tra.as_posix()}@0x{txd_offset:x}")

    composite = normalize_composite(Image.open(png_path), fit)
    tiles = split_composite(composite)
    for suffix, tile in tiles.items():
        name = f"{prefix}_{suffix}"
        if name not in textures:
            raise ValueError(f"Texture {name!r} not found in embedded TXD")
        texture = textures[name]
        if texture["bpp"] != 16:
            raise ValueError(f"Texture {name!r} is {texture['bpp']}bpp, expected 16bpp")
        pixel_offset = int(texture["data_payload_offset"]) + NATIVE_DATA_HEADER_SIZE[16]
        payload = encode_16bpp_tile(tile)
        txd_data[pixel_offset : pixel_offset + len(payload)] = payload
        print(f"{name}: pixel payload 0x{pixel_offset:x}..0x{pixel_offset + len(payload):x}")

    if len(txd_data) != txd_end - txd_start:
        raise ValueError("Embedded TXD size changed; refusing to write TRA")

    tra_data[txd_start:txd_end] = txd_data
    output_tra.parent.mkdir(parents=True, exist_ok=True)
    output_tra.write_bytes(tra_data)
    print(f"Imported {png_path} -> {output_tra}")
    print(f"Embedded TXD span: 0x{txd_start:x}..0x{txd_end:x} ({txd_end - txd_start} bytes)")

    if preview_png:
        preview_png.parent.mkdir(parents=True, exist_ok=True)
        compose_tiles(tiles).save(preview_png)
        print(f"Wrote import preview: {preview_png}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract a 640x512 chapter-card composite PNG")
    extract_parser.add_argument("--input-tra", required=True)
    extract_parser.add_argument("--output-png", required=True)
    extract_parser.add_argument("--txd-offset", type=parse_int, default=DEFAULT_TXD_OFFSET)
    extract_parser.add_argument("--texture-prefix")

    import_parser = subparsers.add_parser("import", help="Import a 640x512 chapter-card composite PNG")
    import_parser.add_argument("--input-tra", required=True)
    import_parser.add_argument("--png", required=True)
    import_parser.add_argument("--output-tra", required=True)
    import_parser.add_argument("--txd-offset", type=parse_int, default=DEFAULT_TXD_OFFSET)
    import_parser.add_argument("--texture-prefix")
    import_parser.add_argument(
        "--fit",
        choices=("reject", "contain", "cover", "stretch"),
        default="contain",
        help="How to normalize non-640x512 source PNGs before splitting",
    )
    import_parser.add_argument("--preview-png")

    args = parser.parse_args()
    if args.command == "extract":
        extract_card(Path(args.input_tra), Path(args.output_png), args.txd_offset, args.texture_prefix)
    elif args.command == "import":
        import_card(
            Path(args.input_tra),
            Path(args.png),
            Path(args.output_tra),
            args.txd_offset,
            args.texture_prefix,
            args.fit,
            Path(args.preview_png) if args.preview_png else None,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
