"""Build a full PS2 test ISO with a rebuilt DATA.CVM."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from font_mapping import project_path


DEFAULT_MKISOFS_CANDIDATES = (
    Path("external_tools/mkisofs-md5-2.01/Cygwin/Gcc-3.4.4/mkisofs.exe"),
    Path("external_tools/mkisofs-md5-2.01/MinGW/Gcc-4.4.5/mkisofs.exe"),
    Path("external_tools/mkisofs-md5-2.01/MinGW/Gcc-3.4.5/mkisofs.exe"),
    Path("external_tools/mkisofs-md5-2.01/Sample/mkisofs.exe"),
)

ROOT_FILES = (
    "MODULES",
    "DATA.CVM",
    "MODULES.TRA",
    "OPENING.PSS",
    "PLAY_A.PSS",
    "PLAY_B.PSS",
    "PLAY_C.PSS",
    "PLAY_D.PSS",
    "SLPS_253.02",
    "SYSTEM.CNF",
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


def verify_system_cnf(game_root: Path) -> None:
    system_cnf = game_root / "SYSTEM.CNF"
    if not system_cnf.is_file():
        raise FileNotFoundError(f"SYSTEM.CNF not found: {system_cnf}")
    text = system_cnf.read_text(encoding="ascii", errors="replace").upper()
    if "SLPS_253.02" not in text:
        raise ValueError(f"SYSTEM.CNF does not reference SLPS_253.02: {system_cnf}")


def build_graft_points(game_root: Path, rebuilt_cvm: Path) -> list[str]:
    grafts: list[str] = []
    for name in ROOT_FILES:
        source = rebuilt_cvm if name == "DATA.CVM" else game_root / name
        if not source.exists():
            raise FileNotFoundError(f"Required disc source missing: {source}")
        grafts.append(f"{name}={source}")
    return grafts


def build_test_iso(mkisofs: Path, game_root: Path, rebuilt_cvm: Path, output_iso: Path) -> None:
    if not game_root.is_dir():
        raise FileNotFoundError(f"Game root directory not found: {game_root}")
    if not rebuilt_cvm.is_file():
        raise FileNotFoundError(f"Rebuilt DATA.CVM not found: {rebuilt_cvm}")

    verify_system_cnf(game_root)
    output_iso.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(mkisofs),
        "-iso-level",
        "3",
        "-l",
        "-V",
        "SLPS_25302",
        "-graft-points",
        "-o",
        str(output_iso),
        *build_graft_points(game_root, rebuilt_cvm),
    ]
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, check=True)
    print(f"Built test ISO: {output_iso} ({output_iso.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mkisofs-exe")
    parser.add_argument("--game-root", default="game_dump")
    parser.add_argument("--rebuilt-cvm", default="build/stage/DATA.CVM")
    parser.add_argument("--output-iso", default="build/out/kamen_rider_text_smoke.iso")
    args = parser.parse_args()

    build_test_iso(
        find_mkisofs(args.mkisofs_exe),
        project_path(args.game_root),
        project_path(args.rebuilt_cvm),
        project_path(args.output_iso),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
