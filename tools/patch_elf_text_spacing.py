"""Patch English text layout behavior in the game ELF.

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
from pathlib import Path

from font_mapping import project_path


ADVANCE_OFFSET = 0x169F7C - 0x100000 + 0x80

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


def patch_elf(
    input_elf: Path,
    output_elf: Path,
    advance: float,
    patch_scenario_anchor: bool,
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

    action = "Would patch" if dry_run else "Patched"
    print(f"{action} afMsgDrawString X advance to {advance:g}: {output_elf}")
    if patch_scenario_anchor:
        print(f"{action} afScenarioMsgKind centering clamp for long lower-textbox lines")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-elf", default="game_dump/SLPS_253.02")
    parser.add_argument("--output-elf", default="build/stage/SLPS_253.02")
    parser.add_argument("--advance", type=float, default=14.0)
    parser.add_argument(
        "--keep-scenario-centering",
        action="store_true",
        help="Only patch glyph advance; leave scenario message centering unchanged",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate expected ELF bytes without writing output")
    args = parser.parse_args()

    patch_elf(
        project_path(args.input_elf),
        project_path(args.output_elf),
        args.advance,
        not args.keep_scenario_centering,
        args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
