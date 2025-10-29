from __future__ import annotations
import csv
import json
import os
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import GoodQ mission logger
try:
    from lib.goodq_logger import get_goodq_logger
    from lib.mission_components import get_component_name, format_duration
    MISSION_LOGGER_AVAILABLE = True
except ImportError:
    MISSION_LOGGER_AVAILABLE = False
    get_goodq_logger = None
    get_component_name = None
    format_duration = None


def _fingerprint_item(item: Optional[Dict[str, Any]]) -> str:
    try:
        if not item:
            return ""
        sp = item.get("source_path") if isinstance(item, dict) else None  # type: ignore[assignment]
        h = hashlib.sha256()
        if isinstance(sp, str) and os.path.isfile(sp):
            with open(sp, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        h.update(repr(item).encode("utf-8", errors="ignore"))
        return h.hexdigest()
    except Exception as e:
        return ""


_GPU_LIKELY_STEPS = {
    "image_caption",
    "image_embed_dino",
    "image_embed_clip",
    "face_embed",
    "object_detect",
    "audio_diarize",
    "audio_transcribe",
    "audio_emotion",
    "audio_embed_clap",
}


def log_step_run(
    cfg: Dict[str, Any],
    step_name: str,
    item: Optional[Dict[str, Any]],
    duration_ms: float,
    status: str,
    error: Optional[str] = None,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log step execution with Q Branch mission styling
    Maintains CSV/JSONL compatibility while adding mission-styled console output
    """
    # Mission-styled console logging (if available)
    if MISSION_LOGGER_AVAILABLE:
        try:
            component = get_component_name(step_name)
            logger = get_goodq_logger(step_name, component=component)
            
            duration_s = duration_ms / 1000.0
            duration_str = format_duration(duration_s)
            
            if status == "ok":
                logger.mission_complete(step_name, duration=duration_s)
            elif status == "skipped":
                reason = (extra or {}).get('reason', 'unknown')
                logger.info(f"Operation bypassed - {reason} [{duration_str}]")
            elif status == "error":
                logger.error(f"Operation failed - {error[:100] if error else 'Unknown error'} [{duration_str}]")
            else:
                logger.info(f"Status: {status} [{duration_str}]")
        except Exception:
            pass  # Don't let mission logging break actual logging
    
    # Original CSV/JSONL logging (preserved for compatibility)
    try:
        log_dir = (cfg.get("paths", {}) or {}).get("log_dir") or ""
        if not log_dir:
            return
        os.makedirs(log_dir, exist_ok=True)

        path = os.path.join(log_dir, "step_runs.csv")
        is_new = not os.path.isfile(path)
        with open(path, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["ts", "step", "modality", "source_path", "duration_ms", "status", "error"])  # header
            modality = (item or {}).get("modality") if isinstance(item, dict) else None
            source_path = (item or {}).get("source_path") if isinstance(item, dict) else None
            w.writerow([
                datetime.utcnow().isoformat(),
                step_name,
                modality or "",
                source_path or "",
                f"{duration_ms:.2f}",
                status,
                (error or "")[:500],
            ])

        jsonl = os.path.join(log_dir, "step_runs.jsonl")
        try:
            env_name = os.environ.get("CONDA_DEFAULT_ENV") or ""
        except Exception as e:
            env_name = ""

        run_cfg = cfg.get("run") if isinstance(cfg, dict) else None
        if not isinstance(run_cfg, dict):
            run_cfg = {}

        entry: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(),
            "step": step_name,
            "duration_ms": float(f"{duration_ms:.3f}"),
            "status": status,
            "error": (error or "")[:2000],
            "env": env_name,
            "modality": (item or {}).get("modality") if isinstance(item, dict) else None,
            "source_path": (item or {}).get("source_path") if isinstance(item, dict) else None,
            "item_hash": _fingerprint_item(item),
            "run_id": run_cfg.get("id"),
            "pipeline": run_cfg.get("pipeline"),
            "timer_unit": run_cfg.get("timer_unit", "ms"),
        }

        if run_cfg.get("started_at"):
            entry["run_started_at"] = run_cfg.get("started_at")
        if run_cfg.get("git_sha"):
            entry["git_sha"] = run_cfg.get("git_sha")
        if run_cfg.get("device"):
            entry["device"] = run_cfg.get("device")
        if run_cfg.get("dtype"):
            entry["dtype"] = run_cfg.get("dtype")

        if isinstance(item, dict):
            for key in ("video_id", "video_hash", "scene_id", "scene_index", "model_signature"):
                if key in item:
                    entry[key] = item.get(key)

        if extra and isinstance(extra, dict):
            entry["extra"] = extra

        flags: List[str] = []
        if status == "ok" and duration_ms < 5.0 and step_name in _GPU_LIKELY_STEPS:
            flags.append("improbable_duration")
        if flags:
            entry["flags"] = flags

        with open(jsonl, "a", encoding="utf-8") as jf:
            jf.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f'[ERROR] Exception in step_logger.py line 124: {str(e)}')
        return
