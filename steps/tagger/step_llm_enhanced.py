"""
LLM-Enhanced Tagger Step

Secondary / off-path perception surface.
This module supports the legacy Phase 2 LLM tagging workflow and dedicated
tests, but it is not part of the canonical scene-centric ingestion runtime.
The default ingestion path continues to rely on the standard tagger surfaces.
"""
from __future__ import annotations
from typing import Any, Dict, List
import logging
import re
import requests

logger = logging.getLogger(__name__)

_NER_PIPELINES: Dict[str, Any] = {}
_PLACEHOLDER_ENTITY_PATTERN = re.compile(r"^(?:SPEAKER|FACE)_\d+$", re.IGNORECASE)

try:
    from steps.common.tag_utils import (
        dedupe_tokens,
        is_valid_entity_token,
        is_valid_tag_token,
        normalize_entity_token,
        normalize_tag_token,
    )
except Exception as e:
    def dedupe_tokens(tokens):
        seen = set()
        deduped = []
        for token in tokens:
            if token is None:
                continue
            text = str(token).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)
        return deduped
    def is_valid_entity_token(token):
        return bool(str(token or "").strip())
    def is_valid_tag_token(token):
        return bool(str(token or "").strip())
    def normalize_entity_token(token):
        text = str(token or "").strip()
        return text or None
    def normalize_tag_token(token):
        text = str(token or "").strip()
        return text or None


def _get_ner_pipeline(model_id: str) -> Any:
    pipeline_obj = _NER_PIPELINES.get(model_id)
    if pipeline_obj is not None:
        return pipeline_obj
    from steps.common.model_provisioner import ensure_model_cached
    from steps.common.config_loader import load_configs
    
    try:
        offline_mode = load_configs({}).get("verification", {}).get("offline_mode", False)
    except Exception:
        offline_mode = False
        
    provision_result = ensure_model_cached(model_id, offline=offline_mode)
    if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
        raise OSError(f"Failed to provision NER model: {provision_result.error or 'reason unknown'}")
        
    local_path = provision_result.local_path
    
    from transformers import pipeline, logging as hf_logging
    hf_logging.set_verbosity_error()
    pipe = pipeline(
        "token-classification",
        model=local_path,
        local_files_only=True,
        aggregation_strategy="simple",
    )
    _NER_PIPELINES[model_id] = pipe
    return pipe


def _gather_text(item: Dict[str, Any]) -> str:
    """Gather all available text from item"""
    texts = []
    for k in ("transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            texts.append(v)
    return " ".join(texts)


def _usefulness_score(text: str) -> float:
    """Calculate usefulness score based on text content"""
    if not text:
        return 0.0
    tokens = [t for t in text.split() if len(t) > 3]
    keywords = sum(1 for t in tokens if t[0].isupper())
    return min(1.0, (len(tokens) / 200.0) + (keywords / 100.0))


def _extract_entities_transformers(text: str, cfg: Dict[str, Any]) -> List[str]:
    """Extract entities using transformer NER model"""
    try:
        model_id = (
            ((cfg.get("config", {}) or {}).get("tagger", {}) or {}).get("ner_model")
            or "dslim/bert-base-NER"
        )
        nlp = _get_ner_pipeline(model_id)
        ents = nlp(text)
        labels = []
        for e in ents:
            word = (e.get("word") or e.get("entity_group") or "").strip()
            if word:
                labels.append(word)
        return list(dict.fromkeys(labels))[:20]
    except Exception as e:
        logger.warning(f"NER extraction failed: {e}")
        return []


def _fallback_entities(text: str) -> List[str]:
    """Phrase-based fallback with basic scaffold suppression."""
    pattern = re.compile(r"\b(?:[A-Z][A-Za-z']{1,}(?:\s+[A-Z][A-Za-z']{1,})*|[A-Z]{2,})\b")
    matches: List[str] = []
    for match in pattern.finditer(text):
        normalized = normalize_entity_token(match.group(0))
        if not normalized or not is_valid_entity_token(normalized):
            continue
        if " " not in normalized:
            prefix = text[:match.start()]
            if not prefix.rstrip() or prefix.rstrip().endswith((".", "!", "?")):
                continue
        matches.append(normalized)
    return dedupe_tokens(matches)[:20]


def _sanitize_llm_values(values: Any, *, kind: str, limit: int) -> List[str]:
    if not isinstance(values, list):
        return []
    validator = is_valid_entity_token if kind == "entity" else is_valid_tag_token
    normalizer = normalize_entity_token if kind == "entity" else normalize_tag_token
    out: List[str] = []
    for value in dedupe_tokens(values, validator=validator, normalizer=normalizer):
        if _PLACEHOLDER_ENTITY_PATTERN.fullmatch(value):
            continue
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _extract_tags_llm(text: str, cfg: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Use LLM to extract intelligent tags, entities, and themes
    
    Returns:
        {
            'tags': List[str],
            'entities': List[str],
            'themes': List[str],
            'keywords': List[str],
            'method': 'llm'
        }
    """
    try:
        llm_config = cfg.get('config', {}).get('llm', {})
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 15)
        
        # Build context
        context_str = ""
        if context:
            caption = context.get('caption', '')
            emotions = context.get('emotions', [])
            if caption:
                context_str += f"\nVisual: {caption}"
            if emotions:
                context_str += f"\nEmotions: {', '.join([str(e) for e in emotions[:3]])}"
        
        # Build prompt
        prompt = f"""Analyze this content and extract structured information:

TEXT: {text[:500]}
{context_str}

Extract and return ONLY a JSON object with these fields:
- tags: 3-5 descriptive tags (topics, themes)
- entities: Named entities (people, places, organizations)
- themes: Key themes or subjects
- keywords: Important keywords

Example format:
{{
  "tags": ["family", "celebration", "outdoor"],
  "entities": ["John", "Chicago"],
  "themes": ["birthday party", "childhood memories"],
  "keywords": ["cake", "presents", "laughter"]
}}

JSON:"""
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a content analysis system. Extract structured metadata as JSON. Be concise and accurate."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 200,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # Try to parse JSON from response
            import json
            # Clean up common LLM response patterns
            content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                parsed = json.loads(content)
                return {
                    'tags': _sanitize_llm_values(parsed.get('tags', []), kind='tag', limit=5),
                    'entities': _sanitize_llm_values(parsed.get('entities', []), kind='entity', limit=20),
                    'themes': _sanitize_llm_values(parsed.get('themes', []), kind='tag', limit=10),
                    'keywords': _sanitize_llm_values(parsed.get('keywords', []), kind='tag', limit=15),
                    'method': 'llm'
                }
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM JSON response: {content[:100]}")
                return None
        else:
            logger.warning(f"LLM API returned status {response.status_code}")
            return None
            
    except requests.Timeout:
        logger.warning("LLM tagging request timed out")
        return None
    except Exception as e:
        logger.warning(f"LLM tagging failed: {e}")
        return None


def tagger_llm_enhanced(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced tagger with LLM support
    
    Tries LLM first for intelligent tagging, falls back to NER
    """
    text = _gather_text(item)
    if not text:
        return {
            "tags": [],
            "usefulness": 0.0,
            "entities": [],
            "themes": [],
            "keywords": [],
            "method": "none"
        }
    
    score = _usefulness_score(text)
    
    # Check if LLM tagging is enabled
    use_llm = cfg.get('config', {}).get('llm', {}).get('features', {}).get('intelligent_tagging', True)
    
    llm_result = None
    if use_llm:
        # Try LLM with context
        context = {
            'caption': item.get('caption', ''),
            'emotions': item.get('emotions', [])
        }
        llm_result = _extract_tags_llm(text, cfg, context)
    
    # Use LLM results if successful
    if llm_result:
        return {
            **llm_result,
            "usefulness": score
        }
    
    # Fall back to NER
    logger.info("Using NER fallback for tagging")
    ents = _extract_entities_transformers(text, cfg) or _fallback_entities(text)
    ents = dedupe_tokens(ents)
    tags = ents[:5]
    
    return {
        "tags": tags,
        "usefulness": score,
        "entities": ents,
        "themes": [],
        "keywords": tags,
        "method": "ner_fallback"
    }


# Alias for compatibility
tagger = tagger_llm_enhanced
