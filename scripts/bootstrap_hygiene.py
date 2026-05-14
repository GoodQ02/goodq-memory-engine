#!/usr/bin/env python
"""Snapshot and plan bootstrap hygiene for troubleshooting first installs.

The helper is intentionally non-destructive. It records the install-relevant
state and prints commands an operator may review before manually resetting
GoodQ-specific bootstrap surfaces.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

try:
    from scripts import bootstrap_install
except Exception:  # noqa: BLE001
    import bootstrap_install  # type: ignore


SAFE_ENV_KEYS = (
    "GOODQ_DATA_ROOT",
    "GOODQ_HOST_PROFILE",
    "GOODQ_REQUIRE_GPU",
    "GOODQ_REQUIRE_WSL_AUDIO",
    "GOODQ_CONDA_ENV",
    "GOODQ_WSL_DISTRO",
    "GOODQ_WSL_USER",
    "GOODQ_WSL_WORKSPACE",
    "GOODQ_POPPLER_BIN",
    "GOODQ_FFMPEG_EXE",
)
LOCAL_CONFIG_FILES = (
    ".env.local",
    "configs/config.local.yaml",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def goodq_env_names() -> list[str]:
    names = [bootstrap_install.ENV_NAME]
    names.extend(spec.name for spec in bootstrap_install.SUPPORTED_STEP_ENVS)
    return list(dict.fromkeys(names))


def load_safe_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    safe = set(SAFE_ENV_KEYS)
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in safe:
            values[key] = value.strip().strip('"').strip("'")
    return values


def detect_conda() -> str | None:
    conda_exe = os.environ.get("CONDA_EXE", "").strip()
    if conda_exe and Path(conda_exe).exists():
        return conda_exe
    return shutil.which("conda")


def list_conda_envs(conda_exe: str | None) -> dict[str, str]:
    if not conda_exe:
        return {}
    completed = subprocess.run(
        [conda_exe, "env", "list", "--json"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {}
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    result: dict[str, str] = {}
    for env_path in payload.get("envs", []):
        path = Path(str(env_path))
        if path.name:
            result[path.name] = str(path)
    return result


def derived_data_paths(data_root: str) -> dict[str, str]:
    root = Path(data_root)
    return {
        "base_data_root": str(root),
        "app_data_root": str(root / "GoodQ_Data"),
        "import_inbox": str(root / "GoodQ_Data" / "import_inbox"),
        "processed": str(root / "GoodQ_Data" / "processed"),
        "failed": str(root / "GoodQ_Data" / "failed"),
        "models": str(root / "models"),
        "qdrant_storage": str(root / "qdrant_storage"),
    }


def path_state(paths: Mapping[str, str]) -> dict[str, dict[str, object]]:
    state: dict[str, dict[str, object]] = {}
    for key, value in paths.items():
        path = Path(value)
        state[key] = {
            "path": value,
            "exists": path.exists(),
            "is_dir": path.is_dir(),
        }
    return state


def collect_snapshot(
    *,
    repo_root: Path,
    conda_runner: Callable[[str | None], dict[str, str]] = list_conda_envs,
    include_conda: bool = True,
) -> dict[str, object]:
    env_values = load_safe_env_file(repo_root / ".env.local")
    data_root = env_values.get("GOODQ_DATA_ROOT") or os.environ.get("GOODQ_DATA_ROOT") or "%USERPROFILE%\\GoodQ_Bootstrap_Test"
    conda_exe = detect_conda() if include_conda else None
    conda_envs = conda_runner(conda_exe) if include_conda else {}
    expected = goodq_env_names()
    derived = derived_data_paths(data_root)

    return {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mode": "snapshot_only",
        "repo_root": str(repo_root),
        "conda_exe": conda_exe,
        "expected_conda_envs": expected,
        "present_goodq_conda_envs": {name: conda_envs[name] for name in expected if name in conda_envs},
        "local_config_files": {
            rel: {"exists": (repo_root / rel).exists(), "path": str(repo_root / rel)}
            for rel in LOCAL_CONFIG_FILES
        },
        "local_env": env_values,
        "derived_paths": path_state(derived),
        "notes": [
            "Snapshot excludes token and secret environment keys.",
            "Use a fresh data root for clean bootstrap testing instead of deleting existing user data.",
            "This helper does not remove Conda environments, services, data, models, or config files.",
        ],
    }


def build_reset_plan(*, repo_root: Path, fresh_data_root: str) -> dict[str, object]:
    commands: list[str] = [
        "# Review these commands before running them.",
        "$Stamp = Get-Date -Format yyyyMMdd_HHmmss",
        '$Backup = ".bootstrap_hygiene_backups\\$Stamp"',
        'New-Item -ItemType Directory -Force -Path "$Backup" | Out-Null',
        'if (Test-Path ".env.local") { Move-Item -LiteralPath ".env.local" -Destination "$Backup\\.env.local" }',
        (
            'if (Test-Path "configs\\config.local.yaml") { '
            'Move-Item -LiteralPath "configs\\config.local.yaml" -Destination "$Backup\\config.local.yaml" }'
        ),
    ]
    for env_name in goodq_env_names():
        commands.append(f"conda env remove -n {env_name} -y")
    commands.extend(
        [
            (
                'python scripts/bootstrap_install.py --yes --disable-gpu --disable-wsl-audio '
                f'--data-root "{fresh_data_root}" --no-launch'
            ),
            ".\\scripts\\bootstrap_validate.bat",
            ".\\LAUNCH_GOODQ.ps1 -DryRun",
        ]
    )
    return {
        "mode": "plan_only",
        "repo_root": str(repo_root),
        "fresh_data_root": fresh_data_root,
        "warning": "Review these commands before running them. This helper does not execute reset commands.",
        "commands": commands,
        "manual_admin_optional": [
            "If you need to retest Qdrant service installation, uninstall GoodQ_Qdrant as Administrator before running bootstrap.",
            "Do not delete existing qdrant_storage or GoodQ_Data unless you have confirmed they are disposable test data.",
        ],
    }


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot", help="write a non-destructive bootstrap state snapshot")
    snapshot.add_argument("--output", type=Path, help="optional JSON output path")
    snapshot.add_argument("--no-conda", action="store_true", help="skip conda env discovery")

    plan = subparsers.add_parser("plan-reset", help="print a reviewed manual reset plan")
    plan.add_argument(
        "--fresh-data-root",
        default="%USERPROFILE%\\GoodQ_Bootstrap_Test",
        help="fresh data root to pass to bootstrap_install.py",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root()
    if args.command == "snapshot":
        payload = collect_snapshot(repo_root=root, include_conda=not args.no_conda)
        if args.output:
            write_json(args.output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "plan-reset":
        payload = build_reset_plan(repo_root=root, fresh_data_root=args.fresh_data_root)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
