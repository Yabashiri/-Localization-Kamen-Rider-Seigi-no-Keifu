"""Inspect RenderWare TXD chunk structure.

This is a diagnostic step toward a safe PS2 TXD round-trip pipeline.  It does
not modify files and does not decode PS2 raster payloads yet.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from font_mapping import project_path


CHUNK_NAMES = {
    0x01: "Struct",
    0x02: "String",
    0x03: "Extension",
    0x06: "Texture",
    0x15: "Texture Native",
    0x16: "Texture Dictionary",
}

CONTAINER_CHUNKS = {0x06, 0x15, 0x16}
HEADER_SIZE = 12


@dataclass(frozen=True)
class Chunk:
    chunk_id: int
    size: int
    version: int
    offset: int
    payload_offset: int

    @property
    def end_offset(self) -> int:
        return self.payload_offset + self.size

    @property
    def name(self) -> str:
        return CHUNK_NAMES.get(self.chunk_id, f"0x{self.chunk_id:08x}")


def read_chunk(data: bytes, offset: int, limit: int) -> Chunk | None:
    if offset + HEADER_SIZE > limit:
        return None
    chunk_id, size, version = struct.unpack_from("<III", data, offset)
    end = offset + HEADER_SIZE + size
    if end > limit:
        raise ValueError(
            f"Chunk at 0x{offset:x} ({CHUNK_NAMES.get(chunk_id, hex(chunk_id))}) "
            f"ends at 0x{end:x}, beyond limit 0x{limit:x}"
        )
    return Chunk(chunk_id, size, version, offset, offset + HEADER_SIZE)


def iter_chunks(data: bytes, start: int, limit: int) -> Iterable[Chunk]:
    offset = start
    while offset < limit:
        chunk = read_chunk(data, offset, limit)
        if chunk is None:
            break
        yield chunk
        offset = chunk.end_offset
    if offset != limit:
        raise ValueError(f"Unparsed bytes from 0x{offset:x} to 0x{limit:x}")


def decode_c_string(payload: bytes) -> str:
    raw = payload.split(b"\x00", 1)[0]
    return raw.decode("ascii", errors="replace")


def rw_version_text(version: int) -> str:
    return f"0x{version:08x}"


def parse_struct_summary(data: bytes, chunk: Chunk, parent_id: int | None) -> dict[str, Any]:
    payload = data[chunk.payload_offset : chunk.end_offset]
    summary: dict[str, Any] = {"hex": payload[:32].hex()}
    if parent_id == 0x16 and len(payload) >= 4:
        texture_count = struct.unpack_from("<H", payload, 0)[0]
        summary["texture_count"] = texture_count
        if len(payload) >= 4:
            summary["device_id_or_padding"] = struct.unpack_from("<H", payload, 2)[0]
    elif parent_id == 0x15 and len(payload) >= 8 and payload[:4] == b"PS2\x00":
        platform = decode_c_string(payload[:4])
        summary["platform"] = platform
        summary["raw_flags"] = struct.unpack_from("<I", payload, 4)[0]
    elif len(payload) == 64:
        words = struct.unpack_from("<16I", payload, 0)
        summary["words_u32"] = [f"0x{word:08x}" for word in words]
        if words[0] in {16, 32, 64, 128, 256, 512, 1024} and words[1] in {16, 32, 64, 128, 256, 512, 1024}:
            summary["width"] = words[0]
            summary["height"] = words[1]
            summary["bit_depth"] = words[2]
    return summary


def payload_looks_like_chunks(data: bytes, chunk: Chunk) -> bool:
    if chunk.payload_offset + HEADER_SIZE > chunk.end_offset:
        return False
    child_id, child_size, _version = struct.unpack_from("<III", data, chunk.payload_offset)
    if child_id not in CHUNK_NAMES:
        return False
    child_end = chunk.payload_offset + HEADER_SIZE + child_size
    return child_end <= chunk.end_offset


def parse_children(data: bytes, start: int, limit: int, depth: int, parent_id: int | None) -> list[dict[str, Any]]:
    result = []
    for chunk in iter_chunks(data, start, limit):
        item: dict[str, Any] = {
            "offset": chunk.offset,
            "id": chunk.chunk_id,
            "name": chunk.name,
            "size": chunk.size,
            "version": rw_version_text(chunk.version),
        }
        if chunk.chunk_id == 0x01:
            item["struct"] = parse_struct_summary(data, chunk, parent_id)
        elif chunk.chunk_id == 0x02:
            item["string"] = decode_c_string(data[chunk.payload_offset : chunk.end_offset])

        if chunk.chunk_id in CONTAINER_CHUNKS or (chunk.chunk_id == 0x01 and payload_looks_like_chunks(data, chunk)):
            item["children"] = parse_children(data, chunk.payload_offset, chunk.end_offset, depth + 1, chunk.chunk_id)
        result.append(item)
    return result


def inspect_txd(path: Path) -> dict[str, Any]:
    path = project_path(path)
    data = path.read_bytes()
    chunks = parse_children(data, 0, len(data), 0, None)
    return {
        "path": path.as_posix(),
        "size": len(data),
        "chunks": chunks,
    }


def find_first(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for item in items:
        if item["name"] == name:
            return item
    return None


def texture_summaries(report: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for root in report["chunks"]:
        if root["name"] != "Texture Dictionary":
            continue
        for native in root.get("children", []):
            if native["name"] != "Texture Native":
                continue
            children = native.get("children", [])
            strings = [child["string"] for child in children if child["name"] == "String"]
            texture_name = strings[0] if strings else ""
            native_payload = next(
                (
                    child
                    for child in children
                    if child["name"] == "Struct" and child.get("children")
                ),
                None,
            )
            if not native_payload:
                continue
            native_children = native_payload["children"]
            header = find_first(native_children, "Struct")
            data_chunk = None
            struct_seen = 0
            for child in native_children:
                if child["name"] == "Struct":
                    struct_seen += 1
                    if struct_seen == 2:
                        data_chunk = child
                        break
            if not header or not data_chunk:
                continue
            header_info = header.get("struct", {})
            summaries.append(
                {
                    "txd": report["path"],
                    "texture": texture_name,
                    "width": header_info.get("width"),
                    "height": header_info.get("height"),
                    "bpp": header_info.get("bit_depth"),
                    "native_offset": native["offset"],
                    "header_offset": header["offset"],
                    "data_offset": data_chunk["offset"],
                    "data_payload_offset": data_chunk["offset"] + 12,
                    "data_size": data_chunk["size"],
                }
            )
    return summaries


def print_tree(items: list[dict[str, Any]], indent: int = 0) -> None:
    pad = "  " * indent
    for item in items:
        line = (
            f"{pad}0x{item['offset']:08x} {item['name']} "
            f"size={item['size']} version={item['version']}"
        )
        print(line)
        if "string" in item:
            print(f"{pad}  string={item['string']!r}")
        if "struct" in item:
            struct_info = item["struct"]
            if "texture_count" in struct_info:
                print(f"{pad}  texture_count={struct_info['texture_count']}")
            if "platform" in struct_info:
                print(f"{pad}  platform={struct_info['platform']!r} flags=0x{struct_info['raw_flags']:08x}")
            elif "width" in struct_info:
                print(
                    f"{pad}  raster_header={struct_info['width']}x{struct_info['height']} "
                    f"{struct_info['bit_depth']}bpp"
                )
            else:
                print(f"{pad}  struct_hex={struct_info['hex']}")
        children = item.get("children")
        if children:
            print_tree(children, indent + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("txd", nargs="+", help="TXD files to inspect")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--textures", action="store_true", help="Print one texture summary per line")
    args = parser.parse_args()

    reports = [inspect_txd(Path(path)) for path in args.txd]
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    elif args.textures:
        print("txd\ttexture\twidth\theight\tbpp\tnative_offset\theader_offset\tdata_offset\tdata_size")
        for report in reports:
            for item in texture_summaries(report):
                print(
                    f"{item['txd']}\t{item['texture']}\t{item['width']}\t{item['height']}\t{item['bpp']}\t"
                    f"0x{item['native_offset']:x}\t0x{item['header_offset']:x}\t"
                    f"0x{item['data_offset']:x}\t{item['data_size']}"
                )
    else:
        for report in reports:
            print(f"{report['path']} ({report['size']} bytes)")
            print_tree(report["chunks"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
