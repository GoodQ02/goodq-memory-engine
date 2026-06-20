from __future__ import annotations
from typing import Any, Dict, List
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import GPU manager for centralized GPU configuration
try:
    from gpu_config import setup_step_gpu, GPUManager
except ImportError:
    try:
        from gpu_config import setup_step_gpu, GPUManager
    except ImportError:
        # Fallback if GPU manager not available
        def setup_step_gpu(step_name):
            return {"device": "cpu", "step_name": step_name}
        class GPUManager:
            @staticmethod
            def clear_cache():
                pass

# Import score_nrc_emotions at module level
try:
    from steps.common.lexicon import score_nrc_emotions
except ImportError:
    from steps.common.lexicon import score_nrc_emotions

_EMO = {"model": None, "tok": None, "labels": [], "device": "cpu", "error": None}


def _load_emotion():
    if _EMO["model"] is not None:
        return
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("emotion_classify")
    device = gpu_config["device"]
    
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore
        from steps.common.model_provisioner import ensure_model_cached

        try:
            from steps.common.config_loader import load_configs
            offline_mode = load_configs({}).get("verification", {}).get("offline_mode", False)
        except Exception:
            offline_mode = False

        provision_result = ensure_model_cached("emotion_classify_model", offline=offline_mode)
        if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
            raise OSError(f"Failed to provision emotion model: {provision_result.error or 'reason unknown'}")

        model_id = provision_result.local_path
        has_safetensors = os.path.exists(os.path.join(model_id, "model.safetensors"))
        tok = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(model_id, use_safetensors=has_safetensors, local_files_only=True)
        
        model = model.to(device).eval()
        labels = [
            "admiration","amusement","anger","annoyance","approval","caring","confusion","curiosity","desire",
            "disappointment","disapproval","disgust","embarrassment","excitement","fear","gratitude","grief",
            "joy","love","nervousness","optimism","pride","realization","relief","remorse","sadness",
            "surprise","neutral",
        ]
        _EMO.update({"model": model, "tok": tok, "labels": labels, "device": device, "error": None})
        memory_fraction = gpu_config.get("memory_fraction")
        if isinstance(memory_fraction, (int, float)):
            logger.info(f"[OK] Emotion model loaded on {device} (GPU config: {memory_fraction:.1%} memory)")
        else:
            logger.info(f"[OK] Emotion model loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load emotion model: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _EMO.update({"model": None, "tok": None, "labels": [], "device": "cpu", "error": str(e)})
        # Clear any partial GPU allocations
        GPUManager.clear_cache()


def _gather_text(item: Dict[str, Any]) -> str:
    for k in ("transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def emotion_classify(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"emotions": None, "emotion_meta": {"status": "no_text"}}
    _load_emotion()
    use_nrc_cfg = bool(((cfg.get("config", {}) or {}).get("analysis", {}) or {}).get("use_nrc_lexicon", False))
    offline = (os.environ.get("TRANSFORMERS_OFFLINE") == "1" or os.environ.get("HF_DATASETS_OFFLINE") == "1")

    # Prefer HF model when available and not offline
    if _EMO["model"] is not None and not offline:
        try:
            import torch  # type: ignore
            import json as _json  # local alias
            from steps.text_embed.step import _content_fingerprint  # reuse fingerprint
            from steps.common.memory import update_fields
            inputs = _EMO["tok"](text, return_tensors="pt", truncation=True, max_length=512).to(_EMO.get("device","cpu"))
            with torch.no_grad():
                if _EMO.get("device") == "cuda":
                    with torch.cuda.amp.autocast():
                        logits = _EMO["model"](**inputs).logits
                else:
                    logits = _EMO["model"](**inputs).logits
                probs = torch.sigmoid(logits).cpu().numpy().tolist()[0]
            pairs = sorted(zip(_EMO["labels"], probs), key=lambda x: x[1], reverse=True)
            top = [{"label": l, "score": float(s)} for l, s in pairs[:5]]
            try:
                update_fields(cfg, _content_fingerprint(item), emotions_json=_json.dumps(top))
                logger.info(f"Successfully updated emotions for item: {item.get('path', 'unknown')[:50]}")
            except Exception as e:
                logger.error(f'Failed to update_fields for emotions: {str(e)}', exc_info=True)
                # Still return the data even if DB update fails
            return {"emotions": top, "emotion_meta": {"engine": "hf"}}
        except Exception as e:
            logger.error(f'Emotion classification failed: {str(e)}', exc_info=True)
            pass

    # NRC lexicon fallback when configured or offline
    if use_nrc_cfg or offline:
        try:
            scr = score_nrc_emotions(text, cfg)
        except Exception as e:
            scr = None
        if scr:
            pairs = sorted(scr.items(), key=lambda x: x[1], reverse=True)
            top = [{"label": l, "score": float(f"{s:.4f}")} for l, s in pairs[:5]]
            return {"emotions": top, "emotion_meta": {"engine": "nrc-lex"}}

    # If nothing else worked
    if _EMO["model"] is None:
        meta = {"status": "unavailable", "engine": "cardiffnlp", "reason": "model_load_failed"}
        if _EMO.get("error"):
            meta["error"] = str(_EMO.get("error"))[:500]
        return {"emotions": None, "emotion_meta": meta}
    try:
        import torch  # type: ignore
        import json as _json  # local alias
        from steps.text_embed.step import _content_fingerprint  # reuse fingerprint
        from steps.common.memory import update_fields
        inputs = _EMO["tok"](text, return_tensors="pt", truncation=True, max_length=512).to(_EMO.get("device","cpu"))
        with torch.no_grad():
            if _EMO.get("device") == "cuda":
                with torch.cuda.amp.autocast():
                    logits = _EMO["model"](**inputs).logits
            else:
                logits = _EMO["model"](**inputs).logits
            probs = torch.sigmoid(logits).cpu().numpy().tolist()[0]
        pairs = sorted(zip(_EMO["labels"], probs), key=lambda x: x[1], reverse=True)
        top = [{"label": l, "score": float(s)} for l, s in pairs[:5]]
        try:
            update_fields(cfg, _content_fingerprint(item), emotions_json=_json.dumps(top))
            logger.info(f"Successfully updated emotions (fallback path) for item: {item.get('path', 'unknown')[:50]}")
        except Exception as e:
            logger.error(f'Failed to update_fields for emotions (fallback): {str(e)}', exc_info=True)
            # Still return the data even if DB update fails
        return {"emotions": top}
    except Exception as e:
        return {"emotions": None, "emotion_meta": {"status": "error", "error": str(e)}}
