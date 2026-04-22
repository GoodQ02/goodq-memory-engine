"""
Phase 6: Multimodal Search Engine
Unified retrieval across text, visual, and audio modalities.
Enables semantic search over the complete GoodQ multimodal knowledge base.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import json
import logging
import numpy as np
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_data_root() -> str:
    explicit_data_root = os.environ.get("GOODQ_DATA_ROOT")
    if explicit_data_root:
        return explicit_data_root
    return str(Path("GoodQ_Data"))

_QUERY_STOPWORDS = {
    "a", "an", "and", "at", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with",
}
_QUERY_INTENT_ALIASES = {
    "angry": {"angry", "negative", "disgust", "complaint", "confrontation"},
    "annoyed": {"angry", "negative", "disgust", "complaint", "confrontation"},
    "awkward": {"surprise", "negative", "awkward", "greeting", "reunion"},
    "complain": {"angry", "negative", "disgust", "frustrated", "complaint", "confrontation"},
    "complaining": {"angry", "negative", "disgust", "frustrated", "complaint", "confrontation"},
    "complaint": {"angry", "negative", "disgust", "frustrated", "complaint", "confrontation"},
    "frustrated": {"angry", "negative", "disgust", "complaint", "confrontation"},
    "greet": {"greeting", "reunion", "awkward"},
    "greeting": {"greeting", "reunion", "awkward"},
    "happy": {"happy", "positive"},
    "romantic": {"happy", "positive"},
    "sad": {"sad", "negative"},
    "surprised": {"surprise", "reunion", "greeting"},
    "surprise": {"surprise", "reunion", "greeting"},
    "upset": {"angry", "negative", "sad", "complaint", "confrontation"},
}
_QUERY_INTENT_PREVIEW_HINTS = {
    "complaint_like": {
        "terms": {"angry", "annoyed", "complain", "complaining", "complaint", "frustrated", "upset"},
        "phrases": {
            "affected by",
            "no one has any interest",
            "wait a second",
            "what woman is coming in",
            "where were you",
            "why coming in",
            "why even",
        },
        "bonus": 0.045,
    },
    "awkward_social": {
        "terms": {"awkward", "greet", "greeting", "surprise"},
        "phrases": {
            "can't believe you're here",
            "good to see you",
            "hi!",
            "interesting greeting",
            "surprise blindfold greeting",
            "you're back",
        },
        "bonus": 0.04,
    },
}
_QUERY_ARTIFACT_TERMS = {
    "phone_call": {"call", "called", "caller", "calling", "hello", "hold", "phone"},
    "repeated_greeting": {"awkward", "greet", "greeting", "hello", "reunion", "surprise"},
    "ambient_reaction": {"ambient", "background", "crowd", "noise", "party", "reaction"},
}
_QUERY_GENERIC_SUBJECT_TERMS = set(_QUERY_INTENT_ALIASES).union(
    {
        "clip",
        "conversation",
        "dialogue",
        "episode",
        "film",
        "joke",
        "memory",
        "moment",
        "movie",
        "scene",
        "show",
        "story",
        "video",
    }
)
_QUERY_SOCIAL_INTENT_TERMS = {
    "angry",
    "annoyed",
    "awkward",
    "complain",
    "complaining",
    "complaint",
    "confrontation",
    "frustrated",
    "greet",
    "greeting",
    "negative",
    "reunion",
    "surprise",
    "upset",
}
_QUERY_CARRYOVER_TOKENS = {
    "and",
    "but",
    "he",
    "her",
    "him",
    "his",
    "look",
    "now",
    "she",
    "so",
    "still",
    "then",
    "they",
    "them",
    "their",
    "well",
    "you",
    "your",
}


class MultimodalSearchEngine:
    """
    Multimodal retrieval engine for GoodQ.
    Searches across text embeddings, scene visual embeddings, and audio embeddings.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize search engine with configuration.
        
        Args:
            config: GoodQ configuration dict
        """
        self.config = config
        qdrant_cfg = (config.get("qdrant") or {}) if isinstance(config, dict) else {}
        paths_cfg = (config.get("paths") or {}) if isinstance(config, dict) else {}
        phase6_cfg = (config.get("phase6") or {}) if isinstance(config, dict) else {}
        collections_cfg = (qdrant_cfg.get("collections") or {}) if isinstance(qdrant_cfg, dict) else {}

        self.qdrant_host = qdrant_cfg.get("host") or config.get("qdrant_host", "http://127.0.0.1:6333")
        self.data_root = paths_cfg.get("data_root") or config.get("data_root") or _default_data_root()
        self.processing_root = paths_cfg.get("processing") or os.path.join(self.data_root, "processing")
        self.kg_db_path = paths_cfg.get("knowledge_graph_db") or config.get("knowledge_graph_db")
        self.text_collection = collections_cfg.get("text") or "goodq_text"
        self.visual_collection = phase6_cfg.get("clip_collection") or collections_cfg.get("clip") or "goodq_clip_scenes"
        
        # Fusion weights
        fusion_cfg = config.get('phase6', {}).get('retrieval', {}).get('fusion_weights', {})
        self.weight_text = fusion_cfg.get('text', 0.5)
        self.weight_visual = fusion_cfg.get('visual', 0.4)
        self.weight_audio = fusion_cfg.get('audio', 0.1)
        
        # Lazy-load models and clients
        self._clip_model = None
        self._text_model = None
        self._qdrant_clients = {}
        self._kg_scene_context: Optional[Dict[str, Dict[str, Any]]] = None
        self._kg_scene_context_error = False

    def _tokenize_terms(self, value: Any) -> List[str]:
        if not isinstance(value, str):
            return []
        terms: List[str] = []
        for raw in re.findall(r"[A-Za-z0-9']+", value.lower()):
            token = raw.strip("'")
            if len(token) < 3 or token in _QUERY_STOPWORDS:
                continue
            terms.append(token)
            if token.endswith("ing") and len(token) > 5:
                terms.append(token[:-3])
            elif token.endswith("ed") and len(token) > 4:
                terms.append(token[:-2])
            elif token.endswith("es") and len(token) > 4:
                terms.append(token[:-2])
            elif token.endswith("s") and len(token) > 4:
                terms.append(token[:-1])
        deduped: List[str] = []
        seen = set()
        for term in terms:
            if term in seen:
                continue
            seen.add(term)
            deduped.append(term)
        return deduped

    def _tokenize_term_stream(self, value: Any) -> List[str]:
        if not isinstance(value, str):
            return []
        stream: List[str] = []
        for raw in re.findall(r"[A-Za-z0-9']+", value.lower()):
            token = raw.strip("'")
            if len(token) < 3 or token in _QUERY_STOPWORDS:
                continue
            stream.append(token)
            if token.endswith("ing") and len(token) > 5:
                stream.append(token[:-3])
            elif token.endswith("ed") and len(token) > 4:
                stream.append(token[:-2])
            elif token.endswith("es") and len(token) > 4:
                stream.append(token[:-2])
            elif token.endswith("s") and len(token) > 4:
                stream.append(token[:-1])
        return stream

    def _payload_term_sets(self, payload: Dict[str, Any]) -> Dict[str, set[str]]:
        def _list_terms(value: Any) -> set[str]:
            out: set[str] = set()
            if isinstance(value, list):
                for item in value:
                    out.update(self._tokenize_terms(item))
            elif isinstance(value, str):
                out.update(self._tokenize_terms(value))
            return out

        return {
            "entities": _list_terms(payload.get("entities")),
            "locations": _list_terms(payload.get("locations")),
            "tags": _list_terms(payload.get("tags")),
            "artifact_hints": _list_terms(payload.get("artifact_hints")),
            "dialogue_hints": _list_terms(payload.get("dialogue_hints")),
            "emotion": _list_terms(payload.get("emotion")),
            "sentiment": _list_terms(payload.get("sentiment")),
            "text_preview": _list_terms(payload.get("text_preview")),
        }

    def _extract_query_named_terms(self, query: str) -> set[str]:
        named_terms: set[str] = set()
        for raw in re.findall(r"[A-Za-z][A-Za-z0-9']*", query):
            token = raw.strip("'")
            if len(token) < 3 or not token[:1].isupper():
                continue
            lowered = token.lower()
            if lowered in _QUERY_STOPWORDS or lowered in _QUERY_GENERIC_SUBJECT_TERMS:
                continue
            named_terms.update(self._tokenize_terms(token))
        return named_terms

    def _expand_query_terms(self, query_terms: set[str]) -> set[str]:
        expanded = set(query_terms)
        for term in list(query_terms):
            expanded.update(_QUERY_INTENT_ALIASES.get(term, set()))
        return expanded

    def _load_kg_scene_context(self) -> Dict[str, Dict[str, Any]]:
        if isinstance(self._kg_scene_context, dict):
            return self._kg_scene_context
        if self._kg_scene_context_error:
            return {}
        if not isinstance(self.kg_db_path, str) or not self.kg_db_path.strip() or not os.path.isfile(self.kg_db_path):
            self._kg_scene_context_error = True
            return {}

        scene_context: Dict[str, Dict[str, Any]] = {}
        try:
            conn = sqlite3.connect(self.kg_db_path)
            cur = conn.cursor()
            rows = cur.execute(
                """
                SELECT
                    e.edge_type,
                    e.properties,
                    src.name,
                    src.node_type,
                    tgt.name,
                    tgt.node_type
                FROM edges e
                JOIN nodes src ON src.id = e.source_id
                JOIN nodes tgt ON tgt.id = e.target_id
                WHERE e.edge_type IN ('appears_in', 'located_in', 'interacts_with')
                """
            ).fetchall()
        except Exception as e:
            logger.warning("KG scene context unavailable: %s", e)
            self._kg_scene_context_error = True
            return {}
        finally:
            try:
                conn.close()
            except Exception:
                pass

        for edge_type, raw_props, src_name, src_type, tgt_name, tgt_type in rows:
            props: Dict[str, Any] = {}
            if isinstance(raw_props, str) and raw_props.strip():
                try:
                    props = json.loads(raw_props)
                except Exception:
                    props = {}
            scene_id = props.get("scene_id")
            if not isinstance(scene_id, str) or not scene_id.strip():
                continue
            context = scene_context.setdefault(
                scene_id,
                {
                    "appears_in": set(),
                    "located_in": set(),
                    "interacts_with": [],
                },
            )
            if edge_type == "appears_in":
                if src_type == "person":
                    context["appears_in"].update(self._tokenize_terms(src_name))
                elif tgt_type == "person":
                    context["appears_in"].update(self._tokenize_terms(tgt_name))
            elif edge_type == "located_in":
                if src_type == "location":
                    context["located_in"].update(self._tokenize_terms(src_name))
                elif tgt_type == "location":
                    context["located_in"].update(self._tokenize_terms(tgt_name))
            elif edge_type == "interacts_with":
                source_terms = set(self._tokenize_terms(src_name))
                target_terms = set(self._tokenize_terms(tgt_name))
                if source_terms and target_terms:
                    context["interacts_with"].append((source_terms, target_terms))

        self._kg_scene_context = scene_context
        return scene_context

    def _kg_context_bonus(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
    ) -> float:
        scene_id = payload.get("scene_id")
        if not isinstance(scene_id, str) or not scene_id.strip():
            return 0.0

        scene_context = self._load_kg_scene_context().get(scene_id)
        if not isinstance(scene_context, dict):
            return 0.0

        bonus = 0.0
        if query_named_terms:
            appears_in = scene_context.get("appears_in") or set()
            located_in = scene_context.get("located_in") or set()
            person_matches = query_named_terms.intersection(appears_in)
            location_matches = query_named_terms.intersection(located_in)
            if person_matches:
                bonus += min(0.018 * len(person_matches), 0.036)
            if location_matches:
                bonus += min(0.015 * len(location_matches), 0.03)

            if expanded_query_terms.intersection(_QUERY_SOCIAL_INTENT_TERMS) and person_matches:
                interactions = scene_context.get("interacts_with") or []
                for source_terms, target_terms in interactions:
                    if person_matches.intersection(source_terms.union(target_terms)):
                        bonus += 0.015
                        break

        return min(bonus, 0.06)

    def _intent_preview_bonus(self, query_terms: set[str], payload: Dict[str, Any]) -> float:
        preview = payload.get("text_preview")
        if not isinstance(preview, str) or not preview.strip():
            return 0.0

        lowered_preview = preview.lower()
        bonus = 0.0
        for group in _QUERY_INTENT_PREVIEW_HINTS.values():
            terms = group.get("terms")
            phrases = group.get("phrases")
            group_bonus = group.get("bonus", 0.0)
            if not isinstance(terms, set) or not isinstance(phrases, set):
                continue
            if not query_terms.intersection(terms):
                continue
            if any(phrase in lowered_preview for phrase in phrases):
                bonus += float(group_bonus)
        return min(bonus, 0.12)

    def _artifact_penalty(self, query_terms: set[str], payload: Dict[str, Any]) -> float:
        artifact_hints = payload.get("artifact_hints")
        if not isinstance(artifact_hints, list):
            return 0.0

        penalty = 0.0
        for hint in artifact_hints:
            if not isinstance(hint, str) or not hint.strip():
                continue
            allowed_terms = _QUERY_ARTIFACT_TERMS.get(hint)
            if allowed_terms and query_terms.intersection(allowed_terms):
                continue
            if hint == "phone_call":
                penalty += 0.03
            elif hint == "repeated_greeting":
                penalty += 0.02
            elif hint == "ambient_reaction":
                penalty += 0.02
        return min(penalty, 0.06)

    def _named_entity_specificity_adjustment(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
        payload_terms: Dict[str, set[str]],
    ) -> float:
        if not query_named_terms:
            return 0.0

        indexed_subject_terms = payload_terms["entities"].union(payload_terms["locations"])
        matched_terms = query_named_terms.intersection(indexed_subject_terms)
        if matched_terms:
            subject_pool_size = max(len(indexed_subject_terms), 1)
            subject_dominance = len(matched_terms) / float(subject_pool_size)
            adjustment = (0.02 * len(matched_terms)) + (0.04 * subject_dominance)
            if payload_terms["dialogue_hints"].intersection(expanded_query_terms):
                adjustment += 0.015 * subject_dominance
            preview = payload.get("text_preview")
            preview_terms = set(self._tokenize_terms(preview)) if isinstance(preview, str) else set()
            preview_matches = query_named_terms.intersection(preview_terms)
            if preview_matches:
                preview_ratio = len(preview_matches) / float(max(len(query_named_terms), 1))
                adjustment += 0.01 * preview_ratio
                if payload_terms["dialogue_hints"].intersection(expanded_query_terms):
                    adjustment += 0.01 * preview_ratio
            else:
                adjustment -= 0.015
            return min(adjustment, 0.08)

        penalty = 0.035
        if payload_terms["artifact_hints"]:
            penalty += 0.015
        elif payload_terms["dialogue_hints"]:
            penalty += 0.01
        return -min(penalty, 0.05)

    def _dialogue_focus_bonus(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
        payload_terms: Dict[str, set[str]],
    ) -> float:
        if not query_named_terms or not expanded_query_terms.intersection(_QUERY_SOCIAL_INTENT_TERMS):
            return 0.0

        entity_terms = payload_terms["entities"]
        if not entity_terms:
            return 0.0

        matched_subject_terms = query_named_terms.intersection(entity_terms)
        if not matched_subject_terms:
            return 0.0

        preview = payload.get("text_preview")
        if not isinstance(preview, str) or not preview.strip():
            return 0.0

        preview_counts: Dict[str, int] = {}
        for term in self._tokenize_term_stream(preview):
            preview_counts[term] = preview_counts.get(term, 0) + 1

        matched_mentions = sum(preview_counts.get(term, 0) for term in matched_subject_terms)
        total_entity_mentions = sum(preview_counts.get(term, 0) for term in entity_terms)
        intent_aligned = bool(payload_terms["dialogue_hints"].intersection(expanded_query_terms))

        if matched_mentions <= 0:
            return -0.015 if intent_aligned else -0.01

        focus_ratio = matched_mentions / float(max(total_entity_mentions, matched_mentions))
        bonus = 0.02 + (0.03 * focus_ratio)
        if intent_aligned:
            bonus += 0.015 * focus_ratio
        if payload_terms["artifact_hints"]:
            bonus -= 0.005
        return max(min(bonus, 0.055), -0.02)

    def _subject_role_bonus(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
        payload_terms: Dict[str, set[str]],
    ) -> float:
        if not query_named_terms or not expanded_query_terms.intersection(_QUERY_SOCIAL_INTENT_TERMS):
            return 0.0

        entity_terms = payload_terms["entities"]
        matched_subject_terms = query_named_terms.intersection(entity_terms)
        if not matched_subject_terms:
            return 0.0

        preview = payload.get("text_preview")
        if not isinstance(preview, str) or not preview.strip():
            return 0.0

        preview_counts: Dict[str, int] = {}
        for term in self._tokenize_term_stream(preview):
            preview_counts[term] = preview_counts.get(term, 0) + 1

        matched_mentions = sum(preview_counts.get(term, 0) for term in matched_subject_terms)
        if matched_mentions <= 0:
            return 0.0

        other_entity_terms = entity_terms.difference(matched_subject_terms)
        other_mentions = sum(preview_counts.get(term, 0) for term in other_entity_terms)
        matched_entity_count = len(matched_subject_terms)
        total_entity_count = len(entity_terms)
        intent_aligned = bool(payload_terms["dialogue_hints"].intersection(expanded_query_terms))

        bonus = 0.0
        if total_entity_count <= matched_entity_count:
            bonus += 0.018
        elif other_mentions <= 0:
            bonus += 0.014
        elif matched_mentions > other_mentions:
            bonus += 0.01
        elif matched_mentions == other_mentions and total_entity_count <= matched_entity_count + 1:
            bonus += 0.006

        if intent_aligned and total_entity_count <= matched_entity_count + 1:
            bonus += 0.008
        if payload_terms["artifact_hints"]:
            bonus -= 0.004
        return max(min(bonus, 0.03), 0.0)

    def _dialogue_proximity_bonus(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
        payload_terms: Dict[str, set[str]],
    ) -> float:
        if not query_named_terms or not expanded_query_terms.intersection(_QUERY_SOCIAL_INTENT_TERMS):
            return 0.0

        preview = payload.get("text_preview")
        if not isinstance(preview, str) or not preview.strip():
            return 0.0

        intent_terms = expanded_query_terms.difference(query_named_terms)
        relevant_phrases: set[str] = set()
        for group in _QUERY_INTENT_PREVIEW_HINTS.values():
            terms = group.get("terms")
            phrases = group.get("phrases")
            if not isinstance(terms, set) or not isinstance(phrases, set):
                continue
            if intent_terms.intersection(terms):
                relevant_phrases.update(phrases)
        if not intent_terms and not relevant_phrases:
            return 0.0

        clauses = [part.strip().lower() for part in re.split(r"[.!?;:\n]+", preview) if part.strip()]
        if not clauses:
            return 0.0

        subject_clause_indexes: List[int] = []
        intent_clause_indexes: List[int] = []
        for idx, clause in enumerate(clauses):
            clause_terms = set(self._tokenize_terms(clause))
            if query_named_terms.intersection(clause_terms):
                subject_clause_indexes.append(idx)
            if intent_terms.intersection(clause_terms) or any(phrase in clause for phrase in relevant_phrases):
                intent_clause_indexes.append(idx)

        if not subject_clause_indexes or not intent_clause_indexes:
            return 0.0

        min_clause_distance = min(abs(subject_idx - intent_idx) for subject_idx in subject_clause_indexes for intent_idx in intent_clause_indexes)
        intent_aligned = bool(payload_terms["dialogue_hints"].intersection(expanded_query_terms))

        if min_clause_distance == 0:
            bonus = 0.028
        elif min_clause_distance == 1:
            bonus = 0.018
        elif min_clause_distance == 2:
            bonus = 0.008
        else:
            bonus = 0.0

        if intent_aligned and min_clause_distance <= 1:
            bonus += 0.01
        if payload_terms["artifact_hints"]:
            bonus -= 0.005
        return max(min(bonus, 0.04), 0.0)

    def _subject_carryover_bonus(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
        payload_terms: Dict[str, set[str]],
    ) -> float:
        if not query_named_terms or not expanded_query_terms.intersection(_QUERY_SOCIAL_INTENT_TERMS):
            return 0.0

        preview = payload.get("text_preview")
        if not isinstance(preview, str) or not preview.strip():
            return 0.0

        intent_terms = expanded_query_terms.difference(query_named_terms)
        relevant_phrases: set[str] = set()
        for group in _QUERY_INTENT_PREVIEW_HINTS.values():
            terms = group.get("terms")
            phrases = group.get("phrases")
            if not isinstance(terms, set) or not isinstance(phrases, set):
                continue
            if intent_terms.intersection(terms):
                relevant_phrases.update(phrases)
        if not intent_terms and not relevant_phrases:
            return 0.0

        clauses = [part.strip().lower() for part in re.split(r"[.!?;:\n]+", preview) if part.strip()]
        if not clauses:
            return 0.0

        subject_clause_indexes: List[int] = []
        intent_clause_indexes: List[int] = []
        clause_raw_tokens: Dict[int, set[str]] = {}
        for idx, clause in enumerate(clauses):
            clause_terms = set(self._tokenize_terms(clause))
            raw_tokens = set(re.findall(r"[a-z']+", clause))
            clause_raw_tokens[idx] = raw_tokens
            if query_named_terms.intersection(clause_terms):
                subject_clause_indexes.append(idx)
            if intent_terms.intersection(clause_terms) or any(phrase in clause for phrase in relevant_phrases):
                intent_clause_indexes.append(idx)

        if not subject_clause_indexes or not intent_clause_indexes:
            return 0.0

        intent_aligned = bool(payload_terms["dialogue_hints"].intersection(expanded_query_terms))
        best_bonus = 0.0
        for intent_idx in intent_clause_indexes:
            nearest_subject_idx = min(subject_clause_indexes, key=lambda subject_idx: abs(subject_idx - intent_idx))
            clause_distance = abs(nearest_subject_idx - intent_idx)
            if clause_distance <= 1 or clause_distance > 4:
                continue

            bridge_start = min(nearest_subject_idx, intent_idx)
            bridge_end = max(nearest_subject_idx, intent_idx)
            bridge_has_carryover = any(
                clause_raw_tokens.get(idx, set()).intersection(_QUERY_CARRYOVER_TOKENS)
                for idx in range(bridge_start, bridge_end + 1)
            )
            if not bridge_has_carryover:
                continue

            if clause_distance == 2:
                bonus = 0.012
            elif clause_distance == 3:
                bonus = 0.009
            else:
                bonus = 0.006

            if intent_aligned:
                bonus += 0.004
            best_bonus = max(best_bonus, bonus)

        if payload_terms["artifact_hints"]:
            best_bonus -= 0.004
        return max(min(best_bonus, 0.02), 0.0)

    def _clause_salience_bonus(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
        payload_terms: Dict[str, set[str]],
    ) -> float:
        if not query_named_terms or not expanded_query_terms.intersection(_QUERY_SOCIAL_INTENT_TERMS):
            return 0.0

        preview = payload.get("text_preview")
        if not isinstance(preview, str) or not preview.strip():
            return 0.0

        intent_terms = expanded_query_terms.difference(query_named_terms)
        relevant_phrases: set[str] = set()
        for group in _QUERY_INTENT_PREVIEW_HINTS.values():
            terms = group.get("terms")
            phrases = group.get("phrases")
            if not isinstance(terms, set) or not isinstance(phrases, set):
                continue
            if intent_terms.intersection(terms):
                relevant_phrases.update(phrases)
        if not intent_terms and not relevant_phrases:
            return 0.0

        clauses = [part.strip().lower() for part in re.split(r"[.!?;:\n]+", preview) if part.strip()]
        if not clauses:
            return 0.0

        clause_data: List[Dict[str, Any]] = []
        for clause in clauses:
            clause_terms = set(self._tokenize_terms(clause))
            phrase_hits = sum(1 for phrase in relevant_phrases if phrase in clause)
            clause_data.append(
                {
                    "terms": clause_terms,
                    "subject_hits": len(query_named_terms.intersection(clause_terms)),
                    "intent_hits": len(intent_terms.intersection(clause_terms)),
                    "phrase_hits": phrase_hits,
                    "term_count": max(len(clause_terms), 1),
                }
            )

        best_bonus = 0.0
        intent_aligned = bool(payload_terms["dialogue_hints"].intersection(expanded_query_terms))
        for idx, clause in enumerate(clause_data):
            local_subject_hits = clause["subject_hits"]
            if local_subject_hits <= 0:
                if idx > 0:
                    local_subject_hits += 0.5 * clause_data[idx - 1]["subject_hits"]
                if idx + 1 < len(clause_data):
                    local_subject_hits += 0.5 * clause_data[idx + 1]["subject_hits"]

            intent_signal = clause["intent_hits"] + (1.25 * clause["phrase_hits"])
            if local_subject_hits <= 0 or intent_signal <= 0:
                continue

            density = min((local_subject_hits + intent_signal) / float(clause["term_count"]), 1.0)
            bonus = 0.008 + (0.006 * min(local_subject_hits, 2.0)) + (0.008 * min(intent_signal, 2.0))
            bonus += 0.01 * density

            if clause["subject_hits"] > 0 and (clause["intent_hits"] > 0 or clause["phrase_hits"] > 0):
                bonus += 0.008
            elif clause["subject_hits"] <= 0:
                bonus -= 0.004

            if intent_aligned:
                bonus += 0.004
            best_bonus = max(best_bonus, bonus)

        if payload_terms["artifact_hints"]:
            best_bonus -= 0.004
        return max(min(best_bonus, 0.032), 0.0)

    def _metadata_bonus(self, query: str, payload: Dict[str, Any]) -> float:
        query_terms = set(self._tokenize_terms(query))
        if not query_terms:
            return 0.0
        expanded_query_terms = self._expand_query_terms(query_terms)
        query_named_terms = self._extract_query_named_terms(query)
        payload_terms = self._payload_term_sets(payload)
        bonus = 0.0
        bonus += 0.08 * len(query_terms.intersection(payload_terms["entities"]))
        bonus += 0.05 * len(query_terms.intersection(payload_terms["locations"]))
        bonus += 0.03 * len(query_terms.intersection(payload_terms["tags"]))
        bonus += 0.04 * len(expanded_query_terms.intersection(payload_terms["dialogue_hints"]))
        bonus += 0.03 * len(expanded_query_terms.intersection(payload_terms["emotion"]))
        bonus += 0.02 * len(expanded_query_terms.intersection(payload_terms["sentiment"]))
        bonus += 0.01 * len(query_terms.intersection(payload_terms["text_preview"]))
        bonus += self._intent_preview_bonus(query_terms, payload)
        bonus += self._named_entity_specificity_adjustment(query_named_terms, expanded_query_terms, payload, payload_terms)
        bonus += self._dialogue_focus_bonus(query_named_terms, expanded_query_terms, payload, payload_terms)
        bonus += self._subject_role_bonus(query_named_terms, expanded_query_terms, payload, payload_terms)
        bonus += self._dialogue_proximity_bonus(query_named_terms, expanded_query_terms, payload, payload_terms)
        bonus += self._subject_carryover_bonus(query_named_terms, expanded_query_terms, payload, payload_terms)
        bonus += self._clause_salience_bonus(query_named_terms, expanded_query_terms, payload, payload_terms)
        bonus += self._kg_context_bonus(query_named_terms, expanded_query_terms, payload)
        bonus -= self._artifact_penalty(expanded_query_terms, payload)
        return max(min(bonus, 0.25), -0.06)

    def _subject_focus_profile(
        self,
        query_named_terms: set[str],
        expanded_query_terms: set[str],
        payload: Dict[str, Any],
        payload_terms: Dict[str, set[str]],
    ) -> Dict[str, Any]:
        indexed_subject_terms = payload_terms["entities"].union(payload_terms["locations"])
        matched_terms = query_named_terms.intersection(indexed_subject_terms)
        if not matched_terms:
            return {
                "matched_terms": set(),
                "subject_dominance": 0.0,
                "preview_subject_mentions": 0,
                "preview_focus_ratio": 0.0,
                "intent_aligned": False,
                "artifact_count": 0,
                "focus_strength": 0.0,
            }

        preview = payload.get("text_preview")
        preview_counts: Dict[str, int] = {}
        if isinstance(preview, str) and preview.strip():
            for term in self._tokenize_term_stream(preview):
                preview_counts[term] = preview_counts.get(term, 0) + 1

        preview_subject_mentions = sum(preview_counts.get(term, 0) for term in matched_terms)
        total_entity_mentions = sum(preview_counts.get(term, 0) for term in payload_terms["entities"])
        subject_dominance = len(matched_terms) / float(max(len(indexed_subject_terms), 1))
        preview_focus_ratio = preview_subject_mentions / float(
            max(total_entity_mentions, preview_subject_mentions, 1)
        )
        intent_aligned = bool(payload_terms["dialogue_hints"].intersection(expanded_query_terms))
        artifact_count = len(payload_terms["artifact_hints"])

        focus_strength = (0.45 * subject_dominance) + (0.35 * preview_focus_ratio)
        if preview_subject_mentions > 0:
            focus_strength += 0.12
        if intent_aligned:
            focus_strength += 0.08
        if artifact_count:
            focus_strength -= 0.05

        return {
            "matched_terms": matched_terms,
            "subject_dominance": subject_dominance,
            "preview_subject_mentions": preview_subject_mentions,
            "preview_focus_ratio": preview_focus_ratio,
            "intent_aligned": intent_aligned,
            "artifact_count": artifact_count,
            "focus_strength": max(min(focus_strength, 1.0), 0.0),
        }

    def _apply_subject_focus_rerank(self, query: str, fused_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(fused_results) < 2:
            return fused_results

        query_terms = set(self._tokenize_terms(query))
        if not query_terms:
            return fused_results

        expanded_query_terms = self._expand_query_terms(query_terms)
        query_named_terms = self._extract_query_named_terms(query)
        if not query_named_terms or not expanded_query_terms.intersection(_QUERY_SOCIAL_INTENT_TERMS):
            return fused_results

        profiled_results: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        best_focus_strength = 0.0
        for result in fused_results:
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
            payload_terms = self._payload_term_sets(payload)
            profile = self._subject_focus_profile(query_named_terms, expanded_query_terms, payload, payload_terms)
            profiled_results.append((result, profile))
            if profile["matched_terms"]:
                best_focus_strength = max(best_focus_strength, float(profile["focus_strength"]))

        if best_focus_strength < 0.45:
            return fused_results

        for result, profile in profiled_results:
            if not profile["matched_terms"]:
                continue
            if profile["focus_strength"] >= best_focus_strength - 0.04:
                continue
            if profile["subject_dominance"] >= 0.45 and profile["preview_subject_mentions"] > 0:
                continue

            penalty = 0.0
            if profile["subject_dominance"] < 0.25:
                penalty += 0.016
            elif profile["subject_dominance"] < 0.4:
                penalty += 0.01

            if profile["preview_subject_mentions"] <= 0:
                penalty += 0.012
            elif profile["preview_focus_ratio"] < 0.34:
                penalty += 0.006

            if not profile["intent_aligned"]:
                penalty += 0.004
            if profile["artifact_count"]:
                penalty += 0.004

            focus_gap = max(best_focus_strength - float(profile["focus_strength"]), 0.0)
            gap_scale = min(max(focus_gap / 0.35, 0.35), 1.0)
            penalty *= gap_scale
            if penalty <= 0.0:
                continue

            result["score"] = float(result.get("score", 0.0)) - min(penalty, 0.03)

        fused_results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return fused_results

    def _result_scene_key(self, result: Dict[str, Any]) -> Tuple[str, str]:
        payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        video_id = payload.get("video_id") or payload.get("video_hash") or result.get("id") or "unknown_video"
        scene_id = payload.get("scene_id") or payload.get("scene_index") or result.get("id") or "unknown_scene"
        return str(video_id), str(scene_id)

    def _fuse_scene_results(self, query: str, results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        fused: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for result in results:
            key = self._result_scene_key(result)
            modality = str(result.get("modality") or "unknown")
            score = float(result.get("score") or 0.0)
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
            entry = fused.get(key)
            if entry is None:
                entry = {
                    "id": result.get("id"),
                    "score": 0.0,
                    "payload": payload,
                    "modality": modality,
                    "modalities": set(),
                    "modality_scores": {},
                    "raw_results": [],
                    "_best_component_score": float("-inf"),
                }
                fused[key] = entry

            previous = entry["modality_scores"].get(modality)
            if previous is None or score > previous:
                if previous is not None:
                    entry["score"] -= float(previous)
                entry["score"] += score
                entry["modality_scores"][modality] = score
            if score >= float(entry["_best_component_score"]):
                entry["_best_component_score"] = score
                entry["payload"] = payload
                entry["id"] = result.get("id")
                entry["modality"] = modality

            entry["modalities"].add(modality)
            entry["raw_results"].append(
                {
                    "id": result.get("id"),
                    "modality": modality,
                    "score": score,
                    "payload": payload,
                }
            )

        fused_results: List[Dict[str, Any]] = []
        for entry in fused.values():
            entry["modalities"] = sorted(entry["modalities"])
            entry["raw_results"].sort(key=lambda item: item.get("score", 0.0), reverse=True)
            entry.pop("_best_component_score", None)
            fused_results.append(entry)

        fused_results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        fused_results = self._apply_subject_focus_rerank(query, fused_results)
        return fused_results[:top_k]
    
    def _load_clip_model(self):
        """Load CLIP model for text encoding."""
        if self._clip_model is not None:
            return
        
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
            
            processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16").eval()
            
            self._clip_model = {'model': model, 'processor': processor}
            logger.info("[OK] CLIP model loaded for text encoding")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
    
    def _load_text_model(self):
        """Load sentence transformer for text encoding."""
        if self._text_model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer('all-MiniLM-L6-v2')
            self._text_model = model
            logger.info("[OK] Text embedding model loaded")
        except Exception as e:
            logger.error(f"Failed to load text model: {e}")
    
    def _get_qdrant_client(self, collection: str):
        """Get or create Qdrant client for collection."""
        if collection in self._qdrant_clients:
            return self._qdrant_clients[collection]
        
        from steps.common.qdrant_client import QdrantClient, QdrantConfig

        paths = (self.config.get("paths") or {}) if isinstance(self.config, dict) else {}
        db_path = paths.get("db_path") if isinstance(paths, dict) else None
        log_retrieval = True
        try:
            from steps.common.retrieval_events import retrieval_events_enabled

            log_retrieval = retrieval_events_enabled(self.config, default=True)
        except Exception:
            log_retrieval = True
        
        # Determine dimension based on collection type
        dim = 512 if 'clip' in collection else 384  # CLIP: 512, SBERT: 384, DINO: 768
        if 'dino' in collection:
            dim = 768
        
        client = QdrantClient(QdrantConfig(
            host=self.qdrant_host,
            collection=collection,
            dim=dim,
            distance='Cosine',
            db_path=db_path,
            log_retrieval_events=log_retrieval,
        ))
        
        self._qdrant_clients[collection] = client
        return client
    
    def encode_text_query(self, query: str) -> np.ndarray:
        """
        Encode text query using sentence transformer.
        
        Args:
            query: Search query string
            
        Returns:
            Query embedding vector
        """
        self._load_text_model()
        
        if self._text_model is None:
            logger.error("Text model unavailable")
            return np.zeros(384)
        
        embedding = self._text_model.encode([query])[0]
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding
    
    def encode_text_for_visual_search(self, query: str) -> np.ndarray:
        """
        Encode text query for visual similarity search using CLIP.
        
        Args:
            query: Search query string
            
        Returns:
            CLIP text embedding vector
        """
        self._load_clip_model()
        
        if self._clip_model is None:
            logger.error("CLIP model unavailable")
            return np.zeros(512)
        
        import torch
        
        model = self._clip_model['model']
        processor = self._clip_model['processor']
        
        inputs = processor(text=[query], return_tensors="pt", padding=True)
        
        with torch.no_grad():
            text_features = model.get_text_features(**inputs)
            embedding = text_features.cpu().numpy()[0]
        
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding
    
    def search_text(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search text embeddings (transcripts, captions, etc.).
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of search results with scores
        """
        logger.info(f"Searching text: '{query}'")
        
        query_embedding = self.encode_text_query(query)
        if not np.any(query_embedding):
            logger.warning("Text search skipped because query embedding is unavailable")
            return []
        
        client = self._get_qdrant_client(self.text_collection)
        results = client.query(query_embedding.tolist(), top_k=top_k)
        
        return results
    
    def search_visual(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search visual scene embeddings using text query.
        
        Args:
            query: Text description of visual content
            top_k: Number of results to return
            
        Returns:
            List of search results with scores
        """
        logger.info(f"Searching visual scenes: '{query}'")
        
        query_embedding = self.encode_text_for_visual_search(query)
        if not np.any(query_embedding):
            logger.warning("Visual search skipped because CLIP query encoding is unavailable")
            return []
        
        client = self._get_qdrant_client(self.visual_collection)
        results = client.query(query_embedding.tolist(), top_k=top_k)
        
        return results
    
    def search_multimodal(
        self,
        query: str,
        top_k: int = 10,
        modalities: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Unified multimodal search with fusion across modalities.
        
        Args:
            query: Search query
            top_k: Total number of results to return
            modalities: List of modalities to search ['text', 'visual', 'audio']
                       If None, searches all available modalities
            
        Returns:
            Fused and ranked search results
        """
        if modalities is None:
            modalities = ['text', 'visual']
        
        logger.info(f"Multimodal search: '{query}' across {modalities}")
        
        all_results = []
        per_modality_top_k = max(int(top_k), 5) * 2
        
        # Search text modality
        if 'text' in modalities and self.weight_text > 0:
            text_results = self.search_text(query, top_k=per_modality_top_k)
            for result in text_results:
                result['modality'] = 'text'
                payload = result.get('payload') if isinstance(result.get('payload'), dict) else {}
                result['score'] = (result.get('score', 0.0) * self.weight_text) + self._metadata_bonus(query, payload)
                all_results.append(result)
        
        # Search visual modality
        if 'visual' in modalities and self.weight_visual > 0:
            visual_results = self.search_visual(query, top_k=per_modality_top_k)
            for result in visual_results:
                result['modality'] = 'visual'
                result['score'] = result.get('score', 0.0) * self.weight_visual
                all_results.append(result)
        
        # TODO: Search audio modality (CLAP embeddings)
        # if 'audio' in modalities and self.weight_audio > 0:
        #     audio_results = self.search_audio(query, top_k=top_k)
        #     ...
        
        # Fuse and rank results
        return self._fuse_scene_results(query, all_results, top_k=top_k)
    
    def retrieve_scene_context(self, video_id: str, scene_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve full multimodal context for a specific scene.
        
        Args:
            video_id: Video identifier
            scene_id: Scene identifier
            
        Returns:
            Complete scene metadata including all modalities
        """
        temporal_index_path = os.path.join(
            self.processing_root,
            video_id,
            'temporal_index.json'
        )
        
        if not os.path.exists(temporal_index_path):
            logger.warning(f"Temporal index not found: {temporal_index_path}")
            return None
        
        with open(temporal_index_path, 'r', encoding='utf-8') as f:
            temporal_index = json.load(f)
        
        # Find matching scene
        for segment in temporal_index.get('segments', []):
            if segment.get('scene_id') == scene_id:
                return segment
        
        return None

    def _scene_object_labels(self, scene_context: Dict[str, Any]) -> List[str]:
        labels = scene_context.get("objects")
        if isinstance(labels, list) and labels:
            return [str(label) for label in labels if label]

        detected_objects = scene_context.get("detected_objects")
        if isinstance(detected_objects, list):
            extracted: List[str] = []
            for obj in detected_objects:
                if not isinstance(obj, dict):
                    continue
                label = obj.get("label")
                if label:
                    extracted.append(str(label))
            return extracted

        return []

    def build_scene_similarity_query(self, scene_context: Dict[str, Any]) -> str:
        """Build a compact semantic query from persisted scene memory."""
        phrases: List[str] = []
        seen: set[str] = set()

        def _add_phrase(value: Any) -> None:
            if not isinstance(value, str):
                return
            phrase = value.strip()
            if not phrase:
                return
            lowered = phrase.lower()
            if lowered in seen:
                return
            seen.add(lowered)
            phrases.append(phrase)

        def _add_many(values: Any, limit: int) -> None:
            if not isinstance(values, list):
                return
            count = 0
            for item in values:
                if not isinstance(item, str):
                    continue
                _add_phrase(item)
                count += 1
                if count >= limit:
                    break

        _add_many(scene_context.get("primary_tags"), limit=3)
        _add_many(scene_context.get("dialogue_topics"), limit=3)
        _add_many(scene_context.get("keywords"), limit=4)
        _add_phrase(scene_context.get("narrative_summary"))
        _add_phrase(scene_context.get("activity_description"))
        _add_phrase(scene_context.get("audio_emotion"))
        _add_many(self._scene_object_labels(scene_context), limit=3)

        if not phrases:
            transcript = scene_context.get("full_transcript")
            if isinstance(transcript, str) and transcript.strip():
                _add_phrase(" ".join(transcript.split()[:20]))

        return ". ".join(phrases[:8])

    def search_similar_scene(self, video_id: str, scene_id: int, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for semantically similar scenes using persisted scene memory as the query source."""
        source_context = self.retrieve_scene_context(video_id, scene_id)
        if not isinstance(source_context, dict):
            return []

        query = self.build_scene_similarity_query(source_context)
        if not query:
            return []

        candidate_limit = max((top_k * 3), top_k + 4)
        raw_results = self.search_multimodal(query, top_k=candidate_limit, modalities=["text", "visual"])

        filtered_results: List[Dict[str, Any]] = []
        seen_scene_keys: set[Tuple[str, str]] = set()
        source_scene_key = (str(video_id), str(scene_id))

        for result in raw_results:
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
            result_video_id = payload.get("video_id")
            result_scene_id = payload.get("scene_id")
            if result_video_id is None or result_scene_id is None:
                continue

            scene_key = (str(result_video_id), str(result_scene_id))
            if scene_key == source_scene_key or scene_key in seen_scene_keys:
                continue

            try:
                scene_id_int = int(result_scene_id)
            except (TypeError, ValueError):
                continue

            scene_context = self.retrieve_scene_context(str(result_video_id), scene_id_int)
            enriched_result = dict(result)
            if isinstance(scene_context, dict):
                enriched_result["scene_context"] = scene_context

            filtered_results.append(enriched_result)
            seen_scene_keys.add(scene_key)

            if len(filtered_results) >= top_k:
                break

        return filtered_results


def multimodal_search(query: str, config: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Main entry point for multimodal search.
    
    Args:
        query: Search query string
        config: GoodQ configuration
        top_k: Number of results to return
        
    Returns:
        List of search results across all modalities
    """
    engine = MultimodalSearchEngine(config)
    results = engine.search_multimodal(query, top_k=top_k)
    
    # Enrich results with full context
    enriched_results = []
    for result in results:
        payload = result.get('payload', {})
        video_id = payload.get('video_id')
        scene_id = payload.get('scene_id')
        
        if video_id and scene_id is not None:
            context = engine.retrieve_scene_context(video_id, scene_id)
            if context:
                result['scene_context'] = context
        
        enriched_results.append(result)
    
    return enriched_results


# CLI entry point
def main():
    """Command-line interface for multimodal search."""
    import argparse
    from goodq4all.steps.common.config_loader import load_configs
    
    parser = argparse.ArgumentParser(description='GoodQ Multimodal Search')
    parser.add_argument('query', type=str, help='Search query')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results')
    parser.add_argument('--modalities', nargs='+', choices=['text', 'visual', 'audio'],
                       help='Modalities to search')
    
    args = parser.parse_args()
    
    # Load config
    config = load_configs({})
    
    # Execute search
    engine = MultimodalSearchEngine(config)
    results = engine.search_multimodal(
        args.query,
        top_k=args.top_k,
        modalities=args.modalities
    )
    
    # Display results
    print(f"\n[SEARCH] Search results for: '{args.query}'\n")
    print("=" * 80)
    
    for idx, result in enumerate(results, 1):
        payload = result.get('payload', {})
        score = result.get('score', 0.0)
        modality = result.get('modality', 'unknown')
        
        print(f"\n{idx}. [{modality.upper()}] Score: {score:.3f}")
        print(f"   Video: {payload.get('video_id', 'N/A')}")
        print(f"   Scene: {payload.get('scene_id', 'N/A')}")
        
        if 'scene_context' in result:
            ctx = result['scene_context']
            print(f"   Time: {ctx.get('start', 0):.1f}s - {ctx.get('end', 0):.1f}s")
            print(f"   Transcript: {ctx.get('full_transcript', 'N/A')[:100]}...")
            print(f"   Keywords: {', '.join(ctx.get('keywords', []))}")
    
    print("\n" + "=" * 80)
    print(f"\nTotal results: {len(results)}")


if __name__ == '__main__':
    main()
