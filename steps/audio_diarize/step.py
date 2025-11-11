from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import os


_PIPELINES: Dict[Tuple[str, str], Any] = {}


def _resolve_device() -> str:
    try:
        import torch  # type: ignore

        return "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
    except Exception as e:
        return "cpu"


def _load_pipeline(model_id: str, device: str, auth_token: Optional[str]):
    key = (model_id, device)
    if key in _PIPELINES:
        return _PIPELINES[key]
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except Exception as e:
        _PIPELINES[key] = None
        print(f'[WARN] _load_pipeline returning None')
        return None
    try:
        pipeline = Pipeline.from_pretrained(model_id, use_auth_token=auth_token)
        if device == "cuda":
            try:
                pipeline.to("cuda")
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 34: {str(e)}')
                pass
        _PIPELINES[key] = pipeline
    except Exception as e:
        _PIPELINES[key] = None
    return _PIPELINES[key]


def _format_segments(diarization) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    if diarization is None:
        return segments
    try:
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            start = float(getattr(turn, "start", 0.0) or 0.0)
            end = float(getattr(turn, "end", 0.0) or 0.0)
            segments.append({
                "start": max(0.0, start),
                "end": max(start, end),
                "speaker": str(speaker),
            })
    except Exception as e:
        return []
    segments.sort(key=lambda s: s.get("start", 0.0))
    return segments


def audio_diarize(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Speaker diarization via PyAnnote pipeline."""
    import time
    
    # Import progress tracker
    try:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
    except:
        tracker = None
    
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"diarization": None, "diarize_meta": {"status": "no_file"}}

    # Check if diarization is enabled
    cfg_audio = (cfg.get("audio", {}) or {})
    dz_cfg = (cfg_audio.get("diarization", {}) or {})
    
    if not dz_cfg.get("enabled", True):
        print("[INFO] Diarization disabled in config, skipping")
        return {"diarization": None, "diarize_meta": {"status": "disabled"}}
    
    token_env = str(dz_cfg.get("token_env") or "PYANNOTE_TOKEN")
    model_id = str(dz_cfg.get("model") or "pyannote/speaker-diarization@2.1")

    auth_token = os.getenv(token_env) or os.getenv("PYANNOTE_AUDIO_AUTH") or os.getenv("HF_TOKEN")
    if not auth_token:
        print("[WARN] No PyAnnote auth token found, skipping diarization")
        return {"diarization": None, "diarize_meta": {"status": "unavailable", "engine": "pyannote", "reason": "no_auth"}}

    device = _resolve_device()
    pipeline = _load_pipeline(model_id, device, auth_token)
    if pipeline is None:
        print("[WARN] Failed to load PyAnnote pipeline, skipping diarization")
        return {"diarization": None, "diarize_meta": {"status": "unavailable", "engine": "pyannote"}}

    try:
        # Get audio duration to estimate processing time
        file_size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"[DIARIZE] Starting diarization for {os.path.basename(path)} ({file_size_mb:.1f}MB) on {device}")
        
        # Update progress
        if tracker:
            tracker.update_step("audio_diarize", 5, {"details": f"Analyzing speakers ({file_size_mb:.1f}MB)"})
        
        start_time = time.time()
        diarization = pipeline(path)
        elapsed = time.time() - start_time
        
        print(f"[DIARIZE] Completed in {elapsed:.1f}s")
        
        segments = _format_segments(diarization)
        if not segments:
            print("[DIARIZE] No speakers detected")
            if tracker:
                tracker.add_warning("No speakers detected in audio", "audio_diarize")
            return {"diarization": None, "diarize_meta": {"status": "empty", "engine": "pyannote"}}
        
        print(f"[DIARIZE] Found {len(segments)} speaker segments")
        
        # Update progress with results
        if tracker:
            tracker.complete_step("audio_diarize", {
                "segment_count": len(segments),
                "processing_time": f"{elapsed:.1f}s"
            })
        
        meta = {
            "status": "ok",
            "engine": "pyannote",
            "model": model_id,
            "device": device,
            "segment_count": len(segments),
            "processing_time": elapsed,
        }
        return {"diarization": segments, "diarize_meta": meta}
    except Exception as exc:
        print(f"[ERROR] Diarization failed: {type(exc).__name__}: {str(exc)}")
        if tracker:
            tracker.add_error(f"Diarization failed: {str(exc)}", "audio_diarize")
        return {"diarization": None, "diarize_meta": {"status": "error", "engine": "pyannote", "error": str(exc)}}
