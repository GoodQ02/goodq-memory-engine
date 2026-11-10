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
import math
from collections import Counter
from pathlib import Path

from steps.common.model_cache_inspector import resolve_pinned_model_snapshot
from steps.common import sqlite_read_authority

logger = logging.getLogger(__name__)


def _default_data_root() -> str:
    explicit_data_root = os.environ.get("GOODQ_DATA_ROOT")
    if explicit_data_root:
        return explicit_data_root
    return str(Path("GoodQ_Data"))


_CLAP_MODEL_ID = "laion/clap-htsat-unfused"
_CLAP_INSTALL_HINT = "conda run -n goodq_core python scripts/bootstrap_models.py"
_CLIP_MODEL_REGISTRY_KEY = "clip_vit"
_TEXT_MODEL_REGISTRY_KEY = "sentence_transformer"


class VisualQueryUnavailable(RuntimeError):
    """A visual query cannot run with the available local model/runtime."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _classify_audio_text_encoder_error(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}".lower()
    if "torch.load" in message and ("2.6" in message or "safetensors" in message):
        return "torch_safetensors_required"
    if "goodq_require_gpu=1" in message and "goodq_no_auto_gpu=1" in message:
        return "gpu_flag_profile_conflict"
    return f"{type(exc).__name__}: {exc}"


def _configure_clap_text_model_env(models_root: Path) -> None:
    os.environ["HF_HOME"] = str(models_root)
    os.environ["TORCH_HOME"] = str(models_root)
    os.environ.setdefault("HF_HUB_CACHE", str(models_root / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(models_root / "transformers"))
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _resolve_local_clap_model_dir(models_root: Path) -> Optional[str]:
    repo_cache = models_root / "hub" / f"models--{_CLAP_MODEL_ID.replace('/', '--')}"
    snapshots_dir = repo_cache / "snapshots"
    refs_main = repo_cache / "refs" / "main"
    required = ("config.json", "preprocessor_config.json")
    candidates: List[Path] = []

    if refs_main.is_file():
        revision = refs_main.read_text(encoding="utf-8").strip()
        if revision:
            candidates.append(snapshots_dir / revision)

    if snapshots_dir.is_dir():
        candidates.extend(sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        has_weights = (candidate / "model.safetensors").is_file() or (candidate / "pytorch_model.bin").is_file()
        if has_weights and all((candidate / name).is_file() for name in required):
            return str(candidate)
    return None

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


def _lexical_payload_predicate(spec, depth=0):
    """Compile scoped equality/boolean filters for SQLite payloads.

    Advanced Qdrant predicates remain available to vector search. Lexical
    candidates are withheld with a diagnostic if their filter cannot be checked.
    """
    if depth > 16 or not isinstance(spec, dict):
        raise ValueError('Unsupported lexical payload filter')
    if set(spec) == {'key', 'match'}:
        key, match = spec['key'], spec['match']
        if (not isinstance(key, str) or not key or any(c in key for c in '.[]')
                or not isinstance(match, dict) or set(match) != {'value'}
                or type(match['value']) not in (str, int, bool)):
            raise ValueError('Unsupported lexical match predicate')
        expected = match['value']

        def matches(payload):
            actual = payload.get(key)
            values = actual if isinstance(actual, list) else [actual]
            return any(type(value) is type(expected) and value == expected for value in values)

        return matches
    if set(spec) - {'must', 'should', 'must_not'}:
        raise ValueError('Unsupported lexical filter clause')
    groups = {}
    for name, conditions in spec.items():
        if conditions is None:
            continue
        conditions = [conditions] if isinstance(conditions, dict) else conditions
        if not isinstance(conditions, list):
            raise ValueError('Unsupported lexical filter conditions')
        groups[name] = [_lexical_payload_predicate(condition, depth + 1) for condition in conditions]
    return lambda payload: (
        all(test(payload) for test in groups.get('must', []))
        and ('should' not in groups or any(test(payload) for test in groups['should']))
        and not any(test(payload) for test in groups.get('must_not', []))
    )


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
        from steps.common.retrieval_events import resolve_retrieval_event_policy

        self._retrieval_event_policy = resolve_retrieval_event_policy(config)
        qdrant_cfg = (config.get("qdrant") or {}) if isinstance(config, dict) else {}
        paths_cfg = (config.get("paths") or {}) if isinstance(config, dict) else {}
        phase6_cfg = (config.get("phase6") or {}) if isinstance(config, dict) else {}
        collections_cfg = (qdrant_cfg.get("collections") or {}) if isinstance(qdrant_cfg, dict) else {}
        embedding_dims_cfg = (qdrant_cfg.get("embedding_dims") or {}) if isinstance(qdrant_cfg, dict) else {}

        self.qdrant_host = qdrant_cfg.get("host") or config.get("qdrant_host", "http://127.0.0.1:6333")
        self.data_root = paths_cfg.get("data_root") or config.get("data_root") or _default_data_root()
        self.processing_root = paths_cfg.get("processing") or os.path.join(self.data_root, "processing")
        self.kg_db_path = paths_cfg.get("knowledge_graph_db") or config.get("knowledge_graph_db")
        self.db_path = paths_cfg.get("db_path") or config.get("db_path")
        self.text_collection = collections_cfg.get("text") or "goodq_text"
        self.visual_collection = phase6_cfg.get("clip_collection") or collections_cfg.get("clip") or "goodq_clip_scenes"
        self.audio_collection = collections_cfg.get("audio") or "goodq_audio"
        self.collection_dims = {
            self.text_collection: int(embedding_dims_cfg.get("text", 384)),
            self.visual_collection: int(embedding_dims_cfg.get("clip", 768)),
            self.audio_collection: int(embedding_dims_cfg.get("audio", 512)),
        }
        
        # Fusion weights
        fusion_cfg = config.get('phase6', {}).get('retrieval', {}).get('fusion_weights', {})
        self.weight_text = fusion_cfg.get('text', 0.5)
        self.weight_visual = fusion_cfg.get('visual', 0.4)
        self.weight_audio = fusion_cfg.get('audio', 0.1)
        
        # Lazy-load models and clients
        self._clip_model = None
        self._clip_model_error_reason: Optional[str] = None
        self._text_model = None
        self._audio_text_model = None
        self._audio_text_model_error = False
        self._audio_text_model_error_reason: Optional[str] = None
        self._qdrant_clients = {}
        self._kg_scene_context: Optional[Dict[str, Dict[str, Any]]] = None
        self._kg_scene_context_error = False
        self._last_search_diagnostics: Dict[str, Dict[str, Any]] = {}

    def _models_cache_root(self) -> Path:
        paths_cfg = (self.config.get("paths") or {}) if isinstance(self.config, dict) else {}
        models_cache = paths_cfg.get("models_cache") if isinstance(paths_cfg, dict) else None
        if isinstance(models_cache, str) and models_cache.strip():
            return Path(models_cache).resolve()
        data_root = Path(str(self.data_root)).resolve()
        return data_root.parent / "models"

    def _reset_search_diagnostics(self) -> None:
        self._last_search_diagnostics = {}

    def _set_search_diagnostic(self, modality: str, *, status: str, label: str, reason: str) -> None:
        self._last_search_diagnostics[str(modality)] = {
            "status": status,
            "label": label,
            "reason": reason,
        }

    def last_search_diagnostics(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._last_search_diagnostics)

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
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite_read_authority.open_sqlite_read_connection(
                self.kg_db_path
            )
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
            if conn is not None:
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
        if not intent_terms:
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
            if intent_terms.intersection(clause_terms):
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
        if not intent_terms:
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
            if intent_terms.intersection(clause_terms):
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
        if not intent_terms:
            return 0.0

        clauses = [part.strip().lower() for part in re.split(r"[.!?;:\n]+", preview) if part.strip()]
        if not clauses:
            return 0.0

        clause_data: List[Dict[str, Any]] = []
        for clause in clauses:
            clause_terms = set(self._tokenize_terms(clause))
            clause_data.append(
                {
                    "terms": clause_terms,
                    "subject_hits": len(query_named_terms.intersection(clause_terms)),
                    "intent_hits": len(intent_terms.intersection(clause_terms)),
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

            intent_signal = clause["intent_hits"]
            if local_subject_hits <= 0 or intent_signal <= 0:
                continue

            density = min((local_subject_hits + intent_signal) / float(clause["term_count"]), 1.0)
            bonus = 0.008 + (0.006 * min(local_subject_hits, 2.0)) + (0.008 * min(intent_signal, 2.0))
            bonus += 0.01 * density

            if clause["subject_hits"] > 0 and clause["intent_hits"] > 0:
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
        # Scene/dialogue heuristics are not document relevance. In particular,
        # a document's opening preview must not overturn its retrieval rank.
        if payload.get("source_kind") == "document" or payload.get("content_type") == "document_text":
            return 0.0
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
        scene_id = next((value for value in (
            payload.get("scene_id"), payload.get("scene_index"), result.get("id"),
        ) if value is not None and value != ""), "unknown_scene")
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
                    "_document_match": None,
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
            if modality == "visual" and result.get("clip_score") is not None:
                entry["clip_score"] = result["clip_score"]
            if modality == "text" and isinstance(payload.get("document_chunk"), dict):
                current_match = entry["_document_match"]
                if current_match is None or score > current_match[0]:
                    entry["_document_match"] = (score, payload["document_chunk"])
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
            document_match = entry.pop("_document_match", None)
            if document_match is not None:
                entry["payload"] = {**entry["payload"], "document_chunk": document_match[1]}
            fused_results.append(entry)

        fused_results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        fused_results = self._apply_subject_focus_rerank(query, fused_results)
        return fused_results[:top_k]
    
    def _load_clip_model(self):
        """Load CLIP model for text encoding."""
        if self._clip_model is not None:
            return

        model_source = resolve_pinned_model_snapshot(
            self._models_cache_root(),
            _CLIP_MODEL_REGISTRY_KEY,
            required_files=("preprocessor_config.json",),
        )
        if model_source is None:
            self._clip_model_error_reason = "model_not_cached"
            logger.warning(
                "Visual search unavailable because pinned CLIP model cache is missing "
                "registry_key=%s install_hint=\"%s\"",
                _CLIP_MODEL_REGISTRY_KEY,
                _CLAP_INSTALL_HINT,
            )
            return

        try:
            from transformers import CLIPModel, CLIPProcessor

            source = str(model_source)
            processor = CLIPProcessor.from_pretrained(source, local_files_only=True)
            model = CLIPModel.from_pretrained(
                source,
                # Prefer safetensors when present; the pinned registry also
                # supports .bin weights through the library's native safety gate.
                use_safetensors=None,
                local_files_only=True,
            ).eval()

            self._clip_model = {'model': model, 'processor': processor}
            self._clip_model_error_reason = None
            logger.info("[OK] CLIP model loaded from pinned local cache for text encoding")
        except Exception as e:
            message = str(e).lower()
            self._clip_model_error_reason = (
                "torch_version_unsupported"
                if "torch.load" in message and "2.6" in message
                else "clip_model_load_failed"
            )
            logger.error(f"Failed to load CLIP model: {e}")

    def _load_text_model(self):
        """Load sentence transformer for text encoding."""
        if self._text_model is not None:
            return

        model_source = resolve_pinned_model_snapshot(
            self._models_cache_root(),
            _TEXT_MODEL_REGISTRY_KEY,
            required_files=("modules.json",),
        )
        if model_source is None:
            logger.warning(
                "Text search unavailable because pinned sentence-transformer cache is missing "
                "registry_key=%s install_hint=\"%s\"",
                _TEXT_MODEL_REGISTRY_KEY,
                _CLAP_INSTALL_HINT,
            )
            return

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(str(model_source), local_files_only=True)
            self._text_model = model
            logger.info("[OK] Text embedding model loaded from pinned local cache")
        except Exception as e:
            logger.error(f"Failed to load text model: {e}")

    def _load_audio_text_model(self):
        """Load CLAP text encoder for audio retrieval queries."""
        if self._audio_text_model is not None or self._audio_text_model_error:
            return

        try:
            import torch
            from transformers import AutoProcessor, ClapModel

            models_root = self._models_cache_root()
            _configure_clap_text_model_env(models_root)
            model_source = _resolve_local_clap_model_dir(models_root)
            if not model_source:
                self._audio_text_model_error = True
                self._audio_text_model_error_reason = "model_not_cached"
                logger.warning(
                    "Audio search unavailable because CLAP model cache missing "
                    "model_id=%s install_hint=\"%s\"",
                    _CLAP_MODEL_ID,
                    _CLAP_INSTALL_HINT,
                )
                return

            try:
                from steps.common.profile_config import gpu_auto_config_enabled

                gpu_enabled = gpu_auto_config_enabled()
            except Exception:
                gpu_enabled = os.environ.get("GOODQ_NO_AUTO_GPU") != "1"
            force_cpu = str(os.environ.get("GOODQ_CLAP_FORCE_CPU") or "").strip().lower() in {"1", "true", "yes", "on"}
            device = "cuda" if not force_cpu and gpu_enabled and getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
            processor = AutoProcessor.from_pretrained(model_source, local_files_only=True)
            model = ClapModel.from_pretrained(model_source, local_files_only=True).to(device).eval()
            self._audio_text_model = {
                "model": model,
                "processor": processor,
                "device": device,
            }
            self._audio_text_model_error_reason = None
            logger.info("[OK] CLAP text encoder loaded for audio search on %s", device)
        except Exception as e:
            self._audio_text_model_error = True
            self._audio_text_model_error_reason = _classify_audio_text_encoder_error(e)
            logger.warning(
                "Audio search unavailable because CLAP text encoder failed "
                "exc_type=%s exc=%s",
                type(e).__name__,
                e,
            )
    
    def _get_qdrant_client(self, collection: str):
        """Get or create Qdrant client for collection."""
        if collection in self._qdrant_clients:
            return self._qdrant_clients[collection]
        
        from steps.common.qdrant_client import QdrantClient, QdrantConfig
        
        # Determine dimension based on collection type
        dim = self.collection_dims.get(collection)
        if dim is None:
            lower_collection = collection.lower()
            if 'clip' in lower_collection:
                dim = 768
            elif 'audio' in lower_collection:
                dim = 512
            elif 'dino' in lower_collection:
                dim = 1024
            else:
                dim = 384
        
        client = QdrantClient(QdrantConfig(
            host=self.qdrant_host,
            collection=collection,
            dim=dim,
            distance='Cosine',
            db_path=self.db_path,
            retrieval_event_policy=self._retrieval_event_policy,
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
            raise VisualQueryUnavailable(self._clip_model_error_reason or "clip_model_load_failed")
        
        import torch
        
        model = self._clip_model['model']
        processor = self._clip_model['processor']
        
        inputs = processor(text=[query], return_tensors="pt", padding=True)
        
        with torch.no_grad():
            text_features = model.get_text_features(**inputs)
            if hasattr(text_features, "pooler_output"):
                text_features = text_features.pooler_output
            elif hasattr(text_features, "text_embeds"):
                text_features = text_features.text_embeds
            embedding = text_features.detach().cpu().numpy()[0]
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if (
            embedding.ndim != 1
            or embedding.size != self.collection_dims[self.visual_collection]
            or not np.isfinite(embedding).all()
            or not np.isfinite(norm)
            or norm == 0
        ):
            raise ValueError("clip_query_embedding_invalid")
        embedding = embedding / norm
        return embedding

    def encode_text_for_audio_search(self, query: str) -> np.ndarray:
        """
        Encode text query for audio similarity search using CLAP text embeddings.

        Args:
            query: Search query string

        Returns:
            CLAP text embedding vector
        """
        self._load_audio_text_model()

        if not isinstance(self._audio_text_model, dict):
            logger.error("CLAP text encoder unavailable")
            return np.zeros(self.collection_dims.get(self.audio_collection, 512), dtype=np.float32)

        import torch

        model = self._audio_text_model["model"]
        processor = self._audio_text_model["processor"]
        device = self._audio_text_model["device"]

        inputs = processor(text=[query], return_tensors="pt", padding=True, truncation=True)
        model_inputs = {
            key: value.to(device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }

        with torch.no_grad():
            text_features = model.get_text_features(**model_inputs)
            if hasattr(text_features, "pooler_output"):
                text_features = text_features.pooler_output
            elif hasattr(text_features, "text_embeds"):
                text_features = text_features.text_embeds
            embedding = text_features.cpu().numpy()[0]

        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding
    
    def _is_fts5_available(self, conn: sqlite3.Connection) -> bool:
        try:
            cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='scene_text_fts'")
            row = cur.fetchone()
            if row and row[0] and 'fts5' in row[0].lower():
                return True
            return False
        except Exception:
            return False

    def search_fts(self, query: str, top_k: int = 5, *, _predicate=None) -> List[Dict[str, Any]]:
        """
        Search exact phrases using FTS5 (or fallback substring search).
        """
        if not self.db_path or not os.path.exists(self.db_path):
            logger.warning("FTS search skipped because database path is invalid or missing.")
            return []

        sanitized_query = re.sub(r'[^\w\s]', ' ', query).strip()
        if not sanitized_query:
            return []

        results = []
        from steps.common.transcript_binding import fts_provenance

        def accept(result):
            payload = result['payload']
            payload.update(fts_provenance(payload, self.config))
            if _predicate is None or _predicate(payload):
                results.append(result)
            return top_k > 0 and len(results) >= top_k

        # Stream scoped matches until enough eligible rows are found. Applying
        # LIMIT before the predicate could hide a valid later source/run.
        scan_limit = -1 if _predicate is not None else top_k
        conn = sqlite_read_authority.open_sqlite_read_connection(self.db_path)
        try:
            is_fts = self._is_fts5_available(conn)
            if is_fts:
                try:
                    cur = conn.execute(
                        """
                        SELECT f.scene_id, f.video_hash, f.content_type, f.text, f.rank, s.start, s.end, s.meta
                        FROM scene_text_fts f
                        JOIN scenes s ON s.id = f.scene_id
                        WHERE scene_text_fts MATCH ?
                        ORDER BY rank ASC
                        LIMIT ?
                        """,
                        (sanitized_query, scan_limit),
                    )
                    rows = cur
                    for scene_id, video_hash, content_type, text, rank, start, end, meta_json in rows:
                        score = float(-rank) if rank is not None else 1.0
                        try:
                            meta = json.loads(meta_json) if meta_json else {}
                        except Exception:
                            meta = {}
                        
                        if accept({
                            "id": scene_id,
                            "score": score,
                            "payload": {
                                "scene_id": scene_id,
                                "video_id": str(video_hash),
                                "video_hash": video_hash,
                                "modality": "fts",
                                "start": float(start or 0.0),
                                "end": float(end or 0.0),
                                "text": text,
                                "content_type": content_type,
                                "meta": meta
                            }
                        }):
                            break
                except sqlite3.OperationalError as match_err:
                    logger.warning(f"FTS5 MATCH failed, falling back to LIKE: {match_err}")
                    like_pattern = f"%{query}%"
                    cur = conn.execute(
                        """
                        SELECT f.scene_id, f.video_hash, f.content_type, f.text, s.start, s.end, s.meta
                        FROM scene_text_fts f
                        JOIN scenes s ON s.id = f.scene_id
                        WHERE f.text LIKE ?
                        LIMIT ?
                        """,
                        (like_pattern, scan_limit),
                    )
                    rows = cur
                    for scene_id, video_hash, content_type, text, start, end, meta_json in rows:
                        try:
                            meta = json.loads(meta_json) if meta_json else {}
                        except Exception:
                            meta = {}
                        if accept({
                            "id": scene_id,
                            "score": 1.0,
                            "payload": {
                                "scene_id": scene_id,
                                "video_id": str(video_hash),
                                "video_hash": video_hash,
                                "modality": "fts",
                                "start": float(start or 0.0),
                                "end": float(end or 0.0),
                                "text": text,
                                "content_type": content_type,
                                "meta": meta
                            }
                        }):
                            break
            else:
                like_pattern = f"%{query}%"
                cur = conn.execute(
                    """
                    SELECT f.scene_id, f.video_hash, f.content_type, f.text, s.start, s.end, s.meta
                    FROM scene_text_fts f
                    JOIN scenes s ON s.id = f.scene_id
                    WHERE f.text LIKE ?
                    LIMIT ?
                    """,
                    (like_pattern, scan_limit),
                )
                rows = cur
                for scene_id, video_hash, content_type, text, start, end, meta_json in rows:
                    try:
                        meta = json.loads(meta_json) if meta_json else {}
                    except Exception:
                        meta = {}
                    if accept({
                        "id": scene_id,
                        "score": 1.0,
                        "payload": {
                            "scene_id": scene_id,
                            "video_id": str(video_hash),
                            "video_hash": video_hash,
                            "modality": "fts",
                            "start": float(start or 0.0),
                            "end": float(end or 0.0),
                            "text": text,
                            "content_type": content_type,
                            "meta": meta
                        }
                    }):
                        break
        except Exception as e:
            logger.error(f"FTS search encountered error: {e}")
        finally:
            conn.close()

        return results

    def reciprocal_rank_fusion(
        self,
        runs: List[List[Dict[str, Any]]],
        k: int = 60,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF) to fuse semantic and lexical runs.
        """
        rrf_scores: Dict[Tuple[str, str], float] = {}
        best_results: Dict[Tuple[str, str], Dict[str, Any]] = {}
        
        for run in runs:
            seen = set()
            for item in run:
                payload = item.get('payload') or {}
                scene_id = payload.get('scene_id') or item.get('id')
                if scene_id is None:
                    continue
                # Vector points identify artifacts; FTS identifies scenes. Fuse
                # the shared scene, with one vote per retrieval run, so multiple
                # embeddings or lexical rows cannot inflate a scene's rank.
                item_id = (str(payload.get('video_id') or payload.get('video_hash') or ''), str(scene_id))
                if item_id in seen:
                    continue
                seen.add(item_id)
                rank = len(seen)
                score = 1.0 / (k + rank)
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + score
                
                if item_id not in best_results:
                    best_results[item_id] = item
                else:
                    current_payload = best_results[item_id].get('payload') or {}
                    new_payload = item.get('payload') or {}
                    # Keep the highest-ranked semantic passage when FTS adds
                    # its scene vote; full lexical text is not the matched span.
                    if (not current_payload.get('document_chunk')
                            and (new_payload.get('document_chunk')
                                 or (not current_payload.get('text') and new_payload.get('text')))):
                        best_results[item_id] = item

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        num_runs = len(runs)
        max_possible_rrf = float(num_runs) / (k + 1)
        
        fused_results = []
        for item_id in sorted_ids[:top_k]:
            original_item = best_results[item_id]
            raw_rrf = rrf_scores[item_id]
            norm_score = raw_rrf / max_possible_rrf if max_possible_rrf > 0 else raw_rrf
            
            fused_results.append({
                "id": original_item.get("id") or item_id[1],
                "score": norm_score,
                "payload": original_item.get("payload", {}),
                "modality": "text"
            })
            
        return fused_results

    def _build_ucf_filter(
        self,
        payload_filter: Optional[Dict[str, Any]] = None,
        ucf_include_terminal: bool = False
    ) -> Dict[str, Any]:
        import copy
        p_filter = copy.deepcopy(payload_filter) if payload_filter else {}
        if ucf_include_terminal:
            return p_filter

        must_list = p_filter.setdefault("must", [])
        if isinstance(must_list, dict):
            must_list = p_filter['must'] = [must_list]
        elif must_list is None:
            must_list = p_filter['must'] = []
        has_status_filter = False
        for item in must_list:
            if isinstance(item, dict) and item.get("key") == "ucf_promotion_status":
                has_status_filter = True
                break
        if not has_status_filter:
            must_list.append({"key": "ucf_promotion_status", "match": {"value": "promoted"}})
        return p_filter

    def search_text(
        self,
        query: str,
        top_k: int = 5,
        payload_filter: Optional[Dict[str, Any]] = None,
        ucf_include_terminal: bool = False,
        *,
        retrieval_context: str,
    ) -> List[Dict[str, Any]]:
        """
        Search text embeddings (transcripts, captions, etc.) with FTS5 hybrid fusion.
        
        Args:
            query: Search query
            top_k: Number of results to return
            payload_filter: Optional payload filter dict
            ucf_include_terminal: Bypass promotion filter if True
            retrieval_context: Origin-owned retrieval audit label
            
        Returns:
            List of fused search results with normalized RRF scores
        """
        logger.info("retrieval_search operation=text top_k=%s", top_k)
        self._last_search_diagnostics.pop("text_passages", None)
        self._last_search_diagnostics.pop("text_lexical", None)
        
        candidate_k = max(top_k * 3, 20)
        
        # 1. Semantic search
        results_semantic = []
        query_embedding = self.encode_text_query(query)
        if np.any(query_embedding):
            try:
                client = self._get_qdrant_client(self.text_collection)
                semantic_limit = candidate_k
                while True:
                    results_semantic = client.query(
                        query_embedding.tolist(),
                        top_k=semantic_limit,
                        payload_filter=self._build_ucf_filter(payload_filter, ucf_include_terminal=ucf_include_terminal),
                        retrieval_context=retrieval_context,
                    )
                    # A long document contributes many vectors but still one
                    # ranked source. Expand only a full, chunk-crowded result
                    # window; bound work when fewer sources exist than top_k.
                    distinct_scenes = {self._result_scene_key(item) for item in results_semantic}
                    has_document_chunks = any(
                        isinstance((item.get("payload") or {}).get("document_chunk"), dict)
                        for item in results_semantic if isinstance(item.get("payload"), dict)
                    )
                    if (len(distinct_scenes) >= top_k or len(results_semantic) < semantic_limit
                            or not has_document_chunks or semantic_limit >= max(candidate_k, 4096)):
                        break
                    semantic_limit = min(semantic_limit * 2, max(candidate_k, 4096))
                for r in results_semantic:
                    r['modality'] = 'text'
            except Exception as e:
                logger.warning(f"Semantic text search failed: {e}")
        else:
            logger.warning("Text search skipped semantic pathway because query embedding is unavailable")

        # 2. FTS search
        if payload_filter:
            try:
                accepts = _lexical_payload_predicate(payload_filter)
            except ValueError:
                results_fts = []
                self._set_search_diagnostic(
                    "text_lexical", status="unavailable",
                    label="Lexical search cannot apply the requested filter",
                    reason="unsupported_lexical_payload_filter",
                )
                logger.warning("Lexical candidates withheld: unsupported caller payload filter")
            else:
                results_fts = self.search_fts(query, top_k=candidate_k, _predicate=accepts)
        else:
            results_fts = self.search_fts(query, top_k=candidate_k)

        # FTS votes for the full document. When a literal query is present in a
        # retained passage, show that passage instead of an unrelated semantic
        # sibling. Keep source ranking and paraphrase order unchanged.
        lexical_documents = {
            self._result_scene_key(item) for item in results_fts
            if isinstance(item.get("payload"), dict)
            and item["payload"].get("content_type") == "document_text"
        }
        literal = " ".join(query.casefold().split())
        literal_passages = {}
        if lexical_documents and literal:
            pattern = re.compile(r"(?<!\w)" + re.escape(literal) + r"(?!\w)")
            for item in results_semantic:
                key = self._result_scene_key(item)
                payload = item.get("payload") or {}
                chunk = payload.get("document_chunk")
                if (key in lexical_documents and key not in literal_passages
                        and isinstance(chunk, dict) and isinstance(chunk.get("text"), str)
                        and pattern.search(" ".join(chunk["text"].casefold().split()))):
                    literal_passages[key] = item
            results_semantic = [literal_passages.get(self._result_scene_key(item), item)
                                for item in results_semantic]
        
        # 3. Reciprocal Rank Fusion
        runs = []
        if results_semantic:
            runs.append(results_semantic)
        if results_fts:
            runs.append(results_fts)
            
        if runs:
            fused = self.reciprocal_rank_fusion(runs, k=60, top_k=top_k)
            # Rank evidence within already selected sources. Source IDs, scores,
            # metadata bonuses and literal passage selection remain unchanged.
            eligible = {self._result_scene_key(item) for item in fused} - literal_passages.keys()
            passages = self._rank_document_passages(query, query_embedding, results_semantic, eligible)
            for item in fused:
                evidence = passages.get(self._result_scene_key(item))
                if evidence is not None:
                    item["payload"] = {**item["payload"], **evidence}
            return fused
        
        return []

    def _rank_document_passages(self, query, query_embedding, candidates, eligible):
        """Select retained evidence with bounded short-window semantic/BM25 RRF.

        All budgets apply to the whole request, never once per source. Windows
        are ranking aids only: the returned evidence is an original stored chunk.
        """
        selected = [item for item in candidates
                    if self._result_scene_key(item) in eligible
                    and isinstance(item.get("payload"), dict)
                    and item["payload"].get("source_kind") == "document"
                    and "document_chunk" in item["payload"]]
        if len(selected) < 2:
            return {}
        limited = len(selected) > 32
        selected = selected[:32]
        groups = {}
        for index, item in enumerate(selected):
            groups.setdefault(self._result_scene_key(item), []).append(index)
        groups = {key: indices for key, indices in groups.items() if len(indices) > 1}
        if not groups:
            return {}
        reason = "passage_ranking_failed"
        try:
            reason = "document_passage_input_limit"
            if len(query) > 4096:
                raise ValueError(reason)
            texts = []
            for item in selected:
                chunk = item["payload"]["document_chunk"]
                reason = "invalid_document_chunk"
                if not isinstance(chunk, dict):
                    raise ValueError(reason)
                text = chunk.get("text")
                fields = [chunk.get(key) for key in ("chunk_index", "char_start", "char_end", "token_count")]
                if (not isinstance(text, str) or not text or any(type(v) is not int for v in fields)
                        or fields[0] < 0 or fields[1] < 0 or fields[2]-fields[1] != len(text) or fields[3] < 1):
                    raise ValueError(reason)
                reason = "document_passage_input_limit"
                if len(text) > 32768:
                    raise ValueError(reason)
                texts.append(text)
            if sum(map(len, texts)) > 262144:
                raise ValueError(reason)
            reason = "passage_encoder_unavailable"
            model = self._text_model  # Already loaded for the original query; never load another model.
            tokenizer = model.tokenizer
            windows, owners = [], []
            reason = "invalid_passage_tokenization"
            for index, text in enumerate(texts):
                offsets = tokenizer(text, add_special_tokens=False, truncation=False,
                                    return_offsets_mapping=True)["offset_mapping"]
                if not offsets or any(not 0 <= a <= b <= len(text) for a, b in offsets):
                    raise ValueError(reason)
                cursor = 0
                while cursor < len(offsets):
                    end = min(cursor+96, len(offsets))
                    a = 0 if cursor == 0 else offsets[cursor][0]
                    while True:
                        b = len(text) if end == len(offsets) else offsets[end][0]
                        window = text[a:b]
                        count = len(tokenizer(window, add_special_tokens=False, truncation=False)["input_ids"])
                        if 0 < count <= 96 and b > a:
                            break
                        if end <= cursor+1:
                            raise ValueError(reason)
                        end -= 1
                    if len(windows) >= 192:
                        reason = "document_passage_window_limit"
                        raise ValueError(reason)
                    windows.append(window)
                    owners.append(index)
                    if end == len(offsets):
                        break
                    cursor = max(cursor+1, end-48)
            reason = "passage_encoding_failed"
            vectors = np.asarray(model.encode(windows, normalize_embeddings=True, batch_size=32,
                                              show_progress_bar=False))
            query_vector = np.asarray(query_embedding)
            reason = "invalid_passage_vectors"
            if (query_vector.ndim != 1 or vectors.shape != (len(windows), query_vector.size)
                    or not np.isfinite(vectors).all() or not np.isfinite(query_vector).all()):
                raise ValueError(reason)
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                norms, query_norm = np.linalg.norm(vectors, axis=1), np.linalg.norm(query_vector)
                if (not np.isfinite(norms).all() or not np.isfinite(query_norm)
                        or query_norm == 0 or np.any(norms == 0)):
                    raise ValueError(reason)
                cosines = (vectors @ query_vector) / (norms*query_norm)
            if not np.isfinite(cosines).all():
                raise ValueError(reason)
            dense = [-float("inf")]*len(selected)
            for index, cosine in zip(owners, cosines):
                dense[index] = max(dense[index], float(cosine))

            reason = "passage_lexical_ranking_failed"
            from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
            def words(text):
                return [word for word in re.findall(r"\w+", text.casefold()) if word not in ENGLISH_STOP_WORDS]
            frequencies = [Counter(words(text)) for text in texts]
            lengths = [sum(freq.values()) for freq in frequencies]
            average = max(sum(lengths)/len(lengths), 1)
            document_frequency = Counter(word for freq in frequencies for word in freq)
            query_terms = set(words(query))
            lexical = [sum(math.log(1+(len(selected)-document_frequency[word]+.5)/(document_frequency[word]+.5))
                           * freq[word]*2.2/(freq[word]+1.2*(.25+.75*length/average))
                           for word in query_terms if freq[word])
                       for freq, length in zip(frequencies, lengths)]
            def concepts(text):
                return {word[:-1] if len(word) > 4 and word.endswith("s")
                        and not word.endswith(("ss", "us", "ies")) else word for word in words(text)}
            coverage = [0]*len(selected)
            query_concepts = concepts(query)
            for index, window in zip(owners, windows):
                coverage[index] = max(coverage[index], len(query_concepts.intersection(concepts(window))))
            winners = {}
            for key, indices in groups.items():
                dense_order = sorted(indices, key=lambda index: dense[index], reverse=True)
                lexical_order = sorted((index for index in indices if lexical[index] > 0),
                                       key=lambda index: lexical[index], reverse=True)
                scores = {index: 1/(60+rank) for rank, index in enumerate(dense_order, 1)}
                for rank, index in enumerate(lexical_order, 1):
                    scores[index] += 1/(60+rank)
                winner = max(indices, key=lambda index: scores[index])
                evidence = {"document_chunk": selected[winner]["payload"]["document_chunk"]}
                # Complement the proven match instead of replacing it when a
                # distant window covers more distinct query concepts.
                extra = max(indices, key=lambda index: (coverage[index], scores[index]))
                if coverage[extra] > coverage[winner]:
                    evidence["document_lexical_chunk"] = selected[extra]["payload"]["document_chunk"]
                winners[key] = evidence
            self._set_search_diagnostic("text_passages", status="limited" if limited else "ok",
                                        label="Document passage ranking", reason="candidate_limit" if limited else "combined_ranking")
            self._last_search_diagnostics["text_passages"].update(candidates=len(selected), windows=len(windows))
            return winners
        except Exception as exc:
            logger.warning("Document passage ranking fallback reason=%s error_type=%s", reason, type(exc).__name__)
            self._set_search_diagnostic("text_passages", status="fallback", label="Document passage ranking unavailable", reason=reason)
            return {}
    
    def search_visual(
        self,
        query: str,
        top_k: int = 5,
        payload_filter: Optional[Dict[str, Any]] = None,
        ucf_include_terminal: bool = False,
        *,
        retrieval_context: str,
    ) -> List[Dict[str, Any]]:
        """
        Search visual scene embeddings using text query.
        
        Args:
            query: Text description of visual content
            top_k: Number of distinct source/scene results to return
            payload_filter: Optional payload filter dict
            ucf_include_terminal: Bypass promotion filter if True
            retrieval_context: Origin-owned retrieval audit label
            
        Returns:
            List of search results with scores
        """
        logger.info("retrieval_search operation=visual top_k=%s", top_k)

        try:
            query_embedding = self.encode_text_for_visual_search(query)
        except VisualQueryUnavailable as exc:
            self._set_search_diagnostic("visual", status="unavailable", label="Visual search unavailable", reason=exc.reason)
            return []
        except Exception as exc:
            self._set_search_diagnostic("visual", status="error", label="Visual query encoding failed", reason="clip_query_encoding_failed")
            logger.warning("Visual query encoding failed exc_type=%s exc=%s", type(exc).__name__, exc)
            return []

        from steps.common.qdrant_client import QdrantQueryError

        try:
            client = self._get_qdrant_client(self.visual_collection)
            # Frame and pooled-scene points can represent the same scene.
            # Apply the result limit to distinct scenes, retaining their best
            # CLIP hit without adding duplicate evidence to the score.
            candidate_limit = max(100, top_k * 8)
            candidate_count = min(candidate_limit, max(10, top_k * 2))
            query_filter = self._build_ucf_filter(payload_filter, ucf_include_terminal=ucf_include_terminal)
            while True:
                candidates = client.query(
                    query_embedding.tolist(),
                    top_k=candidate_count,
                    payload_filter=query_filter,
                    retrieval_context=retrieval_context,
                    raise_on_error=True,
                )
                scenes = {}
                for result in sorted(candidates, key=lambda item: item['score'], reverse=True):
                    scenes.setdefault(self._result_scene_key(result), result)
                results = list(scenes.values())[:top_k]
                exhausted = len(candidates) < candidate_count
                limited = len(results) < top_k and not exhausted and candidate_count == candidate_limit
                if len(results) >= top_k or exhausted or limited:
                    break
                candidate_count = min(candidate_limit, candidate_count * 2)
        except QdrantQueryError as exc:
            status = "unavailable" if exc.reason in {"qdrant_disabled", "collection_unavailable"} else "error"
            self._set_search_diagnostic("visual", status=status, label="Visual search backend unavailable", reason=exc.reason)
            return []
        except Exception as exc:
            self._set_search_diagnostic("visual", status="error", label="Visual search failed", reason="qdrant_query_failed")
            logger.warning("Visual search backend failed exc_type=%s exc=%s", type(exc).__name__, exc)
            return []

        self._set_search_diagnostic(
            "visual", status="limited" if limited else "ready" if results else "no_results",
            label="Visual search candidate limit reached" if limited else
            "Visual search active" if results else "Visual search returned no matching scenes",
            reason="visual_scene_candidate_limit" if limited else
            "qdrant_visual_search_returned_results" if results else "qdrant_visual_search_empty",
        )
        return [{**result, "clip_score": result["score"]} for result in results]

    def rank_visual_captions(self, query, results, captions):
        """Rerank a bounded CLIP set with qualified, scene-bound midpoint text.

        Missing evidence falls back for the whole set rather than penalizing
        scenes whose captions are unavailable. No vectors or text are persisted.
        The strongest CLIP match stays first; remaining matches retain RRF order.
        """
        reason = "caption_evidence_incomplete"
        try:
            if not results:
                return results
            if len(results) > 50 or len(captions) != len(results) or not all(captions):
                raise ValueError(reason)
            reason = "caption_encoder_unavailable"
            self._load_text_model()
            if self._text_model is None:
                raise ValueError(reason)
            reason = "caption_encoding_failed"
            vectors = np.asarray(self._text_model.encode(
                [query, *[item["text"] for item in captions]], batch_size=32,
                normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False,
            ))
            if (vectors.ndim != 2 or vectors.shape[0] != len(results) + 1
                    or not np.isfinite(vectors).all()
                    or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-3)):
                raise ValueError("invalid_caption_vectors")
            similarities = vectors[1:] @ vectors[0]
            order = sorted(range(len(results)), key=lambda i: (-float(similarities[i]), i))
            ranks = {i: rank for rank, i in enumerate(order, 1)}
            ranked = []
            for i, result in enumerate(results):
                # Normalize by the theoretical two-channel maximum. This is
                # rank evidence, never a calibrated probability or CLIP score.
                score = (1 / (60 + i + 1) + 1 / (60 + ranks[i])) / (2 / 61)
                ranked.append({**result, "score": score,
                    "visual_ranking": {"method": "midpoint_caption_clip_rrf", "k": 60,
                        "ordering": "clip_anchor_then_rrf", "is_clip_anchor": i == 0,
                        "clip_rank": i + 1, "clip_score": result.get("clip_score"),
                        "caption_rank": ranks[i], "caption_similarity": float(similarities[i]),
                        "caption_field": "visual_caption", "caption_status": "ok",
                        "sample_timestamp": captions[i].get("sample_timestamp"),
                        "qualification": "unverified_model_observation"}})
            # Captions remain unverified observations. Protect the strongest
            # image match without inflating its score or reordering other matches.
            ranked.sort(key=lambda item: (not item["visual_ranking"]["is_clip_anchor"], -item["score"]))
            self._set_search_diagnostic("visual_captions", status="ready",
                label="Saved midpoint captions and CLIP; strongest CLIP match first", reason="midpoint_caption_clip_rrf")
            self._last_search_diagnostics["visual_captions"].update(candidates=len(results), candidate_limit=50)
            return ranked
        except Exception as exc:
            logger.warning("Visual caption ranking fallback reason=%s error_type=%s", reason, type(exc).__name__)
            self._set_search_diagnostic("visual_captions", status="fallback",
                label="Saved caption ranking unavailable; using CLIP", reason=reason)
            return results

    def search_audio(
        self,
        query: str,
        top_k: int = 5,
        payload_filter: Optional[Dict[str, Any]] = None,
        ucf_include_terminal: bool = False,
        *,
        retrieval_context: str,
    ) -> List[Dict[str, Any]]:
        """
        Search CLAP audio embeddings using a text query.

        Args:
            query: Text description of audio content
            top_k: Number of results to return
            payload_filter: Optional payload filter dict
            ucf_include_terminal: Bypass promotion filter if True
            retrieval_context: Origin-owned retrieval audit label

        Returns:
            List of search results with scores
        """
        logger.info("retrieval_search operation=audio top_k=%s", top_k)

        query_embedding = self.encode_text_for_audio_search(query)
        if not np.any(query_embedding):
            self._set_search_diagnostic(
                "audio",
                status="unavailable",
                label="Audio text-query encoder unavailable",
                reason=self._audio_text_model_error_reason or "clap_query_embedding_unavailable",
            )
            logger.warning("Audio search skipped because CLAP query encoding is unavailable")
            return []

        client = self._get_qdrant_client(self.audio_collection)
        results = client.query(
            query_embedding.tolist(),
            top_k=top_k,
            payload_filter=self._build_ucf_filter(payload_filter, ucf_include_terminal=ucf_include_terminal),
            retrieval_context=retrieval_context,
        )
        if results:
            self._set_search_diagnostic(
                "audio",
                status="ready",
                label="Audio search active",
                reason="qdrant_audio_search_returned_results",
            )
        else:
            self._set_search_diagnostic(
                "audio",
                status="no_results",
                label="Audio search returned no matching scenes",
                reason="qdrant_audio_search_empty",
            )

        return results
    
    def search_multimodal(
        self,
        query: str,
        top_k: int = 10,
        modalities: Optional[List[str]] = None,
        *,
        retrieval_context: str,
    ) -> List[Dict[str, Any]]:
        """
        Unified multimodal search with fusion across modalities.
        
        Args:
            query: Search query
            top_k: Total number of results to return
            modalities: List of modalities to search ['text', 'visual', 'audio']
                       If None, searches all available modalities
            retrieval_context: Origin-owned retrieval audit label
            
        Returns:
            Fused and ranked search results
        """
        if modalities is None:
            modalities = ['text', 'visual']
        self._reset_search_diagnostics()
        
        safe_modalities = [
            modality
            for modality in ("text", "visual", "audio")
            if modality in modalities
        ]
        logger.info(
            "retrieval_search operation=multimodal top_k=%s modalities=%s",
            top_k,
            ",".join(safe_modalities),
        )
        
        all_results = []
        per_modality_top_k = max(int(top_k), 5) * 2
        
        # Search text modality
        if 'text' in modalities and self.weight_text > 0:
            text_results = self.search_text(
                query,
                top_k=per_modality_top_k,
                retrieval_context=retrieval_context,
            )
            for result in text_results:
                result['modality'] = 'text'
                payload = result.get('payload') if isinstance(result.get('payload'), dict) else {}
                result['score'] = (result.get('score', 0.0) * self.weight_text) + self._metadata_bonus(query, payload)
                all_results.append(result)
        
        # Search visual modality
        if 'visual' in modalities and self.weight_visual > 0:
            visual_results = self.search_visual(
                query,
                top_k=per_modality_top_k,
                retrieval_context=retrieval_context,
            )
            for result in visual_results:
                result['modality'] = 'visual'
                result['score'] = result.get('score', 0.0) * self.weight_visual
                all_results.append(result)
        elif 'visual' in modalities:
            self._set_search_diagnostic("visual", status="disabled", label="Visual search disabled", reason="visual_weight_zero")
        
        # Search audio modality
        if 'audio' in modalities and self.weight_audio > 0:
            audio_results = self.search_audio(
                query,
                top_k=per_modality_top_k,
                retrieval_context=retrieval_context,
            )
            for result in audio_results:
                result['modality'] = 'audio'
                result['score'] = result.get('score', 0.0) * self.weight_audio
                all_results.append(result)
        
        # Fuse and rank results
        return self._fuse_scene_results(query, all_results, top_k=top_k)
    
    def retrieve_scene_context(self, video_id: str, scene_id: int | str) -> Optional[Dict[str, Any]]:
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
            if str(segment.get('scene_id')) == str(scene_id):
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

    def search_similar_scene(
        self,
        video_id: str,
        scene_id: int | str,
        top_k: int = 5,
        *,
        retrieval_context: str,
    ) -> List[Dict[str, Any]]:
        """Search for semantically similar scenes using persisted scene memory as the query source."""
        source_context = self.retrieve_scene_context(video_id, scene_id)
        if not isinstance(source_context, dict):
            return []

        query = self.build_scene_similarity_query(source_context)
        if not query:
            return []

        candidate_limit = max((top_k * 3), top_k + 4)
        raw_results = self.search_multimodal(
            query,
            top_k=candidate_limit,
            modalities=["text", "visual", "audio"],
            retrieval_context=retrieval_context,
        )

        filtered_results: List[Dict[str, Any]] = []
        seen_scene_keys: set[Tuple[str, str]] = set()
        source_scene_key = (str(video_id), str(scene_id))
        source_scene_id = str(scene_id)
        source_scene_id_is_global = not source_scene_id.isdigit()

        for result in raw_results:
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
            result_video_id = payload.get("video_id")
            result_scene_id = payload.get("scene_id")
            if result_video_id is None or result_scene_id is None:
                continue

            scene_key = (str(result_video_id), str(result_scene_id))
            if (
                scene_key == source_scene_key
                or (source_scene_id_is_global and str(result_scene_id) == source_scene_id)
                or scene_key in seen_scene_keys
            ):
                continue

            scene_context = self.retrieve_scene_context(str(result_video_id), result_scene_id)
            enriched_result = dict(result)
            if isinstance(scene_context, dict):
                enriched_result["scene_context"] = scene_context

            filtered_results.append(enriched_result)
            seen_scene_keys.add(scene_key)

            if len(filtered_results) >= top_k:
                break

        return filtered_results


def multimodal_search(
    query: str,
    config: Dict[str, Any],
    top_k: int = 10,
    *,
    retrieval_context: str,
) -> List[Dict[str, Any]]:
    """
    Main entry point for multimodal search.
    
    Args:
        query: Search query string
        config: GoodQ configuration
        top_k: Number of results to return
        retrieval_context: Origin-owned retrieval audit label
        
    Returns:
        List of search results across all modalities
    """
    engine = MultimodalSearchEngine(config)
    results = engine.search_multimodal(
        query,
        top_k=top_k,
        retrieval_context=retrieval_context,
    )
    
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
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if str(repo_root.parent) not in sys.path:
        sys.path.insert(0, str(repo_root.parent))
        
    try:
        from steps.common.config_loader import load_configs
    except ModuleNotFoundError as e:
        if e.name in {'steps', 'steps.common', 'steps.common.config_loader'}:
            from goodq4all.steps.common.config_loader import load_configs
        else:
            raise
    
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
        modalities=args.modalities,
        retrieval_context="human.cli.retrieve",
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
