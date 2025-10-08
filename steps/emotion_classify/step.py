from __future__ import annotations
from typing import Any, Dict, List
import os


_EMO = {"model": None, "tok": None, "labels": []}


def _load_emotion():
    if _EMO["model"] is not None:
        return
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore

        # Ensure HF_HOME is set for model caching
        os.environ.setdefault("HF_HOME", "L:/models")
        os.environ.setdefault("TORCH_HOME", "L:/models")
        os.environ.setdefault("TRANSFORMERS_CACHE", "L:/models/transformers")

        name = "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest"
        tok = AutoTokenizer.from_pretrained(name)
        model = AutoModelForSequenceClassification.from_pretrained(name)
        device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        model = model.to(device).eval()
        labels = [
            "admiration","amusement","anger","annoyance","approval","caring","confusion","curiosity","desire",
            "disappointment","disapproval","disgust","embarrassment","excitement","fear","gratitude","grief",
            "joy","love","nervousness","optimism","pride","realization","relief","remorse","sadness",
            "surprise","neutral",
        ]
        _EMO.update({"model": model, "tok": tok, "labels": labels, "device": device})
    except Exception:
        _EMO.update({"model": None, "tok": None, "labels": []})


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
            from zenml_project.steps.text_embed.step import _content_fingerprint  # reuse fingerprint
            from zenml_project.steps.common.memory import update_fields
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
            except Exception:
                pass
            return {"emotions": top, "emotion_meta": {"engine": "hf"}}
        except Exception:
            pass

    # NRC lexicon fallback when configured or offline
    if use_nrc_cfg or offline:
        try:
            scr = score_nrc_emotions(text, cfg)
        except Exception:
            scr = None
        if scr:
            pairs = sorted(scr.items(), key=lambda x: x[1], reverse=True)
            top = [{"label": l, "score": float(f"{s:.4f}")} for l, s in pairs[:5]]
            return {"emotions": top, "emotion_meta": {"engine": "nrc-lex"}}

    # If nothing else worked
    if _EMO["model"] is None:
        return {"emotions": None, "emotion_meta": {"status": "unavailable", "engine": "cardiffnlp"}}
    try:
        import torch  # type: ignore
        import json as _json  # local alias
        from zenml_project.steps.text_embed.step import _content_fingerprint  # reuse fingerprint
        from zenml_project.steps.common.memory import update_fields
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
        except Exception:
            pass
        return {"emotions": top}
    except Exception as e:
        return {"emotions": None, "emotion_meta": {"status": "error", "error": str(e)}}
from zenml_project.steps.common.lexicon import score_nrc_emotions
