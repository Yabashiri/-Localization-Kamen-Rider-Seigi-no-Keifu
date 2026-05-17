"""Build and validate a manifest for TXD texture localization work.

The project does not currently have a trusted PNG -> PS2 TXD importer.  This
tool tracks the original TXD files, the PNG files exported by an external
tool, and the expected rebuilt TXD overlay paths used by the ISO build.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from font_mapping import project_path


DEFAULT_SOURCE_DATA = Path("game_dump/DATA")
DEFAULT_EXPORT_ROOT = Path("dump_jp/EXPORT_TXD")
DEFAULT_OUTPUT = Path("localization/textures_manifest.json")
DEFAULT_TEXTURES_ROOT = Path("textures_en/EXPORT_TXD")
DEFAULT_REBUILT_DATA = Path("rebuilt_en/DATA")


def normalize_relative_data_path(path: Path) -> str:
    return Path("DATA", path).as_posix()


def exported_dir_for_txd(relative_txd: Path, export_root: Path) -> Path:
    if relative_txd.parent == Path("."):
        return export_root
    return export_root / relative_txd.parent


def exported_pngs_for_txd(relative_txd: Path, export_root: Path) -> list[str]:
    export_dir = exported_dir_for_txd(relative_txd, export_root)
    prefix = f"{relative_txd.stem}_"
    if not export_dir.is_dir():
        return []
    return sorted(
        normalize_relative_data_path(path.relative_to(export_root))
        for path in export_dir.glob(f"{prefix}*.png")
        if path.is_file()
    )


def classify_txd(relative_txd: Path) -> tuple[bool | None, str]:
    name = relative_txd.name.upper()
    parent = relative_txd.parent.as_posix().upper()

    if parent == "MENU":
        return True, "menu texture"
    if name.startswith(("TITLE", "WARNING", "LOGO", "STAF")):
        return True, "front-end or staff texture"
    if name == "FONT.TXD":
        return False, "font atlas handled by text/glyph pipeline"
    if parent == "BIKE":
        return None, "bike/gameplay texture; inspect before translating"
    return None, "inspect manually"


def build_manifest(
    source_data: Path,
    export_root: Path,
    textures_root: Path,
    rebuilt_data: Path,
) -> dict[str, Any]:
    source_data_label = source_data.as_posix()
    export_root_label = export_root.as_posix()
    textures_root_label = textures_root.as_posix()
    rebuilt_data_label = rebuilt_data.as_posix()

    source_data = project_path(source_data)
    export_root = project_path(export_root)

    if not source_data.is_dir():
        raise FileNotFoundError(f"Source DATA directory not found: {source_data}")
    if not export_root.is_dir():
        raise FileNotFoundError(f"Export root not found: {export_root}")

    entries: list[dict[str, Any]] = []
    for txd in sorted(source_data.rglob("*.TXD")):
        relative_txd = txd.relative_to(source_data)
        needs_localization, note = classify_txd(relative_txd)
        exported_pngs = exported_pngs_for_txd(relative_txd, export_root)
        relative_data_txd = normalize_relative_data_path(relative_txd)
        entries.append(
            {
                "txd_path": relative_data_txd,
                "original_size": txd.stat().st_size,
                "exported_pngs": exported_pngs,
                "translated_png_dir": (Path(textures_root_label) / relative_txd.parent).as_posix(),
                "rebuilt_txd_path": (Path(rebuilt_data_label) / relative_txd).as_posix(),
                "needs_localization": needs_localization,
                "status": "pending" if needs_localization else "reference",
                "notes": note,
            }
        )

    return {
        "version": 1,
        "source_data": source_data_label,
        "export_root": export_root_label,
        "textures_root": textures_root_label,
        "rebuilt_data": rebuilt_data_label,
        "entries": entries,
    }


def write_manifest(manifest: dict[str, Any], output: Path) -> None:
    output = project_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Wrote TXD manifest: {output}")
    print(f"TXD entries: {len(manifest['entries'])}")


def validate_manifest(path: Path) -> int:
    path = project_path(path)
    with path.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    missing_exports = []
    missing_rebuilt = []
    for entry in manifest["entries"]:
        if not entry["exported_pngs"]:
            missing_exports.append(entry["txd_path"])
        rebuilt_path = project_path(entry["rebuilt_txd_path"])
        if entry["needs_localization"] and not rebuilt_path.is_file():
            missing_rebuilt.append(entry["txd_path"])

    print(f"Manifest entries: {len(manifest['entries'])}")
    print(f"Entries without exported PNGs: {len(missing_exports)}")
    print(f"Localizable entries without rebuilt TXD: {len(missing_rebuilt)}")
    if missing_exports:
        print("Missing exports:")
        for txd_path in missing_exports:
            print(f"  {txd_path}")
    return 0


def init_workspace(textures_root: Path) -> None:
    root = project_path(textures_root)
    for subdir in (root, root / "MENU", root / "BIKE"):
        subdir.mkdir(parents=True, exist_ok=True)
        keep = subdir / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
    print(f"Initialized texture workspace: {root}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Write a TXD manifest")
    build_parser.add_argument("--source-data", default=DEFAULT_SOURCE_DATA)
    build_parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT)
    build_parser.add_argument("--textures-root", default=DEFAULT_TEXTURES_ROOT)
    build_parser.add_argument("--rebuilt-data", default=DEFAULT_REBUILT_DATA)
    build_parser.add_argument("--output", default=DEFAULT_OUTPUT)

    validate_parser = subparsers.add_parser("validate", help="Validate manifest references")
    validate_parser.add_argument("--manifest", default=DEFAULT_OUTPUT)

    init_parser = subparsers.add_parser("init-workspace", help="Create texture workspace folders")
    init_parser.add_argument("--textures-root", default=DEFAULT_TEXTURES_ROOT)

    args = parser.parse_args()

    if args.command == "build":
        manifest = build_manifest(
            Path(args.source_data),
            Path(args.export_root),
            Path(args.textures_root),
            Path(args.rebuilt_data),
        )
        write_manifest(manifest, Path(args.output))
        return 0
    if args.command == "validate":
        return validate_manifest(Path(args.manifest))
    if args.command == "init-workspace":
        init_workspace(Path(args.textures_root))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
