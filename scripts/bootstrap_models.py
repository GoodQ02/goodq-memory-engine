from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

# Ensure vendored dependencies (e.g., huggingface_hub) are importable
_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists():
    sys.path.insert(0, str(_VENDOR_DIR))


def ensure_env(target_models_dir: Path) -> None:
    target_models_dir.mkdir(parents=True, exist_ok=True)
    # Prefer project models dir for all downloads
    os.environ['HF_HOME'] = str(target_models_dir)
    os.environ['TORCH_HOME'] = str(target_models_dir)
    os.environ.setdefault('TRANSFORMERS_CACHE', str(target_models_dir / 'cache'))
    # Default to enabling hf_transfer for faster, resilient downloads
    os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'


def snapshot(model_id: str, auth_token: str | None = None) -> Dict[str, str]:
    repo_id = model_id
    revision = None
    if '@' in model_id:
        repo_id, revision = model_id.split('@', 1)
    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except Exception as exc:  # pragma: no cover
        return {"model": model_id, "status": "error", "error": f"huggingface_hub not available: {exc}"}
    try:
        local_dir = snapshot_download(
            repo_id=repo_id,
            local_dir=None,
            revision=revision,
            local_dir_use_symlinks=False,
            token=auth_token,
        )
        return {"model": model_id, "status": "ok", "path": local_dir}
    except Exception as exc:  # pragma: no cover
        return {"model": model_id, "status": "error", "error": str(exc)}


def download_yolo_n() -> Dict[str, str]:
    # Ultralytics yolov8n.pt hosted in GH assets; cache into models/yolo
    url = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
    target = Path(os.environ.get("TORCH_HOME") or os.environ.get("HF_HOME") or ".") / "yolo" / "yolov8n.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 1024 * 1024:
        return {"asset": "yolov8n.pt", "status": "ok", "path": str(target), "cached": "true"}
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=120) as r, open(target, "wb") as f:
            f.write(r.read())
        return {"asset": "yolov8n.pt", "status": "ok", "path": str(target), "cached": "false"}
    except Exception as exc:  # pragma: no cover
        return {"asset": "yolov8n.pt", "status": "error", "error": str(exc)}


def main() -> None:
    # Resolve project root (scripts/..)
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    if load_dotenv:  # load project-level .env if available
        env_file = repo_root / ".env.local"
        if env_file.exists():
            load_dotenv(env_file)
    models_root = Path(os.environ.get("GOODQ_MODELS_DIR") or "L:/models")
    ensure_env(models_root)

    hf_token = os.environ.get("HF_TOKEN")
    pyannote_token = os.environ.get("PYANNOTE_TOKEN") or hf_token

    wanted: List[str] = [
        # Image caption (primary + fallback)
        "Salesforce/blip-image-captioning-base",
        "nlpconnect/vit-gpt2-image-captioning",
        # Image embeddings
        "openai/clip-vit-base-patch16",
        "facebook/dinov2-base",
        # Text embeddings
        "sentence-transformers/all-MiniLM-L6-v2",
        # Audio CLAP
        "laion/clap-htsat-unfused",
        # PyAnnote diarization pipeline + dependencies
        "pyannote/speaker-diarization@2.1",
        # Whisper variants used by diarize/transcribe stacks
        "openai/whisper-large-v3",
        "Systran/faster-whisper-large-v3",
        "Systran/faster-whisper-medium",
        "Systran/faster-whisper-tiny",
        "superb/hubert-large-superb-er",
        "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    ]

    results: List[Dict[str, str]] = []
    for mid in wanted:
        token = pyannote_token if mid.startswith('pyannote/') else hf_token
        results.append(snapshot(mid, token))

    results.append(download_yolo_n())

    out_dir = repo_root / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "bootstrap_models_report.json"
    report = {
        "models_dir": str(models_root),
        "env": {
            "HF_HOME": os.environ.get("HF_HOME"),
            "TORCH_HOME": os.environ.get("TORCH_HOME"),
        },
        "results": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()

