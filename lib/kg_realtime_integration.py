from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from lib.knowledge_graph import KnowledgeGraph


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


def _add_scene_entities(kg: KnowledgeGraph, media_id: int, scene_data: Dict[str, Any], ts: float) -> Dict[str, int]:
    counts = {
        "nodes_added": 0,
        "links_added": 0,
        "events_added": 0,
    }

    def add_and_link(
        node_type: str,
        name: str,
        *,
        confidence: float = 0.7,
        props: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        node_id = kg.add_node(node_type=node_type, name=name, properties=props or {}, timestamp=ts)
        kg.link_node_to_media(node_id=node_id, media_id=media_id, confidence=float(confidence), context=context or {})
        counts["nodes_added"] += 1
        counts["links_added"] += 1

    for det in scene_data.get("objects", []) or []:
        if not isinstance(det, dict):
            continue
        label = det.get("label") or det.get("class")
        if not isinstance(label, str) or not label.strip():
            continue
        add_and_link(
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
            add_and_link(
                "person",
                face_name,
                confidence=float(face.get("confidence", face.get("score", 0.8)) or 0.8),
                props={"source": "scene_face_detection"},
                context={"bbox": face.get("bbox")},
            )

    caption = scene_data.get("caption")
    if isinstance(caption, str) and caption.strip():
        add_and_link("description", "scene_caption", confidence=0.9, props={"text": caption.strip()[:500]})

    ocr_text = scene_data.get("ocr_text")
    if isinstance(ocr_text, str) and ocr_text.strip():
        add_and_link("concept", "text_overlay", confidence=0.8, props={"text": ocr_text.strip()[:500]})

    for tag in _iter_str_list(scene_data.get("tags")):
        add_and_link("concept", tag, confidence=0.6)

    for entity in _iter_str_list(scene_data.get("entities")):
        add_and_link("entity", entity, confidence=0.7)

    emotions = scene_data.get("emotions")
    if isinstance(emotions, dict):
        for emo_name, emo_score in emotions.items():
            try:
                score = float(emo_score)
            except Exception:
                score = 0.0
            if score <= 0:
                continue
            add_and_link("emotion", str(emo_name), confidence=max(0.1, min(score, 1.0)), props={"score": score})
    else:
        for emo_name in _iter_str_list(emotions):
            add_and_link("emotion", emo_name, confidence=0.6)

    transcript = scene_data.get("transcript")
    if isinstance(transcript, str) and transcript.strip():
        add_and_link("concept", "speech", confidence=0.9, props={"transcript": transcript.strip()[:500]})

    sentiment = scene_data.get("sentiment")
    if isinstance(sentiment, dict):
        label = sentiment.get("label")
        if isinstance(label, str) and label.strip():
            score = float(sentiment.get("score", 0.5) or 0.5)
            add_and_link("sentiment", label.strip().lower(), confidence=max(0.1, min(score, 1.0)), props={"score": score})

    audio_emotion = scene_data.get("audio_emotion")
    if isinstance(audio_emotion, str) and audio_emotion.strip():
        add_and_link("emotion", audio_emotion.strip(), confidence=0.6)
    elif isinstance(audio_emotion, dict):
        top = audio_emotion.get("top_emotion")
        if isinstance(top, str) and top.strip():
            add_and_link("emotion", top.strip(), confidence=0.6)

    for seg in scene_data.get("speaker_transcript", []) or []:
        if not isinstance(seg, dict):
            continue
        speaker = seg.get("speaker")
        if not isinstance(speaker, str) or not speaker.strip():
            continue
        add_and_link(
            "person",
            f"speaker_{speaker.strip()}",
            confidence=0.8,
            props={"source": "speaker_transcript"},
            context={"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text")},
        )

    if not (scene_data.get("speaker_transcript") or []):
        for speaker in scene_data.get("speakers", []) or []:
            if isinstance(speaker, str) and speaker.strip():
                add_and_link("person", f"speaker_{speaker.strip()}", confidence=0.7, props={"source": "speaker_list"})
            elif isinstance(speaker, dict):
                sid = speaker.get("speaker", speaker.get("label"))
                if isinstance(sid, str) and sid.strip():
                    add_and_link("person", f"speaker_{sid.strip()}", confidence=0.7, props={"source": "speaker_dict"})

    for event in scene_data.get("music_events", []) or []:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type", "music"))
        conf = float(event.get("confidence", 0.5) or 0.5)
        add_and_link(
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
                add_and_link(
                    "temporal_context",
                    f"{hint_type}_{hint}",
                    confidence=0.6,
                    props={"source": "time_hints"},
                )

    return counts


def build_scene_relationships(kg: KnowledgeGraph, min_cooccurrence: int = 2) -> Dict[str, int]:
    cur = kg.conn.cursor()
    rows = cur.execute(
        """
        SELECT nm1.node_id AS src, nm2.node_id AS dst, COUNT(*) AS co_count
        FROM node_media nm1
        JOIN node_media nm2 ON nm1.media_id = nm2.media_id
        WHERE nm1.node_id < nm2.node_id
        GROUP BY nm1.node_id, nm2.node_id
        HAVING co_count >= ?
        """,
        (int(min_cooccurrence),),
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

    start_time = float(scene_data.get("start_time", 0.0) or 0.0)
    end_time = float(scene_data.get("end_time", start_time) or start_time)
    duration = max(0.0, end_time - start_time)

    with KnowledgeGraph(str(graph_db_path)) as kg:
        canonical_video_id = str(video_id)
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
            },
        )

        ingest_counts = _add_scene_entities(kg, media_id, scene_data, start_time)
        event_id = kg.add_temporal_event(
            event_type="scene_ingested",
            timestamp=start_time,
            duration=duration,
            properties={
                "scene_id": scene_id,
                "video_id": canonical_video_id,
                "video_hash": canonical_video_id,
                "media_id": media_id,
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
