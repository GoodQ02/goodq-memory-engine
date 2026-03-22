#!/usr/bin/env python
"""Read-only bootstrap verification for clone readiness."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


QDRANT_SERVICE_NAME = "GoodQ_Qdrant"
SUPPORTED_STEP_ENVS: tuple[tuple[str, str, str], ...] = (
    ("goodq_video_scene_detect", "scene detection", "envs/locks/video_scene_detect.lock.txt"),
    ("goodq_image_caption", "ocr, captioning, exif, clip, dino", "envs/locks/image_caption.lock.txt"),
    ("goodq_object_detect", "object detection", "envs/locks/object_detect.lock.txt"),
    ("goodq_face_embed", "face detection and embeddings (Conda dlib + locked pip recipe)", "envs/locks/face_embed.lock.txt"),
    ("goodq_text_embed", "text embeddings", "envs/locks/text_embed.lock.txt"),
    ("goodq_audio_metadata", "audio metadata and time hints", "envs/locks/audio_metadata.lock.txt"),
    ("goodq_audio_transcribe", "audio transcription helpers", "envs/locks/audio_transcribe.lock.txt"),
    ("goodq_audio_emotion", "audio emotion analysis", "envs/locks/audio_emotion.lock.txt"),
    ("goodq_audio_embed", "audio embeddings", "envs/locks/audio_embed.lock.txt"),
)


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


def _detect_conda() -> Path | None:
    candidates: list[Path] = []
    env_conda = os.environ.get("CONDA_EXE")
    if env_conda:
        candidates.append(Path(env_conda))
    which_conda = shutil.which("conda")
    if which_conda:
        candidates.append(Path(which_conda))
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    if user_profile:
        candidates.extend(
            [
                user_profile / "miniconda3" / "Scripts" / "conda.exe",
                user_profile / "anaconda3" / "Scripts" / "conda.exe",
            ]
        )
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def _check_step_env_pack() -> List[CheckResult]:
    conda_exe = _detect_conda()
    if not conda_exe:
        return [CheckResult("step_env_pack", "warn", "conda not found; unable to verify supported step environments")]

    completed = subprocess.run([str(conda_exe), "env", "list", "--json"], capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "conda env list failed"
        return [CheckResult("step_env_pack", "warn", detail)]

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return [CheckResult("step_env_pack", "warn", "conda env list returned invalid JSON")]

    present = {Path(env_path).name.lower() for env_path in payload.get("envs", [])}
    results: List[CheckResult] = []
    for env_name, desc, lock_rel_path in SUPPORTED_STEP_ENVS:
        lock_path = REPO_ROOT / lock_rel_path
        if not lock_path.exists():
            results.append(CheckResult(f"step_env_lock:{env_name}", "fail", f"missing lock recipe at {lock_path}"))
            continue
        if env_name.lower() in present:
            results.append(CheckResult(f"step_env:{env_name}", "pass", f"present ({desc}); lock={lock_rel_path}"))
        else:
            results.append(CheckResult(f"step_env:{env_name}", "fail", f"missing ({desc}); lock={lock_rel_path}"))
    return results


def _check_qdrant_binary() -> CheckResult:
    binary = REPO_ROOT / "vendor" / "qdrant" / "qdrant.exe"
    if binary.exists():
        return CheckResult("qdrant_binary", "pass", str(binary))
    return CheckResult("qdrant_binary", "warn", f"not found at {binary}")


def _run_powershell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
    )


def _inspect_windows_service(name: str) -> Dict[str, str]:
    command = (
        f"$svc = Get-Service -Name '{name}' -ErrorAction SilentlyContinue; "
        "if ($null -eq $svc) { 'exists=false' } "
        "else { 'exists=true'; 'status=' + $svc.Status.ToString(); "
        "try { $cim = Get-CimInstance Win32_Service -Filter \"Name='"
        + name
        + "'\"; if ($cim) { 'start_mode=' + $cim.StartMode } } catch { } }"
    )
    completed = _run_powershell(command)
    info: Dict[str, str] = {}
    for line in (completed.stdout or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        info[key.strip()] = value.strip()
    return info


def _resolve_qdrant_url(cfg: Dict[str, Any]) -> str:
    qdrant_cfg = cfg.get("qdrant") if isinstance(cfg, dict) else {}
    if isinstance(qdrant_cfg, dict):
        host = qdrant_cfg.get("host")
        if isinstance(host, str) and host.strip():
            return host.strip()
    return "http://127.0.0.1:6333"


def _check_qdrant_runtime(cfg: Dict[str, Any]) -> CheckResult:
    url = _resolve_qdrant_url(cfg)
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/collections", timeout=5) as response:
            if response.status == 200:
                return CheckResult("qdrant_runtime", "pass", f"reachable at {url}")
    except urllib.error.URLError as exc:
        detail = str(exc.reason)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
    else:
        detail = "unexpected response"

    service = _inspect_windows_service(QDRANT_SERVICE_NAME)
    installer = REPO_ROOT / "scripts" / "qdrant" / "INSTALL_QDRANT_SERVICE.bat"
    if service.get("exists") == "true":
        service_detail = (
            f"service status={service.get('status', 'unknown')} "
            f"start_mode={service.get('start_mode', 'unknown')}"
        )
    else:
        service_detail = "service not installed"
    return CheckResult(
        "qdrant_runtime",
        "warn",
        f"unreachable at {url} ({detail}); {service_detail}; preferred remediation: {installer}",
    )


def _check_ffmpeg() -> CheckResult:
    override = os.environ.get("GOODQ_FFMPEG_EXE", "").strip().strip('"').strip("'")
    if override:
        override_path = Path(override)
        if override_path.is_dir():
            for name in ("ffmpeg.exe", "ffmpeg"):
                candidate = override_path / name
                if candidate.exists():
                    override_path = candidate
                    break
        if override_path.exists():
            return CheckResult("ffmpeg", "pass", f"GOODQ_FFMPEG_EXE={override_path}")
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return CheckResult("ffmpeg", "pass", ffmpeg_path)

    remediation: List[str] = []
    if shutil.which("winget"):
        remediation.append("winget install --id Gyan.FFmpeg.Essentials -e --accept-package-agreements --accept-source-agreements")
    if shutil.which("choco"):
        remediation.append("choco install ffmpeg -y")
    remediation.append("or set GOODQ_FFMPEG_EXE in .env.local")
    return CheckResult("ffmpeg", "warn", "; ".join(remediation))


def _resolve_pdftotext_from_hint(raw: str) -> Optional[Path]:
    hint = raw.strip()
    if not hint or hint.lower() == "pdftotext":
        return None
    candidate = Path(hint)
    if candidate.is_dir():
        for name in ("pdftotext.exe", "pdftotext"):
            exe = candidate / name
            if exe.exists():
                return exe
        return None
    if candidate.is_file():
        return candidate
    return None


def _check_pdftotext(cfg: Dict[str, Any]) -> CheckResult:
    tools_cfg = {}
    if isinstance(cfg, dict):
        config_cfg = cfg.get("config")
        if isinstance(config_cfg, dict):
            tools_cfg = config_cfg.get("tools") or {}
            if not isinstance(tools_cfg, dict):
                tools_cfg = {}

    env_hint = os.environ.get("GOODQ_POPPLER_BIN", "").strip()
    if env_hint:
        resolved = _resolve_pdftotext_from_hint(env_hint)
        if resolved:
            return CheckResult("pdftotext", "pass", f"GOODQ_POPPLER_BIN={resolved}")

    cfg_hint = str(tools_cfg.get("poppler_bin") or "").strip()
    if cfg_hint:
        resolved = _resolve_pdftotext_from_hint(cfg_hint)
        if resolved:
            return CheckResult("pdftotext", "pass", f"config.tools.poppler_bin={resolved}")

    path_hit = shutil.which("pdftotext")
    if path_hit:
        return CheckResult("pdftotext", "pass", path_hit)

    remediation = ["install Poppler/pdftotext and set GOODQ_POPPLER_BIN or add pdftotext to PATH"]
    if shutil.which("winget") or shutil.which("choco"):
        remediation.insert(0, "use an existing package manager to install Poppler/pdftotext")
    return CheckResult("pdftotext", "warn", "; ".join(remediation))


def _check_wsl_flag() -> CheckResult:
    value = os.environ.get("GOODQ_WSL_DISTRO")
    if value:
        return CheckResult("wsl_flag", "pass", f"GOODQ_WSL_DISTRO={value}")
    try:
        completed = subprocess.run(["wsl", "-l", "-q"], capture_output=True, text=True)
    except FileNotFoundError:
        return CheckResult("wsl_flag", "warn", "GOODQ_WSL_DISTRO not set and WSL is unavailable")
    raw_stdout = (completed.stdout or "").replace("\x00", "")
    distros = [line.strip() for line in raw_stdout.splitlines() if line.strip()]
    ubuntu_like = [candidate for candidate in distros if candidate.lower().startswith("ubuntu")]
    if ubuntu_like:
        chosen = next((candidate for candidate in ubuntu_like if candidate.lower() == "ubuntu"), None) or ubuntu_like[0]
        return CheckResult("wsl_flag", "warn", f"GOODQ_WSL_DISTRO unset (runtime auto-selects {chosen})")
    return CheckResult("wsl_flag", "warn", "GOODQ_WSL_DISTRO unset (runtime default is Ubuntu)")


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
    checks.append(_check_qdrant_runtime(cfg))
    checks.append(_check_ffmpeg())
    checks.append(_check_pdftotext(cfg))
    checks.append(_check_wsl_flag())
    checks.extend(_check_step_env_pack())
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
