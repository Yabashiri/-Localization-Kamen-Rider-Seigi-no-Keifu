"""Generate and import localized MENU telop cards.

The telop TXDs use 8bpp indexed PS2 textures.  Cards are intentionally rendered
locally so the in-texture English stays exact; image-generation models are too
prone to spelling errors for these mission objectives.
"""

from __future__ import annotations

import argparse
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from font_mapping import project_path
from txd_import_png import import_png


OFF_WHITE = (199, 200, 187)
MISSION_SIZE = (512, 256)
BATTLE_SIZE = (512, 256)
FONT_PATHS = [
    Path("C:/Windows/Fonts/mvboli.ttf"),
    Path("C:/Windows/Fonts/segoeprb.ttf"),
    Path("C:/Windows/Fonts/Inkfree.ttf"),
    Path("C:/Windows/Fonts/impact.ttf"),
    Path("C:/Windows/Fonts/ariblk.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
]
SELECTED_STROKE_RATIO = 0.036
SELECTED_SHEAR = -0.025


@dataclass(frozen=True)
class MissionCard:
    stem: str
    left_texture: str
    right_texture: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class BattleSet:
    txd: str
    objective_texture: str
    objective_lines: tuple[str, ...]


MISSION_CARDS = [
    MissionCard("TELOP_A_TEX", "tex_te_01_1", "tex_te_01_2", ("DEFEAT THE", "SHOCKER BIKER UNIT!")),
    MissionCard("TELOP_B_TEX", "tex_te_02_1", "tex_te_02_2", ("BREAK THROUGH", "THE SHOCKER MINEFIELD!")),
    MissionCard("TELOP_C_TEX", "tex_te_03_1", "tex_te_03_2", ("ANNIHILATE", "THE RED COMBATANTS!")),
    MissionCard("TELOP_D_TEX", "tex_te_04_1", "tex_te_04_2", ("BREAK THROUGH", "SHOCKER'S TRAP!")),
    MissionCard("TELOP_E_TEX", "tex_te_05_1", "tex_te_05_2", ("DODGE SHOCKER'S", "ATTACK AND PURSUE!")),
]

BATTLE_COMMON = {
    "telop_battle_01": ("BATTLE START",),
    "telop_battle_02": ("VICTORY",),
    "telop_battle_03": ("DEFEAT",),
}

BATTLE_SETS = [
    BattleSet("TELOP_BATTLE_01_TEX", "telop_battle_04", ("DEFEAT 100", "SHOCKER COMBATANTS!")),
    BattleSet("TELOP_BATTLE_02_TEX", "telop_battle_05", ("DEFEAT 10", "SHOCKER SCIENTISTS!")),
    BattleSet("TELOP_BATTLE_03_TEX", "telop_battle_06", ("DEFEAT 30", "RED COMBATANTS!")),
    BattleSet("TELOP_BATTLE_04_TEX", "telop_battle_07", ("DEFEAT 50", "BLACK COMBATANTS!")),
    BattleSet("TELOP_BATTLE_05_TEX", "telop_battle_08", ("DEFEAT 70", "GEL-SHOCKER", "COMBATANTS!")),
    BattleSet("TELOP_BATTLE_06_TEX", "telop_battle_09", ("DEFEAT 15", "GEL-SHOCKER", "SCIENTISTS!")),
    BattleSet("TELOP_BATTLE_07_TEX", "telop_battle_10", ("DEFEAT 15", "ENHANCED BLACK", "COMBATANTS!")),
    BattleSet("TELOP_BATTLE_08_TEX", "telop_battle_11", ("DEFEAT 20", "ENHANCED RED", "COMBATANTS!")),
    BattleSet("TELOP_BATTLE_09_TEX", "telop_battle_12", ("DEFEAT 25", "WOLF-MAN", "TEST SUBJECTS!")),
]


def font_path() -> Path:
    for path in FONT_PATHS:
        if path.is_file():
            return path
    raise FileNotFoundError("No usable Windows font found for telop cards")


def text_bbox(lines: tuple[str, ...], font: ImageFont.FreeTypeFont, spacing: int) -> tuple[int, int]:
    dummy = Image.new("L", (1, 1), 0)
    draw = ImageDraw.Draw(dummy)
    widths = []
    heights = []
    stroke = max(1, int(font.size * SELECTED_STROKE_RATIO))
    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        widths.append(right - left)
        heights.append(bottom - top)
    return max(widths), sum(heights) + spacing * (len(lines) - 1)


def fitted_font(lines: tuple[str, ...], canvas: tuple[int, int], scale: int) -> ImageFont.FreeTypeFont:
    max_width = int(canvas[0] * scale * 0.90)
    max_height = int(canvas[1] * scale * (0.58 if len(lines) == 1 else 0.72))
    path = font_path()
    for size in range(112 * scale, 16 * scale, -2):
        font = ImageFont.truetype(str(path), size=size)
        spacing = max(4 * scale, size // 12)
        width, height = text_bbox(lines, font, spacing)
        if width <= max_width and height <= max_height:
            return font
    return ImageFont.truetype(str(path), size=18 * scale)


def paste_centered_line(mask: Image.Image, line: str, font: ImageFont.FreeTypeFont, center_y: int, rng: random.Random) -> None:
    draw = ImageDraw.Draw(mask)
    stroke = max(2, font.size // 24)
    left, top, right, bottom = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
    width = right - left
    height = bottom - top
    line_mask = Image.new("L", (width + stroke * 8, height + stroke * 8), 0)
    line_draw = ImageDraw.Draw(line_mask)
    line_draw.text((stroke * 4 - left, stroke * 4 - top), line, fill=255, font=font, stroke_width=stroke, stroke_fill=255)

    shear = rng.uniform(-0.075, -0.025)
    extra = int(abs(shear) * line_mask.height) + 12
    sheared = line_mask.transform(
        (line_mask.width + extra, line_mask.height),
        Image.Transform.AFFINE,
        (1, shear, extra if shear < 0 else 0, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    angle = rng.uniform(-1.5, 1.2)
    sheared = sheared.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    x = (mask.width - sheared.width) // 2 + rng.randint(-12, 12)
    y = center_y - sheared.height // 2 + rng.randint(-5, 5)
    left = max(0, x)
    top = max(0, y)
    right = min(mask.width, x + sheared.width)
    bottom = min(mask.height, y + sheared.height)
    if left >= right or top >= bottom:
        return
    src = sheared.crop((left - x, top - y, right - x, bottom - y))
    dst = mask.crop((left, top, right, bottom))
    mask.paste(ImageChops.lighter(dst, src), (left, top))


def distress_mask(mask: Image.Image, seed_text: str) -> Image.Image:
    rng = random.Random(seed_text)
    noise = Image.effect_noise(mask.size, 42).convert("L")
    keep = noise.point(lambda value: 255 if value > rng.randint(48, 62) else 0)
    distressed = ImageChops.multiply(mask, keep)
    cut = ImageDraw.Draw(distressed)
    for _ in range(mask.width // 9):
        x = rng.randint(0, mask.width - 1)
        y = rng.randint(0, mask.height - 1)
        length = rng.randint(mask.width // 28, mask.width // 9)
        width = rng.choice([1, 1, 1, 2])
        cut.line((x, y, min(mask.width, x + length), y + rng.randint(-2, 2)), fill=0, width=width)
    distressed = distressed.point(lambda value: 255 if value >= 72 else 0)
    return distressed


def render_card(lines: tuple[str, ...], size: tuple[int, int]) -> Image.Image:
    scale = 4
    big = (size[0] * scale, size[1] * scale)
    font = fitted_font(lines, size, scale)
    spacing = max(4 * scale, font.size // 12)
    stroke = max(1, int(font.size * SELECTED_STROKE_RATIO))
    line_layer = Image.new("L", big, 0)
    draw = ImageDraw.Draw(line_layer)
    metrics = []
    total_height = spacing * (len(lines) - 1)
    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        metrics.append((line, left, top, right, bottom))
        total_height += bottom - top

    y = (big[1] - total_height) // 2
    for line, left, top, right, bottom in metrics:
        width = right - left
        x = (big[0] - width) // 2 - left
        draw.text((x, y - top), line, fill=255, font=font, stroke_width=stroke, stroke_fill=255)
        y += bottom - top + spacing

    extra = int(abs(SELECTED_SHEAR) * line_layer.height) + 24
    line_layer = line_layer.transform(
        (line_layer.width + extra, line_layer.height),
        Image.Transform.AFFINE,
        (1, SELECTED_SHEAR, extra if SELECTED_SHEAR < 0 else 0, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    left = (line_layer.width - big[0]) // 2
    gray = line_layer.crop((left, 0, left + big[0], big[1]))
    gray = gray.resize(size, Image.Resampling.LANCZOS).point(lambda value: 255 if value >= 52 else 0)

    card = Image.new("P", size, 0)
    palette = [0] * 768
    palette[255 * 3 : 255 * 3 + 3] = list(OFF_WHITE)
    card.putpalette(palette)
    card.putdata([255 if value else 0 for value in gray.getdata()])
    card.info["transparency"] = 0
    return card


def save_card(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, transparency=0)


def generate_sources(output_root: Path) -> dict[str, Path]:
    output_root = project_path(output_root)
    paths: dict[str, Path] = {}

    for card in MISSION_CARDS:
        composite = render_card(card.lines, MISSION_SIZE)
        composite_path = output_root / f"{card.stem}_composite.png"
        save_card(composite_path, composite)
        left = composite.crop((0, 0, 256, 256))
        right = composite.crop((256, 0, 512, 256))
        left_path = output_root / f"{card.stem}_{card.left_texture}.png"
        right_path = output_root / f"{card.stem}_{card.right_texture}.png"
        save_card(left_path, left)
        save_card(right_path, right)
        paths[f"{card.stem}:{card.left_texture}"] = left_path
        paths[f"{card.stem}:{card.right_texture}"] = right_path

    for texture, lines in BATTLE_COMMON.items():
        path = output_root / f"COMMON_{texture}.png"
        save_card(path, render_card(lines, BATTLE_SIZE))
        paths[f"COMMON:{texture}"] = path

    for battle in BATTLE_SETS:
        path = output_root / f"{battle.txd}_{battle.objective_texture}.png"
        save_card(path, render_card(battle.objective_lines, BATTLE_SIZE))
        paths[f"{battle.txd}:{battle.objective_texture}"] = path

    return paths


def import_telops(source_root: Path, game_root: Path, rebuilt_root: Path) -> None:
    source_root = project_path(source_root)
    game_root = project_path(game_root)
    rebuilt_root = project_path(rebuilt_root)
    rebuilt_root.mkdir(parents=True, exist_ok=True)

    for card in MISSION_CARDS:
        input_txd = game_root / f"{card.stem}.TXD"
        output_txd = rebuilt_root / f"{card.stem}.TXD"
        shutil.copy2(input_txd, output_txd)
        for texture in (card.left_texture, card.right_texture):
            png = source_root / f"{card.stem}_{texture}.png"
            tmp = output_txd.with_suffix(".tmp")
            import_png(output_txd, texture, png, tmp)
            tmp.replace(output_txd)

    for battle in BATTLE_SETS:
        input_txd = game_root / f"{battle.txd}.TXD"
        output_txd = rebuilt_root / f"{battle.txd}.TXD"
        shutil.copy2(input_txd, output_txd)
        for texture in BATTLE_COMMON:
            png = source_root / f"COMMON_{texture}.png"
            tmp = output_txd.with_suffix(".tmp")
            import_png(output_txd, texture, png, tmp)
            tmp.replace(output_txd)
        objective = source_root / f"{battle.txd}_{battle.objective_texture}.png"
        tmp = output_txd.with_suffix(".tmp")
        import_png(output_txd, battle.objective_texture, objective, tmp)
        tmp.replace(output_txd)


def make_contact_sheet(source_root: Path, output_path: Path) -> None:
    source_root = project_path(source_root)
    output_path = project_path(output_path)
    entries: list[tuple[str, Path]] = []
    for card in MISSION_CARDS:
        entries.append((card.stem, source_root / f"{card.stem}_composite.png"))
    for texture in BATTLE_COMMON:
        entries.append((texture, source_root / f"COMMON_{texture}.png"))
    for battle in BATTLE_SETS:
        entries.append((battle.objective_texture, source_root / f"{battle.txd}_{battle.objective_texture}.png"))

    thumb_w, thumb_h = 256, 128
    label_h = 28
    cols = 3
    rows = (len(entries) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(entries):
        image = Image.open(path).convert("RGBA")
        bg = Image.new("RGBA", image.size, (60, 60, 60, 255))
        bg.alpha_composite(image)
        thumb = ImageOps.contain(bg.convert("RGB"), (thumb_w, thumb_h))
        x = (index % cols) * thumb_w
        y = (index // cols) * (thumb_h + label_h)
        sheet.paste(thumb, (x, y))
        draw.text((x + 6, y + thumb_h + 6), label, fill=(230, 230, 230))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default="textures_en/EXPORT_TXD/MENU/telop_cards")
    parser.add_argument("--game-root", default="game_dump/DATA/MENU")
    parser.add_argument("--rebuilt-root", default="rebuilt_en/DATA/MENU")
    parser.add_argument("--contact-sheet", default="build/telop_cards/contact_sheet.png")
    parser.add_argument("--generate-only", action="store_true")
    args = parser.parse_args()

    generate_sources(Path(args.source_root))
    make_contact_sheet(Path(args.source_root), Path(args.contact_sheet))
    if not args.generate_only:
        import_telops(Path(args.source_root), Path(args.game_root), Path(args.rebuilt_root))
    print(f"Generated telop cards: {project_path(args.source_root)}")
    print(f"Contact sheet: {project_path(args.contact_sheet)}")
    if not args.generate_only:
        print(f"Imported TXDs: {project_path(args.rebuilt_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
