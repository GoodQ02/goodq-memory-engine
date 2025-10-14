from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path

import os


_AEMO: Dict[str, Any] = {"pipe": None, "device": "cpu", "model_id": None}
HF_HOME = Path(os.environ.get("HF_HOME", "L:/models"))
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("TORCH_HOME", os.environ.get("TORCH_HOME") or str(HF_HOME))
if not os.environ.get("HF_HUB_ENABLE_HF_TRANSFER"):
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"


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
        from transformers import pipeline, ClapModel, AutoProcessor  # type: ignore
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
            processor = AutoProcessor.from_pretrained(model_id, local_files_only=True)
            model = ClapModel.from_pretrained(model_id, local_files_only=True)
            model = model.to(device).eval()
            pipe = pipeline(
                "audio-classification",
                model=model,
                feature_extractor=processor,
                framework="pt",
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
        wave, _ = librosa.load(path, sr=16000, mono=True)
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
