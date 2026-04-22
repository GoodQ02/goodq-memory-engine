from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import re

from lib.knowledge_graph import KnowledgeGraph


_ENTITY_STOPWORDS = {
    "i", "i'm", "you", "you're", "we", "we're", "they", "it's", "that's",
    "what", "well", "yeah", "okay", "why", "how", "look", "but", "and", "the",
    "this", "that", "these", "those", "there", "here", "people", "person",
    "man", "woman", "did", "does", "do", "done", "where", "when", "who",
    "get", "gets", "got", "then", "once", "see", "not", "yes", "no", "ok",
    "hey", "hi", "hello", "please", "thanks", "thank",
    "all", "although", "always", "any", "because", "break", "dont", "have",
    "hes", "hows", "ill", "ive", "let", "lets", "like", "many", "maybe",
    "men", "never", "now", "right", "same", "theres", "theyre", "thought",
    "uhhuh", "whatever", "wherever", "women", "yellow",
}
_ENTITY_CONTRACTION_PARTS = {"'m", "'re", "'s", "'ll", "'ve", "'d", "n't"}
_TRANSCRIPT_ENTITY_SOURCES = {
    "audio",
    "transcript",
    "transcription",
    "speaker_transcript",
    "whisper",
    "whisperx",
    "wsl_whisperx",
}
_PERSON_ENTITY_TYPES = {"PERSON", "PER", "CHARACTER"}
_LOCATION_ENTITY_TYPES = {"LOCATION", "LOC", "GPE", "PLACE", "FAC"}
_CO_OCCURRENCE_NODE_TYPES = {"person", "location", "speaker", "object", "audio_event"}
_PLACEHOLDER_SPEAKER_PATTERN = re.compile(r"^(?:speaker|face)_\d+$", re.IGNORECASE)
_PLACEHOLDER_IDENTITY_PATTERN = re.compile(r"^(?:unknown(?:_\d+)?|speaker_\d+|face_\d+|person_\d+)$", re.IGNORECASE)
_IDENTITY_SUPPORT_MIN_SCENES = 2
_SPEAKER_PATTERN_SUPPORT_MIN_SCENES = 3
_SPEAKER_PATTERN_EVIDENCE_MIN_SCENES = 5
_SPEAKER_PATTERN_EVIDENCE_MIN_EPISODES = 2
_SPEAKER_PATTERN_SIMILARITY_MIN = 0.92
_SPEAKER_PATTERN_DOMINANT_SHARE_MIN = 0.6
_WEAK_IDENTITY_NAME_REJECTIONS = {"God"}
_WEAK_IDENTITY_CONTEXT_REJECTIONS = {
    "batman": {"like batman"},
    "case": {"case closed", "crack this case"},
    "god": {"oh my god", "my god", "god bless"},
}


def _cfg_get(cfg: Optional[Dict[str, Any]], path: str, default: Any = None) -> Any:
    cur: Any = cfg if isinstance(cfg, dict) else {}
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _resolve_graph_db_path(cfg: Optional[Dict[str, Any]]) -> Path:
    explicit = _cfg_get(cfg, "paths.knowledge_graph_db")
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit)

    legacy = _cfg_get(cfg, "knowledge_graph.db_path")
    if isinstance(legacy, str) and legacy.strip():
        return Path(legacy)

    data_root = _cfg_get(cfg, "paths.data_root")
    if isinstance(data_root, str) and data_root.strip():
        return Path(data_root) / "knowledge_graph.db"

    return Path("data") / "knowledge_graph.db"


def _iter_str_list(value: Any) -> List[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out
    return []


def normalize_entity_name(name: str) -> str:
    cleaned = re.sub(r"^[^\w]+|[^\w]+$", "", name.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    return " ".join(
        word[:1].upper() + word[1:]
        for word in lowered.split()
    )


def _is_valid_entity_token(raw_name: str) -> bool:
    raw = raw_name.strip()
    if not raw:
        return False
    if "##" in raw:
        return False
    lower_raw = raw.lower()
    if lower_raw in _ENTITY_STOPWORDS or lower_raw in _ENTITY_CONTRACTION_PARTS:
        return False
    if re.fullmatch(r"[^\w]+", raw):
        return False
    compact = re.sub(r"[^A-Za-z0-9]+", "", raw)
    if compact and len(compact) < 3 and not raw[:1].isupper():
        return False
    normalized = normalize_entity_name(raw)
    if not normalized:
        return False
    compact_normalized = re.sub(r"[^A-Za-z0-9]+", "", normalized).lower()
    return compact_normalized not in _ENTITY_STOPWORDS


def _is_likely_character_name(name: str) -> bool:
    parts = [p for p in name.split() if p]
    if len(parts) != 1:
        return False
    token = parts[0]
    if not token[:1].isalpha():
        return False
    if not token.replace("'", "").isalpha():
        return False
    return _is_valid_entity_token(token)


def _is_weak_identity_promotion_name(name: str) -> bool:
    normalized = normalize_entity_name(name)
    if not normalized:
        return False
    if normalized in _WEAK_IDENTITY_NAME_REJECTIONS:
        return False
    parts = [part for part in normalized.split() if part]
    if len(parts) == 1:
        compact = re.sub(r"[^A-Za-z0-9]+", "", parts[0])
        if len(compact) < 3:
            return False
    return _is_valid_entity_token(normalized)


def _scene_text_for_identity(scene_data: Dict[str, Any]) -> str:
    texts: List[str] = []
    primary_text = None
    for key in ("transcript", "full_text"):
        value = scene_data.get(key)
        if isinstance(value, str) and value.strip():
            primary_text = value.strip()
            break
    if primary_text:
        texts.append(primary_text)
    else:
        for seg in scene_data.get("speaker_transcript", []) or []:
            if not isinstance(seg, dict):
                continue
            text = seg.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    for key in ("caption", "ocr_text"):
        value = scene_data.get(key)
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())
    return "\n".join(texts)


def _count_identity_name_mentions(name: str, text: str) -> int:
    if not isinstance(name, str) or not name.strip():
        return 0
    if not isinstance(text, str) or not text.strip():
        return 0
    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9']+", name)
        if token
    ]
    if not tokens:
        return 0
    escaped = r"\s+".join(re.escape(token) for token in tokens)
    return len(re.findall(rf"\b{escaped}\b", text, flags=re.IGNORECASE))


def _contextually_reject_weak_identity_name(name: str, text: str) -> bool:
    phrases = _WEAK_IDENTITY_CONTEXT_REJECTIONS.get(name.casefold())
    if not phrases:
        return False
    lowered = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return any(phrase in lowered for phrase in phrases)


def _weak_identity_candidate_allowed(name: str, scene_data: Dict[str, Any]) -> bool:
    normalized = normalize_entity_name(name)
    if not _is_weak_identity_promotion_name(normalized):
        return False
    scene_text = _scene_text_for_identity(scene_data)
    if scene_text and _contextually_reject_weak_identity_name(normalized, scene_text):
        return False
    parts = [part for part in normalized.split() if part]
    if len(parts) >= 2:
        return _count_identity_name_mentions(normalized, scene_text) >= 2
    return True


def _identity_scene_excerpt(scene_data: Dict[str, Any], limit: int = 240) -> Optional[str]:
    scene_text = _scene_text_for_identity(scene_data)
    if not scene_text:
        return None
    compact = re.sub(r"\s+", " ", scene_text).strip()
    if not compact:
        return None
    return compact[:limit]


def _speaker_transcript_excerpt(
    scene_data: Dict[str, Any],
    speaker_label: str,
    *,
    limit: int = 240,
) -> Optional[str]:
    if not isinstance(speaker_label, str) or not speaker_label.strip():
        return None
    segments = scene_data.get("speaker_transcript")
    if not isinstance(segments, list):
        return None
    target = normalize_entity_name(speaker_label)
    parts: List[str] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        seg_speaker = normalize_entity_name(str(segment.get("speaker") or ""))
        if seg_speaker != target:
            continue
        text = segment.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        return None
    compact = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return compact[:limit] if compact else None


def _speaker_duration_share(scene_data: Dict[str, Any], speaker_label: str) -> float:
    if not isinstance(speaker_label, str) or not speaker_label.strip():
        return 0.0
    segments = scene_data.get("speaker_transcript")
    if not isinstance(segments, list):
        return 0.0
    target = normalize_entity_name(speaker_label)
    speaker_seconds = 0.0
    total_seconds = 0.0
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        try:
            start_val = float(segment.get("start") or 0.0)
        except Exception:
            start_val = 0.0
        try:
            end_val = float(segment.get("end") or start_val)
        except Exception:
            end_val = start_val
        duration_val = max(0.0, end_val - start_val)
        if duration_val <= 0.0:
            continue
        total_seconds += duration_val
        seg_speaker = normalize_entity_name(str(segment.get("speaker") or ""))
        if seg_speaker == target:
            speaker_seconds += duration_val
    if total_seconds <= 1e-8:
        return 0.0
    return speaker_seconds / total_seconds


def _speaker_name_alignment_excerpt(
    scene_data: Dict[str, Any],
    speaker_label: str,
    person_name: str,
) -> Optional[str]:
    excerpt = _speaker_transcript_excerpt(scene_data, speaker_label)
    if not excerpt:
        return None
    if _count_identity_name_mentions(person_name, excerpt) < 1:
        return None
    return excerpt


def _coerce_embedding(raw: Any) -> List[float]:
    if not isinstance(raw, list):
        return []
    values: List[float] = []
    for item in raw:
        try:
            value = float(item)
        except Exception:
            return []
        if not math.isfinite(value):
            return []
        values.append(value)
    return values


def _normalize_embedding(embedding: Any) -> List[float]:
    values = _coerce_embedding(embedding)
    if not values:
        return []
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm <= 1e-8:
        return []
    return [float(value / norm) for value in values]


def _cosine_similarity(left: Any, right: Any) -> Optional[float]:
    left_values = _normalize_embedding(left)
    right_values = _normalize_embedding(right)
    if not left_values or not right_values or len(left_values) != len(right_values):
        return None
    return sum(a * b for a, b in zip(left_values, right_values))


def _speaker_voice_signature_map(scene_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    signatures = scene_data.get("speaker_voice_signatures")
    if not isinstance(signatures, list):
        return {}
    by_label: Dict[str, Dict[str, Any]] = {}
    for signature in signatures:
        if not isinstance(signature, dict):
            continue
        speaker = normalize_entity_name(str(signature.get("speaker") or ""))
        embedding = _normalize_embedding(signature.get("embedding"))
        if not speaker or not embedding:
            continue
        voiced_seconds = signature.get("voiced_seconds")
        try:
            voiced_seconds_val = float(voiced_seconds) if voiced_seconds is not None else 0.0
        except Exception:
            voiced_seconds_val = 0.0
        segment_count = signature.get("segment_count")
        try:
            segment_count_val = int(segment_count) if segment_count is not None else 0
        except Exception:
            segment_count_val = 0
        by_label[speaker] = {
            "speaker": speaker,
            "embedding": embedding,
            "embedding_dim": len(embedding),
            "voiced_seconds": voiced_seconds_val,
            "segment_count": segment_count_val,
            "available_segment_count": int(signature.get("available_segment_count") or segment_count_val or 0),
            "selected_segments": list(signature.get("selected_segments") or []),
        }
    return by_label


def _speaker_pattern_name(scene_identifier: str, speaker_label: str) -> str:
    scene_token = re.sub(r"[^A-Za-z0-9_]+", "_", str(scene_identifier or "")).strip("_") or "scene"
    speaker_token = re.sub(r"[^A-Za-z0-9_]+", "_", str(speaker_label or "")).strip("_") or "speaker"
    return f"voice_pattern_{scene_token[:24]}_{speaker_token.lower()}"


def _upsert_speaker_pattern_node(
    kg: KnowledgeGraph,
    *,
    scene_identifier: str,
    speaker_label: str,
    signature: Dict[str, Any],
    timestamp: float,
) -> Dict[str, Any]:
    embedding = _normalize_embedding(signature.get("embedding"))
    if not embedding:
        return {"node_id": None, "similarity": None, "created": False, "pattern_name": None}

    cur = kg.conn.cursor()
    rows = cur.execute(
        "SELECT id, name, properties FROM nodes WHERE node_type = ?",
        ("speaker_pattern",),
    ).fetchall()

    best_match = None
    best_similarity = -1.0
    for row in rows:
        props = _parse_edge_properties(row["properties"])
        similarity = _cosine_similarity(embedding, props.get("embedding"))
        if similarity is None or similarity < _SPEAKER_PATTERN_SIMILARITY_MIN:
            continue
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "properties": props,
            }

    if best_match is None:
        pattern_name = _speaker_pattern_name(scene_identifier, speaker_label)
        node_id = kg.add_node(
            "speaker_pattern",
            pattern_name,
            {
                "embedding": embedding,
                "embedding_dim": len(embedding),
                "signature_count": 1,
                "scene_count": 1,
                "total_voiced_seconds": float(signature.get("voiced_seconds") or 0.0),
                "speaker_labels": [speaker_label],
                "source": "speaker_voice_signature",
            },
            timestamp,
        )
        return {
            "node_id": int(node_id),
            "similarity": 1.0,
            "created": True,
            "pattern_name": pattern_name,
        }

    props = dict(best_match["properties"])
    previous_embedding = _normalize_embedding(props.get("embedding"))
    signature_count = int(props.get("signature_count") or 1)
    if previous_embedding and len(previous_embedding) == len(embedding):
        updated_embedding = [
            ((previous_embedding[idx] * signature_count) + embedding[idx]) / float(signature_count + 1)
            for idx in range(len(embedding))
        ]
        props["embedding"] = _normalize_embedding(updated_embedding) or embedding
    else:
        props["embedding"] = embedding
    props["embedding_dim"] = len(embedding)
    props["signature_count"] = signature_count + 1
    props["scene_count"] = int(props.get("scene_count") or 1) + 1
    props["total_voiced_seconds"] = float(props.get("total_voiced_seconds") or 0.0) + float(signature.get("voiced_seconds") or 0.0)
    speaker_labels = {
        normalize_entity_name(str(label or ""))
        for label in (props.get("speaker_labels") or [])
        if normalize_entity_name(str(label or ""))
    }
    speaker_labels.add(normalize_entity_name(speaker_label))
    props["speaker_labels"] = sorted(speaker_labels)
    cur.execute(
        "UPDATE nodes SET properties = ?, occurrence_count = occurrence_count + 1, last_seen = ? WHERE id = ?",
        (json.dumps(props, ensure_ascii=False, sort_keys=True), float(timestamp), int(best_match["id"])),
    )
    kg.conn.commit()
    return {
        "node_id": int(best_match["id"]),
        "similarity": round(float(best_similarity), 6),
        "created": False,
        "pattern_name": best_match["name"],
    }


def _identity_support_scene_threshold(source_node_type: str, source_rule: str) -> int:
    if source_node_type == "speaker_pattern":
        return _SPEAKER_PATTERN_SUPPORT_MIN_SCENES
    return _IDENTITY_SUPPORT_MIN_SCENES


def _dedupe_identity_evidence_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _append_identity_candidate_edge(
    kg: KnowledgeGraph,
    *,
    source_id: int,
    target_id: int,
    weight: float,
    properties: Dict[str, Any],
) -> int:
    cur = kg.conn.cursor()
    existing = cur.execute(
        "SELECT properties FROM edges WHERE source_id = ? AND target_id = ? AND edge_type = ?",
        (int(source_id), int(target_id), "identity_candidate"),
    ).fetchone()
    merged = dict(properties)
    if existing is not None:
        existing_props = _parse_edge_properties(existing["properties"])
        candidate_scene_ids = {
            str(scene_id).strip()
            for scene_id in existing_props.get("candidate_scene_ids") or []
            if isinstance(scene_id, str) and str(scene_id).strip()
        }
        scene_id = properties.get("scene_id")
        if isinstance(scene_id, str) and scene_id.strip():
            candidate_scene_ids.add(scene_id.strip())
        merged["candidate_scene_ids"] = sorted(candidate_scene_ids)

        candidate_video_ids = {
            str(video_id).strip()
            for video_id in existing_props.get("candidate_video_ids") or []
            if isinstance(video_id, str) and str(video_id).strip()
        }
        video_id = properties.get("video_id")
        if isinstance(video_id, str) and video_id.strip():
            candidate_video_ids.add(video_id.strip())
        merged["candidate_video_ids"] = sorted(candidate_video_ids)

        evidence_items = []
        if isinstance(existing_props.get("candidate_evidence"), list):
            evidence_items.extend(item for item in existing_props["candidate_evidence"] if isinstance(item, dict))
        if isinstance(properties.get("candidate_evidence"), list):
            evidence_items.extend(item for item in properties["candidate_evidence"] if isinstance(item, dict))
        merged["candidate_evidence"] = _dedupe_identity_evidence_items(evidence_items)
    else:
        scene_id = properties.get("scene_id")
        merged["candidate_scene_ids"] = [scene_id] if isinstance(scene_id, str) and scene_id.strip() else []
        video_id = properties.get("video_id")
        merged["candidate_video_ids"] = [video_id] if isinstance(video_id, str) and video_id.strip() else []
        candidate_evidence = properties.get("candidate_evidence")
        if isinstance(candidate_evidence, list):
            merged["candidate_evidence"] = _dedupe_identity_evidence_items(
                [item for item in candidate_evidence if isinstance(item, dict)]
            )
        else:
            merged["candidate_evidence"] = []

    return kg.add_edge(
        source_id=source_id,
        target_id=target_id,
        edge_type="identity_candidate",
        weight=weight,
        properties=merged,
    )


def _resolve_identity_name(raw: Any) -> str:
    candidate = raw
    if isinstance(raw, dict):
        candidate = (
            raw.get("name")
            or raw.get("identity")
            or raw.get("person")
            or raw.get("speaker_id")
            or raw.get("speaker")
            or raw.get("label")
        )
    if not isinstance(candidate, str) or not candidate.strip():
        return ""
    raw_text = candidate.strip()
    if _PLACEHOLDER_IDENTITY_PATTERN.fullmatch(raw_text):
        return ""
    normalized = normalize_entity_name(raw_text)
    if not normalized or _PLACEHOLDER_IDENTITY_PATTERN.fullmatch(normalized):
        return ""
    return normalized if _is_valid_entity_token(normalized) else ""


def _is_meaningful_generic_entity(name: str) -> bool:
    raw = name.strip()
    if not raw or "##" in raw:
        return False

    tokens = [
        re.sub(r"[^A-Za-z0-9']+", "", token)
        for token in raw.split()
    ]
    tokens = [token for token in tokens if token]
    if not tokens:
        return False

    if len(tokens) == 1:
        token = tokens[0]
        compact = re.sub(r"[^A-Za-z0-9]+", "", token)
        return bool(token.isupper() and len(compact) >= 3)

    substantive = [
        token for token in tokens
        if len(re.sub(r"[^A-Za-z0-9]+", "", token)) >= 3
        and token.casefold() not in _ENTITY_STOPWORDS
    ]
    return len(substantive) >= 2


def _is_synthetic_speaker_label(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if text.casefold() in {"unknown", "none"}:
        return True
    return bool(_PLACEHOLDER_SPEAKER_PATTERN.fullmatch(text))


def _scene_scoped_synthetic_speaker_name(scene_identifier: Any, speaker_label: Any) -> Optional[str]:
    if not _is_synthetic_speaker_label(speaker_label):
        return None
    scene_text = str(scene_identifier or "").strip()
    speaker_text = str(speaker_label or "").strip()
    if not scene_text or not speaker_text:
        return None
    scene_token = re.sub(r"[^A-Za-z0-9_]+", "_", scene_text).strip("_") or "scene"
    speaker_token = re.sub(r"[^A-Za-z0-9_]+", "_", speaker_text).strip("_") or "speaker"
    return f"{scene_token}__{speaker_token.lower()}"


def _parse_edge_properties(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _has_conflicting_identity_support(
    kg: KnowledgeGraph,
    *,
    source_id: int,
    target_id: int,
) -> bool:
    cur = kg.conn.cursor()
    row = cur.execute(
        """
        SELECT COUNT(*)
        FROM edges
        WHERE source_id = ?
          AND target_id != ?
          AND edge_type IN ('identity_evidence', 'identity_supported')
        """,
        (int(source_id), int(target_id)),
    ).fetchone()
    return bool(row and int(row[0] or 0) > 0)


def _accumulate_identity_candidate_support(kg: KnowledgeGraph) -> int:
    cur = kg.conn.cursor()
    rows = cur.execute(
        """
        SELECT e.source_id, e.target_id, e.properties, n.node_type AS source_node_type
        FROM edges e
        JOIN nodes n ON n.id = e.source_id
        WHERE e.edge_type = 'identity_candidate'
          AND n.node_type IN ('speaker', 'face', 'speaker_pattern')
        """
    ).fetchall()

    grouped: Dict[tuple[int, str, str, int], Dict[str, Any]] = {}
    for row in rows:
        source_id = int(row["source_id"])
        target_id = int(row["target_id"])
        if _has_conflicting_identity_support(kg, source_id=source_id, target_id=target_id):
            continue

        props = _parse_edge_properties(row["properties"])
        scene_id = props.get("scene_id")
        source_rule = props.get("source")
        source_node_type = str(row["source_node_type"])
        if not isinstance(scene_id, str) or not scene_id.strip():
            continue
        if not isinstance(source_rule, str) or not source_rule.strip():
            continue

        source_rule_clean = source_rule.strip()
        video_id = props.get("video_id")
        group_key = (
            target_id,
            source_node_type,
            source_rule_clean,
            source_id if source_node_type == "speaker_pattern" else 0,
        )
        bundle = grouped.setdefault(
            group_key,
            {
                "scene_ids": set(),
                "video_ids": set(),
                "rows": [],
                "supporting_evidence": [],
            },
        )
        candidate_scene_ids = props.get("candidate_scene_ids") if source_node_type == "speaker_pattern" else None
        if isinstance(candidate_scene_ids, list):
            for candidate_scene_id in candidate_scene_ids:
                if isinstance(candidate_scene_id, str) and candidate_scene_id.strip():
                    bundle["scene_ids"].add(candidate_scene_id.strip())
        else:
            bundle["scene_ids"].add(scene_id.strip())
        if isinstance(video_id, str) and video_id.strip():
            bundle["video_ids"].add(video_id.strip())
        candidate_video_ids = props.get("candidate_video_ids") if source_node_type == "speaker_pattern" else None
        if isinstance(candidate_video_ids, list):
            for candidate_video_id in candidate_video_ids:
                if isinstance(candidate_video_id, str) and candidate_video_id.strip():
                    bundle["video_ids"].add(candidate_video_id.strip())
        evidence: Dict[str, Any] = {
            "scene_id": scene_id.strip(),
            "media_id": props.get("media_id"),
            "candidate_source": source_rule_clean,
            "source_node_type": source_node_type,
        }
        if isinstance(video_id, str) and video_id.strip():
            evidence["video_id"] = video_id.strip()
        if props.get("speaker_label"):
            evidence["speaker_label"] = props.get("speaker_label")
        if props.get("face_index") is not None:
            evidence["face_index"] = props.get("face_index")
        if props.get("voice_similarity") is not None:
            evidence["voice_similarity"] = props.get("voice_similarity")
        if props.get("voiced_seconds") is not None:
            evidence["voiced_seconds"] = props.get("voiced_seconds")
        if props.get("dominant_share") is not None:
            evidence["dominant_share"] = props.get("dominant_share")
        if props.get("transcript_excerpt"):
            evidence["transcript_excerpt"] = props.get("transcript_excerpt")
        if props.get("scene_excerpt"):
            evidence["scene_excerpt"] = props.get("scene_excerpt")
        candidate_evidence = props.get("candidate_evidence") if source_node_type == "speaker_pattern" else None
        if isinstance(candidate_evidence, list) and candidate_evidence:
            bundle["supporting_evidence"].extend(
                item for item in candidate_evidence if isinstance(item, dict)
            )
        else:
            bundle["supporting_evidence"].append(evidence)
        bundle["rows"].append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "scene_id": scene_id.strip(),
                "source_node_type": source_node_type,
                "source_rule": source_rule_clean,
                "properties": props,
            }
        )

    promoted = 0
    for (_target_id, source_node_type, source_rule, _source_group_id), bundle in grouped.items():
        scene_ids = sorted(bundle["scene_ids"])
        min_scenes = _identity_support_scene_threshold(source_node_type, source_rule)
        if len(scene_ids) < min_scenes:
            continue

        evidence_strength = "strong" if len(scene_ids) >= 3 else "moderate"
        support_weight = min(0.8, 0.55 + (0.1 * max(0, len(scene_ids) - 2)))
        supporting_evidence = sorted(
            bundle["supporting_evidence"],
            key=lambda item: (str(item.get("scene_id", "")), str(item.get("source_node_type", ""))),
        )
        supporting_video_ids = sorted(bundle["video_ids"])

        for row in bundle["rows"]:
            props = row["properties"]
            support_props: Dict[str, Any] = {
                "source": "identity_candidate_accumulator",
                "candidate_source": source_rule,
                "source_node_type": source_node_type,
                "scene_id": row["scene_id"],
                "media_id": props.get("media_id"),
                "supporting_scene_count": len(scene_ids),
                "supporting_scene_ids": scene_ids,
                "supporting_video_count": len(supporting_video_ids),
                "supporting_video_ids": supporting_video_ids,
                "supporting_evidence": supporting_evidence,
                "evidence_strength": evidence_strength,
            }
            if props.get("speaker_label"):
                support_props["speaker_label"] = props.get("speaker_label")
            if props.get("face_index") is not None:
                support_props["face_index"] = props.get("face_index")
            if props.get("bbox") is not None:
                support_props["bbox"] = props.get("bbox")
            if props.get("voice_similarity") is not None:
                support_props["voice_similarity"] = props.get("voice_similarity")
            if props.get("voiced_seconds") is not None:
                support_props["voiced_seconds"] = props.get("voiced_seconds")
            if props.get("dominant_share") is not None:
                support_props["dominant_share"] = props.get("dominant_share")

            kg.add_edge(
                source_id=row["source_id"],
                target_id=row["target_id"],
                edge_type="identity_supported",
                weight=support_weight,
                properties=support_props,
            )
            promoted += 1

    return promoted


def _accumulate_identity_supported_evidence(kg: KnowledgeGraph) -> int:
    cur = kg.conn.cursor()
    rows = cur.execute(
        """
        SELECT e.source_id, e.target_id, e.properties
        FROM edges e
        JOIN nodes n ON n.id = e.source_id
        WHERE e.edge_type = 'identity_supported'
          AND n.node_type = 'speaker_pattern'
        """
    ).fetchall()

    grouped: Dict[tuple[int, int, str], Dict[str, Any]] = {}
    for row in rows:
        source_id = int(row["source_id"])
        target_id = int(row["target_id"])
        if _has_conflicting_identity_support(kg, source_id=source_id, target_id=target_id):
            continue

        props = _parse_edge_properties(row["properties"])
        candidate_source = str(props.get("candidate_source") or props.get("source") or "").strip()
        if not candidate_source:
            continue

        group_key = (source_id, target_id, candidate_source)
        bundle = grouped.setdefault(
            group_key,
            {
                "scene_ids": set(),
                "video_ids": set(),
                "supporting_evidence": [],
            },
        )
        for scene_id in props.get("supporting_scene_ids") or []:
            if isinstance(scene_id, str) and scene_id.strip():
                bundle["scene_ids"].add(scene_id.strip())
        scene_id = props.get("scene_id")
        if isinstance(scene_id, str) and scene_id.strip():
            bundle["scene_ids"].add(scene_id.strip())
        for video_id in props.get("supporting_video_ids") or []:
            if isinstance(video_id, str) and video_id.strip():
                bundle["video_ids"].add(video_id.strip())
        video_id = props.get("video_id")
        if isinstance(video_id, str) and video_id.strip():
            bundle["video_ids"].add(video_id.strip())
        supporting_evidence = props.get("supporting_evidence")
        if isinstance(supporting_evidence, list):
            bundle["supporting_evidence"].extend(
                item for item in supporting_evidence if isinstance(item, dict)
            )

    promoted = 0
    for (source_id, target_id, candidate_source), bundle in grouped.items():
        scene_ids = sorted(bundle["scene_ids"])
        video_ids = sorted(bundle["video_ids"])
        if len(scene_ids) < _SPEAKER_PATTERN_EVIDENCE_MIN_SCENES:
            continue
        if len(video_ids) < _SPEAKER_PATTERN_EVIDENCE_MIN_EPISODES:
            continue
        kg.add_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type="identity_evidence",
            weight=0.9,
            properties={
                "source": "identity_supported_accumulator",
                "candidate_source": candidate_source,
                "supporting_scene_count": len(scene_ids),
                "supporting_scene_ids": scene_ids,
                "supporting_video_count": len(video_ids),
                "supporting_video_ids": video_ids,
                "supporting_evidence": sorted(
                    bundle["supporting_evidence"],
                    key=lambda item: (str(item.get("scene_id", "")), str(item.get("source_node_type", ""))),
                ),
                "evidence_strength": "strong",
            },
        )
        promoted += 1

    return promoted


def _entity_type_priority(ent_type: Optional[str]) -> int:
    normalized = ent_type.strip().upper() if isinstance(ent_type, str) and ent_type.strip() else ""
    if normalized in _PERSON_ENTITY_TYPES:
        return 30
    if normalized in _LOCATION_ENTITY_TYPES:
        return 20
    if normalized:
        return 10
    return 0


def _iter_entity_items(value: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(value, list):
        return out

    for item in value:
        if isinstance(item, str):
            text = normalize_entity_name(item)
            if text and _is_valid_entity_token(item):
                out.append({"name": text, "type": None, "sources": []})
            continue
        if not isinstance(item, dict):
            continue
        raw_name = item.get("name") or item.get("text") or item.get("entity") or item.get("value")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        if not _is_valid_entity_token(raw_name):
            continue
        normalized_name = normalize_entity_name(raw_name)
        if not normalized_name:
            continue
        raw_type = item.get("type") or item.get("label") or item.get("entity_type")
        ent_type = raw_type.strip().upper() if isinstance(raw_type, str) and raw_type.strip() else None
        sources: List[str] = []
        for key in ("source_step", "source_steps", "source", "source_modality", "source_modalities"):
            source_value = item.get(key)
            if isinstance(source_value, str) and source_value.strip():
                sources.append(source_value.strip().lower())
            elif isinstance(source_value, list):
                for source_item in source_value:
                    if isinstance(source_item, str) and source_item.strip():
                        sources.append(source_item.strip().lower())
        out.append({"name": normalized_name, "type": ent_type, "sources": sorted(set(sources))})
    return out


def _collapse_entity_items(value: Any) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for entity in _iter_entity_items(value):
        name = entity.get("name")
        if not isinstance(name, str) or not name:
            continue
        ent_type = entity.get("type")
        sources = {
            str(source).strip().lower()
            for source in (entity.get("sources") or [])
            if isinstance(source, str) and source.strip()
        }
        existing = merged.get(name)
        if existing is None:
            merged[name] = {
                "name": name,
                "type": ent_type,
                "sources": sources,
                "mentions": 1,
            }
            continue
        existing["sources"].update(sources)
        existing["mentions"] = int(existing.get("mentions", 1)) + 1
        if _entity_type_priority(ent_type) > _entity_type_priority(existing.get("type")):
            existing["type"] = ent_type

    out: List[Dict[str, Any]] = []
    for entity in merged.values():
        out.append(
            {
                "name": entity["name"],
                "type": entity.get("type"),
                "sources": sorted(entity.get("sources") or set()),
                "mentions": int(entity.get("mentions", 1) or 1),
            }
        )
    return out


def _extract_location_labels(scene_data: Dict[str, Any]) -> List[str]:
    labels: List[str] = []

    def _append(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        if not _is_valid_entity_token(raw):
            return
        text = normalize_entity_name(raw)
        if text and text not in labels:
            labels.append(text)

    for key in ("location", "place"):
        _append(scene_data.get(key))
    for key in ("locations", "places"):
        for item in scene_data.get(key, []) or []:
            _append(item)

    for entity in _iter_entity_items(scene_data.get("entities")):
        ent_name = entity.get("name")
        ent_type = (entity.get("type") or "").upper()
        if ent_name and ent_type in {"LOCATION", "LOC", "GPE", "PLACE", "FAC"}:
            _append(ent_name)

    return labels


def _extract_speaker_ids(scene_data: Dict[str, Any]) -> List[str]:
    speaker_ids: List[str] = []

    def _append(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        speaker = normalize_entity_name(raw)
        if speaker and speaker not in speaker_ids:
            speaker_ids.append(speaker)

    explicit_speaker_ids = scene_data.get("speaker_ids")
    if isinstance(explicit_speaker_ids, list):
        for speaker in explicit_speaker_ids:
            _append(speaker)

    for seg in scene_data.get("speaker_transcript", []) or []:
        if isinstance(seg, dict):
            _append(seg.get("speaker"))

    for speaker in scene_data.get("speakers", []) or []:
        if isinstance(speaker, str):
            _append(speaker)
        elif isinstance(speaker, dict):
            _append(speaker.get("speaker", speaker.get("label")))

    for seg in scene_data.get("diarization", []) or []:
        if isinstance(seg, dict):
            _append(seg.get("speaker"))

    return speaker_ids


def _preferred_entity_node_type(
    kg: KnowledgeGraph,
    ent_name: str,
    ent_type: Optional[str],
    entity_sources: Iterable[str],
) -> str:
    normalized_type = ent_type.strip().upper() if isinstance(ent_type, str) and ent_type.strip() else ""
    source_set = {str(source).strip().lower() for source in entity_sources if isinstance(source, str) and str(source).strip()}
    if normalized_type in _PERSON_ENTITY_TYPES:
        return "person"
    if normalized_type in _LOCATION_ENTITY_TYPES:
        return "location"
    if source_set.intersection(_TRANSCRIPT_ENTITY_SOURCES) and _is_likely_character_name(ent_name):
        return "person"

    cur = kg.conn.cursor()
    row = cur.execute(
        """
        SELECT node_type
        FROM nodes
        WHERE name = ? AND node_type IN ('person', 'location')
        ORDER BY CASE node_type
            WHEN 'person' THEN 0
            WHEN 'location' THEN 1
            ELSE 2
        END
        LIMIT 1
        """,
        (ent_name,),
    ).fetchone()
    if row is not None:
        return str(row["node_type"])
    return "entity"


def _add_scene_entities(kg: KnowledgeGraph, media_id: int, scene_data: Dict[str, Any], ts: float) -> Dict[str, int]:
    counts = {
        "nodes_added": 0,
        "links_added": 0,
        "edges_added": 0,
        "events_added": 0,
    }

    def add_and_link(
        node_type: str,
        name: str,
        *,
        confidence: float = 0.7,
        props: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        if not isinstance(name, str) or not name.strip():
            return None
        canonical_name = name.strip()
        if node_type != "scene":
            if not _is_valid_entity_token(canonical_name):
                return None
            canonical_name = normalize_entity_name(canonical_name)
            if not canonical_name:
                return None
        node_id = kg.add_node(node_type=node_type, name=canonical_name, properties=props or {}, timestamp=ts)
        kg.link_node_to_media(node_id=node_id, media_id=media_id, confidence=float(confidence), context=context or {})
        counts["nodes_added"] += 1
        counts["links_added"] += 1
        return int(node_id)

    def bump_node_occurrences(
        node_type: str,
        name: str,
        mentions: int,
        props: Optional[Dict[str, Any]] = None,
    ) -> None:
        repeat_count = max(0, int(mentions or 1) - 1)
        if repeat_count <= 0:
            return
        for _ in range(repeat_count):
            kg.add_node(node_type=node_type, name=name, properties=props or {}, timestamp=ts)
            counts["nodes_added"] += 1

    scene_identifier = scene_data.get("scene_id")
    if not isinstance(scene_identifier, str) or not scene_identifier.strip():
        scene_identifier = f"media_{media_id}"
    scene_node_id = add_and_link(
        "scene",
        scene_identifier.strip(),
        confidence=1.0,
        props={
            "source": "scene_bundle",
            "scene_id": scene_identifier.strip(),
            "video_id": scene_data.get("video_id"),
            "scene_index": scene_data.get("index"),
        },
        context={"start": scene_data.get("start"), "end": scene_data.get("end")},
    )
    person_node_ids: set[int] = set()
    person_node_names: Dict[int, str] = {}
    location_node_ids: set[int] = set()
    speaker_node_ids: set[int] = set()
    face_node_ids: set[int] = set()
    speaker_pattern_node_ids: set[int] = set()
    anonymous_face_node_ids: set[int] = set()
    anonymous_speaker_node_ids: set[int] = set()
    named_speaker_node_ids: set[int] = set()
    anonymous_face_context: Dict[int, Dict[str, Any]] = {}
    anonymous_speaker_context: Dict[int, Dict[str, Any]] = {}
    speaker_node_by_label: Dict[str, int] = {}
    speaker_pattern_context: Dict[int, Dict[str, Any]] = {}

    def add_structural_speaker(
        speaker_label: str,
        *,
        confidence: float,
        props: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        scoped_name = _scene_scoped_synthetic_speaker_name(scene_identifier, speaker_label)
        if not scoped_name:
            return None
        speaker_props = dict(props or {})
        speaker_props.setdefault("speaker_label", normalize_entity_name(str(speaker_label)))
        speaker_props.setdefault("scene_id", scene_identifier)
        node_id = kg.add_node(
            node_type="speaker",
            name=scoped_name,
            properties=speaker_props,
            timestamp=ts,
        )
        kg.link_node_to_media(
            node_id=node_id,
            media_id=media_id,
            confidence=float(confidence),
            context=context or {},
        )
        counts["nodes_added"] += 1
        counts["links_added"] += 1
        return int(node_id)

    for det in scene_data.get("objects", []) or []:
        if not isinstance(det, dict):
            continue
        label = det.get("label") or det.get("class")
        if not isinstance(label, str) or not label.strip():
            continue
        _ = add_and_link(
            "object",
            label.strip(),
            confidence=float(det.get("confidence", det.get("score", 0.5)) or 0.5),
            props={"source": "scene_object_detection"},
            context={"bbox": det.get("bbox")},
        )

    for idx, face in enumerate(scene_data.get("faces", []) or []):
        if not isinstance(face, dict):
            continue
        face_node_name = f"{scene_identifier.strip()}:face_{idx}"
        face_confidence = float(face.get("confidence", face.get("score", 0.8)) or 0.8)
        face_node_id = add_and_link(
            "face",
            face_node_name,
            confidence=face_confidence,
            props={"source": "scene_face_detection"},
            context={"bbox": face.get("bbox"), "face_index": idx},
        )
        if face_node_id is not None:
            face_node_ids.add(face_node_id)
        identity_name = _resolve_identity_name(face)
        if face_node_id is None or not identity_name:
            if face_node_id is not None:
                anonymous_face_node_ids.add(face_node_id)
                anonymous_face_context[face_node_id] = {
                    "face_index": idx,
                    "bbox": face.get("bbox"),
                }
            continue
        person_node_id = add_and_link(
            "person",
            identity_name,
            confidence=face_confidence,
            props={"source": "scene_face_identity"},
            context={"bbox": face.get("bbox"), "face_index": idx},
        )
        if person_node_id is not None:
            person_node_ids.add(person_node_id)
            person_node_names[person_node_id] = identity_name
            kg.add_edge(
                face_node_id,
                person_node_id,
                "identity_evidence",
                weight=face_confidence,
                properties={"source": "scene_face_detection"},
            )
            counts["edges_added"] += 1

    caption = scene_data.get("caption")
    if isinstance(caption, str) and caption.strip():
        _ = add_and_link("description", "scene_caption", confidence=0.9, props={"text": caption.strip()[:500]})

    ocr_text = scene_data.get("ocr_text")
    if isinstance(ocr_text, str) and ocr_text.strip():
        _ = add_and_link("concept", "text_overlay", confidence=0.8, props={"text": ocr_text.strip()[:500]})

    for tag in _iter_str_list(scene_data.get("tags")):
        _ = add_and_link("concept", tag, confidence=0.6)

    for entity in _collapse_entity_items(scene_data.get("entities")):
        ent_name = entity.get("name")
        if not ent_name:
            continue
        entity_sources = set(entity.get("sources") or [])
        mentions = int(entity.get("mentions", 1) or 1)
        node_type = _preferred_entity_node_type(kg, ent_name, entity.get("type"), entity_sources)
        if node_type == "person":
            props = {"source": "entity_extractor"}
            node_id = add_and_link("person", ent_name, confidence=0.7, props=props)
            if node_id is not None:
                person_node_ids.add(node_id)
                person_node_names[node_id] = ent_name
                bump_node_occurrences("person", ent_name, mentions, props=props)
            continue
        if node_type == "location":
            props = {"source": "entity_extractor"}
            node_id = add_and_link("location", ent_name, confidence=0.7, props=props)
            if node_id is not None:
                location_node_ids.add(node_id)
                bump_node_occurrences("location", ent_name, mentions, props=props)
            continue
        if not _is_meaningful_generic_entity(ent_name):
            continue
        node_id = add_and_link("entity", ent_name, confidence=0.7)
        if node_id is not None:
            bump_node_occurrences("entity", ent_name, mentions)

    for location in _extract_location_labels(scene_data):
        node_id = add_and_link("location", location, confidence=0.7, props={"source": "scene_location"})
        if node_id is not None:
            location_node_ids.add(node_id)

    emotions = scene_data.get("emotions")
    if isinstance(emotions, dict):
        for emo_name, emo_score in emotions.items():
            try:
                score = float(emo_score)
            except Exception:
                score = 0.0
            if score <= 0:
                continue
            _ = add_and_link("emotion", str(emo_name), confidence=max(0.1, min(score, 1.0)), props={"score": score})
    else:
        for emo_name in _iter_str_list(emotions):
            _ = add_and_link("emotion", emo_name, confidence=0.6)

    transcript = scene_data.get("transcript")
    if isinstance(transcript, str) and transcript.strip():
        _ = add_and_link("concept", "speech", confidence=0.9, props={"transcript": transcript.strip()[:500]})

    sentiment = scene_data.get("sentiment")
    if isinstance(sentiment, dict):
        label = sentiment.get("label")
        if isinstance(label, str) and label.strip():
            score = float(sentiment.get("score", 0.5) or 0.5)
            _ = add_and_link("sentiment", label.strip().lower(), confidence=max(0.1, min(score, 1.0)), props={"score": score})

    audio_emotion = scene_data.get("audio_emotion")
    if isinstance(audio_emotion, str) and audio_emotion.strip():
        _ = add_and_link("emotion", audio_emotion.strip(), confidence=0.6)
    elif isinstance(audio_emotion, dict):
        top = audio_emotion.get("top_emotion")
        if isinstance(top, str) and top.strip():
            _ = add_and_link("emotion", top.strip(), confidence=0.6)

    emitted_speaker_ids: set[str] = set()
    for seg in scene_data.get("speaker_transcript", []) or []:
        if not isinstance(seg, dict):
            continue
        speaker = seg.get("speaker")
        if not isinstance(speaker, str) or not speaker.strip():
            continue
        speaker_clean = normalize_entity_name(speaker)
        emitted_speaker_ids.add(speaker_clean)
        if _is_synthetic_speaker_label(speaker_clean):
            speaker_node_id = add_structural_speaker(
                speaker_clean,
                confidence=0.8,
                props={"source": "speaker_transcript"},
                context={"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text")},
            )
        else:
            speaker_node_id = add_and_link(
                "speaker",
                speaker_clean,
                confidence=0.8,
                props={"source": "speaker_transcript"},
                context={"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text")},
            )
        if speaker_node_id is not None:
            speaker_node_ids.add(speaker_node_id)
            speaker_node_by_label[speaker_clean] = speaker_node_id
            if _is_synthetic_speaker_label(speaker_clean):
                anonymous_speaker_node_ids.add(speaker_node_id)
                anonymous_speaker_context[speaker_node_id] = {
                    "speaker_label": speaker_clean,
                    "source": "speaker_transcript",
                }
            else:
                named_speaker_node_ids.add(speaker_node_id)

        if not _is_synthetic_speaker_label(speaker_clean):
            person_node_id = add_and_link(
                "person",
                speaker_clean,
                confidence=0.8,
                props={"source": "speaker_transcript"},
                context={"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text")},
            )
            if person_node_id is not None:
                person_node_ids.add(person_node_id)
                person_node_names[person_node_id] = speaker_clean
                if speaker_node_id is not None:
                    kg.add_edge(
                        speaker_node_id,
                        person_node_id,
                        "identity_evidence",
                        weight=0.8,
                        properties={"source": "speaker_transcript"},
                    )
                    counts["edges_added"] += 1

    for speaker_id in _extract_speaker_ids(scene_data):
        if speaker_id in emitted_speaker_ids:
            continue
        if _is_synthetic_speaker_label(speaker_id):
            speaker_node_id = add_structural_speaker(
                speaker_id,
                confidence=0.7,
                props={"source": "speaker_ids"},
            )
        else:
            speaker_node_id = add_and_link("speaker", speaker_id, confidence=0.7, props={"source": "speaker_ids"})
        if speaker_node_id is not None:
            speaker_node_ids.add(speaker_node_id)
            speaker_node_by_label[speaker_id] = speaker_node_id
            if _is_synthetic_speaker_label(speaker_id):
                anonymous_speaker_node_ids.add(speaker_node_id)
                anonymous_speaker_context.setdefault(
                    speaker_node_id,
                    {
                        "speaker_label": speaker_id,
                        "source": "speaker_ids",
                    },
                )
            else:
                named_speaker_node_ids.add(speaker_node_id)
        if not _is_synthetic_speaker_label(speaker_id):
            person_node_id = add_and_link("person", speaker_id, confidence=0.7, props={"source": "speaker_ids"})
            if person_node_id is not None:
                person_node_ids.add(person_node_id)
                person_node_names[person_node_id] = speaker_id
                if speaker_node_id is not None:
                    kg.add_edge(
                        speaker_node_id,
                        person_node_id,
                        "identity_evidence",
                        weight=0.7,
                        properties={"source": "speaker_ids"},
                    )
                    counts["edges_added"] += 1

    for speaker_label, signature in _speaker_voice_signature_map(scene_data).items():
        speaker_node_id = speaker_node_by_label.get(speaker_label)
        if speaker_node_id is None:
            continue
        pattern_result = _upsert_speaker_pattern_node(
            kg,
            scene_identifier=scene_identifier,
            speaker_label=speaker_label,
            signature=signature,
            timestamp=ts,
        )
        pattern_node_id = pattern_result.get("node_id")
        if pattern_node_id is None:
            continue
        pattern_node_id = int(pattern_node_id)
        speaker_pattern_node_ids.add(pattern_node_id)
        dominant_share = _speaker_duration_share(scene_data, speaker_label)
        pattern_context = {
            "speaker_label": speaker_label,
            "voice_similarity": pattern_result.get("similarity"),
            "voiced_seconds": float(signature.get("voiced_seconds") or 0.0),
            "segment_count": int(signature.get("segment_count") or 0),
            "dominant_share": dominant_share,
            "pattern_name": pattern_result.get("pattern_name"),
        }
        speaker_pattern_context[pattern_node_id] = pattern_context
        kg.link_node_to_media(
            node_id=pattern_node_id,
            media_id=media_id,
            confidence=float(pattern_result.get("similarity") or 1.0),
            context={
                "scene_id": scene_identifier,
                "speaker_label": speaker_label,
                "voiced_seconds": pattern_context["voiced_seconds"],
                "segment_count": pattern_context["segment_count"],
            },
        )
        counts["links_added"] += 1
        kg.add_edge(
            source_id=speaker_node_id,
            target_id=pattern_node_id,
            edge_type="voice_pattern_match",
            weight=float(pattern_result.get("similarity") or 1.0),
            properties={
                "source": "speaker_voice_signature",
                "scene_id": scene_identifier,
                "video_id": str(scene_data.get("video_id") or ""),
                "media_id": media_id,
                "speaker_label": speaker_label,
                "voiced_seconds": pattern_context["voiced_seconds"],
                "segment_count": pattern_context["segment_count"],
                "dominant_share": dominant_share,
                "pattern_name": pattern_result.get("pattern_name"),
                "created": bool(pattern_result.get("created")),
            },
        )
        counts["edges_added"] += 1

    for event in scene_data.get("music_events", []) or []:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type", "music"))
        conf = float(event.get("confidence", 0.5) or 0.5)
        _ = add_and_link(
            "audio_event",
            f"music_{event_type}",
            confidence=max(0.1, min(conf, 1.0)),
            props={"source": "music_events"},
            context={"start": event.get("start"), "end": event.get("end")},
        )

    time_hints = scene_data.get("time_hints")
    if isinstance(time_hints, dict):
        for hint_type, hints in time_hints.items():
            if not isinstance(hints, list):
                continue
            for hint in hints:
                _ = add_and_link(
                    "temporal_context",
                    f"{hint_type}_{hint}",
                    confidence=0.6,
                    props={"source": "time_hints"},
                )

    for person_node_id in sorted(person_node_ids):
        kg.add_edge(
            source_id=person_node_id,
            target_id=scene_node_id,
            edge_type="appears_in",
            weight=1.0,
            properties={"scene_id": scene_identifier, "media_id": media_id},
        )
        counts["edges_added"] += 1

    for speaker_node_id in sorted(speaker_node_ids):
        kg.add_edge(
            source_id=speaker_node_id,
            target_id=scene_node_id,
            edge_type="speaks_in",
            weight=1.0,
            properties={"scene_id": scene_identifier, "media_id": media_id},
        )
        counts["edges_added"] += 1

    for location_node_id in sorted(location_node_ids):
        kg.add_edge(
            source_id=scene_node_id,
            target_id=location_node_id,
            edge_type="located_in",
            weight=1.0,
            properties={"scene_id": scene_identifier, "media_id": media_id},
        )
        counts["edges_added"] += 1

    if len(person_node_ids) == 1:
        sole_person_node_id = next(iter(person_node_ids))
        sole_person_name = person_node_names.get(sole_person_node_id, "")
        allow_weak_identity_promotion = _weak_identity_candidate_allowed(
            sole_person_name,
            scene_data,
        )
        if allow_weak_identity_promotion and len(anonymous_speaker_node_ids) == 1 and not named_speaker_node_ids:
            speaker_node_id = next(iter(anonymous_speaker_node_ids))
            speaker_meta = anonymous_speaker_context.get(speaker_node_id, {})
            speaker_label = str(speaker_meta.get("speaker_label") or "")
            transcript_excerpt = _speaker_name_alignment_excerpt(
                scene_data,
                speaker_label,
                sole_person_name,
            )
            dominant_share = _speaker_duration_share(scene_data, speaker_label)
            if transcript_excerpt and dominant_share >= _SPEAKER_PATTERN_DOMINANT_SHARE_MIN:
                kg.add_edge(
                    source_id=speaker_node_id,
                    target_id=sole_person_node_id,
                    edge_type="identity_candidate",
                    weight=0.35,
                    properties={
                        "source": "scene_single_person_single_speaker",
                        "scene_id": scene_identifier,
                        "video_id": str(scene_data.get("video_id") or ""),
                        "media_id": media_id,
                        "evidence_strength": "weak",
                        "speaker_label": speaker_label,
                        "dominant_share": dominant_share,
                        "transcript_excerpt": transcript_excerpt,
                    },
                )
                counts["edges_added"] += 1
            for pattern_node_id in sorted(speaker_pattern_node_ids):
                pattern_meta = speaker_pattern_context.get(pattern_node_id, {})
                if pattern_meta.get("speaker_label") != speaker_label:
                    continue
                if not transcript_excerpt:
                    continue
                if float(pattern_meta.get("dominant_share") or 0.0) < _SPEAKER_PATTERN_DOMINANT_SHARE_MIN:
                    continue
                _append_identity_candidate_edge(
                    kg,
                    source_id=pattern_node_id,
                    target_id=sole_person_node_id,
                    weight=0.4,
                    properties={
                        "source": "scene_single_person_single_speaker_pattern",
                        "scene_id": scene_identifier,
                        "video_id": str(scene_data.get("video_id") or ""),
                        "media_id": media_id,
                        "evidence_strength": "weak",
                        "speaker_label": speaker_label,
                        "voice_similarity": pattern_meta.get("voice_similarity"),
                        "voiced_seconds": pattern_meta.get("voiced_seconds"),
                        "segment_count": pattern_meta.get("segment_count"),
                        "dominant_share": pattern_meta.get("dominant_share"),
                        "transcript_excerpt": transcript_excerpt,
                        "candidate_evidence": [
                            {
                                "scene_id": scene_identifier,
                                "video_id": str(scene_data.get("video_id") or ""),
                                "candidate_source": "scene_single_person_single_speaker_pattern",
                                "source_node_type": "speaker_pattern",
                                "speaker_label": speaker_label,
                                "voice_similarity": pattern_meta.get("voice_similarity"),
                                "voiced_seconds": pattern_meta.get("voiced_seconds"),
                                "segment_count": pattern_meta.get("segment_count"),
                                "dominant_share": pattern_meta.get("dominant_share"),
                                "transcript_excerpt": transcript_excerpt,
                            }
                        ],
                    },
                )
                counts["edges_added"] += 1
        if allow_weak_identity_promotion and len(face_node_ids) == 1 and len(anonymous_face_node_ids) == 1:
            face_node_id = next(iter(anonymous_face_node_ids))
            face_meta = anonymous_face_context.get(face_node_id, {})
            kg.add_edge(
                source_id=face_node_id,
                target_id=sole_person_node_id,
                edge_type="identity_candidate",
                weight=0.3,
                properties={
                    "source": "scene_single_person_single_face",
                    "scene_id": scene_identifier,
                    "media_id": media_id,
                    "evidence_strength": "weak",
                    "face_index": face_meta.get("face_index"),
                    "bbox": face_meta.get("bbox"),
                    "scene_excerpt": _identity_scene_excerpt(scene_data),
                },
            )
            counts["edges_added"] += 1

    counts["edges_added"] += _accumulate_identity_candidate_support(kg)
    counts["edges_added"] += _accumulate_identity_supported_evidence(kg)

    person_ids_sorted = sorted(person_node_ids)
    for left_idx, left_node_id in enumerate(person_ids_sorted):
        for right_node_id in person_ids_sorted[left_idx + 1 :]:
            kg.add_edge(
                source_id=left_node_id,
                target_id=right_node_id,
                edge_type="interacts_with",
                weight=1.0,
                properties={"scene_id": scene_identifier, "media_id": media_id},
            )
            counts["edges_added"] += 1

    return counts


def build_scene_relationships(kg: KnowledgeGraph, min_cooccurrence: int = 2) -> Dict[str, int]:
    cur = kg.conn.cursor()
    placeholders = ", ".join("?" for _ in sorted(_CO_OCCURRENCE_NODE_TYPES))
    rows = cur.execute(
        f"""
        SELECT nm1.node_id AS src, nm2.node_id AS dst, COUNT(*) AS co_count
        FROM node_media nm1
        JOIN node_media nm2 ON nm1.media_id = nm2.media_id
        JOIN nodes n1 ON n1.id = nm1.node_id
        JOIN nodes n2 ON n2.id = nm2.node_id
        WHERE nm1.node_id < nm2.node_id
          AND n1.node_type IN ({placeholders})
          AND n2.node_type IN ({placeholders})
        GROUP BY nm1.node_id, nm2.node_id
        HAVING co_count >= ?
        """,
        tuple(sorted(_CO_OCCURRENCE_NODE_TYPES)) + tuple(sorted(_CO_OCCURRENCE_NODE_TYPES)) + (int(min_cooccurrence),),
    ).fetchall()

    added = 0
    for row in rows:
        kg.add_edge(
            int(row["src"]),
            int(row["dst"]),
            "co_occurs",
            weight=float(row["co_count"]),
            properties={"count": int(row["co_count"])},
        )
        added += 1

    return {"co_occurrence_edges_added": added}


def update_kg_for_scene(
    scene_data: Dict[str, Any],
    scene_id: str,
    video_id: str,
    video_path: str,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    graph_db_path = _resolve_graph_db_path(cfg).resolve()
    graph_db_path.parent.mkdir(parents=True, exist_ok=True)

    start_time = float(scene_data.get("start_time", scene_data.get("start", 0.0)) or 0.0)
    end_time = float(scene_data.get("end_time", scene_data.get("end", start_time)) or start_time)
    duration = max(0.0, end_time - start_time)

    with KnowledgeGraph(str(graph_db_path)) as kg:
        canonical_video_id = str(video_id)
        speaker_ids = _extract_speaker_ids(scene_data)
        raw_speaker_count = scene_data.get("speaker_count")
        try:
            speaker_count = int(raw_speaker_count) if raw_speaker_count is not None else len(speaker_ids)
        except Exception:
            speaker_count = len(speaker_ids)
        if speaker_count < 0:
            speaker_count = 0
        if speaker_count == 0 and speaker_ids:
            speaker_count = len(speaker_ids)
        media_id = kg.add_media_node(
            media_type="video_scene",
            media_path=str(video_path),
            scene_id=scene_id,
            timestamp_start=start_time,
            timestamp_end=end_time,
            properties={
                "video_id": canonical_video_id,
                "video_hash": canonical_video_id,
                "confidence": scene_data.get("confidence", 0.0),
                "scene_index": scene_data.get("index"),
                "speaker_ids": speaker_ids,
                "speaker_count": speaker_count,
            },
        )

        scene_payload = dict(scene_data)
        scene_payload.setdefault("scene_id", scene_id)
        scene_payload.setdefault("video_id", canonical_video_id)
        scene_payload.setdefault("start", start_time)
        scene_payload.setdefault("end", end_time)
        ingest_counts = _add_scene_entities(kg, media_id, scene_payload, start_time)
        event_id = kg.add_temporal_event(
            event_type="scene_ingested",
            timestamp=start_time,
            duration=duration,
            properties={
                "scene_id": scene_id,
                "video_id": canonical_video_id,
                "video_hash": canonical_video_id,
                "media_id": media_id,
                "speaker_ids": speaker_ids,
                "speaker_count": speaker_count,
            },
        )
        ingest_counts["events_added"] += 1

        cur = kg.conn.cursor()
        node_rows = cur.execute(
            "SELECT DISTINCT node_id FROM node_media WHERE media_id = ?",
            (int(media_id),),
        ).fetchall()
        for row in node_rows:
            node_id = int(row["node_id"])
            kg.link_event_to_node(event_id, node_id, role="participant")

        rel_counts = build_scene_relationships(kg, min_cooccurrence=2)
        stats = kg.get_statistics()

    return {
        "status": "success",
        "graph_db_path": str(graph_db_path),
        "scene_id": scene_id,
        "video_id": canonical_video_id,
        "media_id": media_id,
        "ingest_counts": ingest_counts,
        "relationship_counts": rel_counts,
        "statistics": stats,
    }
