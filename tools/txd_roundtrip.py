"""Rebuild TXD RenderWare chunk headers without changing payload bytes.

This tool is the first safety gate for a future PNG -> PS2 TXD importer.  It
parses the top-level chunk stream and writes it back recursively.  With no
texture edits, output should be byte-identical to the original input.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import struct
from dataclasses import dataclass, field
from pathlib import Path

from font_mapping import project_path
from txd_inspect import CONTAINER_CHUNKS, HEADER_SIZE, Chunk, iter_chunks, payload_looks_like_chunks


@dataclass
class Node:
    chunk: Chunk
    payload: bytes
    children: list["Node"] = field(default_factory=list)

    def serialize(self) -> bytes:
        if self.children:
            payload = b"".join(child.serialize() for child in self.children)
        else:
            payload = self.payload
        return struct.pack("<III", self.chunk.chunk_id, len(payload), self.chunk.version) + payload


def parse_nodes(data: bytes, start: int, limit: int) -> list[Node]:
    nodes: list[Node] = []
    for chunk in iter_chunks(data, start, limit):
        payload = data[chunk.payload_offset : chunk.end_offset]
        node = Node(chunk=chunk, payload=payload)
        if chunk.chunk_id in CONTAINER_CHUNKS or (chunk.chunk_id == 0x01 and payload_looks_like_chunks(data, chunk)):
            node.children = parse_nodes(data, chunk.payload_offset, chunk.end_offset)
        nodes.append(node)
    return nodes


def rebuild_bytes(data: bytes) -> bytes:
    return b"".join(node.serialize() for node in parse_nodes(data, 0, len(data)))


def roundtrip_file(input_txd: Path, output_txd: Path) -> bool:
    input_txd = project_path(input_txd)
    output_txd = project_path(output_txd)
    data = input_txd.read_bytes()
    rebuilt = rebuild_bytes(data)
    output_txd.parent.mkdir(parents=True, exist_ok=True)
    output_txd.write_bytes(rebuilt)
    return rebuilt == data


def relative_output(input_txd: Path, source_root: Path, output_root: Path) -> Path:
    input_txd = project_path(input_txd)
    source_root = project_path(source_root)
    output_root = project_path(output_root)
    return output_root / input_txd.relative_to(source_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("txd", nargs="*", help="Input TXD file(s). If omitted, scan --source-root.")
    parser.add_argument("--source-root", default="game_dump/DATA")
    parser.add_argument("--output-root", default="build/txd_roundtrip/DATA")
    parser.add_argument("--output", help="Single-file output path. Only valid with one input file.")
    parser.add_argument("--check", action="store_true", help="Fail if rebuilt output differs from input")
    parser.add_argument("--copy-on-diff", action="store_true", help="Copy original bytes if rebuild differs")
    args = parser.parse_args()

    source_root = project_path(args.source_root)
    if args.txd:
        inputs = [project_path(path) for path in args.txd]
    else:
        inputs = sorted(source_root.rglob("*.TXD"))

    if args.output and len(inputs) != 1:
        raise ValueError("--output can only be used with exactly one input TXD")

    failures = []
    for input_txd in inputs:
        output_txd = project_path(args.output) if args.output else relative_output(input_txd, source_root, Path(args.output_root))
        identical = roundtrip_file(input_txd, output_txd)
        if not identical and args.copy_on_diff:
            shutil.copy2(input_txd, output_txd)
            identical = filecmp.cmp(input_txd, output_txd, shallow=False)
        status = "OK" if identical else "DIFF"
        print(f"{status} {input_txd} -> {output_txd}")
        if not identical:
            failures.append(input_txd)

    if args.check and failures:
        print(f"Round-trip differences: {len(failures)}")
        return 1
    print(f"Processed TXD files: {len(inputs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
