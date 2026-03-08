from __future__ import annotations
from typing import Any, Dict
import os
import logging
from pathlib import Path

from steps.common.lexicon import score_nrc_sentiment
from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)

_SENT = {"tok": None, "model": None, "device": "cpu", "load_attempted": False}


def _resolve_models_root() -> str:
    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


def _load():
    """Load sentiment model with proper error handling and caching."""
    # Only attempt load once
    if _SENT["load_attempted"]:
        return _SENT["model"] is not None
    
    _SENT["load_attempted"] = True
    
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore

        # Ensure HF_HOME is set for model caching
        models_root = _resolve_models_root()
        os.environ["HF_HOME"] = models_root
        os.environ["TORCH_HOME"] = models_root
        os.environ.setdefault("TRANSFORMERS_CACHE", str(Path(models_root) / "transformers"))

        name = "distilbert-base-uncased-finetuned-sst-2-english"
        
        print(f'[INFO] Loading sentiment model: {name}')
        
        # Try local first (fast)
        try:
            tok = AutoTokenizer.from_pretrained(
                name, 
                cache_dir=os.environ["TRANSFORMERS_CACHE"],
                local_files_only=True
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                name,
                cache_dir=os.environ["TRANSFORMERS_CACHE"],
                local_files_only=True
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _SENT.update({"tok": tok, "model": model.to(device).eval(), "device": device})
            print(f'[INFO] Sentiment model loaded from cache ({device})')
            return True
        except Exception as e:
            print(f'[INFO] Model not in cache: {type(e).__name__}')
            
            # Try downloading with timeout
            print(f'[INFO] Attempting to download model (this may take a while)...')
            import threading
            import time
            
            download_result = {"success": False, "error": None}
            
            def download_model():
                try:
                    tok = AutoTokenizer.from_pretrained(
                        name,
                        cache_dir=os.environ["TRANSFORMERS_CACHE"]
                    )
                    model = AutoModelForSequenceClassification.from_pretrained(
                        name,
                        cache_dir=os.environ["TRANSFORMERS_CACHE"]
                    )
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    _SENT.update({"tok": tok, "model": model.to(device).eval(), "device": device})
                    download_result["success"] = True
                except Exception as e:
                    download_result["error"] = f"{type(e).__name__}: {str(e)}"
            
            # Run with 180-second timeout (3 minutes for download)
            download_thread = threading.Thread(target=download_model, daemon=True)
            start_time = time.time()
            download_thread.start()
            download_thread.join(timeout=180)
            
            if download_thread.is_alive():
                elapsed = time.time() - start_time
                print(f'[ERROR] Model download timed out after {elapsed:.1f}s - using fallback')
                _SENT.update({"tok": None, "model": None})
                return False
            elif download_result["success"]:
                print(f'[INFO] Model downloaded and loaded successfully')
                return True
            else:
                print(f'[ERROR] Model download failed: {download_result["error"]}')
                _SENT.update({"tok": None, "model": None})
                return False
                
    except Exception as e:
        print(f'[ERROR] Sentiment model initialization failed: {type(e).__name__}: {str(e)}')
        _SENT.update({"tok": None, "model": None})
        return False


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
    
    # Check if we're in offline mode
    offline = (os.environ.get("TRANSFORMERS_OFFLINE") == "1" or 
               os.environ.get("HF_DATASETS_OFFLINE") == "1")
    use_nrc_cfg = bool(((cfg.get("config", {}) or {}).get("analysis", {}) or {}).get("use_nrc_lexicon", False))

    # Try HF model if available and not offline
    if not offline:
        model_loaded = _load()
        
        if model_loaded and _SENT["model"] is not None:
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
                    print(f'[ERROR] Exception in step.py sentiment update: {str(e)}')
                    pass
                return {"sentiment": {"label": label, "score": score}, "sentiment_meta": {"engine": "hf-distilbert"}}
            except Exception as e:
                print(f'[ERROR] Sentiment inference failed: {type(e).__name__}: {str(e)}')
                # Fall through to fallback options
                pass

    # Lexicon fallback when configured or offline
    if use_nrc_cfg or offline:
        try:
            res = score_nrc_sentiment(text, cfg)
        except Exception as e:
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
        return {"sentiment": {"label": "NEUTRAL", "score": 0.5}, "sentiment_meta": {"engine": "rule-lex-fast"}}
    label = "POSITIVE" if pos >= neg else "NEGATIVE"
    margin = abs(pos - neg)
    total = max(1, pos + neg)
    conf = 0.5 + min(0.45, (margin / total) * 0.5)
    return {
        "sentiment": {"label": label, "score": float(f"{conf:.3f}")},
        "sentiment_meta": {"engine": "rule-lex-fast"},
    }
