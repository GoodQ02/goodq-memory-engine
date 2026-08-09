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

_EMO = {
    "model": None,
    "tok": None,
    "labels": [],
    "device": "cpu",
    "error": None,
    "problem_type": None,
    "model_id": None,
    "model_revision": None,
}


def _ordered_model_labels(model: Any) -> List[str]:
    """Return labels in the loaded model's output-logit order."""

    id2label = getattr(getattr(model, "config", None), "id2label", None)
    if not isinstance(id2label, dict) or not id2label:
        raise ValueError("Loaded emotion model does not expose a non-empty config.id2label mapping")

    try:
        ordered = sorted(((int(index), str(label)) for index, label in id2label.items()), key=lambda item: item[0])
    except (TypeError, ValueError) as exc:
        raise ValueError("Loaded emotion model config.id2label keys must be integer-like") from exc

    return [label for _, label in ordered]


def _model_emotion_meta() -> Dict[str, Any]:
    return {
        "engine": "cardiffnlp",
        "status": "ok",
        "source": "model",
        "problem_type": _EMO["problem_type"],
        "label_count": len(_EMO["labels"]),
        "model_id": _EMO["model_id"],
        "model_revision": _EMO["model_revision"],
    }


def _rank_model_emotions(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Run the cached model and preserve every score with its model-owned label."""

    import json as _json
    import torch  # type: ignore

    from steps.common.memory import update_fields
    from steps.text_embed.step import _content_fingerprint

    inputs = _EMO["tok"](_gather_text(item), return_tensors="pt", truncation=True, max_length=512).to(_EMO["device"])
    with torch.no_grad():
        if _EMO.get("device") == "cuda":
            with torch.cuda.amp.autocast():
                logits = _EMO["model"](**inputs).logits
        else:
            logits = _EMO["model"](**inputs).logits

        if _EMO["problem_type"] == "multi_label_classification":
            probabilities = torch.sigmoid(logits)
        elif _EMO["problem_type"] == "single_label_classification":
            probabilities = torch.softmax(logits, dim=-1)
        else:
            raise ValueError(f"Unsupported emotion model problem_type: {_EMO['problem_type']!r}")

    scores = probabilities.cpu().numpy().tolist()[0]
    labels = _EMO["labels"]
    if len(scores) != len(labels):
        raise ValueError(
            f"Emotion model output has {len(scores)} logits but config.id2label defines {len(labels)} labels"
        )

    emotions = [
        {"label": label, "score": float(score)}
        for label, score in sorted(zip(labels, scores), key=lambda item: item[1], reverse=True)
    ]
    try:
        update_fields(cfg, _content_fingerprint(item), emotions_json=_json.dumps(emotions))
        logger.info("Successfully updated complete model emotion ranking for item: %s", item.get("path", "unknown")[:50])
    except Exception as exc:
        logger.error("Failed to persist model emotion ranking: %s", exc, exc_info=True)
    return {"emotions": emotions, "emotion_meta": _model_emotion_meta()}


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
        labels = _ordered_model_labels(model)
        problem_type = str(getattr(model.config, "problem_type", "") or "").strip()
        if problem_type not in {"multi_label_classification", "single_label_classification"}:
            raise ValueError(f"Unsupported emotion model config.problem_type: {problem_type!r}")
        _EMO.update(
            {
                "model": model,
                "tok": tok,
                "labels": labels,
                "device": device,
                "error": None,
                "problem_type": problem_type,
                "model_id": provision_result.repo_id,
                "model_revision": provision_result.revision,
            }
        )
        memory_fraction = gpu_config.get("memory_fraction")
        if isinstance(memory_fraction, (int, float)):
            logger.info(f"[OK] Emotion model loaded on {device} (GPU config: {memory_fraction:.1%} memory)")
        else:
            logger.info(f"[OK] Emotion model loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load emotion model: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _EMO.update(
            {
                "model": None,
                "tok": None,
                "labels": [],
                "device": "cpu",
                "error": str(e),
                "problem_type": None,
                "model_id": None,
                "model_revision": None,
            }
        )
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
    # A verified local model remains usable in offline mode; only provisioning may
    # be offline-constrained.
    model_failed = False
    model_error: Exception | None = None
    if _EMO["model"] is not None:
        try:
            return _rank_model_emotions(item, cfg)
        except Exception as exc:
            model_failed = True
            model_error = exc
            logger.error("Emotion classification failed: %s", exc, exc_info=True)

    # NRC is a distinct lexicon fallback, never a blended model result.
    if use_nrc_cfg or model_failed or _EMO["model"] is None:
        try:
            scr = score_nrc_emotions(text, cfg)
        except Exception as e:
            scr = None
        if scr:
            pairs = sorted(scr.items(), key=lambda x: x[1], reverse=True)
            emotions = [{"label": label, "score": float(f"{score:.4f}")} for label, score in pairs]
            return {
                "emotions": emotions,
                "emotion_meta": {
                    "engine": "nrc-lex",
                    "status": "fallback",
                    "source": "lexicon",
                    "label_count": len(emotions),
                    "reason": "model_inference_failed" if model_failed else "model_unavailable",
                },
            }

    # If nothing else worked
    if _EMO["model"] is None:
        meta = {"status": "unavailable", "engine": "cardiffnlp", "reason": "model_load_failed"}
        if _EMO.get("error"):
            meta["error"] = str(_EMO.get("error"))[:500]
        return {"emotions": None, "emotion_meta": meta}

    return {
        "emotions": None,
        "emotion_meta": {
            "engine": "cardiffnlp",
            "status": "error",
            "reason": "model_inference_failed",
            "error": str(model_error or "reason unknown")[:500],
        },
    }
