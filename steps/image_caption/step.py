"""Scene image description with the sealed WeVisOne-VL-2B vision-language model.

WeVisOne-VL-2B (Qwen3-VL architecture, Apache-2.0) replaced BLIP after meeting
the frozen caption criteria on October 25, 2026
(``tmp/visual-criteria-20261025-001/RESULT.md``). Its descriptions are richer but
are model inference, not observed fact: ``caption_meta.inference_kind`` says so,
and consumers must not promote caption-only claims to confirmed evidence.

The worker runs in the locked ``envs/caption_vlm/.venv`` runtime and loads the
model once per process. Callers pass all sampled frames of a scene in one
``samples`` request so a 9.8 GB model is not reloaded per frame.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.grounding_markup import has_grounding_markup, strip_grounding_markup

logger = logging.getLogger(__name__)

try:
    from scripts.gpu_config import GPUManager, setup_step_gpu
except ImportError as exc:  # pragma: no cover - source-only resilience
    logger.warning("scripts.gpu_config unavailable; using CPU fallback: %s", exc)

    def setup_step_gpu(step_name: str) -> Dict[str, Any]:
        return {"device": "cpu", "step_name": step_name}

    class GPUManager:
        @staticmethod
        def clear_cache() -> None:
            return None

ENGINE = "wevisone-vl"
MODEL_KEY = "wevisone_vl_2b"
MODEL_IDENTITY = ("tencent/WeVisOne-VL-2B", "3dad9ce8bcb6fbe0aea945bf8860bd2cfc3663bf")
# Frozen with the October 25 criteria; changing it requires re-evaluation.
PROMPT = (
    "Describe this scene concisely in one or two factual sentences, "
    "focusing on visible people, setting, and key objects."
)
GENERATION = {"max_new_tokens": 256, "do_sample": False}
_HASHED_ON_LOAD_MAX_BYTES = 64 * 1024 * 1024

_MODEL: Dict[str, Any] = {"model": None, "processor": None, "device": None, "load_seconds": None}

_DEFAULT_BLANK_RGB_STD_MAX_THRESHOLD = 2.0
_DEFAULT_BLANK_P99_P1_THRESHOLD = 5.0


class CaptionUnavailable(RuntimeError):
    """The sealed model, its runtime or the selected device is unavailable."""


def _force_cpu(env: Optional[Dict[str, str]] = None) -> bool:
    active = env if env is not None else os.environ
    return (
        str(active.get("GOODQ_IMAGE_CAPTION_FORCE_CPU", "")).strip() == "1"
        or str(active.get("GOODQ_FORCE_CPU", "")).strip() == "1"
        or str(active.get("GOODQ_NO_AUTO_GPU", "")).strip() == "1"
        or str(active.get("CUDA_VISIBLE_DEVICES", "0")).strip() in {"", "-1"}
        or str(active.get("GOODQ_DEVICE", "")).strip().lower() == "cpu"
    )


def _resolve_model_dir(cfg: Dict[str, Any]) -> Path:
    """Resolve and verify the pinned sealed asset beneath the models root."""
    from steps.common.model_provisioner import load_registry, resolve_models_root

    configured = (cfg.get("paths") or {}).get("models_cache") if isinstance(cfg, dict) else None
    root = (Path(configured) if configured else resolve_models_root()).resolve()
    entry = load_registry().get("huggingface_models", {}).get(MODEL_KEY, {})
    if (entry.get("repo_id"), entry.get("revision")) != MODEL_IDENTITY:
        raise CaptionUnavailable(f"Pinned caption model registry identity does not match: {MODEL_KEY}")
    local = entry.get("local_path")
    if not isinstance(local, str) or Path(local).is_absolute():
        raise CaptionUnavailable(f"Invalid relative caption asset path: {MODEL_KEY}")
    directory = (root / local).resolve()
    if not directory.is_relative_to(root):
        raise CaptionUnavailable("Caption asset escapes the model root")
    files = entry.get("files")
    if not isinstance(files, dict) or "model.safetensors" not in files:
        raise CaptionUnavailable(f"Caption asset hash manifest incomplete: {MODEL_KEY}")
    for name, expected in files.items():
        path = directory / name
        if not path.is_file():
            raise CaptionUnavailable(f"Required local caption file missing: {name}")
        if path.stat().st_size != int(expected["bytes"]):
            raise CaptionUnavailable(f"Local caption file size mismatch: {name}")
        # Full hashes of small files every load; the 9.8 GB weights are hashed
        # at provisioning and size-checked here to keep per-scene startup bounded.
        if int(expected["bytes"]) <= _HASHED_ON_LOAD_MAX_BYTES:
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
                raise CaptionUnavailable(f"Local caption file failed verification: {name}")
    return directory


def _load_model(cfg: Dict[str, Any]) -> bool:
    if _MODEL["model"] is not None:
        return False
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    try:
        import torch  # type: ignore
        from transformers import AutoModelForImageTextToText, AutoProcessor  # type: ignore
    except Exception as exc:
        raise CaptionUnavailable(f"Caption runtime unavailable: {exc}") from exc
    model_dir = _resolve_model_dir(cfg)
    device = "cuda" if (not _force_cpu() and torch.cuda.is_available()) else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    started = time.perf_counter()
    processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForImageTextToText.from_pretrained(
        str(model_dir), dtype=dtype, local_files_only=True
    ).eval().to(device)
    _MODEL.update(model=model, processor=processor, device=device,
                  load_seconds=round(time.perf_counter() - started, 3))
    logger.info("WeVisOne-VL-2B loaded on %s in %.2fs", device, _MODEL["load_seconds"])
    return True


def _describe(img: Any) -> tuple[str, int]:
    import torch  # type: ignore

    processor, model = _MODEL["processor"], _MODEL["model"]
    messages = [{"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": PROMPT}]}]
    inputs = processor.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
    ).to(model.device)
    with torch.inference_mode():
        generated = model.generate(**inputs, **GENERATION)
    new_tokens = generated[:, inputs.input_ids.shape[1]:]
    text = processor.batch_decode(new_tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    return text.strip(), int(new_tokens.shape[1])


def _measure_image_blank_stats(img: Any) -> Optional[Dict[str, float]]:
    """Compute deterministic luminance/channel variance and gradient statistics."""
    try:
        import numpy as np  # type: ignore

        arr = np.asarray(img, dtype=np.float32)
    except Exception:
        return None

    if arr.ndim == 2:
        gray = arr
        rgb_std_max = float(gray.std())
    elif arr.ndim == 3 and arr.shape[2] >= 3:
        rgb = arr[:, :, :3]
        gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        rgb_std_max = float(rgb.std(axis=(0, 1)).max())
    else:
        return None

    if gray.size == 0:
        return None

    p99, p1 = np.percentile(gray, [99, 1])
    dx = float(np.abs(np.diff(gray, axis=1)).mean()) if gray.shape[1] > 1 else 0.0
    dy = float(np.abs(np.diff(gray, axis=0)).mean()) if gray.shape[0] > 1 else 0.0
    return {
        "gray_mean": round(float(gray.mean()), 4),
        "gray_std": round(float(gray.std()), 4),
        "rgb_std_max": round(rgb_std_max, 4),
        "min": round(float(gray.min()), 4),
        "max": round(float(gray.max()), 4),
        "dynamic_range": round(float(gray.max() - gray.min()), 4),
        "p99_p1": round(float(p99 - p1), 4),
        "grad_mean": round(0.5 * (dx + dy), 4),
    }


def _is_blank_or_low_variance_frame(
    image_stats: Optional[Dict[str, float]],
    cfg: Optional[Dict[str, Any]] = None,
) -> bool:
    if not isinstance(image_stats, dict):
        return False
    cap_cfg = (cfg or {}).get("image_caption") if isinstance(cfg, dict) else None
    if not isinstance(cap_cfg, dict):
        cap_cfg = {}
    rgb_std_threshold = float(cap_cfg.get("blank_rgb_std_max_threshold", _DEFAULT_BLANK_RGB_STD_MAX_THRESHOLD))
    p99_p1_threshold = float(cap_cfg.get("blank_p99_p1_threshold", _DEFAULT_BLANK_P99_P1_THRESHOLD))
    rgb_std_max = image_stats.get("rgb_std_max")
    p99_p1 = image_stats.get("p99_p1")
    if rgb_std_max is None or p99_p1 is None:
        return False
    return float(rgb_std_max) < rgb_std_threshold and float(p99_p1) < p99_p1_threshold


def _base_meta(sample: Dict[str, Any]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"engine": ENGINE, "model": MODEL_IDENTITY[0], "model_revision": MODEL_IDENTITY[1]}
    if sample.get("timestamp") is not None:
        meta["sample_timestamp"] = sample.get("timestamp")
    if sample.get("is_midpoint_sample") is not None:
        meta["is_midpoint_sample"] = bool(sample.get("is_midpoint_sample"))
    return meta


def _caption_one(sample: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = sample.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"caption": None, "caption_meta": {**_base_meta(sample), "status": "no_file"}}
    meta = _base_meta(sample)
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as original:
            img = original.convert("RGB")
    except Exception as exc:
        return {"caption": None, "caption_meta": {**meta, "status": "error", "reason": "image_decode_failed", "error": str(exc)}}
    image_stats = _measure_image_blank_stats(img)
    if image_stats is not None:
        meta["image_stats"] = image_stats
    if _is_blank_or_low_variance_frame(image_stats, cfg):
        return {"caption": None, "caption_meta": {**meta, "status": "not_applicable", "reason": "blank_or_low_variance_frame"}}
    try:
        model_loaded_now = _load_model(cfg)
        _log_diagnostics("before_inference", source_path=path, model_loaded_now=model_loaded_now)
        started = time.perf_counter()
        text, tokens = _describe(img)
        _log_diagnostics("after_inference", source_path=path, model_loaded_now=model_loaded_now)
    except CaptionUnavailable as exc:
        return {"caption": None, "caption_meta": {**meta, "status": "unavailable", "error": str(exc)}}
    except Exception as exc:
        logger.exception("image_caption failed")
        GPUManager.clear_cache()
        return {"caption": None, "caption_meta": {**meta, "status": "error", "error": str(exc), "exc_type": type(exc).__name__}}
    meta.update(
        status="ok" if text else "no_text",
        device=_MODEL["device"],
        prompt=PROMPT,
        generation=dict(GENERATION),
        generated_tokens=tokens,
        inference_kind="model_generated_description",
        duration_seconds=round(time.perf_counter() - started, 3),
        model_loaded_now=model_loaded_now,
    )
    if model_loaded_now:
        meta["model_load_seconds"] = _MODEL["load_seconds"]
    if has_grounding_markup(text):
        # Keep the described phrase; box coordinates are not user-facing evidence.
        text = strip_grounding_markup(text)
        meta["grounding_markup_removed"] = True
        meta["status"] = "ok" if text else "no_text"
    return {"caption": text or None, "caption_meta": meta}


def _log_diagnostics(stage: str, *, source_path: str, model_loaded_now: bool) -> None:
    payload = {
        "event": "image_caption_diagnostics",
        "stage": stage,
        "source_path": source_path,
        "model_loaded_now": model_loaded_now,
        "engine": ENGINE,
        "model": MODEL_IDENTITY[0],
        "device": _MODEL["device"],
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)
    logger.info("image_caption diagnostics %s", payload)


def _summarize_batch_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {"caption": None, "caption_meta": {"engine": ENGINE, "model": MODEL_IDENTITY[0], "model_revision": MODEL_IDENTITY[1], "status": "no_file"}}
    ok_rows = [r for r in results if isinstance(r.get("caption_meta"), dict) and r["caption_meta"].get("status") == "ok" and r.get("caption")]
    if ok_rows:
        primary = next((r for r in ok_rows if r["caption_meta"].get("is_midpoint_sample") is True), ok_rows[0])
        return {"caption": primary.get("caption"), "caption_meta": dict(primary["caption_meta"])}
    err_rows = [r for r in results if isinstance(r.get("caption_meta"), dict) and r["caption_meta"].get("status") in {"error", "unavailable"}]
    if err_rows:
        return {"caption": None, "caption_meta": dict(err_rows[0]["caption_meta"])}
    mid = next((r for r in results if isinstance(r.get("caption_meta"), dict) and r["caption_meta"].get("is_midpoint_sample") is True), results[0])
    return {"caption": mid.get("caption"), "caption_meta": dict(mid.get("caption_meta") or {"engine": ENGINE, "status": "no_text"})}


def image_caption(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Describe one frame (``source_path``) or every frame in ``samples`` with one model load."""
    samples = item.get("samples")
    if isinstance(samples, list):
        results: List[Dict[str, Any]] = [_caption_one(sample if isinstance(sample, dict) else {}, cfg) for sample in samples]
        summary = _summarize_batch_results(results)
        return {"samples": results, **summary}
    return _caption_one(item, cfg)
