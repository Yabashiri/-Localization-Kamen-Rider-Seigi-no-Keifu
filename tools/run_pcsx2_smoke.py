"""Launch a built smoke-test ISO in PCSX2."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from font_mapping import project_path


DEFAULT_PCSX2_CANDIDATES = (
    Path("external_tools/pcsx2/pcsx2-qt.exe"),
    Path(r"C:\PCSX2 2.3.222\pcsx2-qt.exe"),
)


def find_pcsx2(explicit_path: str | None) -> Path:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    if os.environ.get("PCSX2_EXE"):
        candidates.append(Path(os.environ["PCSX2_EXE"]))
    candidates.extend(DEFAULT_PCSX2_CANDIDATES)

    for candidate in candidates:
        path = project_path(candidate)
        if path.is_file():
            return path
    raise FileNotFoundError("pcsx2-qt.exe not found; set --pcsx2-exe or PCSX2_EXE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", nargs="?", default="build/out/kamen_rider_text_smoke.iso")
    parser.add_argument("--pcsx2-exe")
    parser.add_argument("--batch", action="store_true", help="Pass -batch to PCSX2")
    args = parser.parse_args()

    iso_path = project_path(args.iso)
    if not iso_path.is_file():
        raise FileNotFoundError(f"ISO not found: {iso_path}")

    pcsx2 = find_pcsx2(args.pcsx2_exe)
    command = [str(pcsx2)]
    if args.batch:
        command.append("-batch")
    command.append(str(iso_path))

    print("Running:", " ".join(command), flush=True)
    subprocess.Popen(command, cwd=str(pcsx2.parent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
