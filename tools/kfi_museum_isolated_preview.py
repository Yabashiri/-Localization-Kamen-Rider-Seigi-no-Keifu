"""Build isolated KFI museum previews without touching the pilot import pipeline.

This tool exists so museum-layout iteration can happen in a separate output
tree while other work continues on `tools/kfi_museum_pilot.py`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from font_mapping import project_path
from txd_import_png import png_index_to_native_index, psmt8_swizzled_offset
from txd_inspect import parse_children, read_chunk, texture_summaries


KFI36_RSC = Path("game_dump/DATA/KFI_KIJIN_36.RSC")
KFI36_TXD_OFFSET = 0x43118
KFI_BG_RSC = Path("game_dump/DATA/KFI_BG_TEX.RSC")
KFI_BG_TXD_OFFSET = 0x5C

TEXT_HEADER_SIZE = 0x50
TEXTURE_SIZE = 256
PAGE_SIZE = (640, 448)
BASE_PAGE_COLOR = (156, 160, 138, 255)

DETAIL_PAGE_TILES = ("001", "002", "003", "004", "005", "006")

TRANSLATION_ROOT = Path("textures_en/EXPORT_TXD/KFI/museum_pilot")
OUTPUT_ROOT = Path("build/museum_preview_isolated")
CONTACT_SHEET_NAME = "kfi_bg_contact_sheet.png"

TEXTURE_A_NAME = "KFI_KIJIN_36_RSC__tex_kfi_tx_3600a.png"
TEXTURE_B_NAME = "KFI_KIJIN_36_RSC__tex_kfi_tx_3600b.png"
TEXTURE_A_LEFT = 320
TEXTURE_A_TOP = 104
TEXTURE_B_LEFT = 248
TEXTURE_B_TOP = 104


def native_to_png_index(index: int) -> int:
    for png_index in range(256):
        if png_index_to_native_index(png_index) == index:
            return png_index
    raise ValueError(f"No PNG index maps to native index {index}")


NATIVE_TO_PNG = [native_to_png_index(index) for index in range(256)]


def embedded_txd(data: bytes, txd_offset: int) -> bytes:
    chunk = read_chunk(data, txd_offset, len(data))
    if chunk is None or chunk.chunk_id != 0x16:
        raise ValueError(f"No embedded TXD at 0x{txd_offset:x}")
    return data[txd_offset : chunk.end_offset]


def texture_map(txd_data: bytes) -> dict[str, dict]:
    report = {
        "path": "embedded",
        "size": len(txd_data),
        "chunks": parse_children(txd_data, 0, len(txd_data), 0, None),
    }
    return {str(texture["texture"]): texture for texture in texture_summaries(report)}


def logical_palette(clut: bytes) -> list[int]:
    palette = [0] * 768
    for png_index in range(256):
        native_index = png_index_to_native_index(png_index)
        start = native_index * 4
        if start + 3 < len(clut):
            palette[png_index * 3 : png_index * 3 + 3] = list(clut[start : start + 3])
    return palette


def logical_alpha(clut: bytes) -> bytes:
    alpha = [0] * 256
    for png_index in range(256):
        native_index = png_index_to_native_index(png_index)
        start = native_index * 4
        if start + 3 < len(clut):
            alpha[png_index] = min(255, clut[start + 3] * 2)
    return bytes(alpha)


def decode_8bpp_texture(txd_data: bytes, texture_name: str) -> Image.Image:
    textures = texture_map(txd_data)
    texture = textures[texture_name]
    if texture["bpp"] != 8 or texture["width"] != TEXTURE_SIZE or texture["height"] != TEXTURE_SIZE:
        raise ValueError(f"{texture_name} is not a 256x256 8bpp texture")

    payload_offset = int(texture["data_payload_offset"])
    payload = txd_data[payload_offset : payload_offset + int(texture["data_size"])]
    pixel_data = payload[TEXT_HEADER_SIZE : TEXT_HEADER_SIZE + TEXTURE_SIZE * TEXTURE_SIZE]
    clut = payload[TEXT_HEADER_SIZE + TEXTURE_SIZE * TEXTURE_SIZE :][:1024]

    linear_indices = bytearray(TEXTURE_SIZE * TEXTURE_SIZE)
    for y in range(TEXTURE_SIZE):
        row = y * TEXTURE_SIZE
        for x in range(TEXTURE_SIZE):
            native_index = pixel_data[psmt8_swizzled_offset(x, y, TEXTURE_SIZE)]
            linear_indices[row + x] = NATIVE_TO_PNG[native_index]

    image = Image.new("P", (TEXTURE_SIZE, TEXTURE_SIZE), 0)
    image.putpalette(logical_palette(clut))
    image.info["transparency"] = logical_alpha(clut)
    image.putdata(linear_indices)
    return image


def binary_alpha_rgba(path: Path) -> Image.Image:
    image = Image.open(path)
    if image.mode != "P":
        return image.convert("RGBA")

    rgba = image.convert("RGBA")
    alpha = Image.new("L", image.size, 255)
    alpha.putdata([0 if index == 0 else 255 for index in image.getdata()])
    rgba.putalpha(alpha)
    return rgba


def compose_page(tile_ids: tuple[str, ...]) -> Image.Image:
    txd_data = embedded_txd(project_path(KFI_BG_RSC).read_bytes(), KFI_BG_TXD_OFFSET)
    page = Image.new("RGBA", PAGE_SIZE, BASE_PAGE_COLOR)
    for index, tile_id in enumerate(tile_ids):
        x = (index % 3) * TEXTURE_SIZE
        y = (index // 3) * TEXTURE_SIZE
        tile = decode_8bpp_texture(txd_data, f"tex_kfi_bg_{tile_id}").convert("RGBA")
        page.alpha_composite(tile, (x, y))
    return page


def muted_notebook_background(image: Image.Image) -> Image.Image:
    rgb = ImageEnhance.Color(image.convert("RGB")).enhance(0.06)
    pixels = rgb.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, int(r * 0.96))),
                max(0, min(255, int(g * 1.00))),
                max(0, min(255, int(b * 0.90))),
            )
    return rgb.convert("RGBA")


def compose_translation_preview(background: Image.Image, translation_root: Path) -> Image.Image:
    page = background.copy()
    a = binary_alpha_rgba(translation_root / TEXTURE_A_NAME)
    b = binary_alpha_rgba(translation_root / TEXTURE_B_NAME)
    page.alpha_composite(b, (TEXTURE_B_LEFT, TEXTURE_B_TOP))
    page.alpha_composite(a, (TEXTURE_A_LEFT, TEXTURE_A_TOP))
    return page


def add_label(image: Image.Image, label: str) -> Image.Image:
    labeled = image.convert("RGB")
    draw = ImageDraw.Draw(labeled)
    font = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 14)
    draw.rectangle((8, 8, 188, 29), fill=(18, 18, 18))
    draw.text((13, 10), label, fill=(255, 255, 235), font=font)
    return labeled


def build_contact_sheet(output_root: Path) -> Path:
    txd_data = embedded_txd(project_path(KFI_BG_RSC).read_bytes(), KFI_BG_TXD_OFFSET)
    tile_names = [f"tex_kfi_bg_{index:03d}" for index in range(1, 19)]
    cols = 3
    rows = (len(tile_names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 256, rows * 288), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 16)

    for index, name in enumerate(tile_names):
        x = (index % cols) * 256
        y = (index // cols) * 288
        tile = decode_8bpp_texture(txd_data, name).convert("RGBA")
        base = Image.new("RGBA", (256, 256), BASE_PAGE_COLOR)
        base.alpha_composite(tile)
        sheet.paste(base.convert("RGB"), (x, y))
        draw.rectangle((x, y + 256, x + 256, y + 288), fill=(20, 20, 20))
        draw.text((x + 8, y + 264), name, fill=(240, 240, 240), font=font)

    out_path = output_root / CONTACT_SHEET_NAME
    sheet.save(out_path)
    return out_path


def generate_previews(translation_root: Path, output_root: Path) -> list[Path]:
    output_root.mkdir(parents=True, exist_ok=True)

    raw_background = compose_page(DETAIL_PAGE_TILES)
    muted_background = muted_notebook_background(raw_background)

    raw_preview = add_label(
        compose_translation_preview(raw_background, translation_root),
        "isolated preview: raw page colors",
    )
    muted_preview = add_label(
        compose_translation_preview(muted_background, translation_root),
        "isolated preview: muted notebook",
    )

    outputs = [
        output_root / "kfi36_background_raw.png",
        output_root / "kfi36_background_muted.png",
        output_root / "kfi36_preview_raw.png",
        output_root / "kfi36_preview_muted.png",
    ]
    raw_background.convert("RGB").save(outputs[0])
    muted_background.convert("RGB").save(outputs[1])
    raw_preview.save(outputs[2])
    muted_preview.save(outputs[3])
    outputs.append(build_contact_sheet(output_root))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation-root", default=TRANSLATION_ROOT)
    parser.add_argument("--output-root", default=OUTPUT_ROOT)
    args = parser.parse_args()

    outputs = generate_previews(project_path(args.translation_root), project_path(args.output_root))
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
