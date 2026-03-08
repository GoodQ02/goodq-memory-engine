from __future__ import annotations

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
    location_node_ids: set[int] = set()
    speaker_node_ids: set[int] = set()

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
        if isinstance(face, dict):
            identity = face.get("identity")
            if isinstance(identity, str) and identity.strip():
                face_name = f"face_{identity.strip()}"
            else:
                face_name = f"face_{idx}"
            node_id = add_and_link(
                "person",
                face_name,
                confidence=float(face.get("confidence", face.get("score", 0.8)) or 0.8),
                props={"source": "scene_face_detection"},
                context={"bbox": face.get("bbox")},
            )
            if node_id is not None:
                person_node_ids.add(node_id)

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
        speaker_node_id = add_and_link(
            "speaker",
            speaker_clean,
            confidence=0.8,
            props={"source": "speaker_transcript"},
            context={"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text")},
        )
        if speaker_node_id is not None:
            speaker_node_ids.add(speaker_node_id)

        person_node_id = add_and_link(
            "person",
            f"speaker_{speaker_clean}",
            confidence=0.8,
            props={"source": "speaker_transcript"},
            context={"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text")},
        )
        if person_node_id is not None:
            person_node_ids.add(person_node_id)

    for speaker_id in _extract_speaker_ids(scene_data):
        if speaker_id in emitted_speaker_ids:
            continue
        speaker_node_id = add_and_link("speaker", speaker_id, confidence=0.7, props={"source": "speaker_ids"})
        if speaker_node_id is not None:
            speaker_node_ids.add(speaker_node_id)
        person_node_id = add_and_link("person", f"speaker_{speaker_id}", confidence=0.7, props={"source": "speaker_ids"})
        if person_node_id is not None:
            person_node_ids.add(person_node_id)

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
