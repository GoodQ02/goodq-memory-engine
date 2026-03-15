#!/usr/bin/env python
"""Cache readiness checker for goodq4all assets and models."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
try:
    from steps.common.config_loader import get_runtime_paths, load_configs
except Exception:  # pragma: no cover
    get_runtime_paths = None  # type: ignore[assignment]
    load_configs = None  # type: ignore[assignment]


def _default_models_dir() -> Path:
    if load_configs and get_runtime_paths:
        try:
            return Path(get_runtime_paths(load_configs({}), "models_cache"))
        except Exception:
            pass
    return REPO_ROOT / "_DATA" / "models"


MODELS_DEFAULT = _default_models_dir()
BOOTSTRAP_MODELS = REPO_ROOT / "scripts" / "bootstrap_models.py"
BOOTSTRAP_ASSETS = REPO_ROOT / "scripts" / "bootstrap_assets.ps1"

MODEL_SNAPSHOTS = {
    "Salesforce/blip-image-captioning-base": "models--Salesforce--blip-image-captioning-base",
    "nlpconnect/vit-gpt2-image-captioning": "models--nlpconnect--vit-gpt2-image-captioning",
    "openai/clip-vit-base-patch16": "models--openai--clip-vit-base-patch16",
    "facebook/dinov2-base": "models--facebook--dinov2-base",
    "sentence-transformers/all-MiniLM-L6-v2": "models--sentence-transformers--all-MiniLM-L6-v2",
    "laion/clap-htsat-unfused": "models--laion--clap-htsat-unfused",
    "pyannote/speaker-diarization@2.1": "models--pyannote--speaker-diarization",
    "openai/whisper-large-v3": "models--openai--whisper-large-v3",
    "Systran/faster-whisper-large-v3": "models--Systran--faster-whisper-large-v3",
    "Systran/faster-whisper-medium": "models--Systran--faster-whisper-medium",
    "Systran/faster-whisper-tiny": "models--Systran--faster-whisper-tiny",
}

YOLO_PATH = Path("yolo/yolov8n.pt")
LEXICON_PATH = Path("lexicons/NRC-Emotion-Lexicon")
DATASET_ROOT = Path("hf/datasets")

@dataclass
class CacheItem:
    name: str
    path: Path
    kind: str  # model / asset / dataset
    optional: bool = False

    def exists(self) -> bool:
        if self.kind == "model":
            return self._has_snapshot()
        if self.path.is_file():
            return True
        if self.path.is_dir() and any(self.path.iterdir()):
            return True
        return False

    def _has_snapshot(self) -> bool:
        if not self.path.exists():
            return False
        if not self.path.is_dir():
            return False
        snapshots = list(self.path.glob("snapshots/*"))
        return any(p.is_dir() and any(p.iterdir()) for p in snapshots)


def ensure_env() -> Path:
    if load_dotenv:
        env_file = REPO_ROOT / ".env.local"
        if env_file.exists():
            load_dotenv(env_file)
    raw_home = os.environ.get("HF_HOME")
    if not raw_home or "poppler" in raw_home.lower():
        raw_home = str(MODELS_DEFAULT)
    models_dir = Path(raw_home)
    models_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(models_dir)
    raw_torch = os.environ.get("TORCH_HOME")
    if not raw_torch or "poppler" in raw_torch.lower():
        raw_torch = str(models_dir)
    os.environ["TORCH_HOME"] = raw_torch
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    token = os.environ.get("HF_TOKEN") or os.environ.get("PYANNOTE_TOKEN")
    if not token:
        print("[WARN] HF_TOKEN/PYANNOTE_TOKEN not set; gated model checks may fail.")
    else:
        os.environ.setdefault("HF_TOKEN", token)
        os.environ.setdefault("PYANNOTE_TOKEN", token)
    return models_dir


def build_inventory(models_dir: Path) -> List[CacheItem]:
    items: List[CacheItem] = []
    hub_root = models_dir / "hub"
    for model_id, folder in MODEL_SNAPSHOTS.items():
        items.append(CacheItem(name=model_id, path=hub_root / folder, kind="model"))
    items.append(CacheItem(name="yolov8n.pt", path=models_dir / YOLO_PATH, kind="asset"))
    items.append(CacheItem(name="NRC-Emotion-Lexicon", path=models_dir / LEXICON_PATH, kind="asset"))
    items.append(CacheItem(name="HF datasets cache", path=models_dir / DATASET_ROOT, kind="dataset", optional=True))
    return items


def run_bootstrap_models() -> subprocess.CompletedProcess[str]:
    cmd = [
        "conda", "run", "-n", "goodq_text_embed",
        "python", str(BOOTSTRAP_MODELS),
    ]
    return subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, env=os.environ.copy())


def run_bootstrap_assets() -> subprocess.CompletedProcess[str]:
    cmd = [
        "pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(BOOTSTRAP_ASSETS),
        "-ModelsDir", os.environ.get("HF_HOME", str(MODELS_DEFAULT)),
    ]
    return subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, env=os.environ.copy())


def check_cache(auto_fix: bool) -> Dict[str, Dict[str, str]]:
    models_dir = ensure_env()
    inventory = build_inventory(models_dir)
    report: Dict[str, Dict[str, str]] = {}
    missing_models = False
    missing_assets = False

    for item in inventory:
        status = "present" if item.exists() else "missing"
        report[item.name] = {
            "status": status,
            "path": str(item.path),
            "kind": item.kind,
            "optional": str(item.optional).lower(),
        }
        if status == "missing" and not item.optional:
            if item.kind == "model":
                missing_models = True
            elif item.kind == "asset":
                missing_assets = True

    bootstrap_logs: Dict[str, str] = {}

    if auto_fix and (missing_models or missing_assets):
        if missing_models:
            result = run_bootstrap_models()
            bootstrap_logs["bootstrap_models"] = result.stdout.strip() or result.stderr.strip()
            # re-evaluate model entries
            for item in inventory:
                if item.kind == "model":
                    report[item.name]["status"] = "present" if item.exists() else "missing"
        if missing_assets:
            result = run_bootstrap_assets()
            bootstrap_logs["bootstrap_assets"] = result.stdout.strip() or result.stderr.strip()
            for item in inventory:
                if item.kind == "asset":
                    report[item.name]["status"] = "present" if item.exists() else "missing"

    if bootstrap_logs:
        report["bootstrap"] = bootstrap_logs

    return report


def summarize(report: Dict[str, Dict[str, str]]) -> int:
    missing = [key for key, entry in report.items() if entry.get("status") == "missing" and entry.get("optional") != 'true']
    print("Cache Readiness Report")
    print("======================")
    for key, entry in report.items():
        if key == "bootstrap":
            continue
        status = entry.get("status")
        icon = "[OK]" if status == "present" else "[MISS]"
        print(f"{icon} {key} -> {entry.get('path')}")
    if "bootstrap" in report:
        print("\nBootstrap Actions")
        for name, log in report["bootstrap"].items():
            print(f"- {name}: {log[:400]}" + ("..." if len(log) > 400 else ""))
    print()
    if missing:
        print("Missing items: " + ", ".join(missing))
        return 1
    print("All required caches are present.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify cached models/assets for goodq4all")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--auto-fix", action="store_true", help="Attempt to re-fetch missing caches")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = check_cache(auto_fix=args.auto_fix)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        if any(entry.get("status") == "missing" and entry.get("optional") != 'true' for key, entry in report.items() if key != "bootstrap"):
            sys.exit(1)
        return
    exit_code = summarize(report)
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()
