from __future__ import annotations
from typing import Any, Dict
import os
import logging
from pathlib import Path

from steps.common.lexicon import score_nrc_sentiment

logger = logging.getLogger(__name__)
_MODELS_FALLBACK_WARNED = False

_SENT = {"tok": None, "model": None, "device": "cpu"}


def _resolve_models_root() -> str:
    global _MODELS_FALLBACK_WARNED
    explicit = os.environ.get("HF_HOME") or os.environ.get("GOODQ_MODELS_DIR")
    if explicit:
        return explicit
    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        if not _MODELS_FALLBACK_WARNED:
            logger.warning(
                "sentiment path fallback used path_key=%s derived_from=%s",
                "HF_HOME",
                "GOODQ_DATA_ROOT",
            )
            _MODELS_FALLBACK_WARNED = True
        return str(Path(data_root) / "models")
    if not _MODELS_FALLBACK_WARNED:
        logger.warning(
            "sentiment path fallback used path_key=%s derived_from=%s",
            "HF_HOME",
            "cwd",
        )
        _MODELS_FALLBACK_WARNED = True
    return str(Path.cwd() / "models")


def _load():
    if _SENT["model"] is not None:
        return
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore

        # Ensure HF_HOME is set for model caching
        models_root = _resolve_models_root()
        os.environ.setdefault("HF_HOME", models_root)
        os.environ.setdefault("TORCH_HOME", models_root)
        os.environ.setdefault("TRANSFORMERS_CACHE", str(Path(models_root) / "transformers"))
        # Disable hf_transfer to avoid dependency issues
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

        name = "distilbert-base-uncased-finetuned-sst-2-english"
        
        # Direct loading without timeout - models are cached now
        tok = AutoTokenizer.from_pretrained(name)
        model = AutoModelForSequenceClassification.from_pretrained(name)
        device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        _SENT.update({"tok": tok, "model": model.to(device).eval(), "device": device})
    except Exception as e:
        print(f'[ERROR] Sentiment model initialization failed: {type(e).__name__}: {str(e)}')
        _SENT.update({"tok": None, "model": None})


def _gather_text(item: Dict[str, Any]) -> str:
    for k in ("transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def sentiment(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"sentiment": None, "sentiment_meta": {"status": "no_text"}}
    
    # Re-enabled sentiment model now that it's cached and HF_TRANSFER is disabled
    offline = (os.environ.get("TRANSFORMERS_OFFLINE") == "1" or os.environ.get("HF_DATASETS_OFFLINE") == "1")
    use_nrc_cfg = bool(((cfg.get("config", {}) or {}).get("analysis", {}) or {}).get("use_nrc_lexicon", False))

    # Try model first when available and not offline
    if not offline:
        _load()
        if _SENT["model"] is not None:
            try:
                import torch  # type: ignore
                from steps.text_embed.step import _content_fingerprint  # reuse fingerprint
                from steps.common.memory import update_fields

                inputs = _SENT["tok"](text, return_tensors="pt", truncation=True, max_length=512).to(_SENT["device"])
                with torch.no_grad():
                    if _SENT.get("device") == "cuda":
                        with torch.cuda.amp.autocast():
                            logits = _SENT["model"](**inputs).logits
                    else:
                        logits = _SENT["model"](**inputs).logits
                    probs = torch.softmax(logits, dim=-1).cpu().numpy().tolist()[0]
                labels = ["NEGATIVE", "POSITIVE"]
                idx = int(probs[1] >= probs[0])
                label = labels[idx]
                score = float(probs[idx])
                try:
                    update_fields(cfg, _content_fingerprint(item), sentiment_label=label, sentiment_score=score)
                except Exception as e:
                    print(f'[ERROR] Exception in step.py line 69: {str(e)}')
                    pass
                return {"sentiment": {"label": label, "score": score}, "sentiment_meta": {"engine": "hf"}}
            except Exception as e:
                # Fall through to lexicon/rule-based options
                print(f'[ERROR] Sentiment HF model failed: {type(e).__name__}: {str(e)}')
                pass

    # Lexicon fallback when configured or HF failed
    if False and use_nrc_cfg:  # Disabled for now
        try:
            res = score_nrc_sentiment(text, cfg)
        except Exception as e:
            res = None
        if res:
            label, score = res
            return {"sentiment": {"label": label, "score": score}, "sentiment_meta": {"engine": "nrc-lex"}}

    # Fast rule-based fallback with tiny lexicon
    lex_pos = {
        "good", "great", "excellent", "amazing", "love", "like", "enjoy", "happy", "joy", "wonderful",
        "awesome", "fantastic", "positive", "delight", "thrilled", "beautiful", "nice", "best", "win",
        "success", "cool",
    }
    lex_neg = {
        "bad", "terrible", "awful", "hate", "dislike", "angry", "sad", "horrible", "worst", "negative",
        "fail", "annoying", "broken", "bug", "issue", "problem", "ugly", "cry", "upset", "pain", "boring",
    }
    txt = text.lower()
    tokens = [t.strip(".,!?;:") for t in txt.split()]
    pos = sum(1 for t in tokens if t in lex_pos)
    neg = sum(1 for t in tokens if t in lex_neg)
    for i, tok in enumerate(tokens):
        if tok in ("not", "no", "never", "n't") and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            if nxt in lex_pos:
                pos -= 1
                neg += 1
            elif nxt in lex_neg:
                neg -= 1
                pos += 1
    if pos == 0 and neg == 0:
        return {"sentiment": {"label": "NEUTRAL", "score": 0.5}, "sentiment_meta": {"engine": "rule-lex-fast"}}
    label = "POSITIVE" if pos >= neg else "NEGATIVE"
    margin = abs(pos - neg)
    total = max(1, pos + neg)
    conf = 0.5 + min(0.45, (margin / total) * 0.5)
    return {
        "sentiment": {"label": label, "score": float(f"{conf:.3f}")},
        "sentiment_meta": {"engine": "rule-lex-fast"},
    }
