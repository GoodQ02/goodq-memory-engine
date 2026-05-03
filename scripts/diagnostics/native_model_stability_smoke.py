"""Read-only native/model environment stability smoke.

This diagnostic probes crash-family model environments without invoking
ingestion, writing scene artifacts, or touching memory/vector stores.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


NATIVE_CRASH_CODES = {
    3221226505: "0xC0000409",
    -1073740791: "0xC0000409",
}


TARGETS: dict[str, dict[str, Any]] = {
    "object_detect": {
        "env": "goodq_object_detect",
        "step": "object_detect",
        "component": "YOLO",
        "model": "ultralytics/yolov8n",
        "imports": ["torch", "torchvision", "ultralytics", "numpy", "PIL"],
        "packages": ["torch", "torchvision", "torchaudio", "ultralytics", "numpy", "pillow"],
        "model_candidates": ["models/yolov8n.pt", "yolov8n.pt"],
    },
    "image_caption": {
        "env": "goodq_image_caption",
        "step": "image_caption",
        "component": "BLIP captioning",
        "model": "Salesforce/blip-image-captioning-base",
        "imports": ["torch", "torchvision", "transformers", "PIL"],
        "packages": ["torch", "torchvision", "torchaudio", "transformers", "timm", "pillow"],
        "model_candidates": [],
    },
    "image_embed_dino": {
        "env": "goodq_image_caption",
        "step": "image_embed_dino",
        "component": "DINO",
        "model": "facebook/dinov2-base",
        "imports": ["torch", "torchvision", "transformers", "PIL"],
        "packages": ["torch", "torchvision", "torchaudio", "transformers", "timm", "pillow"],
        "model_candidates": [],
    },
    "audio_embed_clap": {
        "env": "goodq_audio_embed",
        "step": "audio_embed_clap",
        "component": "CLAP",
        "model": "laion/clap-htsat-unfused",
        "imports": ["torch", "torchaudio", "transformers", "numpy"],
        "packages": ["torch", "torchaudio", "transformers", "numpy", "librosa", "soundfile"],
        "model_candidates": [],
    },
}


CHILD_PROBE = r"""
import importlib
import importlib.metadata as metadata
import json
import os
import pathlib
import sys
import time
import traceback


def _clean_error(exc):
    text = str(exc).replace("\\", "/")
    return text[-500:]


def _version(package):
    try:
        return metadata.version(package)
    except Exception:
        return None


def _import_status(module_name):
    started = time.perf_counter()
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        return {
            "module": module_name,
            "ok": True,
            "version": str(version) if version is not None else None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except Exception as exc:
        return {
            "module": module_name,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": _clean_error(exc),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }


def _torch_status():
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        device_name = None
        if cuda_available and torch.cuda.device_count() > 0:
            try:
                device_name = torch.cuda.get_device_name(0)
            except Exception:
                device_name = None
        return {
            "ok": True,
            "torch_version": str(torch.__version__),
            "cuda_compiled": getattr(torch.version, "cuda", None),
            "cuda_available": cuda_available,
            "device_count": int(torch.cuda.device_count()) if hasattr(torch, "cuda") else 0,
            "selected_device": "cuda:0" if cuda_available else "cpu",
            "device_name": device_name,
        }
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "error": _clean_error(exc)}


def _missing_cache_error(exc):
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "local_files_only",
            "couldn't connect",
            "could not connect",
            "not found in cache",
            "no such file",
            "does not appear to have",
        )
    )


def _try_model_load(target, allow_downloads):
    model = target.get("model")
    step = target.get("step")
    candidates = [pathlib.Path(p) for p in target.get("model_candidates", [])]
    local_path = next((p for p in candidates if p.exists()), None)
    started = time.perf_counter()
    try:
        if step == "object_detect":
            if local_path is None and not allow_downloads:
                return {"attempted": False, "status": "missing_model_cache", "elapsed_ms": 0.0}
            from ultralytics import YOLO

            YOLO(str(local_path or model))
        elif step == "audio_embed_clap":
            from transformers import ClapModel

            ClapModel.from_pretrained(model, local_files_only=not allow_downloads)
        else:
            if not allow_downloads:
                return {"attempted": False, "status": "missing_model_cache", "elapsed_ms": 0.0}
            from transformers import AutoModel

            AutoModel.from_pretrained(model, local_files_only=False)
        return {
            "attempted": True,
            "status": "ok",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except Exception as exc:
        status = "missing_model_cache" if _missing_cache_error(exc) else "error"
        return {
            "attempted": True,
            "status": status,
            "error_type": type(exc).__name__,
            "error": _clean_error(exc),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }


target = json.loads(os.environ["GOODQ_NATIVE_SMOKE_TARGET"])
model_load = os.environ.get("GOODQ_NATIVE_SMOKE_MODEL_LOAD") == "1"
allow_downloads = os.environ.get("GOODQ_NATIVE_SMOKE_ALLOW_DOWNLOADS") == "1"

if not allow_downloads:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

report = {
    "target": target.get("name"),
    "step": target.get("step"),
    "env": target.get("env"),
    "component": target.get("component"),
    "model": target.get("model"),
    "mode": "model_load" if model_load else "metadata",
    "allow_downloads": allow_downloads,
    "python": sys.version.split()[0],
    "packages": {package: _version(package) for package in target.get("packages", [])},
    "imports": [_import_status(module) for module in target.get("imports", [])],
    "torch": _torch_status(),
    "model_load": {"attempted": False, "status": "not_requested"},
}

if model_load:
    report["model_load"] = _try_model_load(target, allow_downloads)

print(json.dumps(report, sort_keys=True))
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _tail(text: str | None, limit: int = 2000) -> str:
    if not text:
        return ""
    text = text.replace("\\", "/")
    return text[-limit:]


def _native_status_code(return_code: int | None) -> str | None:
    if return_code is None:
        return None
    return NATIVE_CRASH_CODES.get(return_code)


def _classify_probe_result(result: dict[str, Any]) -> str:
    if result.get("timeout"):
        return "timeout"
    status_code = _native_status_code(result.get("return_code"))
    if status_code:
        return "native_crash"
    child = result.get("probe") or {}
    if not child:
        return "probe_output_missing" if result.get("return_code") == 0 else "subprocess_error"
    imports = child.get("imports") or []
    if any(not item.get("ok") for item in imports):
        return "import_failed"
    model_load = child.get("model_load") or {}
    model_status = model_load.get("status")
    if model_status == "missing_model_cache":
        return "missing_model_cache"
    if model_status == "error":
        return "model_load_failed"
    if result.get("return_code") not in (0, None):
        return "subprocess_error"
    return "ok" if model_status == "ok" else "metadata_only"


def _child_command() -> str:
    encoded = base64.b64encode(CHILD_PROBE.encode("utf-8")).decode("ascii")
    return f"import base64; exec(base64.b64decode('{encoded}').decode('utf-8'))"


def _run_target(
    target_name: str,
    *,
    conda_exe: str,
    model_load: bool,
    allow_downloads: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    target = dict(TARGETS[target_name])
    target["name"] = target_name
    env = os.environ.copy()
    env["GOODQ_NATIVE_SMOKE_TARGET"] = json.dumps(target, sort_keys=True)
    env["GOODQ_NATIVE_SMOKE_MODEL_LOAD"] = "1" if model_load else "0"
    env["GOODQ_NATIVE_SMOKE_ALLOW_DOWNLOADS"] = "1" if allow_downloads else "0"
    if not allow_downloads:
        env.setdefault("HF_HUB_OFFLINE", "1")
        env.setdefault("TRANSFORMERS_OFFLINE", "1")

    cmd = [
        conda_exe,
        "run",
        "-n",
        target["env"],
        "python",
        "-c",
        _child_command(),
    ]
    started = time.perf_counter()
    result: dict[str, Any] = {
        "target": target_name,
        "step": target["step"],
        "env": target["env"],
        "component": target["component"],
        "model": target["model"],
        "mode": "model_load" if model_load else "metadata",
        "return_code": None,
        "status_code": None,
        "elapsed_ms": None,
        "stderr_tail": "",
        "stdout_tail": "",
        "probe": None,
        "timeout": False,
    }
    try:
        completed = subprocess.run(
            cmd,
            cwd=_repo_root(),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        result["return_code"] = completed.returncode
        result["status_code"] = _native_status_code(completed.returncode)
        result["stderr_tail"] = _tail(completed.stderr)
        result["stdout_tail"] = _tail(completed.stdout)
        if completed.stdout.strip():
            try:
                result["probe"] = json.loads(completed.stdout.strip().splitlines()[-1])
            except json.JSONDecodeError:
                result["probe"] = None
    except subprocess.TimeoutExpired as exc:
        result["timeout"] = True
        result["return_code"] = None
        result["stderr_tail"] = _tail(exc.stderr if isinstance(exc.stderr, str) else "")
        result["stdout_tail"] = _tail(exc.stdout if isinstance(exc.stdout, str) else "")
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    result["classification"] = _classify_probe_result(result)
    return result


def run_smoke(
    targets: list[str],
    *,
    conda_exe: str = "conda",
    model_load: bool = False,
    allow_downloads: bool = False,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "model_load" if model_load else "metadata",
        "safety_boundary": {
            "ingestion_triggered": False,
            "scene_artifacts_written": False,
            "qdrant_written": False,
            "kg_written": False,
            "reports_written": False,
            "network_downloads_allowed": allow_downloads,
        },
        "targets": [
            _run_target(
                target,
                conda_exe=conda_exe,
                model_load=model_load,
                allow_downloads=allow_downloads,
                timeout_seconds=timeout_seconds,
            )
            for target in targets
        ],
    }


def _human_summary(report: dict[str, Any]) -> str:
    lines = [
        f"Native model stability smoke ({report['mode']})",
        "Safety: no ingestion, no scene writes, no Qdrant writes, no KG writes.",
    ]
    for target in report["targets"]:
        code = f" {target['status_code']}" if target.get("status_code") else ""
        lines.append(
            f"- {target['step']} [{target['env']}]: {target['classification']}"
            f"{code} ({target['elapsed_ms']} ms)"
        )
    return "\n".join(lines)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        choices=sorted(TARGETS),
        help="Target to probe. Repeat for multiple targets. Defaults to all targets.",
    )
    parser.add_argument("--json", action="store_true", help="Emit structured JSON to stdout.")
    parser.add_argument(
        "--model-load",
        action="store_true",
        help="Attempt local-cache-only model load. Network downloads stay disabled unless --allow-downloads is set.",
    )
    parser.add_argument(
        "--no-model-load",
        action="store_true",
        help="Force metadata/import-only mode. This is the default.",
    )
    parser.add_argument(
        "--allow-downloads",
        action="store_true",
        help="Allow model downloads during --model-load. Off by default.",
    )
    parser.add_argument("--conda-exe", default=os.environ.get("CONDA_EXE") or shutil.which("conda") or "conda")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    targets = args.target or list(TARGETS)
    report = run_smoke(
        targets,
        conda_exe=args.conda_exe,
        model_load=bool(args.model_load and not args.no_model_load),
        allow_downloads=bool(args.allow_downloads),
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_human_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
