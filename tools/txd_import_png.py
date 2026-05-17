"""Import a PNG into one texture entry of a PS2 RenderWare TXD.

Initial scope is intentionally narrow: linear 16bpp native textures.  This is
enough for TITLE title_00_* smoke tests and avoids pretending that indexed PS2
pixel swizzle is solved.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image

from font_mapping import project_path
from txd_inspect import inspect_txd, texture_summaries


NATIVE_DATA_HEADER_SIZE = {
    16: 0x50,
}


def encode_rgba5551_pixel(r: int, g: int, b: int, a: int) -> bytes:
    value = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10) | ((1 if a >= 128 else 0) << 15)
    return value.to_bytes(2, "little")


def encode_16bpp_rgba5551(image_path: Path, width: int, height: int) -> bytes:
    image = Image.open(image_path).convert("RGBA")
    if image.size != (width, height):
        raise ValueError(f"PNG size {image.size} does not match TXD texture size {(width, height)}")
    return b"".join(encode_rgba5551_pixel(*pixel) for pixel in image.getdata())


def import_png(input_txd: Path, texture_name: str, png_path: Path, output_txd: Path) -> None:
    input_txd = project_path(input_txd)
    png_path = project_path(png_path)
    output_txd = project_path(output_txd)

    report = inspect_txd(input_txd)
    matches = [texture for texture in texture_summaries(report) if texture["texture"] == texture_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one texture named {texture_name!r}, found {len(matches)}")
    texture = matches[0]
    bpp = texture["bpp"]
    if bpp not in NATIVE_DATA_HEADER_SIZE:
        raise NotImplementedError(f"PNG import for {bpp}bpp textures is not implemented yet")

    replacement = encode_16bpp_rgba5551(png_path, texture["width"], texture["height"])
    expected_size = texture["width"] * texture["height"] * bpp // 8
    if len(replacement) != expected_size:
        raise ValueError(f"Encoded PNG size {len(replacement)} != expected {expected_size}")

    data = bytearray(input_txd.read_bytes())
    pixel_offset = texture["data_payload_offset"] + NATIVE_DATA_HEADER_SIZE[bpp]
    data[pixel_offset : pixel_offset + expected_size] = replacement

    output_txd.parent.mkdir(parents=True, exist_ok=True)
    output_txd.write_bytes(data)
    print(f"Imported {png_path} -> {output_txd}")
    print(f"Texture: {texture_name} {texture['width']}x{texture['height']} {bpp}bpp")
    print(f"Pixel payload: 0x{pixel_offset:x}..0x{pixel_offset + expected_size:x}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-txd", required=True)
    parser.add_argument("--texture", required=True)
    parser.add_argument("--png", required=True)
    parser.add_argument("--output-txd", required=True)
    parser.add_argument("--copy-if-identical", action="store_true", help="Preserve metadata by copying input if output is identical")
    args = parser.parse_args()

    import_png(Path(args.input_txd), args.texture, Path(args.png), Path(args.output_txd))
    if args.copy_if_identical:
        input_txd = project_path(args.input_txd)
        output_txd = project_path(args.output_txd)
        if input_txd.read_bytes() == output_txd.read_bytes():
            shutil.copy2(input_txd, output_txd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
