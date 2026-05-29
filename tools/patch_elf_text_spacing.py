"""Patch English text layout behavior and hardcoded UI strings in the game ELF.

The custom message font advances the X cursor by a fixed 28.0 pixels after each
glyph. That matches Japanese full-width cells, but it makes Latin text render as
widely spaced letters. This smoke-test patch lowers that fixed X advance.

The scenario message renderer also centers text with ``(18 - maxLineLen) * 14``.
For English lines longer than 18 glyphs that correction becomes negative and
pushes lower textbox text off the left edge. The scenario anchor patch clamps
that correction at zero while preserving the original centering for short lines.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

from font_mapping import project_path


ADVANCE_OFFSET = 0x169F7C - 0x100000 + 0x80
PROPORTIONAL_ADVANCE_CAVE_OFFSET = 0x24EED0
PROPORTIONAL_ADVANCE_CAVE_VADDR = PROPORTIONAL_ADVANCE_CAVE_OFFSET - 0x80 + 0x100000
PROPORTIONAL_ADVANCE_TABLE_SIZE = 0x200
PROPORTIONAL_ADVANCE_TABLE_VADDR = PROPORTIONAL_ADVANCE_CAVE_VADDR + 0x50

SCENARIO_CENTERING_OFFSET = 0x171180 - 0x100000 + 0x80
SCENARIO_CENTERING_EXPECTED = bytes.fromhex(
    # 0x171180: mtc1 v1,f0
    # 0x171184: subu a0,a0,a1
    # 0x171188: sll v1,a0,3
    # 0x17118c: subu v1,v1,a0
    # 0x171190: sll v1,v1,2
    # 0x171194: mtc1 v1,f1
    # 0x171198: nop
    # 0x17119c: cvt.s.w f1,f1
    # 0x1711a0: div.s f0,f1,f0
    "00008344"
    "23208500"
    "c0180400"
    "23186400"
    "80180300"
    "00088344"
    "00000000"
    "60088046"
    "03080046"
)
SCENARIO_CENTERING_REPLACEMENT = bytes.fromhex(
    # a0 = 18 - maxLineLen
    # if a0 < 0, v1 = 0
    # else v1 = a0 * 14
    # f0 = float(v1)
    "23208500"  # subu a0,a0,a1
    "2a088000"  # slt at,a0,zero
    "00190400"  # sll v1,a0,4
    "23186400"  # subu v1,v1,a0
    "23186400"  # subu v1,v1,a0
    "0b180100"  # movn v1,zero,at
    "00088344"  # mtc1 v1,f1
    "60088046"  # cvt.s.w f1,f1
    "06080046"  # mov.s f0,f1
)


@dataclass(frozen=True)
class SjisTextPatch:
    offset: int
    slot_size: int
    expected: str
    replacement: str
    label: str


SJIS_TEXT_PATCHES = (
    SjisTextPatch(0x2F7DA0, 16, "ＰＡＵＳＥ", "PAUSE", "pause label"),
    SjisTextPatch(
        0x2FC640,
        64,
        "　　　　　怪人ファイル『ガラガランダ』\\n　　　　　を入手した",
        "Obtained kaijin file\\nGaragaranda",
        "Garagaranda file pickup",
    ),
    SjisTextPatch(
        0x2FC680,
        64,
        "　　　　怪人ファイル『ヒルカメレオン』\\n　　　　を入手した",
        "Obtained kaijin file\\nHiruchameleon",
        "Hiruchameleon file pickup",
    ),
    SjisTextPatch(
        0x2FC6C0,
        64,
        "　　　怪人ファイル『ヒルカメレオン転生体』\\n　　　を入手した",
        "Obtained kaijin file\\nHiruchameleon Reborn",
        "Hiruchameleon Reborn file pickup",
    ),
    SjisTextPatch(
        0x2FC700,
        64,
        "　　怪人ファイル『イソギンジャガー転生体』\\n　　を入手した",
        "Obtained kaijin file\\nIsoginjaguar Reborn",
        "Isoginjaguar Reborn file pickup",
    ),
    SjisTextPatch(
        0x2FC740,
        64,
        "　　　怪人ファイル『サソリトカゲス転生体』\\n　　　を入手した",
        "Obtained kaijin file\\nSasoritokages Reborn",
        "Sasoritokages Reborn file pickup",
    ),
    SjisTextPatch(
        0x2FC780,
        64,
        "　　　　　怪人ファイル『イカデビル』\\n　　　　　を入手した",
        "Obtained kaijin file\\nIkadevil",
        "Ikadevil file pickup",
    ),
    SjisTextPatch(
        0x2FC7C0,
        64,
        "　　　　　怪人ファイル『ザンジオー』\\n　　　　　を入手した",
        "Obtained kaijin file\\nZanji-O",
        "Zanji-O file pickup",
    ),
    SjisTextPatch(
        0x2FC800,
        64,
        "　　　　怪人ファイル『ザンジオー強化体』\\n　　　　を入手した",
        "Obtained kaijin file\\nEnhanced Zanji-O",
        "Enhanced Zanji-O file pickup",
    ),
    SjisTextPatch(
        0x2FC840,
        64,
        "　　　　　　怪人ファイル『狼男』\\n　　　　　　を入手した",
        "Obtained kaijin file\\nWolf Man",
        "Wolf Man file pickup",
    ),
    SjisTextPatch(
        0x2FC880,
        64,
        "　　　　　怪人ファイル『サボテグロン』\\n　　　　　を入手した",
        "Obtained kaijin file\\nSabotegron",
        "Sabotegron file pickup",
    ),
    SjisTextPatch(
        0x2FC8C0,
        64,
        "　　　　怪人ファイル『邪眼完全体』\\n　　　　を入手した",
        "Obtained kaijin file\\nJagan Complete Form",
        "Jagan Complete Form file pickup",
    ),
    SjisTextPatch(
        0x2FC900,
        64,
        "　　　　怪人ファイル『邪眼究極体』\\n　　　　を入手した",
        "Obtained kaijin file\\nJagan Ultimate Form",
        "Jagan Ultimate Form file pickup",
    ),
    SjisTextPatch(0x2FCBF0, 48, "ＰＲＥＳＳ　ＳＴＡＲＴ　ＢＵＴＴＯＮ", "PRESS START BUTTON", "press start label"),
    SjisTextPatch(0x2FD360, 32, "仮面ライダー正義の系譜", "Kamen Rider: Seigi no Keifu", "game title label"),
    SjisTextPatch(0x2FDB30, 48, "　　　オプションの設定をセーブしますか？", "      Save option settings?", "option save prompt"),
    SjisTextPatch(0x2FDB60, 40, "　　　　　　　　はい　　　いいえ", "        Yes        No", "option save choices"),
    SjisTextPatch(0x2FE160, 32, "残り時間　%02d:%02d:%02d", "Time Left %02d:%02d:%02d", "remaining time label"),
    SjisTextPatch(0x2FE3A0, 48, "\\n\\n　　リンクボタンを選択して下さい　　", "\\n\\n    Select a link button", "link button prompt"),
    SjisTextPatch(0x2FE410, 8, "Ｌ３", "L3", "L3 button label"),
    SjisTextPatch(0x2FE418, 8, "Ｒ３", "R3", "R3 button label"),
    SjisTextPatch(0x2FE420, 8, "Ｌ１", "L1", "L1 button label"),
    SjisTextPatch(0x2FE428, 8, "Ｌ２", "L2", "L2 button label"),
    SjisTextPatch(0x2FE430, 8, "Ｒ１", "R1", "R1 button label"),
    SjisTextPatch(0x2FE438, 8, "Ｒ２", "R2", "R2 button label"),
    SjisTextPatch(0x2FE440, 16, "スタート", "Start", "Start button label"),
    SjisTextPatch(0x2FE450, 16, "セレクト", "Select", "Select button label"),
    SjisTextPatch(0x2FE7C8, 16, "クリアタイム", "Clear Time", "clear time result label"),
    SjisTextPatch(0x2FE7D8, 24, "倒した戦闘員数", "Troops Defeated", "defeated soldiers result label"),
    SjisTextPatch(0x2FE7F0, 32, "必殺技で倒した怪人数", "Kaijin Finisher KOs", "special kaijin result label"),
    SjisTextPatch(0x2FE810, 32, "バイクアクションランキング", "Bike Action Ranking", "bike ranking result label"),
    SjisTextPatch(0x2FE830, 8, "Ｖ３", "V3", "V3 label"),
    SjisTextPatch(0x2FE838, 8, "１号", "No1", "No1 label"),
    SjisTextPatch(0x2FE840, 16, "ランキング", "Ranking", "ranking label"),
    SjisTextPatch(0x2FE880, 16, "%02d：%02d", "%02d:%02d", "result time format"),
    SjisTextPatch(0x2FE890, 8, "%04d体", "%04d", "result four-digit count format"),
    SjisTextPatch(0x2FE898, 8, "%02d体", "%02d", "result two-digit count format"),
    SjisTextPatch(0x2FEF20, 48, "　　　　どちらの１号で戦いますか？", "    Which No1 Rider will fight?", "No1 rider select prompt"),
    SjisTextPatch(0x2FEF50, 32, "\t\t\t　　　旧１号　　　新１号", "\t\t\tOld No1    New No1", "No1 rider select choices"),
    SjisTextPatch(0x2FEF70, 48, "　　　　どちらの２号で戦いますか？", "    Which No2 Rider will fight?", "No2 rider select prompt"),
    SjisTextPatch(0x2FEFA0, 32, "\t\t\t　　　旧２号　　　新２号", "\t\t\tOld No2    New No2", "No2 rider select choices"),
    SjisTextPatch(0x2FEFD0, 48, "　　　この仮面ライダーで戦いますか？", "    Fight as this Kamen Rider?", "rider confirm prompt"),
    SjisTextPatch(0x2FF000, 32, "\t\t\t　　　　はい　　　いいえ", "\t\t\t        Yes        No", "rider confirm choices"),
    SjisTextPatch(0x2FF020, 48, "使用する仮面ライダーを選んでください", "Select the Kamen Rider to use", "rider select instruction"),
    SjisTextPatch(0x2FF070, 16, "倒した戦闘員数", "Troops Defeated", "defeated soldiers record label"),
    SjisTextPatch(0x2FF080, 24, "必殺技で倒した怪人数", "Kaijin Finisher KOs", "special kaijin record label"),
    SjisTextPatch(0x2FF098, 16, "トータルタイム", "Total Time", "total time record label"),
    SjisTextPatch(0x2FF0A8, 16, "ベストタイム", "Best Time", "best time record label"),
    SjisTextPatch(0x2FF0B8, 16, "ベストランク", "Best Rank", "best rank record label"),
    SjisTextPatch(0x2FF0C8, 8, "コース", "Course", "course record label"),
    SjisTextPatch(0x2FF0E0, 16, "%02d：%02d", "%02d:%02d", "record time format"),
    SjisTextPatch(0x2FF0F0, 8, "%04d体", "%04d", "record four-digit count format"),
    SjisTextPatch(0x2FF0F8, 8, "%03d体", "%03d", "record three-digit count format"),
)


def patch_expected_bytes(handle, offset: int, expected: bytes, replacement: bytes, label: str, dry_run: bool) -> None:
    handle.seek(offset)
    current = handle.read(len(expected))
    if current != expected:
        raise ValueError(
            f"Unexpected bytes for {label} at 0x{offset:X}: {current.hex()} != {expected.hex()}"
        )
    if not dry_run:
        handle.seek(offset)
        handle.write(replacement)


def encode_r(rs: int, rt: int, rd: int, shamt: int, funct: int) -> bytes:
    return struct.pack("<I", (rs << 21) | (rt << 16) | (rd << 11) | (shamt << 6) | funct)


def encode_i(opcode: int, rs: int, rt: int, immediate: int) -> bytes:
    return struct.pack("<I", (opcode << 26) | (rs << 21) | (rt << 16) | (immediate & 0xFFFF))


def encode_j(opcode: int, target_vaddr: int) -> bytes:
    return struct.pack("<I", (opcode << 26) | ((target_vaddr >> 2) & 0x03FFFFFF))


def encode_beq(rs: int, rt: int, pc: int, target_vaddr: int) -> bytes:
    offset = (target_vaddr - (pc + 4)) // 4
    if target_vaddr != pc + 4 + offset * 4:
        raise ValueError(f"Unaligned branch target: 0x{target_vaddr:X}")
    if not -0x8000 <= offset <= 0x7FFF:
        raise ValueError(f"Branch target out of range: 0x{pc:X} -> 0x{target_vaddr:X}")
    return encode_i(0x04, rs, rt, offset)


def encode_lui(rt: int, value: int) -> bytes:
    return encode_i(0x0F, 0, rt, value)


def split_hi_lo(address: int) -> tuple[int, int]:
    return (address + 0x8000) >> 16, address & 0xFFFF


def build_proportional_width_table(atlas_root: Path, fallback_advance: int) -> bytes:
    if not 1 <= fallback_advance <= 28:
        raise ValueError(f"Fallback advance should stay in a conservative range: {fallback_advance}")

    from PIL import Image
    from build_font_atlas_prototype import (
        CELL_SIZE,
        page0_positions,
        page1_positions,
        proportional_advance,
        visible_bbox,
    )
    from encode_all_text import ASCII_DIRECT_FONT_CODES

    positions: dict[str, tuple[int, int, int]] = {}
    for char, (col, row) in page0_positions().items():
        positions[char] = (0, col, row)
    for char, (col, row) in page1_positions().items():
        positions[char] = (1, col, row)

    pages = {
        0: Image.open(atlas_root / "FONT_font_00.png").convert("RGBA"),
        1: Image.open(atlas_root / "FONT_font_01.png").convert("RGBA"),
    }
    table = bytearray([fallback_advance] * PROPORTIONAL_ADVANCE_TABLE_SIZE)
    for char, code in ASCII_DIRECT_FONT_CODES.items():
        if code >= len(table):
            continue
        if char not in positions:
            continue
        page, col, row = positions[char]
        glyph = pages[page].crop((col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
        table[code] = proportional_advance(char, glyph)
    table[ASCII_DIRECT_FONT_CODES[" "]] = 6

    def page0_glyph_advance(code: int, padding: int = 2) -> int:
        col = code % 9
        row = code // 9
        glyph = pages[0].crop((col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
        bbox = visible_bbox(glyph)
        if bbox is None:
            return fallback_advance
        x0, _y0, x1, _y1 = bbox
        return max(1, min(28, x1 - x0 + 1 + padding))

    # HINT.BIN can emit these through fullwidth SJIS punctuation and button
    # placeholders. They are wider than the Latin fallback, so reserve their
    # real cell width to keep following letters from touching them.
    for code in (0x0020, 0x0021, 0x0027, 0x002A, 0x002B, 0x002C):
        table[code] = page0_glyph_advance(code)
    return bytes(table)


def build_proportional_advance_payload(atlas_root: Path, fallback_advance: int) -> bytes:
    zero = 0
    at = 1
    v0 = 2
    v1 = 3
    s1 = 17
    f0 = 0
    f21 = 21

    default_vaddr = PROPORTIONAL_ADVANCE_CAVE_VADDR + 0x2C
    convert_vaddr = PROPORTIONAL_ADVANCE_CAVE_VADDR + 0x30
    table_hi, table_lo = split_hi_lo(PROPORTIONAL_ADVANCE_TABLE_VADDR)

    code = bytearray()
    pc = PROPORTIONAL_ADVANCE_CAVE_VADDR

    def emit(instruction: bytes) -> None:
        nonlocal pc
        code.extend(instruction)
        pc += 4

    emit(encode_i(0x25, s1, v0, 0))  # lhu v0,0(s1)
    emit(encode_i(0x09, s1, s1, 2))  # addiu s1,s1,2
    emit(encode_i(0x0B, v0, at, PROPORTIONAL_ADVANCE_TABLE_SIZE))  # sltiu at,v0,0x200
    emit(encode_beq(at, zero, pc, default_vaddr))
    emit(struct.pack("<I", 0))  # nop
    emit(encode_lui(v1, table_hi))
    emit(encode_i(0x09, v1, v1, table_lo))
    emit(encode_r(v1, v0, v1, 0, 0x21))  # addu v1,v1,v0
    emit(encode_i(0x24, v1, v1, 0))  # lbu v1,0(v1)
    emit(encode_beq(zero, zero, pc, convert_vaddr))
    emit(struct.pack("<I", 0))  # nop
    emit(encode_i(0x09, zero, v1, fallback_advance))  # addiu v1,zero,fallback
    emit(struct.pack("<I", (0x11 << 26) | (4 << 21) | (v1 << 16) | (f0 << 11)))  # mtc1 v1,f0
    emit(struct.pack("<I", 0))  # nop
    emit(struct.pack("<I", 0x46800020))  # cvt.s.w f0,f0
    emit(struct.pack("<I", 0))  # nop
    emit(struct.pack("<I", 0x4600AD40))  # add.s f21,f21,f0
    emit(encode_j(0x02, 0x00169F90))
    emit(struct.pack("<I", 0))  # nop

    if len(code) > 0x50:
        raise ValueError(f"Proportional advance code is too large: 0x{len(code):X}")
    code.extend(bytes(0x50 - len(code)))
    code.extend(build_proportional_width_table(atlas_root, fallback_advance))
    return bytes(code)


def patch_proportional_advance(handle, atlas_root: Path, fallback_advance: int, dry_run: bool) -> None:
    expected = bytes.fromhex(
        "e041033c"  # lui v1,0x41e0
        "02003126"  # addiu s1,s1,2
    )
    replacement = encode_j(0x02, PROPORTIONAL_ADVANCE_CAVE_VADDR) + bytes(4)
    patch_expected_bytes(
        handle,
        ADVANCE_OFFSET,
        expected,
        replacement,
        "afMsgDrawString proportional X advance jump",
        dry_run,
    )

    payload = build_proportional_advance_payload(atlas_root, fallback_advance)
    handle.seek(PROPORTIONAL_ADVANCE_CAVE_OFFSET)
    current = handle.read(len(payload))
    if current != bytes(len(payload)):
        raise ValueError(
            "Proportional advance code cave is not empty at "
            f"0x{PROPORTIONAL_ADVANCE_CAVE_OFFSET:X}"
        )
    if not dry_run:
        handle.seek(PROPORTIONAL_ADVANCE_CAVE_OFFSET)
        handle.write(payload)


def patch_embedded_sjis_text(handle, dry_run: bool) -> None:
    encoding = "shift_jis"
    for patch in SJIS_TEXT_PATCHES:
        expected = patch.expected.encode(encoding)
        replacement = patch.replacement.encode(encoding)
        if len(replacement) >= patch.slot_size:
            raise ValueError(
                f"{patch.label} replacement is too long for 0x{patch.offset:X}: "
                f"{len(replacement)} >= {patch.slot_size}"
            )

        handle.seek(patch.offset)
        current = handle.read(len(expected))
        if current != expected:
            raise ValueError(
                f"Unexpected bytes for {patch.label} at 0x{patch.offset:X}: "
                f"{current.hex()} != {expected.hex()}"
            )

        if not dry_run:
            handle.seek(patch.offset)
            handle.write(replacement)
            handle.write(bytes(patch.slot_size - len(replacement)))


def patch_elf(
    input_elf: Path,
    output_elf: Path,
    advance: float,
    proportional_font_atlas: Path | None,
    fallback_advance: int,
    patch_scenario_anchor: bool,
    patch_hardcoded_ui_text: bool,
    dry_run: bool,
) -> None:
    if not 1.0 <= advance <= 28.0:
        raise ValueError(f"Advance should stay in a conservative range: {advance}")
    if not input_elf.is_file():
        raise FileNotFoundError(f"Input ELF not found: {input_elf}")

    if not dry_run:
        output_elf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(input_elf, output_elf)

    advance_expected = (0x3C0341E0).to_bytes(4, "little")
    advance_bits = struct.unpack("<I", struct.pack("<f", advance))[0]
    if advance_bits & 0xFFFF:
        raise ValueError(f"Advance must be exactly representable as a float with zero low bits: {advance}")
    advance_replacement = (0x3C030000 | (advance_bits >> 16)).to_bytes(4, "little")
    open_path = input_elf if dry_run else output_elf
    open_mode = "rb" if dry_run else "r+b"
    with open_path.open(open_mode) as handle:
        if proportional_font_atlas is not None:
            patch_proportional_advance(handle, proportional_font_atlas, fallback_advance, dry_run)
        else:
            patch_expected_bytes(
                handle,
                ADVANCE_OFFSET,
                advance_expected,
                advance_replacement,
                "afMsgDrawString X advance",
                dry_run,
            )
        if patch_scenario_anchor:
            patch_expected_bytes(
                handle,
                SCENARIO_CENTERING_OFFSET,
                SCENARIO_CENTERING_EXPECTED,
                SCENARIO_CENTERING_REPLACEMENT,
                "afScenarioMsgKind centering clamp",
                dry_run,
            )
        if patch_hardcoded_ui_text:
            patch_embedded_sjis_text(handle, dry_run)

    action = "Would patch" if dry_run else "Patched"
    if proportional_font_atlas is not None:
        print(
            f"{action} afMsgDrawString proportional X advance from {proportional_font_atlas}: "
            f"{output_elf}"
        )
    else:
        print(f"{action} afMsgDrawString X advance to {advance:g}: {output_elf}")
    if patch_scenario_anchor:
        print(f"{action} afScenarioMsgKind centering clamp for long lower-textbox lines")
    if patch_hardcoded_ui_text:
        print(f"{action} {len(SJIS_TEXT_PATCHES)} hardcoded ELF UI strings")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-elf", default="game_dump/SLPS_253.02")
    parser.add_argument("--output-elf", default="build/stage/SLPS_253.02")
    parser.add_argument("--advance", type=float, default=14.0)
    parser.add_argument(
        "--proportional-font",
        action="store_true",
        help="Patch afMsgDrawString to use per-glyph Latin widths from the current font atlas",
    )
    parser.add_argument("--font-atlas-root", default="textures_en/EXPORT_TXD/font_prototype")
    parser.add_argument("--fallback-advance", type=int, default=14)
    parser.add_argument(
        "--keep-scenario-centering",
        action="store_true",
        help="Only patch glyph advance; leave scenario message centering unchanged",
    )
    parser.add_argument(
        "--keep-hardcoded-ui-text",
        action="store_true",
        help="Leave hardcoded ELF UI strings unchanged",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate expected ELF bytes without writing output")
    args = parser.parse_args()

    patch_elf(
        project_path(args.input_elf),
        project_path(args.output_elf),
        args.advance,
        project_path(args.font_atlas_root) if args.proportional_font else None,
        args.fallback_advance,
        not args.keep_scenario_centering,
        not args.keep_hardcoded_ui_text,
        args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
