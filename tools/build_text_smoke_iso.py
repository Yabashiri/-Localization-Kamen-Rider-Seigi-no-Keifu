"""Run the menu-smoke localization build pipeline and optionally launch PCSX2."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from font_mapping import project_path


def run_python(script: str, args: list[str]) -> None:
    command = [sys.executable, str(project_path(script)), *args]
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="menu-smoke", choices=("menu-smoke",))
    parser.add_argument("--output-iso", default="build/out/kamen_rider_text_smoke.iso")
    parser.add_argument("--run-pcsx2", action="store_true")
    parser.add_argument("--pcsx2-exe")
    parser.add_argument("--pcsx2-batch", action="store_true")
    args = parser.parse_args()

    run_python("tools/encode_all_text.py", ["--input-root", "translation_en", "--output-root", "rebuilt_en"])
    run_python("tools/stage_rebuilt_text.py", ["--profile", args.profile])
    run_python("tools/build_data_iso.py", [])
    run_python("tools/build_data_cvm.py", [])
    run_python("tools/build_patched_iso.py", ["--output-iso", args.output_iso])

    if args.run_pcsx2:
        pcsx2_args = [args.output_iso]
        if args.pcsx2_exe:
            pcsx2_args.extend(["--pcsx2-exe", args.pcsx2_exe])
        if args.pcsx2_batch:
            pcsx2_args.append("--batch")
        run_python("tools/run_pcsx2_smoke.py", pcsx2_args)

    print(f"Smoke ISO ready: {project_path(Path(args.output_iso))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
