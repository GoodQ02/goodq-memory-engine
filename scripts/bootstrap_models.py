from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

# Ensure vendored dependencies (e.g., huggingface_hub) are importable
_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_DIR = _REPO_ROOT / "vendor"
sys.path.insert(0, str(_REPO_ROOT))
if _VENDOR_DIR.exists():
    sys.path.append(str(_VENDOR_DIR))


DEFAULT_DOWNLOAD_RETRIES = 4
YOLO_URL = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
_HF_TOKEN_CANDIDATES = ("HF_TOKEN", "HF_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")
_PLACEHOLDER_TOKENS = {
    "your_huggingface_token_here",
    "your_pyannote_token_here",
    "your_token_here",
    "changeme",
}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _clean_token(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().strip('"').strip("'")
    if not value:
        return None
    if value.lower() in _PLACEHOLDER_TOKENS:
        return None
    return value


def _resolve_env_token(*names: str) -> tuple[str | None, str | None]:
    for name in names:
        token = _clean_token(os.environ.get(name))
        if token:
            return token, name
    return None, None


def resolve_auth_tokens() -> Dict[str, str | bool | None]:
    hf_token, hf_source = _resolve_env_token(*_HF_TOKEN_CANDIDATES)
    pyannote_token, pyannote_source = _resolve_env_token("PYANNOTE_TOKEN")
    if not pyannote_token:
        pyannote_token = hf_token
        pyannote_source = hf_source

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ.setdefault("HF_HUB_TOKEN", hf_token)
    if pyannote_token:
        os.environ.setdefault("PYANNOTE_TOKEN", pyannote_token)

    return {
        "hf_token": hf_token,
        "hf_source": hf_source,
        "pyannote_token": pyannote_token,
        "pyannote_source": pyannote_source,
        "hf_present": bool(hf_token),
        "pyannote_present": bool(pyannote_token),
    }


def _default_retry_count() -> int:
    raw = os.environ.get("GOODQ_MODEL_DOWNLOAD_RETRIES", str(DEFAULT_DOWNLOAD_RETRIES)).strip()
    try:
        return max(int(raw), 1)
    except ValueError:
        return DEFAULT_DOWNLOAD_RETRIES


def _is_transient_download_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        token in lowered
        for token in (
            "connection reset",
            "connection broken",
            "connection aborted",
            "read timed out",
            "read timeout",
            "timed out",
            "server disconnected",
            "temporary failure",
            "temporarily unavailable",
            "name resolution",
            "http 502",
            "http 503",
            "http 504",
            "chunkedencodingerror",
            "incomplete read",
            "connectionerror",
        )
    )


def _retry_pause(attempt: int) -> None:
    time.sleep(min(3 * attempt, 15))


def ensure_env(target_models_dir: Path) -> None:
    target_models_dir.mkdir(parents=True, exist_ok=True)
    # Prefer project models dir for all downloads
    os.environ['HF_HOME'] = str(target_models_dir)
    os.environ['HF_HUB_CACHE'] = str(target_models_dir / 'hub')
    os.environ['TORCH_HOME'] = str(target_models_dir)
    os.environ.setdefault('TRANSFORMERS_CACHE', str(target_models_dir / 'cache'))
    # Default to enabling hf_transfer for faster, resilient downloads
    os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'
    os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS', '0')
    os.environ.setdefault('PYTHONUNBUFFERED', '1')


def _repo_cache_dir(models_root: Path, repo_id: str) -> Path:
    repo_cache_name = repo_id.replace("/", "--")
    return models_root / "hub" / f"models--{repo_cache_name}"


def _cache_snapshot_present(models_root: Path, repo_id: str) -> bool:
    repo_cache = _repo_cache_dir(models_root, repo_id) / "snapshots"
    if not repo_cache.exists():
        return False
    for candidate in repo_cache.iterdir():
        if candidate.is_dir() and any(candidate.iterdir()):
            return True
    return False


def snapshot(
    model_id: str,
    auth_token: str | None = None,
    revision: str | None = None,
    *,
    models_root: Path | None = None,
    retries: int = DEFAULT_DOWNLOAD_RETRIES,
    progress_label: str = "",
) -> Dict[str, str]:
    """
    Download a model snapshot from HuggingFace Hub.
    
    Args:
        model_id: Model ID (may include @revision)
        auth_token: HuggingFace auth token
        revision: Explicit revision (commit SHA, tag, or branch). Overrides @revision in model_id.
        models_root: Canonical GoodQ models root for local placement.
    """
    repo_id = model_id
    if '@' in model_id and revision is None:
        repo_id, revision = model_id.split('@', 1)
    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except Exception as exc:  # pragma: no cover
        return {"model": model_id, "status": "error", "error": f"huggingface_hub not available: {exc}"}
    target_models_root = models_root or Path(os.environ.get("HF_HOME") or ".")
    cache_dir = target_models_root / "hub"
    cache_dir.mkdir(parents=True, exist_ok=True)
    attempts = max(int(retries), 1)
    label = f"[bootstrap] [{progress_label}] " if progress_label else "[bootstrap] "

    for attempt in range(1, attempts + 1):
        _log(f"{label}syncing {repo_id} (attempt {attempt}/{attempts})")
        try:
            resolved_dir = snapshot_download(
                repo_id=repo_id,
                cache_dir=str(cache_dir),
                revision=revision,
                token=auth_token,
            )
            if not _cache_snapshot_present(target_models_root, repo_id):
                return {
                    "model": model_id,
                    "status": "error",
                    "error": f"cache layout incomplete for {repo_id} under {cache_dir}",
                    "attempts": str(attempt),
                }
            _log(f"{label}ready {repo_id}")
            return {
                "model": model_id,
                "status": "ok",
                "path": resolved_dir,
                "revision": revision or "default",
                "attempts": str(attempt),
                "cache_verified": "true",
            }
        except Exception as exc:  # pragma: no cover
            detail = str(exc)
            if attempt < attempts and _is_transient_download_error(detail):
                _log(f"{label}transient failure for {repo_id}: {detail}. Retrying...")
                _retry_pause(attempt)
                continue
            return {"model": model_id, "status": "error", "error": detail, "attempts": str(attempt)}


def download_yolo_n(*, retries: int = DEFAULT_DOWNLOAD_RETRIES, progress_label: str = "") -> Dict[str, str]:
    # Ultralytics yolov8n.pt hosted in GH assets; cache into models/yolo
    target = Path(os.environ.get("TORCH_HOME") or os.environ.get("HF_HOME") or ".") / "yolo" / "yolov8n.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 1024 * 1024:
        return {"asset": "yolov8n.pt", "status": "ok", "path": str(target), "cached": "true"}
    attempts = max(int(retries), 1)
    label = f"[bootstrap] [{progress_label}] " if progress_label else "[bootstrap] "
    temp_target = target.with_suffix(".tmp")
    for attempt in range(1, attempts + 1):
        try:
            _log(f"{label}downloading yolov8n.pt (attempt {attempt}/{attempts})")
            with urllib.request.urlopen(YOLO_URL, timeout=120) as response, open(temp_target, "wb") as handle:
                total = int(response.headers.get("Content-Length", "0") or "0")
                downloaded = 0
                next_marker = 25
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        percent = int((downloaded / total) * 100)
                        while percent >= next_marker and next_marker <= 100:
                            _log(f"{label}yolov8n.pt {next_marker}%")
                            next_marker += 25
            os.replace(temp_target, target)
            _log(f"{label}ready yolov8n.pt")
            return {"asset": "yolov8n.pt", "status": "ok", "path": str(target), "cached": "false", "attempts": str(attempt)}
        except Exception as exc:  # pragma: no cover
            detail = str(exc)
            try:
                temp_target.unlink(missing_ok=True)
            except Exception:
                pass
            if attempt < attempts and _is_transient_download_error(detail):
                _log(f"{label}transient failure for yolov8n.pt: {detail}. Retrying...")
                _retry_pause(attempt)
                continue
            return {"asset": "yolov8n.pt", "status": "error", "error": detail, "attempts": str(attempt)}


def load_registry(repo_root: Path) -> Dict | None:
    """Load model registry if it exists."""
    try:
        import yaml  # type: ignore
        registry_path = repo_root / "configs" / "model_registry.yaml"
        if registry_path.exists():
            with open(registry_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return None


def build_wanted_models(registry: Dict | None) -> List[str]:
    if isinstance(registry, dict):
        huggingface_models = registry.get("huggingface_models")
        if isinstance(huggingface_models, dict):
            wanted = []
            for model_info in huggingface_models.values():
                if not isinstance(model_info, dict):
                    continue
                repo_id = str(model_info.get("repo_id") or "").strip()
                if repo_id:
                    wanted.append(repo_id)
            if wanted:
                return wanted

    # Fallback list if registry is unavailable
    return [
        "Salesforce/blip-image-captioning-base",
        "nlpconnect/vit-gpt2-image-captioning",
        "openai/clip-vit-base-patch16",
        "facebook/dinov2-base",
        "sentence-transformers/all-MiniLM-L6-v2",
        "laion/clap-htsat-unfused",
        "pyannote/speaker-diarization",
        "openai/whisper-large-v3",
        "Systran/faster-whisper-large-v3",
        "Systran/faster-whisper-medium",
        "Systran/faster-whisper-tiny",
        "superb/hubert-large-superb-er",
        "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    ]


def resolve_models_root() -> Path:
    explicit = os.environ.get("GOODQ_MODELS_DIR")
    if explicit:
        return Path(explicit)
    try:
        from steps.common.config_loader import load_configs

        cfg = load_configs({})
        models_cache = (((cfg.get("paths", {}) or {}).get("models_cache")) or "").strip()
        if models_cache:
            return Path(models_cache)
    except Exception:
        pass
    fallback_data_root = os.environ.get("GOODQ_DATA_ROOT")
    if fallback_data_root:
        return Path(fallback_data_root) / "models"
    return Path("models")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prefetch local model cache for GoodQ bootstrap")
    parser.add_argument("--report-path", help="Write machine-readable JSON report to this path")
    parser.add_argument("--retries", type=int, default=_default_retry_count(), help="Retries for transient download failures")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # Resolve project root (scripts/..)
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    if load_dotenv:  # load project-level .env if available
        env_file = repo_root / ".env.local"
        if env_file.exists():
            load_dotenv(env_file)
    models_root = resolve_models_root()
    ensure_env(models_root)

    auth = resolve_auth_tokens()
    hf_token = auth["hf_token"] if isinstance(auth["hf_token"], str) else None
    pyannote_token = auth["pyannote_token"] if isinstance(auth["pyannote_token"], str) else None
    if auth["hf_present"]:
        _log(f"[bootstrap] Hugging Face auth detected via {auth['hf_source']}")
    else:
        _log("[bootstrap] Hugging Face auth not detected in .env.local or environment")
    if auth["pyannote_present"]:
        _log(f"[bootstrap] PyAnnote auth detected via {auth['pyannote_source']}")
    else:
        _log("[bootstrap] PyAnnote auth not detected; gated diarization downloads may be skipped")

    # Load registry for pinned versions
    registry = load_registry(repo_root)
    pinned_models = {}
    
    if registry and 'huggingface_models' in registry:
        print("[bootstrap] Using model_registry.yaml for version pinning")
        for model_key, model_info in registry['huggingface_models'].items():
            repo_id = model_info.get('repo_id')
            revision = model_info.get('revision')
            if repo_id and revision:
                pinned_models[repo_id] = revision
    else:
        print("[bootstrap] WARNING: model_registry.yaml not found, using latest versions")

    wanted = build_wanted_models(registry)

    results: List[Dict[str, str]] = []
    total_assets = len(wanted) + 1
    _log(f"[bootstrap] Prefetching {total_assets} model assets into {models_root}")
    for index, mid in enumerate(wanted, start=1):
        # Strip any existing @revision
        repo_id = mid.split('@')[0] if '@' in mid else mid
        
        # Use pinned revision if available
        revision = pinned_models.get(repo_id)
        
        # Determine auth token
        token = pyannote_token if repo_id.startswith('pyannote/') else hf_token
        
        # Download with pinned revision
        result = snapshot(
            mid,
            token,
            revision,
            models_root=models_root,
            retries=args.retries,
            progress_label=f"{index}/{total_assets}",
        )
        if revision:
            result['pinned_revision'] = revision
        results.append(result)

    results.append(download_yolo_n(retries=args.retries, progress_label=f"{total_assets}/{total_assets}"))

    report_path = Path(args.report_path) if args.report_path else repo_root / "logs" / "bootstrap_models_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "models_dir": str(models_root),
        "registry_loaded": registry is not None,
        "pinned_models_count": len(pinned_models),
        "download_retries": args.retries,
        "env": {
            "HF_HOME": os.environ.get("HF_HOME"),
            "TORCH_HOME": os.environ.get("TORCH_HOME"),
            "hf_auth_present": bool(auth["hf_present"]),
            "hf_auth_source": auth["hf_source"],
            "pyannote_auth_present": bool(auth["pyannote_present"]),
            "pyannote_auth_source": auth["pyannote_source"],
        },
        "results": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"[bootstrap] Wrote model prefetch report to {report_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
