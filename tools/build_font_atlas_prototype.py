"""Build a Latin font atlas prototype from an external reference sheet.

This is an experiment for the PS2 message font.  It keeps the original Japanese
font pages untouched, replaces only digits and Latin letters in copied PNG
pages, and emits quick sample renders that approximate the fixed-advance game
renderer.
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from font_mapping import project_path


CELL_SIZE = 28
TARGET_BACKGROUND = (0, 0, 0, 255)

# Per-glyph adjustments are intentionally boring data: dx, extra dy, scale.
# They let us tune visual bearings before touching the in-game renderer again.
GLYPH_ADJUSTMENTS = {
    "A": (0, 0, 0.96),
    "C": (0, 0, 1.04),
    "O": (0, 0, 1.04),
    "Q": (0, -1, 1.0),
    "I": (0, 0, 1.04),
    "W": (0, 0, 0.92),
    "'": (-2, 0, 1.25),
    ".": (-2, 0, 1.0),
    ",": (-2, 0, 1.0),
}


@dataclass(frozen=True)
class GlyphSource:
    char: str
    box: tuple[int, int, int, int]
    trim_y: bool


def source_glyphs() -> dict[str, GlyphSource]:
    glyphs: dict[str, GlyphSource] = {}

    def add(char: str, box: tuple[int, int, int, int], trim_y: bool) -> None:
        glyphs[char] = GlyphSource(char, box, trim_y)

    def add_many(chars: str, boxes: list[tuple[int, int]], y0: int, y1: int, trim_y: bool) -> None:
        if len(chars) != len(boxes):
            raise ValueError(f"Glyph list length mismatch for {chars!r}")
        for char, (x0, x1) in zip(chars, boxes):
            glyphs[char] = GlyphSource(char, (x0, y0, x1, y1), trim_y)

    add("!", (31, 0, 36, 27), False)
    add("'", (197, 1, 203, 8), True)
    add('"', (57, 0, 68, 27), False)
    add("%", (142, 0, 166, 27), False)
    add("(", (227, 0, 235, 27), False)
    add(")", (254, 0, 262, 27), False)
    add("+", (310, 0, 326, 27), False)
    add(",", (337, 0, 343, 27), False)
    add("-", (365, 0, 382, 27), False)
    add(".", (393, 0, 399, 27), False)
    add("/", (422, 0, 445, 27), False)
    add_many("01", [(450, 464), (480, 490)], 0, 27, True)
    add(":", (227, 28, 233, 54), False)
    add(";", (255, 28, 261, 54), False)
    add("?", (367, 28, 380, 54), False)
    add_many(
        "23456789",
        [(2, 16), (31, 44), (58, 72), (87, 100), (114, 128), (143, 156), (170, 184), (198, 212)],
        28,
        54,
        True,
    )
    add_many("ABC", [(421, 441), (449, 469), (478, 496)], 28, 54, True)
    add_many(
        "DEFGHIJKLMNOPQRSTU",
        [
            (1, 21),
            (30, 48),
            (58, 76),
            (85, 105),
            (113, 134),
            (141, 152),
            (169, 184),
            (197, 219),
            (225, 242),
            (253, 277),
            (281, 303),
            (309, 329),
            (337, 355),
            (365, 385),
            (393, 413),
            (421, 437),
            (449, 466),
            (477, 497),
        ],
        56,
        83,
        True,
    )
    add_many("VWXYZ", [(1, 20), (28, 55), (57, 77), (84, 105), (113, 130)], 84, 111, True)
    add_many(
        "abcdefg",
        [(308, 322), (336, 350), (364, 374), (392, 406), (420, 433), (449, 461), (476, 492)],
        84,
        111,
        False,
    )
    add_many(
        "hijklmnopqrstuvwxy",
        [
            (0, 16),
            (28, 36),
            (56, 66),
            (84, 100),
            (112, 120),
            (140, 162),
            (168, 184),
            (196, 210),
            (224, 238),
            (252, 266),
            (280, 292),
            (309, 320),
            (336, 346),
            (364, 380),
            (392, 406),
            (420, 439),
            (448, 462),
            (476, 491),
        ],
        112,
        139,
        False,
    )
    glyphs["z"] = GlyphSource("z", (0, 142, 13, 165), False)
    return glyphs


def visible_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    pixels = image.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a and (r or g or b):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def remap_reference_colors(image: Image.Image, palette: list[tuple[int, int, int, int]]) -> Image.Image:
    """Map reference colors to the closest colors from the current game font."""

    output = Image.new("RGBA", image.size, (0, 0, 0, 0))
    in_pixels = image.load()
    out_pixels = output.load()

    def distance(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> int:
        return sum((left[i] - right[i]) ** 2 for i in range(3))

    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = in_pixels[x, y]
            if not a or not (r or g or b):
                continue
            closest = min((color for color in palette if color != TARGET_BACKGROUND), key=lambda color: distance((r, g, b, a), color))
            out_pixels[x, y] = closest
    return output


def glyph_adjustment(source_char: str, cap_dy: int) -> tuple[int, int, float]:
    dx, dy, scale = GLYPH_ADJUSTMENTS.get(source_char, (0, 0, 1.0))
    if "A" <= source_char <= "Z":
        dy += cap_dy
    return dx, dy, scale


def paste_glyph(
    cell: Image.Image,
    source_char: str,
    glyph: Image.Image,
    trim_y: bool,
    scale: float,
    cap_dy: int,
    bearing_mode: str,
) -> None:
    bbox = visible_bbox(glyph)
    if bbox is None:
        return
    dx, dy, glyph_scale = glyph_adjustment(source_char, cap_dy)
    scale *= glyph_scale
    x0, y0, x1, y1 = bbox
    glyph = glyph.crop((x0, y0, x1 + 1, y1 + 1))
    if scale != 1.0:
        scaled_size = (
            max(1, round(glyph.size[0] * scale)),
            max(1, round(glyph.size[1] * scale)),
        )
        glyph = glyph.resize(scaled_size, Image.Resampling.LANCZOS)
    width, height = glyph.size
    if bearing_mode == "left":
        x = 2 + dx
    else:
        x = (CELL_SIZE - width) // 2 + dx
    x = max(0, min(CELL_SIZE - width, x))
    if trim_y:
        y = max(0, min(CELL_SIZE - height, round(4 + (1.0 - scale) * 4)))
    else:
        baseline = 24
        y = round(baseline - (baseline - y0) * scale)
        y = max(0, min(CELL_SIZE - height, y))
    y = max(0, min(CELL_SIZE - height, y + dy))

    cell.paste(TARGET_BACKGROUND, (0, 0, CELL_SIZE, CELL_SIZE))
    cell.alpha_composite(glyph, (x, y))


def font_palette(*images: Image.Image) -> list[tuple[int, int, int, int]]:
    colors: set[tuple[int, int, int, int]] = set()
    for image in images:
        for color_count in image.getcolors(maxcolors=1000000) or []:
            _count, color = color_count
            colors.add(color)
    return sorted(colors)


def page0_positions() -> dict[str, tuple[int, int]]:
    positions: dict[str, tuple[int, int]] = {}
    for index, char in enumerate("012345678"):
        positions[char] = (index, 0)
    positions["9"] = (0, 1)
    positions["+"] = (2, 1)
    positions["-"] = (3, 1)
    positions[":"] = (4, 1)
    positions[","] = (5, 1)
    positions["."] = (7, 1)
    positions["?"] = (0, 2)
    positions["!"] = (1, 2)
    positions['"'] = (6, 2)
    positions["'"] = (7, 2)
    positions["("] = (8, 2)
    positions[")"] = (0, 3)
    positions["%"] = (7, 3)
    positions[";"] = (0, 5)
    positions["/"] = (2, 5)

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    page0_indexes = range(55, 81)
    for index, char in zip(page0_indexes, letters):
        positions[char] = (index % 9, index // 9)
    return positions


def page1_positions() -> dict[str, tuple[int, int]]:
    positions: dict[str, tuple[int, int]] = {}
    for index, char in enumerate("abcdefghijklmnopqrstuvwxyz"):
        positions[char] = (index % 9, index // 9)
    return positions


def apply_replacements(
    reference_path: Path,
    output_root: Path,
    scale: float,
    cap_dy: int,
    bearing_mode: str,
) -> tuple[Path, Path]:
    page0_path = project_path("dump_jp/EXPORT_TXD/FONT_font_00.png")
    page1_path = project_path("dump_jp/EXPORT_TXD/FONT_font_01.png")
    page0 = Image.open(page0_path).convert("RGBA")
    page1 = Image.open(page1_path).convert("RGBA")
    reference = Image.open(reference_path).convert("RGBA")
    palette = font_palette(page0, page1)
    glyph_map = source_glyphs()

    for char, (col, row) in page0_positions().items():
        source = glyph_map[char]
        raw = reference.crop((source.box[0], source.box[1], source.box[2] + 1, source.box[3] + 1))
        glyph = remap_reference_colors(raw, palette)
        cell = page0.crop((col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
        paste_glyph(cell, char, glyph, source.trim_y, scale, cap_dy, bearing_mode)
        page0.paste(cell, (col * CELL_SIZE, row * CELL_SIZE))

    for char, (col, row) in page1_positions().items():
        source = glyph_map[char]
        raw = reference.crop((source.box[0], source.box[1], source.box[2] + 1, source.box[3] + 1))
        glyph = remap_reference_colors(raw, palette)
        cell = page1.crop((col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
        paste_glyph(cell, char, glyph, source.trim_y, scale, cap_dy, bearing_mode)
        page1.paste(cell, (col * CELL_SIZE, row * CELL_SIZE))

    output_root.mkdir(parents=True, exist_ok=True)
    out0 = output_root / "FONT_font_00.png"
    out1 = output_root / "FONT_font_01.png"
    page0.save(out0)
    page1.save(out1)
    return out0, out1


def physical_positions() -> dict[str, tuple[int, int, int]]:
    positions: dict[str, tuple[int, int, int]] = {}
    for char, (col, row) in page0_positions().items():
        positions[char] = (0, col, row)
    for char, (col, row) in page1_positions().items():
        positions[char] = (1, col, row)
    return positions


def render_sample(pages: dict[int, Image.Image], text: str, advance: int, output_path: Path) -> None:
    positions = physical_positions()
    width = max(1, (len(text) - 1) * advance + CELL_SIZE + 12)
    height = 52
    image = Image.new("RGBA", (width, height), TARGET_BACKGROUND)
    x = 6
    y = 12
    for char in text:
        if char == " ":
            x += advance
            continue
        if char not in positions:
            x += advance
            continue
        page, col, row = positions[char]
        glyph = pages[page].crop((col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
        mask = Image.new("L", glyph.size, 0)
        mask_pixels = mask.load()
        glyph_pixels = glyph.load()
        for gy in range(glyph.height):
            for gx in range(glyph.width):
                r, g, b, a = glyph_pixels[gx, gy]
                if a and (r or g or b):
                    mask_pixels[gx, gy] = 255
        image.paste(glyph, (x, y), mask)
        x += advance
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def build_previews(prototype_root: Path, preview_root: Path) -> None:
    current_pages = {
        0: Image.open(project_path("dump_jp/EXPORT_TXD/FONT_font_00.png")).convert("RGBA"),
        1: Image.open(project_path("dump_jp/EXPORT_TXD/FONT_font_01.png")).convert("RGBA"),
    }
    prototype_pages = {
        0: Image.open(prototype_root / "FONT_font_00.png").convert("RGBA"),
        1: Image.open(prototype_root / "FONT_font_01.png").convert("RGBA"),
    }
    sample_lines = [
        "Rider Energy L",
        "Restores a large",
        "amount of Rider Energy",
    ]
    for advance in (12, 13, 14):
        for index, line in enumerate(sample_lines):
            render_sample(current_pages, line, advance, preview_root / f"current_a{advance}_{index}.png")
            render_sample(prototype_pages, line, advance, preview_root / f"prototype_a{advance}_{index}.png")

    for advance in (10, 11, 12, 13, 14):
        build_preview_sheet(prototype_pages, advance, preview_root / f"prototype_phrase_sheet_a{advance}.png")
    build_proportional_preview_sheet(prototype_pages, preview_root / "prototype_phrase_sheet_prop.png")


def render_line_on_sheet(draw_target: Image.Image, pages: dict[int, Image.Image], text: str, advance: int, x: int, y: int) -> None:
    positions = physical_positions()
    cursor_x = x
    for char in text:
        if char == " ":
            cursor_x += advance
            continue
        if char not in positions:
            cursor_x += advance
            continue
        page, col, row = positions[char]
        glyph = pages[page].crop((col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
        mask = Image.new("L", glyph.size, 0)
        mask_pixels = mask.load()
        glyph_pixels = glyph.load()
        for gy in range(glyph.height):
            for gx in range(glyph.width):
                r, g, b, a = glyph_pixels[gx, gy]
                if a and (r or g or b):
                    mask_pixels[gx, gy] = 255
        draw_target.paste(glyph, (cursor_x, y), mask)
        cursor_x += advance


PROPORTIONAL_ADVANCE_OVERRIDES = {
    " ": 6,
    "'": 4,
    '"': 7,
    ".": 5,
    ",": 5,
    ":": 5,
    ";": 5,
    "!": 5,
    "?": 10,
    "(": 7,
    ")": 7,
    "/": 10,
    "-": 8,
    "+": 11,
    "%": 16,
    "I": 8,
    "J": 10,
    "L": 12,
    "M": 17,
    "T": 12,
    "W": 18,
    "i": 7,
    "j": 7,
    "l": 7,
    "f": 8,
    "r": 8,
    "t": 8,
    "m": 16,
    "w": 14,
}


def proportional_advance(char: str, glyph: Image.Image) -> int:
    if char == " ":
        return PROPORTIONAL_ADVANCE_OVERRIDES[char]
    bbox = visible_bbox(glyph)
    if bbox is None:
        return PROPORTIONAL_ADVANCE_OVERRIDES[" "]
    x0, _y0, x1, _y1 = bbox
    width = x1 - x0 + 1
    if char in PROPORTIONAL_ADVANCE_OVERRIDES:
        advance = PROPORTIONAL_ADVANCE_OVERRIDES[char]
        if char in {"'", ".", ",", ":", ";", "!"}:
            return max(advance, width)
        return max(advance, width + 1)
    if "A" <= char <= "Z":
        return max(8, min(20, width + 1))
    if "a" <= char <= "z":
        return max(7, min(18, width + 1))
    if "0" <= char <= "9":
        return max(9, min(13, width + 1))
    return max(5, min(18, width + 1))


def render_line_on_sheet_proportional(
    draw_target: Image.Image,
    pages: dict[int, Image.Image],
    text: str,
    x: int,
    y: int,
) -> None:
    positions = physical_positions()
    cursor_x = x
    for char in text:
        if char == " ":
            cursor_x += proportional_advance(char, Image.new("RGBA", (1, 1)))
            continue
        if char not in positions:
            cursor_x += proportional_advance(char, Image.new("RGBA", (1, 1)))
            continue
        page, col, row = positions[char]
        glyph = pages[page].crop((col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
        mask = Image.new("L", glyph.size, 0)
        mask_pixels = mask.load()
        glyph_pixels = glyph.load()
        for gy in range(glyph.height):
            for gx in range(glyph.width):
                r, g, b, a = glyph_pixels[gx, gy]
                if a and (r or g or b):
                    mask_pixels[gx, gy] = 255
        draw_target.paste(glyph, (cursor_x, y), mask)
        cursor_x += proportional_advance(char, glyph)


def build_preview_sheet(pages: dict[int, Image.Image], advance: int, output_path: Path) -> None:
    phrases = [
        "Don't remove the Memory Card PS2.",
        "What's this? It's locked.",
        "ROOM ACCESS CODE CHANGE ORDER",
        "CHANGE THE ACCESS CODE",
        "FOR THE OPERATIONS PLANNING ROOM",
        "Rider Energy S",
        "Restores a small amount of Rider Energy",
        "Chapter Agi to Power Plant Entrance",
        "Power Plant Central Control Room",
        "No data",
        "Loading...",
        "Old No1 - New No1",
        "(Test) A/B + 50%",
        "Garagaranda's file was obtained.",
        "Kamen Rider, show us your true power.",
        "The door won't open from this side.",
    ]
    line_height = 38
    width = 980
    height = len(phrases) * line_height + 18
    sheet = Image.new("RGBA", (width, height), TARGET_BACKGROUND)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(sheet)
    for row, phrase in enumerate(phrases):
        y = 10 + row * line_height
        draw.line((0, y + line_height - 4, width, y + line_height - 4), fill=(24, 24, 24, 255))
        draw.text((6, y + 6), f"a{advance}", fill=(90, 90, 90, 255))
        render_line_on_sheet(sheet, pages, phrase, advance, 46, y + 5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def build_proportional_preview_sheet(pages: dict[int, Image.Image], output_path: Path) -> None:
    phrases = [
        "Don't remove the Memory Card PS2.",
        "What's this? It's locked.",
        "ROOM ACCESS CODE CHANGE ORDER",
        "CHANGE THE ACCESS CODE",
        "FOR THE OPERATIONS PLANNING ROOM",
        "Rider Energy S",
        "Restores a small amount of Rider Energy",
        "Chapter Agi to Power Plant Entrance",
        "Power Plant Central Control Room",
        "No data",
        "Loading...",
        "Old No1 - New No1",
        "(Test) A/B + 50%",
        "Garagaranda's file was obtained.",
        "Kamen Rider, show us your true power.",
        "The door won't open from this side.",
    ]
    line_height = 38
    width = 980
    height = len(phrases) * line_height + 18
    sheet = Image.new("RGBA", (width, height), TARGET_BACKGROUND)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(sheet)
    for row, phrase in enumerate(phrases):
        y = 10 + row * line_height
        draw.line((0, y + line_height - 4, width, y + line_height - 4), fill=(24, 24, 24, 255))
        draw.text((6, y + 6), "prop", fill=(90, 90, 90, 255))
        render_line_on_sheet_proportional(sheet, pages, phrase, 46, y + 5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default=r"E:\Download\11\257365.png")
    parser.add_argument("--output-root", default="textures_en/EXPORT_TXD/font_prototype")
    parser.add_argument("--preview-root", default="build/font_preview")
    parser.add_argument("--scale", type=float, default=0.74)
    parser.add_argument("--cap-dy", type=int, default=1)
    parser.add_argument("--bearing-mode", choices=("center", "left"), default="left")
    parser.add_argument("--copy-unchanged-pages", action="store_true")
    args = parser.parse_args()

    output_root = project_path(args.output_root)
    preview_root = project_path(args.preview_root)
    out0, out1 = apply_replacements(Path(args.reference), output_root, args.scale, args.cap_dy, args.bearing_mode)
    if args.copy_unchanged_pages:
        for page in range(2, 14):
            shutil.copy2(project_path(f"dump_jp/EXPORT_TXD/FONT_font_{page:02d}.png"), output_root / f"FONT_font_{page:02d}.png")
    build_previews(output_root, preview_root)
    print(f"Wrote {out0}")
    print(f"Wrote {out1}")
    print(f"Wrote previews to {preview_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
