"""Build DATA.CVM from an ISO payload and a cvm_tool header."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from font_mapping import project_path


DEFAULT_CVM_TOOL_CANDIDATES = (
    Path("external_tools/cvm_tool/cvm_tool.exe"),
    Path("external_tools/cvm_tool_02/cvm_tool.exe"),
)


def find_cvm_tool(explicit_path: str | None) -> Path:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    if os.environ.get("CVM_TOOL"):
        candidates.append(Path(os.environ["CVM_TOOL"]))
    candidates.extend(DEFAULT_CVM_TOOL_CANDIDATES)

    for candidate in candidates:
        path = project_path(candidate)
        if path.is_file():
            return path
    raise FileNotFoundError("cvm_tool.exe not found; set --cvm-tool or CVM_TOOL")


def run_tool(cvm_tool: Path, args: list[str]) -> None:
    command = [str(cvm_tool), *args]
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def ensure_header(cvm_tool: Path, original_cvm: Path, iso_output: Path, header_output: Path) -> None:
    if header_output.is_file():
        return
    iso_output.parent.mkdir(parents=True, exist_ok=True)
    run_tool(cvm_tool, ["split", str(original_cvm), str(iso_output), str(header_output)])


def verify_cvm(path: Path) -> None:
    header = path.read_bytes()[:0x800]
    if not header.startswith(b"CVMH"):
        raise ValueError(f"Built file does not start with CVMH: {path}")
    if b"ROFS" not in header:
        raise ValueError(f"Built file header does not contain ROFS: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cvm-tool")
    parser.add_argument("--original-cvm", default="game_dump/DATA.CVM")
    parser.add_argument("--input-iso", default="build/stage/DATA.iso")
    parser.add_argument("--header", default="work_cvm/DATA.hdr")
    parser.add_argument("--split-iso", default="work_cvm/DATA.iso")
    parser.add_argument("--output-cvm", default="build/stage/DATA.CVM")
    args = parser.parse_args()

    cvm_tool = find_cvm_tool(args.cvm_tool)
    original_cvm = project_path(args.original_cvm)
    input_iso = project_path(args.input_iso)
    header = project_path(args.header)
    split_iso = project_path(args.split_iso)
    output_cvm = project_path(args.output_cvm)

    if not original_cvm.is_file():
        raise FileNotFoundError(f"Original CVM not found: {original_cvm}")
    if not input_iso.is_file():
        raise FileNotFoundError(f"Input ISO not found: {input_iso}")

    ensure_header(cvm_tool, original_cvm, split_iso, header)
    output_cvm.parent.mkdir(parents=True, exist_ok=True)
    run_tool(cvm_tool, ["mkcvm", str(output_cvm), str(input_iso), str(header)])
    verify_cvm(output_cvm)
    print(f"Built CVM: {output_cvm} ({output_cvm.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
