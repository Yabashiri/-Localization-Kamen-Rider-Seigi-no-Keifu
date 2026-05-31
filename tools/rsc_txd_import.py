"""Import PNG replacements into a TXD embedded in an RSC-like container."""

from __future__ import annotations

import argparse
from pathlib import Path

from font_mapping import project_path
from txd_import_png import NATIVE_DATA_HEADER_SIZE, encode_8bpp_psmt8, encode_16bpp_rgba5551
from txd_inspect import parse_children, read_chunk, texture_summaries


def parse_int(text: str) -> int:
    return int(text, 0)


def embedded_txd_span(container_data: bytes, txd_offset: int) -> tuple[int, int]:
    chunk = read_chunk(container_data, txd_offset, len(container_data))
    if chunk is None:
        raise ValueError(f"No RenderWare chunk found at 0x{txd_offset:x}")
    if chunk.chunk_id != 0x16:
        raise ValueError(f"Expected TXD chunk at 0x{txd_offset:x}, found 0x{chunk.chunk_id:x}")
    return txd_offset, chunk.end_offset


def import_png_into_txd(txd_data: bytearray, texture_name: str, png_path: Path) -> None:
    report = {
        "path": f"embedded@{texture_name}",
        "size": len(txd_data),
        "chunks": parse_children(bytes(txd_data), 0, len(txd_data), 0, None),
    }
    matches = [texture for texture in texture_summaries(report) if texture["texture"] == texture_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one texture named {texture_name!r}, found {len(matches)}")

    texture = matches[0]
    bpp = int(texture["bpp"])
    if bpp not in NATIVE_DATA_HEADER_SIZE:
        raise NotImplementedError(f"PNG import for {bpp}bpp textures is not implemented yet")

    width = int(texture["width"])
    height = int(texture["height"])
    if bpp == 8:
        replacement = encode_8bpp_psmt8(png_path, width, height)
    else:
        replacement = encode_16bpp_rgba5551(png_path, width, height)

    expected_size = width * height * bpp // 8
    if len(replacement) != expected_size:
        raise ValueError(f"Encoded PNG size {len(replacement)} != expected {expected_size}")

    pixel_offset = int(texture["data_payload_offset"]) + NATIVE_DATA_HEADER_SIZE[bpp]
    txd_data[pixel_offset : pixel_offset + expected_size] = replacement
    print(f"{texture_name}: {width}x{height} {bpp}bpp pixel payload 0x{pixel_offset:x}..0x{pixel_offset + expected_size:x}")


def parse_replacement(text: str) -> tuple[str, Path]:
    if "=" not in text:
        raise ValueError(f"Replacement must be TEXTURE=PNG, got {text!r}")
    texture, png = text.split("=", 1)
    if not texture or not png:
        raise ValueError(f"Replacement must be TEXTURE=PNG, got {text!r}")
    return texture, Path(png)


def import_rsc_txd(input_rsc: Path, txd_offset: int, replacements: list[tuple[str, Path]], output_rsc: Path) -> None:
    input_rsc = project_path(input_rsc)
    output_rsc = project_path(output_rsc)
    container_data = bytearray(input_rsc.read_bytes())
    txd_start, txd_end = embedded_txd_span(container_data, txd_offset)
    txd_data = bytearray(container_data[txd_start:txd_end])

    for texture_name, png_path in replacements:
        import_png_into_txd(txd_data, texture_name, project_path(png_path))

    if len(txd_data) != txd_end - txd_start:
        raise ValueError("Embedded TXD size changed; refusing to write container")
    container_data[txd_start:txd_end] = txd_data

    output_rsc.parent.mkdir(parents=True, exist_ok=True)
    output_rsc.write_bytes(container_data)
    print(f"Imported {len(replacements)} texture(s): {input_rsc} -> {output_rsc}")
    print(f"Embedded TXD span: 0x{txd_start:x}..0x{txd_end:x} ({txd_end - txd_start} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-rsc", required=True)
    parser.add_argument("--txd-offset", type=parse_int, required=True)
    parser.add_argument("--output-rsc", required=True)
    parser.add_argument(
        "--replace",
        action="append",
        required=True,
        metavar="TEXTURE=PNG",
        help="Texture replacement. May be passed multiple times.",
    )
    args = parser.parse_args()

    replacements = [parse_replacement(item) for item in args.replace]
    import_rsc_txd(Path(args.input_rsc), args.txd_offset, replacements, Path(args.output_rsc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
