#!/usr/bin/env python
"""System readiness checker for the goodq4all stack."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dataset_specs import DATASET_SPECS, find_local_copy

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = REPO_ROOT / 'vendor'
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    print("Missing dependency 'pyyaml': {}".format(exc), file=sys.stderr)
    sys.exit(2)

if load_dotenv:
    env_file = REPO_ROOT / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)

FALLBACKS: Dict[str, Optional[str]] = {}


def apply_default(name: str, default: str, *, invalid: Optional[callable] = None) -> None:
    current = os.environ.get(name)
    needs_default = False
    if invalid is None:
        needs_default = current in (None, "")
    else:
        needs_default = current in (None, "") or invalid(current)
    if needs_default:
        FALLBACKS[name] = current
        os.environ[name] = default


apply_default("HF_HOME", "L:/models", invalid=lambda v: "poppler" in v.lower() if v else True)
apply_default("TORCH_HOME", "L:/models", invalid=lambda v: "poppler" in v.lower() if v else True)
# Prefer hf_transfer enabled by default for faster local-first fetches
apply_default("HF_HUB_ENABLE_HF_TRANSFER", "1", invalid=lambda v: v not in {None, "", "1"})
if os.environ.get("HF_TOKEN") and not os.environ.get("PYANNOTE_TOKEN"):
    os.environ["PYANNOTE_TOKEN"] = os.environ["HF_TOKEN"]
if os.environ.get("PYANNOTE_TOKEN") and not os.environ.get("HF_TOKEN"):
    os.environ["HF_TOKEN"] = os.environ["PYANNOTE_TOKEN"]

def _dataset_cache_root() -> Path:
    cache = os.environ.get('HF_DATASETS_CACHE')
    if cache:
        return Path(cache)
    hf_home = os.environ.get('HF_HOME') or 'L:/models'
    return Path(hf_home) / 'hf' / 'datasets'




@dataclass
class CheckResult:
    name: str
    status: str  # green, yellow, red
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def mask(value: Optional[str], keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return value
    return value[:keep] + "..." + value[-keep:]


def run_conda(env: str, code: str, timeout: int = 180, label: Optional[str] = None) -> CheckResult:
    conda_exe = os.environ.get("CONDA_EXE")
    if not conda_exe:
        candidates = [
            Path(os.environ.get("CONDA_PREFIX", "")) / "Scripts" / "conda.exe",
            Path(os.environ.get("CONDA_ROOT", "")) / "Scripts" / "conda.exe",
            Path("C:/Users/jdben/miniconda3/Scripts/conda.exe"),
            Path("C:/ProgramData/miniconda3/Scripts/conda.exe"),
        ]
        for candidate in candidates:
            if candidate and candidate.is_file():
                conda_exe = str(candidate)
                break
    conda_bat: Optional[str] = None
    if conda_exe and str(conda_exe).lower().endswith('.exe'):
        candidate_bat = Path(conda_exe).with_suffix('.bat')
        if candidate_bat.exists():
            conda_bat = str(candidate_bat)
    if not conda_exe:
        conda_exe = 'conda'
    if conda_bat:
        cmd = ['cmd.exe', '/C', conda_bat, 'run', '-n', env, 'python', '-c', code]
    else:
        cmd = [str(conda_exe), 'run', '-n', env, 'python', '-c', code]
    run_env = dict(os.environ)
    run_env.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '0')
    run_env.pop('PYTHONHOME', None)
    run_env.pop('PYTHONPATH', None)
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
            env=run_env,
        )
    except FileNotFoundError:
        return CheckResult(label or env, 'red', 'conda not found')
    except subprocess.TimeoutExpired:
        return CheckResult(label or env, 'yellow', 'timeout after {}s'.format(timeout))

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        return CheckResult(label or env, 'red', detail or 'command failed')
    return CheckResult(label or env, 'green', completed.stdout.strip() or 'ok')


def check_hf_access(model_id: str, token: Optional[str], revision: Optional[str] = None) -> CheckResult:
    try:
        from huggingface_hub import HfApi  # type: ignore
        try:
            from huggingface_hub.utils import GatedRepoError  # type: ignore
        except ImportError:  # pragma: no cover
            from huggingface_hub import GatedRepoError  # type: ignore
    except Exception as exc:
        return CheckResult("huggingface", "yellow", "huggingface_hub missing: {}".format(exc))

    if not token:
        return CheckResult("huggingface", "red", "token missing for {}".format(model_id))

    api = HfApi(token=token)
    try:
        api.model_info(model_id, revision=revision)
        return CheckResult("huggingface", "green", "access ok for {}".format(model_id))
    except GatedRepoError as exc:
        return CheckResult("huggingface", "red", "gated repo access denied: {}".format(exc))
    except Exception as exc:
        return CheckResult("huggingface", "yellow", "error: {}".format(exc))


def gather_env_checks() -> List[CheckResult]:
    def normalize(name: str, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return raw
        if name in {"HF_HOME", "TORCH_HOME"}:
            try:
                return Path(raw).as_posix()
            except Exception:
                return raw.replace('\\', '/')
        return raw

    targets = [
        ("HF_HOME", False),
        ("TORCH_HOME", False),
        ("HF_HUB_ENABLE_HF_TRANSFER", False),
        ("HF_TOKEN", True),
        ("PYANNOTE_TOKEN", True),
        ("GOODQ_API_HOST", False),
        ("GOODQ_API_PORT", False),
    ]
    results: List[CheckResult] = []
    for name, sensitive in targets:
        raw = normalize(name, os.environ.get(name))
        status = "green" if raw else "red"
        if name in ("HF_HOME", "TORCH_HOME") and raw:
            if not Path(raw).exists():
                status = "yellow"
        detail = mask(raw) if sensitive else (raw or "(missing)")
        results.append(CheckResult(name, status, detail))
    return results


def gather_path_checks(cfg: Dict[str, Any]) -> List[CheckResult]:
    checks: List[CheckResult] = []

    def check_path(name: str, path_value: Optional[str], must_exist: bool = True) -> None:
        if not path_value:
            checks.append(CheckResult(name, "red", "not configured"))
            return
        path_obj = Path(path_value)
        if path_obj.exists():
            status = "green"
        else:
            status = "red" if must_exist else "yellow"
        checks.append(CheckResult(name, status, str(path_obj)))

    tools_cfg = cfg.get("tools", {})
    check_path("tools_root", tools_cfg.get("root"))
    check_path("ffmpeg", tools_cfg.get("ffmpeg_exe"))
    check_path("whisper_cli", tools_cfg.get("whisper_cli"))
    check_path("whisper_model", tools_cfg.get("whisper_ggml_model"))
    check_path("tesseract", tools_cfg.get("tesseract_exe"), must_exist=False)
    check_path("poppler_bin", tools_cfg.get("poppler_bin"), must_exist=False)

    models_cfg = cfg.get("models", {})
    check_path("yolo_model", models_cfg.get("yolo_model_path"))
    lex_cfg = models_cfg.get("lexicons", {})
    check_path("nrc_emotion_dir", lex_cfg.get("nrc_emotion_dir"), must_exist=False)

    models_root = Path(os.environ.get("HF_HOME", "L:/models"))
    if models_root.exists():
        checks.append(CheckResult("models_root", "green", str(models_root)))
    else:
        checks.append(CheckResult("models_root", "red", str(models_root)))

    layers = [
        models_root / "hub" / "models--pyannote--speaker-diarization",
        models_root / "hf" / "datasets",
    ]
    for layer in layers:
        status = "green" if layer.exists() else "yellow"
        checks.append(CheckResult(layer.name, status, str(layer)))

    ffmpeg_path = Path(tools_cfg.get("ffmpeg_exe") or "")
    checks.append(check_ffmpeg(ffmpeg_path))

    return checks


def gather_dataset_checks(cache_root: Path) -> List[CheckResult]:
    checks: List[CheckResult] = []
    token_present = bool(os.environ.get('HF_TOKEN') or os.environ.get('HF_HUB_TOKEN'))
    for spec in DATASET_SPECS:
        info = find_local_copy(spec, cache_root)
        name = f"dataset:{spec.display_name}"
        if info:
            detail = f"{info['source']} ({info['path']})"
            checks.append(CheckResult(name, 'green', detail))
            continue
        if spec.gated and not token_present:
            checks.append(CheckResult(name, 'yellow', 'missing (gated dataset; configure HF_TOKEN)'))
        else:
            checks.append(CheckResult(name, 'yellow', 'missing (download on demand)'))
    return checks




def gather_conda_checks(token_present: bool) -> List[CheckResult]:
    checks: List[CheckResult] = []
    torch_probe = (
        "import os; os.environ.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '0'); "
        "import torch, torchaudio; print(str({'cuda': torch.cuda.is_available(), 'token': bool(os.getenv('PYANNOTE_TOKEN'))}))"
    )
    checks.append(run_conda("goodq_audio_diarize", torch_probe, label="goodq_audio_diarize:torch"))

    if token_present:
        pipeline_probe = (
            "import os; os.environ.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '0'); "
            "from pyannote.audio import Pipeline; token = os.getenv('PYANNOTE_TOKEN'); "
            "Pipeline.from_pretrained('pyannote/speaker-diarization@2.1', use_auth_token=token, cache_dir=os.getenv('HF_HOME')); "
            "print('pipeline ok')"
        )
        checks.append(run_conda("goodq_audio_diarize", pipeline_probe, label="goodq_audio_diarize:pyannote"))
    else:
        checks.append(CheckResult("goodq_audio_diarize:pyannote", "red", "token missing; skipped"))

    text_probe = (
        "import os; os.environ.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '0'); "
        "from huggingface_hub import HfFolder; print('token set' if HfFolder.get_token() else 'no token')"
    )
    checks.append(run_conda("goodq_text_embed", text_probe, label="goodq_text_embed:hf_token"))

    scene_probe = "import cv2; print('cv2 {} loaded'.format(cv2.__version__))"
    checks.append(run_conda("goodq_video_scene_detect", scene_probe, label="goodq_video_scene_detect:cv2"))

    return checks


def check_ffmpeg(ffmpeg_path: Path) -> CheckResult:
    if not ffmpeg_path:
        return CheckResult("ffmpeg", "yellow", "not configured")
    try:
        proc = subprocess.run([str(ffmpeg_path), "-version"], capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return CheckResult("ffmpeg", "red", "not found at {}".format(ffmpeg_path))
    except subprocess.TimeoutExpired:
        return CheckResult("ffmpeg", "yellow", "ffmpeg -version timed out")
    status = "green" if proc.returncode == 0 else "red"
    detail = proc.stdout.splitlines()[0] if proc.stdout else proc.stderr.strip()
    return CheckResult("ffmpeg", status, detail or "no output")


def load_project_config() -> Dict[str, Any]:
    cfg_path = REPO_ROOT / "configs" / "config_open.yaml"
    with cfg_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_report() -> Dict[str, Any]:
    cfg = load_project_config()
    env_results = gather_env_checks()
    path_results = gather_path_checks(cfg)
    dataset_results = gather_dataset_checks(_dataset_cache_root())
    token = os.environ.get("PYANNOTE_TOKEN") or DEFAULT_TOKEN
    hf_result = check_hf_access("pyannote/speaker-diarization", token, revision="2.1")
    conda_results = gather_conda_checks(bool(token))

    report_sections: Dict[str, Any] = {
        "env": [r.as_dict() for r in env_results],
        "paths": [r.as_dict() for r in path_results],
        "datasets": [r.as_dict() for r in dataset_results],
        "huggingface": hf_result.as_dict(),
        "conda": [r.as_dict() for r in conda_results],
    }
    if FALLBACKS:
        report_sections["fallbacks"] = {k: mask(v) for k, v in FALLBACKS.items()}

    statuses = [r.status for r in env_results + path_results + dataset_results + [hf_result] + conda_results]
    overall = "green"
    if "red" in statuses:
        overall = "red"
    elif "yellow" in statuses:
        overall = "yellow"

    return {"overall": overall, **report_sections}


def print_report(report: Dict[str, Any]) -> None:
    icons = {"green": "[OK]", "yellow": "[WARN]", "red": "[FAIL]"}
    print("System Readiness Report")
    print("========================")
    print("Overall status: {}".format(report["overall"].upper()))
    print()

    def dump(title: str, entries: List[Dict[str, str]]) -> None:
        if not entries:
            return
        print(title)
        for entry in entries:
            icon = icons.get(entry.get("status", ""), "[??]")
            detail = entry.get("detail", "")
            print("  {} {}: {}".format(icon, entry.get("name", ""), detail))
        print()

    dump("Environment", report.get("env", []))
    dump("Paths", report.get("paths", []))
    dump("Datasets", report.get("datasets", []))
    hf = report.get("huggingface")
    if hf:
        icon = icons.get(hf.get("status", ""), "[??]")
        print("HuggingFace")
        print("  {} {}".format(icon, hf.get("detail", "")))
        print()
    dump("Conda Envs", report.get("conda", []))
    fallbacks = report.get("fallbacks") or {}
    if fallbacks:
        print("Fallbacks Applied")
        for name, original in fallbacks.items():
            print("  [fallback] {}: previous={}".format(name, original or "(unset)"))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check system readiness for goodq4all")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_report(report)

    if report["overall"] == "red":
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
