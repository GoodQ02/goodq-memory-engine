from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List

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

try:
    from scripts.wsl_audio_preflight import WSL_DIARIZATION_MODEL_REPOS
except Exception:  # pragma: no cover
    from wsl_audio_preflight import WSL_DIARIZATION_MODEL_REPOS


DEFAULT_DOWNLOAD_RETRIES = 4
YOLO_URL = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
_HF_TOKEN_CANDIDATES = ("HF_TOKEN", "HF_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")
_PLACEHOLDER_TOKENS = {
    "your_huggingface_token_here",
    "your_pyannote_token_here",
    "your_token_here",
    "changeme",
}


def redact_sensitive_info(text: str) -> str:
    if not text:
        return text
    for key in ("HF_TOKEN", "HF_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN", "PYANNOTE_TOKEN"):
        val = os.environ.get(key)
        if val and len(val) > 5 and val in text:
            text = text.replace(val, "<REDACTED>")
    import re
    hf_pat = re.compile(r"hf_[a-zA-Z0-9]+")
    text = hf_pat.sub("hf_***", text)
    return text


def _log(msg: str) -> None:
    print(redact_sensitive_info(msg), file=sys.stderr, flush=True)


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def _clean_token(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().strip('"').strip("'")
    if not value:
        return None
    if value.lower() in _PLACEHOLDER_TOKENS:
        return None
    return value


def _load_env_file_values(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def _resolve_env_token(*names: str) -> tuple[str | None, str | None]:
    for name in names:
        token = _clean_token(os.environ.get(name))
        if token:
            return token, name
    return None, None


def _resolve_preferred_token(
    env_file_values: Dict[str, str],
    *names: str,
) -> tuple[str | None, str | None]:
    if any(name in env_file_values for name in names):
        for name in names:
            token = _clean_token(env_file_values.get(name))
            if token:
                return token, name
        return None, None
    return _resolve_env_token(*names)


def resolve_auth_tokens(env_file_values: Dict[str, str] | None = None) -> Dict[str, str | bool | None]:
    if env_file_values is not None:
        env_values = env_file_values
    else:
        repo_env = _load_env_file_values(_REPO_ROOT / ".env.local")
        models_env = {}
        try:
            models_root = resolve_models_root()
            if models_root:
                models_env = _load_env_file_values(models_root.parent / ".env.local")
        except Exception:
            pass
        env_values = {}
        env_values.update(repo_env)
        env_values.update(models_env)

    hf_token, hf_source = _resolve_preferred_token(env_values, *_HF_TOKEN_CANDIDATES)
    pyannote_token, pyannote_source = _resolve_preferred_token(env_values, "PYANNOTE_TOKEN")
    if not pyannote_token:
        pyannote_token = hf_token
        pyannote_source = hf_source

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ["HF_HUB_TOKEN"] = hf_token
        os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token
        os.environ["HUGGINGFACE_TOKEN"] = hf_token
    if pyannote_token:
        os.environ["PYANNOTE_TOKEN"] = pyannote_token

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


def _normalize_main_ref_for_pinned_snapshot(
    models_root: Path,
    repo_id: str,
    requested_revision: str | None,
    resolved_dir: str,
) -> None:
    if not requested_revision:
        return
    resolved_path = Path(resolved_dir)
    resolved_revision = resolved_path.name if resolved_path.parent.name == "snapshots" else requested_revision
    if not resolved_revision:
        return
    refs_dir = _repo_cache_dir(models_root, repo_id) / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "main").write_bytes(resolved_revision.encode("utf-8"))


def _build_report(
    *,
    models_root: Path,
    registry_loaded: bool,
    pinned_models_count: int,
    retries: int,
    auth: Dict[str, str | bool | None],
    results: List[Dict[str, Any]],
    status: str,
    progress_path: Path,
    current_model: str | None = None,
    fatal_error: str | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "models_dir": str(models_root),
        "registry_loaded": registry_loaded,
        "pinned_models_count": pinned_models_count,
        "download_retries": retries,
        "status": status,
        "completed_count": len(results),
        "current_model": current_model,
        "progress_path": str(progress_path),
        "updated_at": time.time(),
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
    if fatal_error:
        payload["fatal_error"] = fatal_error
    return payload


def snapshot(
    model_id: str,
    auth_token: str | None = None,
    revision: str | None = None,
    *,
    models_root: Path | None = None,
    retries: int = DEFAULT_DOWNLOAD_RETRIES,
    progress_label: str = "",
    progress_cb: Callable[..., None] | None = None,
) -> Dict[str, str]:
    """
    Download a model snapshot from HuggingFace Hub via ensure_model_cached.
    """
    repo_id = model_id
    if '@' in model_id and revision is None:
        repo_id, revision = model_id.split('@', 1)

    if auth_token:
        os.environ["HF_TOKEN"] = auth_token

    label = f"[bootstrap] [{progress_label}] " if progress_label else "[bootstrap] "
    _log(f"{label}syncing {repo_id} via ensure_model_cached")
    
    started = time.time()
    if progress_cb:
        progress_cb(current_attempt=1, last_event="snapshot_download_started")
        
    from steps.common.model_provisioner import ensure_model_cached
    
    # We run ensure_model_cached with offline=False to trigger download if missing
    res = ensure_model_cached(repo_id, revision=revision, offline=False)
    
    elapsed_sec = round(time.time() - started, 1)
    
    if res.status in ("cached", "downloaded"):
        if progress_cb:
            progress_cb(current_attempt=getattr(res, "attempts_made", 1), last_event="snapshot_ready")
        _log(f"{label}ready {repo_id} ({elapsed_sec:.1f}s)")
        return {
            "model": model_id,
            "status": "ok",
            "path": res.local_path,
            "revision": res.revision or "default",
            "attempts": str(getattr(res, "attempts_made", 1)),
            "cache_verified": "true",
            "elapsed_sec": elapsed_sec,
        }
    else:
        if progress_cb:
            progress_cb(current_attempt=getattr(res, "attempts_made", 1), last_event="snapshot_error", last_error=res.error)
        return {
            "model": model_id,
            "status": "error",
            "error": res.error or "provisioning failed",
            "attempts": str(getattr(res, "attempts_made", 1))
        }


def download_yolo_n(
    *,
    retries: int = DEFAULT_DOWNLOAD_RETRIES,
    progress_label: str = "",
    progress_cb: Callable[..., None] | None = None,
) -> Dict[str, str]:
    # Ultralytics yolov8n.pt hosted in GH assets; cache into models/yolo
    target = Path(os.environ.get("TORCH_HOME") or os.environ.get("HF_HOME") or ".") / "yolo" / "yolov8n.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 1024 * 1024:
        return {"asset": "yolov8n.pt", "status": "ok", "path": str(target), "cached": "true"}
    attempts = max(int(retries), 1)
    label = f"[bootstrap] [{progress_label}] " if progress_label else "[bootstrap] "
    temp_target = target.with_suffix(".tmp")
    for attempt in range(1, attempts + 1):
        started = time.time()
        try:
            if progress_cb:
                progress_cb(current_attempt=attempt, last_event="asset_download_started")
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
                            if progress_cb:
                                progress_cb(current_attempt=attempt, last_event=f"asset_download_{next_marker}pct")
                            _log(f"{label}yolov8n.pt {next_marker}%")
                            next_marker += 25
            os.replace(temp_target, target)
            elapsed_sec = round(time.time() - started, 1)
            if progress_cb:
                progress_cb(current_attempt=attempt, last_event="asset_ready")
            _log(f"{label}ready yolov8n.pt ({elapsed_sec:.1f}s)")
            return {"asset": "yolov8n.pt", "status": "ok", "path": str(target), "cached": "false", "attempts": str(attempt), "elapsed_sec": elapsed_sec}
        except Exception as exc:  # pragma: no cover
            detail = str(exc)
            try:
                temp_target.unlink(missing_ok=True)
            except Exception:
                pass
            if attempt < attempts and _is_transient_download_error(detail):
                if progress_cb:
                    progress_cb(current_attempt=attempt, last_event="transient_retry", last_error=detail)
                _log(f"{label}transient failure for yolov8n.pt: {detail}. Retrying...")
                _retry_pause(attempt)
                continue
            if progress_cb:
                progress_cb(current_attempt=attempt, last_event="asset_error", last_error=detail)
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
        *WSL_DIARIZATION_MODEL_REPOS,
        "openai/whisper-large-v3",
        "Systran/faster-whisper-large-v3",
        "Systran/faster-whisper-medium",
        "Systran/faster-whisper-tiny",
        "superb/hubert-large-superb-er",
        "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
        "facebook/wav2vec2-base-960h",
        "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest",
        "distilbert-base-uncased-finetuned-sst-2-english",
        "snakers4/silero-vad",
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


def _is_log_dir_writable(path: Path) -> bool:
    try:
        p = Path(path)
        # Find the closest parent that exists
        while not p.exists() and p != p.parent:
            p = p.parent
        if not p.exists():
            return False
        # Try to write a temp file
        test_file = p / f".tmp_write_test_{os.getpid()}"
        try:
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            return True
        except Exception:
            return False
    except Exception:
        return False


def _is_under_program_files(path: Path) -> bool:
    try:
        path_str = str(Path(path).resolve()).lower()
        if "program files" in path_str or "programfiles" in path_str:
            return True
        for env_var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            val = os.environ.get(env_var)
            if val:
                p_val = Path(val).resolve()
                res_path = Path(path).resolve()
                if p_val in res_path.parents or res_path == p_val:
                    return True
    except Exception:
        pass
    return False


def resolve_bootstrap_log_dir(repo_root: Path) -> Path:
    # 1. Explicit CLI paths: if `--report-path` or `--progress-path` are provided, use their directories.
    report_path_cli = None
    progress_path_cli = None
    try:
        for idx, arg in enumerate(sys.argv):
            if arg == "--report-path" and idx + 1 < len(sys.argv):
                report_path_cli = sys.argv[idx + 1]
            elif arg.startswith("--report-path="):
                report_path_cli = arg.split("=", 1)[1]
            elif arg == "--progress-path" and idx + 1 < len(sys.argv):
                progress_path_cli = sys.argv[idx + 1]
            elif arg.startswith("--progress-path="):
                progress_path_cli = arg.split("=", 1)[1]
    except Exception:
        pass

    if report_path_cli:
        return Path(report_path_cli).parent
    if progress_path_cli:
        return Path(progress_path_cli).parent

    # 2. GOODQ_DATA_ROOT\logs (if the GOODQ_DATA_ROOT env var is set and writable).
    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        candidate = Path(data_root) / "logs"
        if not _is_under_program_files(candidate) and _is_log_dir_writable(candidate):
            return candidate

    # 3. C:\ProgramData\GoodQ4All\logs (if writable).
    candidate = Path("C:/ProgramData/GoodQ4All/logs")
    if not _is_under_program_files(candidate) and _is_log_dir_writable(candidate):
        return candidate

    # 4. %LOCALAPPDATA%\GoodQ4All\logs (as the final user-writable fallback, using os.getenv("LOCALAPPDATA") or similar).
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        candidate = Path(local_appdata) / "GoodQ4All" / "logs"
        if not _is_under_program_files(candidate) and _is_log_dir_writable(candidate):
            return candidate

    # 5. repo_root\logs (ONLY when bootstrap detects dev/source-tree mode; i.e., repo_root is NOT under Program Files or Program Files (x86)).
    if not _is_under_program_files(repo_root):
        candidate = repo_root / "logs"
        if _is_log_dir_writable(candidate):
            return candidate

    # Fallback in case of absolute failure
    temp_dir = os.getenv("TEMP") or os.getenv("TMP")
    if temp_dir:
        candidate = Path(temp_dir) / "GoodQ4All" / "logs"
        if not _is_under_program_files(candidate) and _is_log_dir_writable(candidate):
            return candidate

    fallback = Path(os.path.expanduser("~")) / "GoodQ4All" / "logs"
    if not _is_under_program_files(fallback):
        return fallback

    import tempfile
    return Path(tempfile.gettempdir()) / "GoodQ4All" / "logs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prefetch local model cache for GoodQ bootstrap")
    parser.add_argument("--report-path", help="Write machine-readable JSON report to this path")
    parser.add_argument("--progress-path", help="Write machine-readable progress JSON to this path")
    parser.add_argument("--retries", type=int, default=_default_retry_count(), help="Retries for transient download failures")
    parser.add_argument("--first-launch", "--open-only", dest="first_launch", action="store_true", help="Only filter and download required non-gated models")
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

    from steps.common.model_provisioner import log_download_event, lookup_model, _FALLBACK_REGISTRY
    
    log_download_event(f"Bootstrap models started. First launch mode: {getattr(args, 'first_launch', False)}")

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

    # Filter wanted models if first launch is active
    if getattr(args, "first_launch", False):
        filtered_wanted = []
        for mid in wanted:
            repo_id = mid.split('@')[0] if '@' in mid else mid
            resolved_repo_id, metadata = lookup_model(repo_id)
            if resolved_repo_id:
                is_gated = metadata.get("gated", False)
                is_required = metadata.get("required", True)
                if is_required and not is_gated:
                    filtered_wanted.append(mid)
            else:
                fb = _FALLBACK_REGISTRY.get(repo_id)
                if fb:
                    is_gated = fb.get("gated", False)
                    is_required = fb.get("required", True)
                    if is_required and not is_gated:
                        filtered_wanted.append(mid)
        wanted = filtered_wanted

    # Print a list of models and their metadata first
    _log("[bootstrap] --- PRE-DOWNLOAD MODEL LIST ---")
    for mid in wanted:
        repo_id = mid.split('@')[0] if '@' in mid else mid
        _, metadata = lookup_model(repo_id)
        _log(f"Model: {repo_id} | Revision: {metadata.get('revision') or 'default'} | Gated: {metadata.get('gated', False)} | Required: {metadata.get('required', True)}")
    _log("Model: yolov8n.pt | Source: GitHub | Gated: False | Required: True")
    _log("[bootstrap] --------------------------------")

    log_dir = resolve_bootstrap_log_dir(repo_root)
    log_dir.mkdir(parents=True, exist_ok=True)

    report_path = Path(args.report_path) if args.report_path else log_dir / "bootstrap_models_report.json"
    progress_path = Path(args.progress_path) if args.progress_path else log_dir / "bootstrap_models_progress.json"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    total_assets = len(wanted) + 1
    progress_state: Dict[str, Any] = {
        "status": "in_progress",
        "models_dir": str(models_root),
        "current_model": None,
        "current_index": 0,
        "total_assets": total_assets,
        "current_attempt": None,
        "started_at": time.time(),
        "last_progress_at": time.time(),
        "last_event": "bootstrap_started",
        "completed_count": 0,
        "report_path": str(report_path),
    }

    def emit_progress(**updates: Any) -> None:
        progress_state.update(updates)
        progress_state["last_progress_at"] = time.time()
        _write_json_atomic(progress_path, progress_state)

    def write_report(status: str, *, current_model: str | None = None, fatal_error: str | None = None) -> None:
        _write_json_atomic(
            report_path,
            _build_report(
                models_root=models_root,
                registry_loaded=registry is not None,
                pinned_models_count=len(pinned_models),
                retries=args.retries,
                auth=auth,
                results=results,
                status=status,
                progress_path=progress_path,
                current_model=current_model,
                fatal_error=fatal_error,
            ),
        )

    emit_progress()
    write_report("in_progress")
    _log(f"[bootstrap] Prefetching {total_assets} model assets into {models_root}")
    try:
        for index, mid in enumerate(wanted, start=1):
            repo_id = mid.split('@')[0] if '@' in mid else mid
            revision = pinned_models.get(repo_id)
            token = pyannote_token if repo_id.startswith('pyannote/') else hf_token

            emit_progress(
                current_model=repo_id,
                current_index=index,
                current_attempt=1,
                last_event="model_started",
                completed_count=len(results),
            )
            result = snapshot(
                mid,
                token,
                revision,
                models_root=models_root,
                retries=args.retries,
                progress_label=f"{index}/{total_assets}",
                progress_cb=emit_progress,
            )
            if revision:
                result["pinned_revision"] = revision
            results.append(result)
            emit_progress(
                current_model=repo_id,
                current_index=index,
                current_attempt=result.get("attempts"),
                last_event="model_completed",
                completed_count=len(results),
            )
            write_report("in_progress", current_model=repo_id)

        emit_progress(
            current_model="yolov8n.pt",
            current_index=total_assets,
            current_attempt=1,
            last_event="asset_started",
            completed_count=len(results),
        )
        results.append(
            download_yolo_n(
                retries=args.retries,
                progress_label=f"{total_assets}/{total_assets}",
                progress_cb=emit_progress,
            )
        )
        emit_progress(
            current_model="yolov8n.pt",
            current_index=total_assets,
            current_attempt=results[-1].get("attempts"),
            last_event="asset_completed",
            completed_count=len(results),
        )
        write_report("complete", current_model=None)
        emit_progress(
            status="complete",
            current_model=None,
            current_attempt=None,
            current_index=total_assets,
            last_event="bootstrap_complete",
            completed_count=len(results),
        )
        log_download_event("Bootstrap models completed successfully.")
    except KeyboardInterrupt:
        emit_progress(
            status="interrupted",
            last_event="keyboard_interrupt",
            completed_count=len(results),
        )
        write_report("interrupted", current_model=str(progress_state.get("current_model") or ""), fatal_error="KeyboardInterrupt")
        log_download_event("Bootstrap models interrupted by user.")
        raise
    except Exception as exc:
        exc_str = redact_sensitive_info(str(exc))
        emit_progress(
            status="failed",
            last_event="fatal_error",
            last_error=exc_str,
            completed_count=len(results),
        )
        write_report("failed", current_model=str(progress_state.get("current_model") or ""), fatal_error=exc_str)
        log_download_event(f"Bootstrap models failed: {exc_str}")
        raise

    final_report = json.loads(report_path.read_text(encoding="utf-8"))
    _log(f"[bootstrap] Wrote model prefetch report to {report_path}")
    print(json.dumps(final_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
