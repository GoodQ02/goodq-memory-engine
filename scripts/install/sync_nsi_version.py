"""Synchronize or verify installer metadata against ``GOODQ_VERSION``."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VERSION_PATH = SCRIPT_DIR.parent.parent / "goodq_version.py"
NSI_PATH = SCRIPT_DIR / "goodq4all_installer.nsi"
VERSION_INFO_PATH = SCRIPT_DIR / "versioninfo.json"


def _canonical_version() -> tuple[str, int, int, int]:
    version_py = VERSION_PATH.read_text(encoding="utf-8")
    match = re.search(r'GOODQ_VERSION\s*=\s*"([^"]+)"', version_py)
    if match is None:
        raise ValueError("Could not find GOODQ_VERSION in goodq_version.py")
    version = match.group(1)
    parts = version.lstrip("v").split(".")
    patch_match = re.match(r"^(\d+)", parts[2] if len(parts) > 2 else "0")
    return version, int(parts[0]), int(parts[1]), int(patch_match.group(1) if patch_match else 0)


def _synchronized_nsi(content: str, version: str) -> str:
    replacements = (
        (
            r'OutFile\s+"[^"]+GoodQ4All_Setup_[^"]+\.exe"',
            f'OutFile "${{GOODQ_INSTALLER_OUTPUT_ROOT}}\\GoodQ4All_Setup_{version}.exe"',
        ),
        (
            r'!define\s+MUI_WELCOMEPAGE_TITLE\s+"[^"]+Offline Installer"',
            f'!define MUI_WELCOMEPAGE_TITLE "Welcome to the GoodQ4All v{version} Offline Installer"',
        ),
        (r'"DisplayVersion"\s+"[^"]+"', f'"DisplayVersion" "{version}"'),
    )
    for pattern, replacement in replacements:
        content, count = re.subn(pattern, lambda _match: replacement, content)
        if count != 1:
            raise ValueError(f"Expected exactly one installer metadata match for {pattern!r}, found {count}")
    return content


def _synchronized_version_info(info: dict[str, object], version: str, major: int, minor: int, patch: int) -> dict[str, object]:
    result = json.loads(json.dumps(info))
    fixed = result["FixedFileInfo"]
    for key in ("FileVersion", "ProductVersion"):
        fixed[key].update({"Major": major, "Minor": minor, "Patch": patch, "Build": 0})
    strings = result["StringFileInfo"]
    strings["FileVersion"] = f"{version}.0"
    strings["ProductVersion"] = f"{version}.0"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report metadata drift without writing files")
    args = parser.parse_args()

    version, major, minor, patch = _canonical_version()
    current_nsi = NSI_PATH.read_text(encoding="utf-8")
    current_info = json.loads(VERSION_INFO_PATH.read_text(encoding="utf-8"))
    expected_nsi = _synchronized_nsi(current_nsi, version)
    expected_info = _synchronized_version_info(current_info, version, major, minor, patch)
    nsi_stale = expected_nsi != current_nsi
    info_stale = expected_info != current_info

    if args.check:
        if nsi_stale or info_stale:
            stale = ", ".join(name for name, value in (("NSIS", nsi_stale), ("versioninfo", info_stale)) if value)
            print(f"[ERROR] Installer metadata out of sync with GOODQ_VERSION {version}: {stale}")
            return 1
        print(f"[OK] Installer metadata matches GOODQ_VERSION {version}")
        return 0

    if nsi_stale:
        NSI_PATH.write_text(expected_nsi, encoding="utf-8", newline="\r\n")
    if info_stale:
        VERSION_INFO_PATH.write_text(json.dumps(expected_info, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Installer metadata synchronized with GOODQ_VERSION {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
