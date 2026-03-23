from __future__ import annotations
from typing import Any, Dict, List

import os
import logging
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


def _resolve_models_root() -> str:
    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


def _load_yolo(cfg: Dict[str, Any]):
    global _YOLO, _YOLO_DEVICE
    if _YOLO is not None:
        return _YOLO
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("object_detect")
    _YOLO_DEVICE = gpu_config["device"]
    
    try:
        from ultralytics import YOLO  # type: ignore
        
        # Try multiple config paths
        model_path = (
            cfg.get("models", {}).get("external_models", {}).get("yolo_v8n", {}).get("local_path")
            or cfg.get("models", {}).get("yolo_model_path")
            or cfg.get("config", {}).get("models", {}).get("yolo_model_path")
            or "yolov8n.pt"
        )
        # If local_path is relative, resolve under configured model cache root
        if model_path and not os.path.isabs(model_path):
            model_base = _resolve_models_root()
            model_path = os.path.join(model_base, model_path)
        
        _YOLO = YOLO(model_path)
        logger.info(f"[OK] YOLO model loaded on {_YOLO_DEVICE} (GPU config: {gpu_config['memory_fraction']:.1%} memory)")
            
    except Exception as e:
        logger.error(f"[FAIL] Failed to load YOLO model: {str(e)}")
        _YOLO = None
        GPUManager.clear_cache()
    return _YOLO


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

    model = _load_yolo(cfg)
    if model is None:
        return {"objects": [], "detect_meta": {"status": "unavailable", "engine": "yolo"}}
    try:
        # First attempt: default device selection (GPU if available)
        results = _run_yolo(model, path)
    except Exception as e:
        msg = str(e)
        # Known failure: torchvision::nms CUDA op unavailable -> retry on CPU
        if "torchvision::nms" in msg or "nms" in msg.lower():
            try:
                results = _run_yolo(model, path, device="cpu")
            except Exception as e2:
                return {"objects": [], "detect_meta": {"status": "error", "error": str(e2), "engine": "yolo", "device": "cpu"}}
        else:
            return {"objects": [], "detect_meta": {"status": "error", "error": msg, "engine": "yolo"}}

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
        return {"objects": [], "detect_meta": {"status": "error", "error": str(e), "engine": "yolo"}}
