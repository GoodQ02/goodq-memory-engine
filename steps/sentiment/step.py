from __future__ import annotations
from typing import Any, Dict, Optional
import os
import logging
import re
import unicodedata
from pathlib import Path

from steps.common.lexicon import score_nrc_sentiment
from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)

_SENTIMENT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"
_SENT = {"tok": None, "model": None, "device": "cpu", "load_attempted": False, "load_error": None}


def _resolve_models_root() -> str:
    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


def _configure_model_env() -> None:
    models_root = _resolve_models_root()
    os.environ["HF_HOME"] = models_root
    os.environ["TORCH_HOME"] = models_root
    os.environ.setdefault("TRANSFORMERS_CACHE", str(Path(models_root) / "transformers"))
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch if (ch.isprintable() or ch.isspace()) else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _looks_too_short(text: str) -> bool:
    tokens = re.findall(r"[A-Za-z0-9']+", text)
    if not tokens:
        return True
    return len(tokens) < 2 and len(text) < 8


def _preferred_device() -> str:
    try:
        import torch  # type: ignore

        if getattr(torch, "cuda", None) and torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _should_retry_on_cpu(exc: Exception) -> bool:
    message = f"{type(exc).__name__}: {exc}".lower()
    return any(
        token in message
        for token in (
            "cuda",
            "cublas",
            "cudnn",
            "out of memory",
            "device-side",
            "device type",
            "driver shutting down",
        )
    )


def _load(preferred_device: Optional[str] = None) -> bool:
    target_device = preferred_device or _preferred_device()
    if _SENT["model"] is not None:
        if _SENT["device"] == target_device:
            return True
        try:
            _SENT["model"] = _SENT["model"].to(target_device).eval()
            _SENT["device"] = target_device
            return True
        except Exception as exc:
            logger.warning(
                "sentiment model move failed target_device=%s exc_type=%s exc=%s",
                target_device,
                type(exc).__name__,
                exc,
            )
            _SENT.update({"tok": None, "model": None, "device": "cpu"})
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore
        from steps.common.model_provisioner import ensure_model_cached

        _configure_model_env()
        device = target_device if target_device == "cpu" or torch.cuda.is_available() else "cpu"
        
        try:
            from steps.common.config_loader import load_configs
            offline_mode = load_configs({}).get("verification", {}).get("offline_mode", False)
        except Exception:
            offline_mode = False
            
        provision_result = ensure_model_cached("sentiment_model", offline=offline_mode)
        if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
            raise OSError(f"Failed to provision sentiment model: {provision_result.error or 'reason unknown'}")
            
        model_id = provision_result.local_path
        
        tok = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(model_id, local_files_only=True)
        _SENT.update({"tok": tok, "model": model.to(device).eval(), "device": device})
        _SENT["load_attempted"] = True
        _SENT["load_error"] = None
        return True
    except Exception as e:
        _SENT["load_attempted"] = True
        _SENT["load_error"] = f"{type(e).__name__}: {str(e)}"
        logger.warning(
            "sentiment model initialization failed preferred_device=%s exc_type=%s exc=%s",
            target_device,
            type(e).__name__,
            e,
        )
        _SENT.update({"tok": None, "model": None, "device": "cpu"})
        return False


def _gather_text(item: Dict[str, Any]) -> str:
    for k in ("transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def sentiment(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _normalize_text(_gather_text(item))
    if not text:
        return {"sentiment": None, "sentiment_meta": {"status": "no_text", "reason": "no_text"}}
    if _looks_too_short(text):
        return {"sentiment": None, "sentiment_meta": {"status": "skipped", "reason": "too_short"}}

    offline = (os.environ.get("TRANSFORMERS_OFFLINE") == "1" or os.environ.get("HF_DATASETS_OFFLINE") == "1")
    use_nrc_cfg = bool(((cfg.get("config", {}) or {}).get("analysis", {}) or {}).get("use_nrc_lexicon", False))

    if not offline:
        preferred_device = _preferred_device()
        if _load(preferred_device):
            try:
                import torch  # type: ignore
                from steps.text_embed.step import _content_fingerprint  # reuse fingerprint
                from steps.common.memory import update_fields

                inputs = _SENT["tok"](text, return_tensors="pt", truncation=True, max_length=512).to(_SENT["device"])
                with torch.no_grad():
                    if _SENT.get("device") == "cuda":
                        with torch.amp.autocast("cuda"):
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
                    logger.warning(
                        "sentiment sqlite update failed exc_type=%s exc=%s",
                        type(e).__name__,
                        e,
                    )
                return {"sentiment": {"label": label, "score": score}, "sentiment_meta": {"engine": "hf"}}
            except Exception as e:
                logger.warning(
                    "sentiment inference failed device=%s exc_type=%s exc=%s",
                    _SENT.get("device"),
                    type(e).__name__,
                    e,
                )
                if _SENT.get("device") == "cuda" and _should_retry_on_cpu(e) and _load("cpu"):
                    try:
                        inputs = _SENT["tok"](text, return_tensors="pt", truncation=True, max_length=512).to(_SENT["device"])
                        with torch.no_grad():
                            logits = _SENT["model"](**inputs).logits
                            probs = torch.softmax(logits, dim=-1).cpu().numpy().tolist()[0]
                        labels = ["NEGATIVE", "POSITIVE"]
                        idx = int(probs[1] >= probs[0])
                        label = labels[idx]
                        score = float(probs[idx])
                        try:
                            update_fields(cfg, _content_fingerprint(item), sentiment_label=label, sentiment_score=score)
                        except Exception as update_exc:
                            logger.warning(
                                "sentiment sqlite update failed after cpu retry exc_type=%s exc=%s",
                                type(update_exc).__name__,
                                update_exc,
                            )
                        return {"sentiment": {"label": label, "score": score}, "sentiment_meta": {"engine": "hf"}}
                    except Exception as retry_exc:
                        logger.warning(
                            "sentiment cpu retry failed exc_type=%s exc=%s",
                            type(retry_exc).__name__,
                            retry_exc,
                        )

    # Lexicon fallback when configured or HF failed
    if False and use_nrc_cfg:  # Disabled for now
        try:
            res = score_nrc_sentiment(text, cfg)
        except Exception:
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
