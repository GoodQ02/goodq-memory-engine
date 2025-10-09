from __future__ import annotations
from typing import Any, Dict
import os

from GoodQ_4_All.steps.common.lexicon import score_nrc_sentiment


_SENT = {"tok": None, "model": None, "device": "cpu"}


def _load():
    if _SENT["model"] is not None:
        return
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore

        # Ensure HF_HOME is set for model caching
        os.environ.setdefault("HF_HOME", "L:/models")
        os.environ.setdefault("TORCH_HOME", "L:/models")
        os.environ.setdefault("TRANSFORMERS_CACHE", "L:/models/transformers")

        name = "distilbert-base-uncased-finetuned-sst-2-english"
        tok = AutoTokenizer.from_pretrained(name)
        model = AutoModelForSequenceClassification.from_pretrained(name)
        device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        _SENT.update({"tok": tok, "model": model.to(device).eval(), "device": device})
    except Exception:
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
    _load()
    use_nrc_cfg = bool(((cfg.get("config", {}) or {}).get("analysis", {}) or {}).get("use_nrc_lexicon", False))
    offline = (os.environ.get("TRANSFORMERS_OFFLINE") == "1" or os.environ.get("HF_DATASETS_OFFLINE") == "1")

    # Prefer HF model when available and not offline
    if _SENT["model"] is not None and not offline:
        try:
            import torch  # type: ignore
            from GoodQ_4_All.steps.text_embed.step import _content_fingerprint  # reuse fingerprint
            from GoodQ_4_All.steps.common.memory import update_fields

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
            except Exception:
                pass
            return {"sentiment": {"label": label, "score": score}, "sentiment_meta": {"engine": "hf"}}
        except Exception:
            # Fall through to lexicon/rule-based options
            pass

    # Lexicon fallback when configured or offline
    if use_nrc_cfg or offline:
        try:
            res = score_nrc_sentiment(text, cfg)
        except Exception:
            res = None
        if res:
            label, score = res
            return {"sentiment": {"label": label, "score": score}, "sentiment_meta": {"engine": "nrc-lex"}}

    # Final rule-based fallback with tiny lexicon so we always emit sentiment
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
        return {"sentiment": {"label": "NEUTRAL", "score": 0.5}, "sentiment_meta": {"engine": "rule-lex"}}
    label = "POSITIVE" if pos >= neg else "NEGATIVE"
    margin = abs(pos - neg)
    total = max(1, pos + neg)
    conf = 0.5 + min(0.45, (margin / total) * 0.5)
    return {
        "sentiment": {"label": label, "score": float(f"{conf:.3f}")},
        "sentiment_meta": {"engine": "rule-lex"},
    }
