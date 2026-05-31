"""Generate and import the pilot localized KFI museum record.

Pilot scope:
  * KFI_KIJIN_36.RSC: Shocker Combatant (bone/masked type) body card.

The museum name/index sheet is intentionally left untouched until its layout is
approved separately.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont

from font_mapping import project_path
from rsc_txd_import import import_rsc_txd
from txd_import_png import png_index_to_native_index, psmt8_swizzled_offset
from txd_inspect import parse_children, read_chunk, texture_summaries


KFI36_RSC = Path("game_dump/DATA/KFI_KIJIN_36.RSC")
KFI36_OUT = Path("rebuilt_en/DATA/KFI_KIJIN_36.RSC")
KFI36_TXD_OFFSET = 0x43118
KFI36_TEXTURE_A = "tex_kfi_tx_3600a"
KFI36_TEXTURE_B = "tex_kfi_tx_3600b"

KFI_BG_RSC = Path("game_dump/DATA/KFI_BG_TEX.RSC")
KFI_BG_TXD_OFFSET = 0x5C

SOURCE_ROOT = Path("textures_en/EXPORT_TXD/KFI/museum_pilot")
PREVIEW_ROOT = Path("build/museum_pilot_preview")
FONT_PATH = Path("C:/Windows/Fonts/segoeuib.ttf")

TEXT_HEADER_SIZE = 0x50
TEXTURE_SIZE = 256
SHOT_RECT = (133, 83, 238, 145)
TEXT_SPLIT_X = 72
TEXT_PANEL_SIZE = (TEXT_SPLIT_X + TEXTURE_SIZE, TEXTURE_SIZE)
A_BACKGROUND_LEFT = 320
A_BACKGROUND_TOP = 104

# These indices come from the original KFI_KIJIN_36 body-card palettes.
# tex_kfi_tx_3600a is rendered as an opaque card material in game, so its
# cleared pixels must stay on the paper index instead of transparent index 0.
A_PAPER_INDEX = 202
A_TEXT_FILL_INDEX = 48
A_TEXT_STROKE_INDEX = 251
# KFI_TX_3600.dff maps only the first 71 texels of tex_kfi_tx_3600b.
# In that original visible strip, the dominant opaque black ink index is 162.
B_TEXT_FILL_INDEX = 162
B_TEXT_STROKE_INDEX = 253


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


def palette_color(image: Image.Image, index: int) -> tuple[int, int, int]:
    palette = image.getpalette()
    if palette is None:
        raise ValueError("Expected paletted image")
    start = index * 3
    return tuple(palette[start : start + 3])


def palette_alpha(image: Image.Image, index: int) -> int:
    transparency = image.info.get("transparency")
    if isinstance(transparency, bytes) and index < len(transparency):
        return transparency[index]
    if isinstance(transparency, list) and index < len(transparency):
        return int(transparency[index])
    if isinstance(transparency, int):
        return 0 if index == transparency else 255
    return 255


def nearest_index(image: Image.Image, color: tuple[int, int, int], exclude: set[int] | None = None) -> int:
    exclude = exclude or set()
    return min(
        (index for index in range(256) if index not in exclude),
        key=lambda index: sum((palette_color(image, index)[channel] - color[channel]) ** 2 for channel in range(3)),
    )


def nearest_opaque_index(image: Image.Image, color: tuple[int, int, int], exclude: set[int] | None = None) -> int:
    exclude = exclude or set()
    candidates = [index for index in range(256) if index not in exclude and palette_alpha(image, index) >= 192]
    if not candidates:
        return nearest_index(image, color, exclude)
    return min(
        candidates,
        key=lambda index: sum((palette_color(image, index)[channel] - color[channel]) ** 2 for channel in range(3)),
    )


def text_masks(size: tuple[int, int], xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont) -> tuple[Image.Image, Image.Image]:
    stroke_mask = Image.new("L", size, 0)
    fill_mask = Image.new("L", size, 0)
    ImageDraw.Draw(stroke_mask).text(xy, text, font=font, fill=255, stroke_width=1, stroke_fill=255)
    ImageDraw.Draw(fill_mask).text(xy, text, font=font, fill=255)
    return stroke_mask, fill_mask


def wrap_line(draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.FreeTypeFont, width: int) -> tuple[str, int]:
    line = ""
    used = 0
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if draw.textbbox((0, 0), candidate, font=font, stroke_width=1)[2] <= width:
            line = candidate
            used += 1
        else:
            break
    if not line and words:
        return words[0], 1
    return line, used


def flow_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    width: int,
    line_height: int,
    bottom: int,
    avoid_rect: tuple[int, int, int, int],
) -> list[tuple[str, tuple[int, int]]]:
    words = text.split()
    index = 0
    lines: list[tuple[str, tuple[int, int]]] = []
    while index < len(words) and y < bottom:
        line_width = width
        if y + line_height > avoid_rect[1] and y < avoid_rect[3]:
            line_width = max(80, avoid_rect[0] - x - 8)
        line, used = wrap_line(draw, words[index:], font, line_width)
        if not line:
            break
        lines.append((line, (x, y)))
        index += used
        y += line_height
    if index < len(words):
        raise ValueError("Pilot KFI text does not fit the texture")
    return lines


def apply_masked_color(image: Image.Image, mask: Image.Image, index: int, threshold: int = 32) -> None:
    pixels = image.load()
    mask_pixels = mask.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            if mask_pixels[x, y] >= threshold:
                pixels[x, y] = index


def apply_masked_dithered_color(
    image: Image.Image,
    mask: Image.Image,
    base_index: int,
    darken_index: int,
    threshold: int = 32,
) -> None:
    pixels = image.load()
    mask_pixels = mask.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            if mask_pixels[x, y] < threshold:
                continue
            pixels[x, y] = darken_index if mask_pixels[x, y] >= 160 and (x + y) % 3 == 0 else base_index


def clear_text_regions(image: Image.Image, background_index: int, keep_rect: tuple[int, int, int, int] | None = None) -> None:
    pixels = image.load()
    for y in range(0, 242):
        for x in range(TEXTURE_SIZE):
            if keep_rect and keep_rect[0] <= x < keep_rect[2] and keep_rect[1] <= y < keep_rect[3]:
                continue
            pixels[x, y] = background_index


def is_red_artifact(color: tuple[int, int, int]) -> bool:
    r, g, b = color
    if r > 24 and g <= 4 and b <= 4:
        return True
    return r > 40 and r >= g + 18 and r >= b + 18


def neutral_luma_index(image: Image.Image, color: tuple[int, int, int]) -> int:
    palette = image.getpalette()
    if palette is None:
        raise ValueError("Expected paletted image")
    luma = color[0] * 299 + color[1] * 587 + color[2] * 114
    candidates = [
        index
        for index in range(256)
        if palette_alpha(image, index) >= 192 and not is_red_artifact(tuple(palette[index * 3 : index * 3 + 3]))
    ]
    return min(
        candidates,
        key=lambda index: (
            abs(
                luma
                - (
                    palette[index * 3] * 299
                    + palette[index * 3 + 1] * 587
                    + palette[index * 3 + 2] * 114
                )
            ),
            max(palette[index * 3 : index * 3 + 3]) - min(palette[index * 3 : index * 3 + 3]),
        ),
    )


def neutral_low_alpha_index(image: Image.Image, color: tuple[int, int, int], alpha: int) -> int:
    palette = image.getpalette()
    if palette is None:
        raise ValueError("Expected paletted image")
    candidates = [
        index
        for index in range(256)
        if palette_alpha(image, index) < 192
        and not is_red_artifact(tuple(palette[index * 3 : index * 3 + 3]))
        and sum(palette[index * 3 : index * 3 + 3]) <= 12
    ]
    if not candidates:
        return neutral_luma_index(image, color)
    return min(candidates, key=lambda index: (abs(palette_alpha(image, index) - alpha), index))


def neutralize_red_pixels(image: Image.Image, rect: tuple[int, int, int, int]) -> None:
    pixels = image.load()
    replacement_cache: dict[int, int] = {}
    for y in range(rect[1], rect[3]):
        for x in range(rect[0], rect[2]):
            index = pixels[x, y]
            color = palette_color(image, index)
            if not is_red_artifact(color):
                continue
            if index not in replacement_cache:
                alpha = palette_alpha(image, index)
                replacement_cache[index] = (
                    neutral_low_alpha_index(image, color, alpha) if alpha < 192 else neutral_luma_index(image, color)
                )
            pixels[x, y] = replacement_cache[index]


def compose_detail_background() -> Image.Image:
    txd_data = embedded_txd(project_path(KFI_BG_RSC).read_bytes(), KFI_BG_TXD_OFFSET)
    page = Image.new("RGBA", (640, 448), (156, 160, 138, 255))
    for name, x, y in [
        ("001", 0, 0),
        ("002", 256, 0),
        ("003", 512, 0),
        ("004", 0, 256),
        ("005", 256, 256),
        ("006", 512, 256),
    ]:
        tile = decode_8bpp_texture(txd_data, f"tex_kfi_bg_{name}").convert("RGBA")
        page.alpha_composite(tile, (x, y))
    return page


def clean_preview_background(image: Image.Image) -> Image.Image:
    """Approximate the in-game muted notebook background for previews.

    Diagnostic TXD extraction exposes PS2 palette colors that the game blends
    down heavily.  The replacement textures themselves stay transparent; this
    cleanup is only for the preview composite.
    """

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


def quantize_to_palette(source: Image.Image, template: Image.Image) -> Image.Image:
    palette = template.getpalette()
    if palette is None:
        raise ValueError("Expected paletted template image")
    output = Image.new("P", source.size, 0)
    output.putpalette(palette)
    pixels = output.load()
    cache: dict[tuple[int, int, int], int] = {}
    source_pixels = source.convert("RGB").load()
    for y in range(source.height):
        for x in range(source.width):
            color = source_pixels[x, y]
            if color not in cache:
                cache[color] = nearest_index(template, color)
            pixels[x, y] = cache[color]
    return output


def render_body_masks() -> tuple[Image.Image, Image.Image]:
    font = ImageFont.truetype(str(FONT_PATH), 17)
    text = (
        "Combatants in black suits bearing a bone emblem. They serve mainly under Ambassador Hell. "
        "Core field troops modified for combat. They also handle abduction and intelligence work."
    )
    dummy = Image.new("L", (1, 1), 0)
    shot_rect = (
        TEXT_SPLIT_X + SHOT_RECT[0],
        SHOT_RECT[1],
        TEXT_SPLIT_X + SHOT_RECT[2],
        SHOT_RECT[3],
    )
    lines = flow_text(
        ImageDraw.Draw(dummy),
        text,
        font,
        x=10,
        y=8,
        width=TEXT_PANEL_SIZE[0] - 20,
        line_height=22,
        bottom=236,
        avoid_rect=shot_rect,
    )
    stroke_mask = Image.new("L", TEXT_PANEL_SIZE, 0)
    fill_mask = Image.new("L", TEXT_PANEL_SIZE, 0)
    for line, xy in lines:
        line_stroke, line_fill = text_masks(TEXT_PANEL_SIZE, xy, line, font)
        stroke_mask = ImageChops.lighter(stroke_mask, line_stroke)
        fill_mask = ImageChops.lighter(fill_mask, line_fill)
    return stroke_mask, fill_mask


def render_mask_slice(
    image: Image.Image,
    stroke_mask: Image.Image,
    fill_mask: Image.Image,
    left: int,
    fill_color: tuple[int, int, int] = (24, 23, 24),
    stroke_color: tuple[int, int, int] = (160, 160, 142),
    fill_index: int | None = None,
    stroke_index: int | None = None,
    darken_index: int | None = None,
) -> None:
    if fill_index is None:
        fill_index = nearest_opaque_index(image, fill_color, exclude={0})
    if stroke_index is None:
        stroke_index = nearest_opaque_index(image, stroke_color, exclude={0, fill_index})
    box = (left, 0, left + TEXTURE_SIZE, TEXTURE_SIZE)
    apply_masked_color(image, stroke_mask.crop(box), stroke_index)
    if darken_index is None:
        apply_masked_color(image, fill_mask.crop(box), fill_index)
    else:
        apply_masked_dithered_color(image, fill_mask.crop(box), fill_index, darken_index)


def render_kfi36_textures(source_root: Path) -> tuple[Path, Path]:
    txd_data = embedded_txd(project_path(KFI36_RSC).read_bytes(), KFI36_TXD_OFFSET)
    original_a = decode_8bpp_texture(txd_data, KFI36_TEXTURE_A)
    original_b = decode_8bpp_texture(txd_data, KFI36_TEXTURE_B)

    image_a = original_a.copy()
    clear_text_regions(image_a, A_PAPER_INDEX, keep_rect=SHOT_RECT)

    image_b = Image.new("P", original_b.size, 0)
    image_b.putpalette(original_b.getpalette())
    image_b.info["transparency"] = original_b.info.get("transparency", bytes([0] + [255] * 255))

    stroke_mask, fill_mask = render_body_masks()
    render_mask_slice(
        image_b,
        stroke_mask,
        fill_mask,
        0,
        fill_index=B_TEXT_FILL_INDEX,
        stroke_index=B_TEXT_STROKE_INDEX,
    )
    render_mask_slice(
        image_a,
        stroke_mask,
        fill_mask,
        TEXT_SPLIT_X,
        fill_index=A_TEXT_FILL_INDEX,
        stroke_index=A_TEXT_STROKE_INDEX,
    )

    source_root.mkdir(parents=True, exist_ok=True)
    path_a = source_root / "KFI_KIJIN_36_RSC__tex_kfi_tx_3600a.png"
    path_b = source_root / "KFI_KIJIN_36_RSC__tex_kfi_tx_3600b.png"
    image_a.save(path_a)
    image_b.save(path_b)
    return path_a, path_b


def make_preview(paths: tuple[Path, Path], preview_root: Path) -> Path:
    path_a, path_b = paths
    preview_root.mkdir(parents=True, exist_ok=True)
    a_pal = Image.open(path_a)
    b_pal = Image.open(path_b)
    a = a_pal.convert("RGBA")
    b = b_pal.convert("RGBA")
    b_alpha = Image.new("L", b_pal.size, 255)
    b_alpha.putdata([0 if index == 0 else 255 for index in b_pal.getdata()])
    b.putalpha(b_alpha)

    game = clean_preview_background(compose_detail_background())
    game.alpha_composite(b, (A_BACKGROUND_LEFT - TEXT_SPLIT_X, A_BACKGROUND_TOP))
    game.alpha_composite(a, (A_BACKGROUND_LEFT, A_BACKGROUND_TOP))

    sheet = game.convert("RGB")
    label_font = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 14)
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((8, 8, 154, 29), fill=(18, 18, 18))
    draw.text((13, 10), "game layout", fill=(255, 255, 235), font=label_font)
    out = preview_root / "kfi36_import_sources.png"
    sheet.save(out)
    return out


def generate_sources(source_root: Path, preview_root: Path) -> tuple[Path, Path]:
    body_a, body_b = render_kfi36_textures(source_root)
    preview = make_preview((body_a, body_b), preview_root)
    print(f"Generated KFI36 source textures under {source_root}")
    print(f"Preview: {preview}")
    return body_a, body_b


def import_sources(source_root: Path) -> None:
    body_a = source_root / "KFI_KIJIN_36_RSC__tex_kfi_tx_3600a.png"
    body_b = source_root / "KFI_KIJIN_36_RSC__tex_kfi_tx_3600b.png"
    for path in (body_a, body_b):
        if not path.is_file():
            raise FileNotFoundError(f"Missing generated source texture: {path}")

    import_rsc_txd(
        KFI36_RSC,
        KFI36_TXD_OFFSET,
        [(KFI36_TEXTURE_A, body_a), (KFI36_TEXTURE_B, body_b)],
        KFI36_OUT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=SOURCE_ROOT)
    parser.add_argument("--preview-root", default=PREVIEW_ROOT)
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--import-only", action="store_true")
    args = parser.parse_args()

    source_root = project_path(args.source_root)
    preview_root = project_path(args.preview_root)
    if not args.import_only:
        generate_sources(source_root, preview_root)
    if not args.generate_only:
        import_sources(source_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
