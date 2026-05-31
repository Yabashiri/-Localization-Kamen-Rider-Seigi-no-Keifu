"""Stage rebuilt files over an extracted DATA tree for smoke builds."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from font_mapping import project_path


MENU_SMOKE_FILES = (
    Path("DATA/MENU/CONFIG_MSG.DAT"),
    Path("DATA/MENU/ITEM_GET_MSG.DAT"),
    Path("DATA/MENU/ITEM_MSG.DAT"),
)


def clean_output(output_data: Path) -> None:
    root = project_path(".").resolve()
    output_data = output_data.resolve()
    if output_data == root or root not in output_data.parents:
        raise ValueError(f"Refusing to clean output outside project root: {output_data}")
    if output_data.exists():
        shutil.rmtree(output_data)


def normalize_overlay_path(path_text: str) -> Path:
    path = Path(path_text.replace("\\", "/"))
    parts = path.parts
    if parts and parts[0].upper() == "DATA":
        return Path(*parts[1:])
    return path


def iter_rebuilt_files(rebuilt_data: Path, only: list[str] | None) -> list[Path]:
    if only:
        return [normalize_overlay_path(path_text) for path_text in only]
    return sorted(
        path.relative_to(rebuilt_data)
        for path in rebuilt_data.rglob("*")
        if path.is_file() and path.suffix.upper() in {".DAT", ".BIN", ".TXD", ".TRA", ".RSC"}
    )


def stage_rebuilt_text(source_data: Path, rebuilt_data: Path, output_data: Path, only: list[str] | None) -> int:
    source_data = project_path(source_data)
    rebuilt_data = project_path(rebuilt_data)
    output_data = project_path(output_data)

    if not source_data.is_dir():
        raise FileNotFoundError(f"Source DATA directory not found: {source_data}")
    if not rebuilt_data.is_dir():
        raise FileNotFoundError(f"Rebuilt DATA directory not found: {rebuilt_data}")

    clean_output(output_data)
    shutil.copytree(source_data, output_data)

    replaced = 0
    for relative_path in iter_rebuilt_files(rebuilt_data, only):
        source_file = rebuilt_data / relative_path
        target_file = output_data / relative_path
        original_size = target_file.stat().st_size if target_file.exists() else 0
        if not source_file.is_file():
            raise FileNotFoundError(f"Rebuilt file not found: {source_file}")
        if not target_file.exists():
            raise FileNotFoundError(f"Target file does not exist in staged DATA: {target_file}")

        shutil.copy2(source_file, target_file)
        new_size = target_file.stat().st_size
        print(f"{relative_path.as_posix()}: {original_size} -> {new_size}")
        replaced += 1

    print(f"Staged DATA: {output_data}")
    print(f"Files replaced: {replaced}")
    return replaced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-data", default="game_dump/DATA")
    parser.add_argument("--rebuilt-data", default="rebuilt_en/DATA")
    parser.add_argument("--output-data", default="build/stage/DATA")
    parser.add_argument("--only", nargs="*", help="Project paths to overlay, with or without DATA/ prefix")
    parser.add_argument("--profile", choices=("menu-smoke",), help="Named replacement profile")
    args = parser.parse_args()

    only = args.only
    if args.profile == "menu-smoke":
        only = [path.as_posix() for path in MENU_SMOKE_FILES]

    stage_rebuilt_text(Path(args.source_data), Path(args.rebuilt_data), Path(args.output_data), only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
