#!/usr/bin/env python
"""Read-only bootstrap verification for clone readiness."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class CheckResult:
    name: str
    status: str  # pass, warn, fail
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _check_config_load() -> tuple[CheckResult, Dict[str, Any]]:
    try:
        from steps.common.config_loader import load_configs

        cfg = load_configs()
        if not isinstance(cfg, dict) or not cfg:
            return CheckResult("config_load", "fail", "config returned empty or invalid payload"), {}
        return CheckResult("config_load", "pass", "config loaded successfully"), cfg
    except Exception as exc:  # noqa: BLE001
        return CheckResult("config_load", "fail", f"{type(exc).__name__}: {exc}"), {}


def _check_required_folders() -> List[CheckResult]:
    required = [
        "configs",
        "docs",
        "scripts",
        "steps",
    ]
    results: List[CheckResult] = []
    for folder in required:
        path_obj = REPO_ROOT / folder
        status = "pass" if path_obj.exists() else "fail"
        detail = str(path_obj)
        results.append(CheckResult(f"folder:{folder}", status, detail))
    return results


def _check_qdrant_binary() -> CheckResult:
    binary = REPO_ROOT / "vendor" / "qdrant" / "qdrant.exe"
    if binary.exists():
        return CheckResult("qdrant_binary", "pass", str(binary))
    return CheckResult("qdrant_binary", "warn", f"not found at {binary}")


def _check_wsl_flag() -> CheckResult:
    value = os.environ.get("GOODQ_WSL_DISTRO")
    if value:
        return CheckResult("wsl_flag", "pass", f"GOODQ_WSL_DISTRO={value}")
    return CheckResult("wsl_flag", "warn", "GOODQ_WSL_DISTRO not set (runtime default is Ubuntu)")


def _check_env_resolution(cfg: Dict[str, Any]) -> List[CheckResult]:
    paths = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
    resolved_data_root = paths.get("data_root")
    resolved_db_path = paths.get("db_path")
    profile = os.environ.get("GOODQ_HOST_PROFILE")

    results: List[CheckResult] = []
    if resolved_data_root:
        results.append(CheckResult("env:data_root", "pass", f"resolved data_root={resolved_data_root}"))
    else:
        results.append(CheckResult("env:data_root", "fail", "unable to resolve paths.data_root"))

    if resolved_db_path:
        results.append(CheckResult("env:db_path", "pass", f"resolved db_path={resolved_db_path}"))
    else:
        results.append(CheckResult("env:db_path", "warn", "unable to resolve paths.db_path"))

    if profile:
        results.append(CheckResult("env:host_profile", "pass", f"GOODQ_HOST_PROFILE={profile}"))
    else:
        results.append(CheckResult("env:host_profile", "warn", "GOODQ_HOST_PROFILE unset (legacy behavior)"))

    for name in ("GOODQ_DATA_ROOT", "GOODQ_WSL_USER", "GOODQ_WSL_WORKSPACE"):
        value = os.environ.get(name)
        if value:
            results.append(CheckResult(f"env:{name}", "pass", f"{name}={value}"))
        else:
            results.append(CheckResult(f"env:{name}", "warn", f"{name} unset (using defaults)"))

    return results


def build_report() -> Dict[str, Any]:
    checks: List[CheckResult] = []

    config_check, cfg = _check_config_load()
    checks.append(config_check)
    checks.extend(_check_required_folders())
    checks.append(_check_qdrant_binary())
    checks.append(_check_wsl_flag())
    checks.extend(_check_env_resolution(cfg))

    statuses = [entry.status for entry in checks]
    overall = "pass"
    if "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"

    return {"overall": overall, "checks": [entry.as_dict() for entry in checks]}


def _print_human(report: Dict[str, Any]) -> None:
    icon = {"pass": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}
    print("Bootstrap Verify")
    print("================")
    print(f"overall: {report['overall']}")
    print()
    for entry in report.get("checks", []):
        status = entry.get("status", "")
        print(f"{icon.get(status, '[??]')} {entry.get('name')}: {entry.get('detail')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only bootstrap verification for clone readiness")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human(report)

    if report["overall"] == "fail":
        sys.exit(1)


if __name__ == "__main__":
    main()
