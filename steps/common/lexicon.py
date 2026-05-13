from __future__ import annotations
from typing import Any, Dict, Tuple, Optional, List

import os
import logging

_NRC_CACHE: Dict[str, Any] = {"path": None, "lex": None, "emotions": ()}
logger = logging.getLogger(__name__)


def _cfg_get(cfg: Dict[str, Any], path: str, default: Optional[str] = None) -> Optional[str]:
    cur: Any = cfg
    for key in path.split('.'):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur if isinstance(cur, str) else default


def _find_nrc_file(dir_path: str) -> Optional[str]:
    try:
        for name in os.listdir(dir_path):
            if name.lower().endswith('.txt') and 'nrc' in name.lower():
                return os.path.join(dir_path, name)
    except Exception as e:
        logger.warning(
            "lexicon operation failed operation=%s dir_path=%s exc_type=%s exc=%s",
            "find_nrc_file",
            dir_path,
            type(e).__name__,
            e,
        )
        return None
    return None


def load_nrc(cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Dict[str, int]]], Tuple[str, ...]]:
    """Load NRC Emotion Lexicon into memory.

    Returns (lex, emotions)
      lex: dict word -> {emotion: 0/1}
      emotions: tuple of emotion labels present in the file
    """
    # Cached by path to avoid repeated loads across steps
    if _NRC_CACHE.get("lex") is not None:
        return _NRC_CACHE["lex"], _NRC_CACHE["emotions"]

    dir_path = _cfg_get(cfg, 'config.models.lexicons.nrc_emotion_dir')
    if not dir_path or not os.path.isdir(dir_path):
        logger.warning(
            "lexicon operation failed operation=%s reason=%s dir_path=%s",
            "load_nrc",
            "nrc_directory_not_found_or_invalid",
            dir_path,
        )
        return None, tuple()
    file_path = _find_nrc_file(dir_path)
    if not file_path or not os.path.isfile(file_path):
        logger.warning(
            "lexicon operation failed operation=%s reason=%s dir_path=%s",
            "load_nrc",
            "nrc_file_not_found",
            dir_path,
        )
        return None, tuple()

    emotions_set = []
    lex: Dict[str, Dict[str, int]] = {}
    try:
        # Expected format: word\temotion\t0|1
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) < 3:
                    continue
                w, emo, assoc = parts[0].strip(), parts[1].strip(), parts[2].strip()
                if not w or not emo:
                    continue
                try:
                    val = int(assoc)
                except Exception as e:
                    logger.warning(
                        "lexicon operation failed operation=%s file_path=%s assoc=%s exc_type=%s exc=%s",
                        "parse_association",
                        file_path,
                        assoc,
                        type(e).__name__,
                        e,
                    )
                    continue
                if emo not in emotions_set:
                    emotions_set.append(emo)
                d = lex.get(w)
                if d is None:
                    d = {}
                    lex[w] = d
                d[emo] = val
    except Exception as e:
        logger.warning(
            "lexicon operation failed operation=%s file_path=%s exc_type=%s exc=%s",
            "load_nrc",
            file_path,
            type(e).__name__,
            e,
        )
        return None, tuple()

    _NRC_CACHE.update({"path": dir_path, "lex": lex, "emotions": tuple(emotions_set)})
    return lex, tuple(emotions_set)


def _tokenize(text: str) -> List[str]:
    return [t.strip(".,!?;:\"'()[]{}<>").lower() for t in text.split() if t.strip()]


def score_nrc_emotions(text: str, cfg: Dict[str, Any]) -> Optional[Dict[str, float]]:
    lex, emotions = load_nrc(cfg)
    if not lex:
        logger.warning(
            "lexicon operation failed operation=%s reason=%s",
            "score_nrc_emotions",
            "lexicon_unavailable",
        )
        return None
    counts: Dict[str, int] = {e: 0 for e in emotions}
    tokens = _tokenize(text)
    for t in tokens:
        entry = lex.get(t)
        if not entry:
            continue
        for emo, assoc in entry.items():
            if assoc:
                counts[emo] = counts.get(emo, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return {e: 0.0 for e in emotions}
    return {e: (counts.get(e, 0) / total) for e in emotions}


def score_nrc_sentiment(text: str, cfg: Dict[str, Any]) -> Optional[Tuple[str, float]]:
    # Derive a polarity from NRC positive/negative categories if present
    emo_scores = score_nrc_emotions(text, cfg)
    if not emo_scores:
        logger.warning(
            "lexicon operation failed operation=%s reason=%s",
            "score_nrc_sentiment",
            "emotion_scores_unavailable",
        )
        return None
    pos = emo_scores.get('positive', 0.0)
    neg = emo_scores.get('negative', 0.0)
    if pos == 0.0 and neg == 0.0:
        return ("NEUTRAL", 0.5)
    if pos >= neg:
        # confidence scaled by difference
        conf = 0.5 + min(0.45, (pos - neg))
        return ("POSITIVE", float(f"{conf:.3f}"))
    else:
        conf = 0.5 + min(0.45, (neg - pos))
        return ("NEGATIVE", float(f"{conf:.3f}"))
