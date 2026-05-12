"""Patch the afMsgDrawString glyph advance in the game ELF.

The custom message font advances the X cursor by a fixed 28.0 pixels after each
glyph. That matches Japanese full-width cells, but it makes Latin text render as
widely spaced letters. This smoke-test patch lowers that fixed X advance.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path

from font_mapping import project_path


ADVANCE_OFFSET = 0x169F7C - 0x100000 + 0x80


def patch_elf(input_elf: Path, output_elf: Path, advance: float) -> None:
    if not 1.0 <= advance <= 28.0:
        raise ValueError(f"Advance should stay in a conservative range: {advance}")
    if not input_elf.is_file():
        raise FileNotFoundError(f"Input ELF not found: {input_elf}")

    output_elf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_elf, output_elf)

    expected = (0x3C0341E0).to_bytes(4, "little")
    advance_bits = struct.unpack("<I", struct.pack("<f", advance))[0]
    if advance_bits & 0xFFFF:
        raise ValueError(f"Advance must be exactly representable as a float with zero low bits: {advance}")
    replacement = (0x3C030000 | (advance_bits >> 16)).to_bytes(4, "little")
    with output_elf.open("r+b") as handle:
        handle.seek(ADVANCE_OFFSET)
        current = handle.read(4)
        if current != expected:
            raise ValueError(
                f"Unexpected instruction at 0x{ADVANCE_OFFSET:X}: {current.hex()} != {expected.hex()}"
            )
        handle.seek(ADVANCE_OFFSET)
        handle.write(replacement)

    print(f"Patched afMsgDrawString X advance to {advance:g}: {output_elf}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-elf", default="game_dump/SLPS_253.02")
    parser.add_argument("--output-elf", default="build/stage/SLPS_253.02")
    parser.add_argument("--advance", type=float, default=14.0)
    args = parser.parse_args()

    patch_elf(project_path(args.input_elf), project_path(args.output_elf), args.advance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
