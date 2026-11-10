"""Install the locked, isolated OCR runtime without changing other environments."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import venv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, required=True,
                        help="Local directory containing the locked Windows wheels")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info[:2] != (3, 10):
        parser.error("The qualified OCR lock requires Windows x64 and Python 3.10")
    if not args.wheelhouse.is_dir():
        parser.error("The local wheelhouse does not exist")
    root = Path(__file__).resolve().parents[2]
    target = root / "envs" / "ocr" / ".venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(target)
    python = target / "Scripts" / "python.exe"
    subprocess.run([
        str(python), "-m", "pip", "install", "--no-index", "--no-deps",
        "--find-links", str(args.wheelhouse.resolve()),
        "-r", str(root / "envs" / "locks" / "ocr.lock.txt"),
    ], check=True)
    subprocess.run([str(python), "-m", "pip", "check"], check=True)
    print(f"Installed isolated OCR runtime: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
