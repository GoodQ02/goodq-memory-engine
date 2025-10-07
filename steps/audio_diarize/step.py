from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import os


_PIPELINES: Dict[Tuple[str, str], Any] = {}


def _resolve_device() -> str:
    try:
        import torch  # type: ignore

        return "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _load_pipeline(model_id: str, device: str, auth_token: Optional[str]):
    key = (model_id, device)
    if key in _PIPELINES:
        return _PIPELINES[key]
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except Exception:
        _PIPELINES[key] = None
        return None
    try:
        pipeline = Pipeline.from_pretrained(model_id, use_auth_token=auth_token)
        if device == "cuda":
            try:
                pipeline.to("cuda")
            except Exception:
                pass
        _PIPELINES[key] = pipeline
    except Exception:
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
    except Exception:
        return []
    segments.sort(key=lambda s: s.get("start", 0.0))
    return segments


def audio_diarize(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Speaker diarization via PyAnnote pipeline."""
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"diarization": None, "diarize_meta": {"status": "no_file"}}

    cfg_audio = (cfg.get("audio", {}) or {})
    dz_cfg = (cfg_audio.get("diarization", {}) or {})
    token_env = str(dz_cfg.get("token_env") or "PYANNOTE_TOKEN")
    model_id = str(dz_cfg.get("model") or "pyannote/speaker-diarization@2.1")

    auth_token = os.getenv(token_env) or os.getenv("PYANNOTE_AUDIO_AUTH") or os.getenv("HF_TOKEN")
    if not auth_token:
        return {"diarization": None, "diarize_meta": {"status": "unavailable", "engine": "pyannote", "reason": "no_auth"}}

    device = _resolve_device()
    pipeline = _load_pipeline(model_id, device, auth_token)
    if pipeline is None:
        return {"diarization": None, "diarize_meta": {"status": "unavailable", "engine": "pyannote"}}

    try:
        diarization = pipeline(path)
        segments = _format_segments(diarization)
        if not segments:
            return {"diarization": None, "diarize_meta": {"status": "empty", "engine": "pyannote"}}
        meta = {
            "status": "ok",
            "engine": "pyannote",
            "model": model_id,
            "device": device,
            "segment_count": len(segments),
        }
        return {"diarization": segments, "diarize_meta": meta}
    except Exception as exc:
        return {"diarization": None, "diarize_meta": {"status": "error", "engine": "pyannote", "error": str(exc)}}
