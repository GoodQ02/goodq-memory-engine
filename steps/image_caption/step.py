from __future__ import annotations
from typing import Any, Dict, Optional
import os
import logging
import json
import sys
from contextlib import nullcontext
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


_BLIP = {"model": None, "proc": None, "device": "cpu"}
_FALLBACK = {"pipe": None, "device": "cpu"}


def _resolve_device(requested_device: str) -> str:
    if os.getenv("GOODQ_IMAGE_CAPTION_FORCE_CPU", "").strip() == "1":
        return "cpu"
    return requested_device


def _amp_enabled(device: str) -> bool:
    if device != "cuda":
        return False
    return os.getenv("GOODQ_IMAGE_CAPTION_DISABLE_AMP", "").strip() != "1"


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


def _shape_for_log(value: Any) -> Optional[list[int]]:
    shape = getattr(value, "shape", None)
    if shape is None:
        return None
    try:
        return [int(dim) for dim in shape]
    except Exception:
        return None


def _log_caption_diagnostics(
    stage: str,
    *,
    source_path: str,
    device: str,
    image_size: Optional[tuple[int, int]] = None,
    tensor_shape: Optional[list[int]] = None,
    model_loaded_now: Optional[bool] = None,
    amp_enabled: Optional[bool] = None,
    gpu_memory: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "event": "image_caption_diagnostics",
        "stage": stage,
        "source_path": source_path,
        "device": device,
        "image_size": list(image_size) if image_size else None,
        "tensor_shape": tensor_shape,
        "model_loaded_now": model_loaded_now,
        "amp_enabled": amp_enabled,
        "gpu_memory": gpu_memory,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)
    logger.info("image_caption diagnostics %s", payload)


def _resolve_models_root() -> str:
    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


def _resolve_blip_local_dir(models_root: str) -> Optional[str]:
    """Resolve a local HF Hub snapshot for the BLIP model."""
    repo_cache = Path(models_root) / "hub" / "models--Salesforce--blip-image-captioning-base"
    snapshots_dir = repo_cache / "snapshots"
    refs_main = repo_cache / "refs" / "main"
    required_config = ("config.json", "preprocessor_config.json")
    weight_files = ("pytorch_model.bin", "model.safetensors")
    candidates = []

    if refs_main.is_file():
        try:
            revision = refs_main.read_text(encoding="utf-8").strip()
            if revision:
                candidates.append(snapshots_dir / revision)
        except OSError:
            pass

    if snapshots_dir.is_dir():
        candidates.extend(sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        if (all((candidate / name).is_file() for name in required_config)
                and any((candidate / w).is_file() for w in weight_files)):
            return str(candidate)
    return None


def _load_blip() -> bool:
    if _BLIP["model"] is not None:
        return False
    
    # Configure GPU using centralized manager
    gpu_config = setup_step_gpu("image_caption")
    device = _resolve_device(gpu_config["device"])
    
    try:
        import torch  # type: ignore
        from transformers import BlipProcessor, BlipForConditionalGeneration  # type: ignore

        # Ensure HF_HOME is set for model caching
        models_root = _resolve_models_root()
        os.environ["HF_HOME"] = models_root
        os.environ["TORCH_HOME"] = models_root
        os.environ.setdefault("TRANSFORMERS_CACHE", str(Path(models_root) / "transformers"))
        
        # Prefer local snapshot if available for offline/air-gapped operation
        local_dir = _resolve_blip_local_dir(models_root)
        model_id = local_dir or "Salesforce/blip-image-captioning-base"
        local_only = local_dir is not None
        if local_only:
            logger.info(f"[OK] BLIP using local snapshot: {local_dir}")
        
        proc = BlipProcessor.from_pretrained(model_id, local_files_only=local_only)
        model = BlipForConditionalGeneration.from_pretrained(model_id, local_files_only=local_only).to(device).eval()
        _BLIP.update({"model": model, "proc": proc, "device": device})
        logger.info(f"[OK] BLIP model loaded on {device} (GPU config: {gpu_config['memory_fraction']:.1%} memory)")
        return True
    except Exception as e:
        logger.error(f"[FAIL] Failed to load BLIP model: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _BLIP.update({"model": None, "proc": None, "device": "cpu"})
        GPUManager.clear_cache()
        return False


def _load_fallback() -> None:
    if _FALLBACK["pipe"] is not None:
        return
    
    # Configure GPU using centralized manager
    gpu_config = setup_step_gpu("image_caption")
    device = _resolve_device(gpu_config["device"])
    
    try:
        import torch  # type: ignore
        from transformers import pipeline  # type: ignore
        
        pipe = pipeline("image-to-text", model="nlpconnect/vit-gpt2-image-captioning", device=0 if device=="cuda" else -1)
        _FALLBACK.update({"pipe": pipe, "device": device})
        logger.info(f"[OK] Fallback caption model loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load fallback model: {str(e)}")
        _FALLBACK.update({"pipe": None})
        GPUManager.clear_cache()


def image_caption(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"caption": None}

    model_loaded_now = _load_blip()
    if _BLIP["model"] is None:
        # try fallback pipeline
        _load_fallback()
        if _FALLBACK["pipe"] is None:
            return {"caption": None, "caption_meta": {"status": "unavailable", "engine": "blip"}}
        try:
            from PIL import Image  # type: ignore
            img = Image.open(path).convert("RGB")
            out = _FALLBACK["pipe"](img)
            text = (out[0].get("generated_text") if out else None) or None
            return {"caption": text, "caption_meta": {"status": "ok", "engine": "vit-gpt2"}}
        except Exception as e:
            logger.error(f"[FAIL] Fallback captioning failed: {str(e)}")
            GPUManager.clear_cache()
            return {"caption": None, "caption_meta": {"status": "error", "error": str(e)}}

    try:
        import torch  # type: ignore
        from PIL import Image  # type: ignore

        img = Image.open(path).convert("RGB")
        image_size = getattr(img, "size", None)
        inputs = _BLIP["proc"](images=img, return_tensors="pt").to(_BLIP["device"])
        tensor_shape = _shape_for_log(inputs.get("pixel_values"))
        amp_enabled = _amp_enabled(_BLIP["device"])
        gpu_memory_before = _gpu_memory_snapshot(torch)
        _log_caption_diagnostics(
            "before_inference",
            source_path=path,
            device=_BLIP["device"],
            image_size=image_size,
            tensor_shape=tensor_shape,
            model_loaded_now=model_loaded_now,
            amp_enabled=amp_enabled,
            gpu_memory=gpu_memory_before,
        )
        
        with torch.no_grad():
            autocast_ctx = (
                torch.amp.autocast(device_type="cuda", dtype=torch.float16)
                if amp_enabled
                else nullcontext()
            )
            with autocast_ctx:
                out = _BLIP["model"].generate(**inputs, max_new_tokens=32)
        _log_caption_diagnostics(
            "after_inference",
            source_path=path,
            device=_BLIP["device"],
            image_size=image_size,
            tensor_shape=tensor_shape,
            model_loaded_now=model_loaded_now,
            amp_enabled=amp_enabled,
            gpu_memory=_gpu_memory_snapshot(torch),
        )
        
        text = _BLIP["proc"].decode(out[0], skip_special_tokens=True)
        return {"caption": text, "caption_meta": {"status": "ok", "engine": "blip"}}
    except Exception as e:
        logger.error(f"[FAIL] Image captioning failed: {str(e)}")
        GPUManager.clear_cache()
        return {
            "caption": None,
            "caption_meta": {
                "status": "error",
                "error": str(e),
                "exc_type": type(e).__name__,
            },
        }
