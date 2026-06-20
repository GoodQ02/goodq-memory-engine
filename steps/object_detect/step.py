from __future__ import annotations
from typing import Any, Dict, List, Optional

import os
import logging
import json
import sys
from pathlib import Path

from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)

# Import GPU manager for centralized GPU configuration
try:
    from scripts.gpu_config import setup_step_gpu, GPUManager
except ImportError as exc:
    logger.warning("[WARN] scripts.gpu_config unavailable; using CPU fallback: %s", exc)

    def setup_step_gpu(step_name):
        return {"device": "cpu", "step_name": step_name}

    class GPUManager:
        @staticmethod
        def clear_cache():
            pass


_YOLO = None
_YOLO_DEVICE = "cpu"


def _resolve_device(requested_device: str) -> str:
    if os.getenv("GOODQ_OBJECT_DETECT_FORCE_CPU", "").strip() == "1":
        return "cpu"
    return requested_device


def _gpu_memory_snapshot(torch_module) -> Dict[str, Any]:
    if not getattr(torch_module, "cuda", None):
        return {"available": False}
    try:
        if not torch_module.cuda.is_available():
            return {"available": False}
        return {
            "available": True,
            "allocated_mb": round(float(torch_module.cuda.memory_allocated()) / (1024 * 1024), 2),
            "reserved_mb": round(float(torch_module.cuda.memory_reserved()) / (1024 * 1024), 2),
            "max_allocated_mb": round(float(torch_module.cuda.max_memory_allocated()) / (1024 * 1024), 2),
        }
    except Exception as exc:
        return {"available": "unknown", "error": str(exc)}


def _log_object_detect_diagnostics(
    stage: str,
    *,
    source_path: str,
    device: str,
    image_size: Optional[tuple[int, int]] = None,
    model_loaded_now: Optional[bool] = None,
    gpu_memory: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "event": "object_detect_diagnostics",
        "stage": stage,
        "source_path": source_path,
        "device": device,
        "image_size": list(image_size) if image_size else None,
        "model_loaded_now": model_loaded_now,
        "gpu_memory": gpu_memory,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)
    logger.info("object_detect diagnostics %s", payload)


def _resolve_models_root() -> str:
    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


def _load_yolo(cfg: Dict[str, Any]) -> bool:
    global _YOLO, _YOLO_DEVICE
    if _YOLO is not None:
        return False
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("object_detect")
    _YOLO_DEVICE = _resolve_device(gpu_config["device"])
    
    try:
        from ultralytics import YOLO  # type: ignore
        
        from steps.common.model_provisioner import ensure_model_cached
        
        try:
            from steps.common.config_loader import load_configs
            offline_mode = load_configs({}).get("verification", {}).get("offline_mode", False)
        except Exception:
            offline_mode = False
            
        provision_result = ensure_model_cached("yolo_v8n", offline=offline_mode)
        if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
            raise OSError(f"Failed to provision YOLO model: {provision_result.error or 'reason unknown'}")
            
        model_path = provision_result.local_path
        
        _YOLO = YOLO(model_path)
        logger.info(f"[OK] YOLO model loaded on {_YOLO_DEVICE} (GPU config: {gpu_config['memory_fraction']:.1%} memory)")
        return True
            
    except Exception as e:
        logger.error(f"[FAIL] Failed to load YOLO model: {str(e)}")
        _YOLO = None
        GPUManager.clear_cache()
        return False


def _run_yolo(model, path: str, device: str | None = None):
    try:
        # Prefer explicit predict API so we can choose device
        return model.predict(source=path, device=device or _YOLO_DEVICE, verbose=False)
    except Exception as e:
        # Fallback to callable interface
        if device:
            try:
                model.to(device)
            except Exception as e:
                logger.warning(f'Could not set YOLO device: {str(e)}')
                pass
        return model(path)


def object_detect(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"objects": [], "detect_meta": {"status": "no_file"}}

    model_loaded_now = _load_yolo(cfg)
    model = _YOLO
    if model is None:
        return {"objects": [], "detect_meta": {"status": "unavailable", "engine": "yolo"}}
    image_size = None
    gpu_memory_before = None
    try:
        import torch  # type: ignore
        from PIL import Image  # type: ignore

        with Image.open(path) as img:
            image_size = getattr(img, "size", None)
        gpu_memory_before = _gpu_memory_snapshot(torch)
        _log_object_detect_diagnostics(
            "before_inference",
            source_path=path,
            device=_YOLO_DEVICE,
            image_size=image_size,
            model_loaded_now=model_loaded_now,
            gpu_memory=gpu_memory_before,
        )
        # First attempt: default device selection (GPU if available)
        results = _run_yolo(model, path)
        _log_object_detect_diagnostics(
            "after_inference",
            source_path=path,
            device=_YOLO_DEVICE,
            image_size=image_size,
            model_loaded_now=model_loaded_now,
            gpu_memory=_gpu_memory_snapshot(torch),
        )
    except Exception as e:
        msg = str(e)
        # Known failure: torchvision::nms CUDA op unavailable -> retry on CPU
        if "torchvision::nms" in msg or "nms" in msg.lower():
            try:
                results = _run_yolo(model, path, device="cpu")
            except Exception as e2:
                return {"objects": [], "detect_meta": {"status": "error", "error": str(e2), "engine": "yolo", "device": "cpu", "exc_type": type(e2).__name__}}
        else:
            return {"objects": [], "detect_meta": {"status": "error", "error": msg, "engine": "yolo", "exc_type": type(e).__name__}}

    try:
        detections: List[Dict[str, Any]] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            names = getattr(r, "names", {}) or {}
            if boxes is None:
                continue
            for b in boxes:
                xyxy = getattr(b, "xyxy", None)
                conf = getattr(b, "conf", None)
                cls = getattr(b, "cls", None)
                if xyxy is None or conf is None or cls is None:
                    continue
                try:
                    x1, y1, x2, y2 = [float(v) for v in xyxy[0].tolist()]
                except Exception as e:
                    vals = getattr(xyxy, "tolist", lambda: [])()
                    if vals and len(vals[0]) == 4:
                        x1, y1, x2, y2 = [float(v) for v in vals[0]]
                    else:
                        continue
                label = names.get(int(cls[0].item()) if hasattr(cls[0], "item") else int(cls[0])) if len(names) else None
                score = float(conf[0].item()) if hasattr(conf[0], "item") else float(conf[0])
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "label": label,
                    "score": score,
                })
        return {"objects": detections}
    except Exception as e:
        return {"objects": [], "detect_meta": {"status": "error", "error": str(e), "engine": "yolo", "exc_type": type(e).__name__}}
