"""Build the ISO9660 payload that will be wrapped into DATA.CVM."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from font_mapping import project_path


DEFAULT_MKISOFS_CANDIDATES = (
    Path("external_tools/mkisofs-md5-2.01/MinGW/Gcc-4.4.5/mkisofs.exe"),
    Path("external_tools/mkisofs-md5-2.01/MinGW/Gcc-3.4.5/mkisofs.exe"),
    Path("external_tools/mkisofs-md5-2.01/Sample/mkisofs.exe"),
)


def find_mkisofs(explicit_path: str | None) -> Path:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    if os.environ.get("MKISOFS_EXE"):
        candidates.append(Path(os.environ["MKISOFS_EXE"]))
    candidates.extend(DEFAULT_MKISOFS_CANDIDATES)

    for candidate in candidates:
        path = project_path(candidate)
        if path.is_file():
            return path
    raise FileNotFoundError("mkisofs.exe not found; set --mkisofs-exe or MKISOFS_EXE")


def run_mkisofs(command: list[str]) -> None:
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def build_data_iso(mkisofs: Path, input_data: Path, output_iso: Path) -> None:
    if not input_data.is_dir():
        raise FileNotFoundError(f"Input DATA directory not found: {input_data}")

    output_iso.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(mkisofs),
        "-iso-level",
        "2",
        "-l",
        "-sysid",
        "CRI ROFS",
        "-V",
        "SAMPLE_GAME_TITLE",
        "-volset",
        "SAMPLE_GAME_TITLE",
        "-publisher",
        "PUBLISHER_NAME",
        "-p",
        "PUBLISHER_NAME",
        "-graft-points",
        "-o",
        str(output_iso),
        f"DATA={input_data}",
    ]
    run_mkisofs(command)
    print(f"Built DATA ISO: {output_iso} ({output_iso.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mkisofs-exe")
    parser.add_argument("--input-data", default="build/stage/DATA")
    parser.add_argument("--output-iso", default="build/stage/DATA.iso")
    args = parser.parse_args()

    build_data_iso(
        find_mkisofs(args.mkisofs_exe),
        project_path(args.input_data),
        project_path(args.output_iso),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
