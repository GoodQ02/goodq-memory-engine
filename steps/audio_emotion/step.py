from __future__ import annotations

# GPU Configuration - Auto-configured on import
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats


from typing import Any, Dict, List
from pathlib import Path

import os


_AEMO: Dict[str, Any] = {"pipe": None, "device": "cpu", "model_id": None}
HF_HOME = Path(os.environ.get("HF_HOME", "L:/models"))
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("TORCH_HOME", os.environ.get("TORCH_HOME") or str(HF_HOME))
# Disable hf_transfer to avoid dependency issues
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"


def _cache_snapshot_exists(model_id: str) -> bool:
    repo_id, _, _ = model_id.partition("@")
    safe_repo = repo_id.replace("/", "--")
    hub_root = HF_HOME / "hub"
    base_dir = hub_root / f"models--{safe_repo}"
    if not base_dir.exists():
        return False
    snapshots_dir = base_dir / "snapshots"
    if not snapshots_dir.exists():
        return False
    for snapshot in snapshots_dir.iterdir():
        if snapshot.is_dir() and any(snapshot.iterdir()):
            return True
    return False


def _load() -> None:
    if _AEMO["pipe"] is not None:
        return
    try:
        import torch  # type: ignore
        from transformers import pipeline  # type: ignore
    except Exception as exc:
        _AEMO.update({"pipe": None, "model_id": None, "error": str(exc)})
        return

    device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
    candidates = [
        "superb/hubert-large-superb-er",
        "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    ]
    errors: Dict[str, str] = {}
    for model_id in candidates:
        if not _cache_snapshot_exists(model_id):
            errors[model_id] = f"cache_missing:{HF_HOME}"
            continue
        try:
            # Use the correct pipeline - these are audio-classification models, not CLAP
            pipe = pipeline(
                "audio-classification",
                model=model_id,
                device=0 if device == "cuda" else -1,
            )
            _AEMO.update({"pipe": pipe, "device": device, "model_id": model_id, "error": None})
            return
        except Exception as err:
            errors[model_id] = str(err)
            continue
    _AEMO.update({"pipe": None, "model_id": None, "error": errors})


def audio_emotion(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"audio_emotion": None, "audio_emotion_meta": {"status": "no_file"}}

    _load()
    if _AEMO.get("pipe") is None:
        error_detail = _AEMO.get("error")
        if isinstance(error_detail, dict):
            error_detail = "; ".join(f"{k}: {v}" for k, v in error_detail.items())
        return {"audio_emotion": None, "audio_emotion_meta": {"status": "unavailable", "error": error_detail}}

    try:
        import librosa  # type: ignore
        
        # VAD Preprocessing - filter silence before emotion detection
        vad_enabled = cfg.get("vad_enabled", True)
        audio_path_to_use = path
        
        if vad_enabled:
            try:
                from steps.common.vad_preprocessor import preprocess_audio_with_vad
                print(f"[AUDIO_EMOTION] Running VAD preprocessing on {path}")
                
                vad_path, vad_segments = preprocess_audio_with_vad(
                    path,
                    threshold=0.5,
                    min_speech_duration_ms=400,
                    min_silence_duration_ms=200,
                    extract_to_file=True
                )
                
                if vad_path and vad_segments:
                    audio_path_to_use = vad_path
                    print(f"[AUDIO_EMOTION] Using VAD-filtered audio ({len(vad_segments)} segments)")
                else:
                    print(f"[AUDIO_EMOTION] VAD found no speech, using original audio")
            except Exception as vad_exc:
                print(f"[AUDIO_EMOTION] VAD failed: {vad_exc}, using original audio")
        
        wave, _ = librosa.load(audio_path_to_use, sr=16000, mono=True)
        result: List[Dict[str, Any]] = _AEMO["pipe"]({"array": wave, "sampling_rate": 16000})  # type: ignore
        top = [
            {"label": str(entry.get("label", "")), "score": float(entry.get("score", 0.0))}
            for entry in (result or [])
        ][:5]
        # Status is "ok" only if we got results, otherwise "failed"
        status = "ok" if top else "failed"
        meta = {"status": status, "model": _AEMO.get("model_id"), "device": _AEMO.get("device")}
        if not top:
            print(f'[WARN] audio_emotion: No emotions detected in {path}')
        return {"audio_emotion": top, "audio_emotion_meta": meta}
    except Exception as exc:
        return {"audio_emotion": None, "audio_emotion_meta": {"status": "error", "error": str(exc)}}
