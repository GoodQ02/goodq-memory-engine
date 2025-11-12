from __future__ import annotations
from typing import Any, Dict
import os
import logging

logger = logging.getLogger(__name__)

# Import GPU manager for centralized GPU configuration
try:
    from gpu_config import setup_step_gpu, GPUManager
except ImportError:
    try:
        from goodq4all.gpu_config import setup_step_gpu, GPUManager
    except ImportError:
        def setup_step_gpu(step_name):
            return {"device": "cpu", "step_name": step_name}
        class GPUManager:
            @staticmethod
            def clear_cache():
                pass


_BLIP = {"model": None, "proc": None, "device": "cpu"}
_FALLBACK = {"pipe": None, "device": "cpu"}


def _load_blip() -> None:
    if _BLIP["model"] is not None:
        return
    
    # Configure GPU using centralized manager
    gpu_config = setup_step_gpu("image_caption")
    device = gpu_config["device"]
    
    try:
        import torch  # type: ignore
        from transformers import BlipProcessor, BlipForConditionalGeneration  # type: ignore

        # Ensure HF_HOME is set for model caching
        os.environ.setdefault("HF_HOME", "L:/models")
        os.environ.setdefault("TORCH_HOME", "L:/models")
        os.environ.setdefault("TRANSFORMERS_CACHE", "L:/models/transformers")
        
        proc = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device).eval()
        _BLIP.update({"model": model, "proc": proc, "device": device})
        logger.info(f"✅ BLIP model loaded on {device} (GPU config: {gpu_config['memory_fraction']:.1%} memory)")
    except Exception as e:
        logger.error(f"❌ Failed to load BLIP model: {str(e)}")
        logger.info("⚠️  Falling back to CPU mode")
        _BLIP.update({"model": None, "proc": None, "device": "cpu"})
        GPUManager.clear_cache()


def _load_fallback() -> None:
    if _FALLBACK["pipe"] is not None:
        return
    
    # Configure GPU using centralized manager
    gpu_config = setup_step_gpu("image_caption")
    device = gpu_config["device"]
    
    try:
        import torch  # type: ignore
        from transformers import pipeline  # type: ignore
        
        pipe = pipeline("image-to-text", model="nlpconnect/vit-gpt2-image-captioning", device=0 if device=="cuda" else -1)
        _FALLBACK.update({"pipe": pipe, "device": device})
        logger.info(f"✅ Fallback caption model loaded on {device}")
    except Exception as e:
        logger.error(f"❌ Failed to load fallback model: {str(e)}")
        _FALLBACK.update({"pipe": None})
        GPUManager.clear_cache()


def image_caption(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"caption": None}

    _load_blip()
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
            logger.error(f"❌ Fallback captioning failed: {str(e)}")
            GPUManager.clear_cache()
            return {"caption": None, "caption_meta": {"status": "error", "error": str(e)}}

    try:
        import torch  # type: ignore
        from PIL import Image  # type: ignore

        img = Image.open(path).convert("RGB")
        inputs = _BLIP["proc"](images=img, return_tensors="pt").to(_BLIP["device"])
        
        with torch.no_grad():
            if _BLIP["device"] == "cuda":
                with torch.cuda.amp.autocast():
                    out = _BLIP["model"].generate(**inputs, max_new_tokens=32)
            else:
                out = _BLIP["model"].generate(**inputs, max_new_tokens=32)
        
        text = _BLIP["proc"].decode(out[0], skip_special_tokens=True)
        return {"caption": text, "caption_meta": {"status": "ok", "engine": "blip"}}
    except Exception as e:
        logger.error(f"❌ Image captioning failed: {str(e)}")
        GPUManager.clear_cache()
        return {"caption": None, "caption_meta": {"status": "error", "error": str(e)}}
