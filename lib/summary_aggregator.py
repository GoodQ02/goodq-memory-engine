from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sqlite3
import uuid

from filelock import FileLock

from api.utils.loaders import DataLoader

logger = logging.getLogger(__name__)

OCCASION_KEYWORDS = {
    "holiday": ["holiday", "christmas", "santa", "thanksgiving", "easter", "new year", "halloween"],
    "birthday": ["birthday", "birth"],
    "wedding": ["wedding", "marriage", "bride", "groom"],
    "graduation": ["graduation", "graduate"],
    "vacation": ["vacation", "trip", "travel", "beach", "hotel"],
    "school": ["school", "class", "teacher", "student", "grad"],
    "family_gathering": ["gathering", "reunion", "dinner", "party", "celebration", "anniversary", "family"]
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_stable_entity_id(node_type: str, name: str) -> str:
    return f"{node_type}:{name}"


def _parse_stable_entity_id(entity_id: str) -> Tuple[str, str]:
    if ":" in entity_id:
        node_type, name = entity_id.split(":", 1)
        return node_type, name
    raise ValueError(f"Invalid stable entity_id: {entity_id}")


def _classify_occasion_type(name: str) -> Optional[str]:
    name_lower = name.lower()
    for o_type, keywords in OCCASION_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return o_type
    return None


def get_scope_metadata(db_path: Path, data_loader: DataLoader) -> Dict[str, Any]:
    """Compile execution scope metadata."""
    video_ids = data_loader.list_processed_videos()
    video_count = len(video_ids)
    
    # Load all temporal indices to count scenes
    scene_count = 0
    temporal_index_count = 0
    for vid in video_ids:
        idx = data_loader.load_temporal_index(vid)
        if idx:
            temporal_index_count += 1
            scene_count += len(idx.get("segments", []))

    return {
        "epoch": db_path.parent.name,
        "db_path": db_path.name,
        "video_count": video_count,
        "scene_count": scene_count,
        "temporal_index_count": temporal_index_count,
        "video_ids": video_ids,
        "generated_at_utc": _utc_now_iso(),
        "source_surfaces_used": ["sqlite_knowledge_graph", "temporal_index_json"]
    }


def get_summary_dashboard(db_path: Path, data_loader: DataLoader) -> Dict[str, Any]:
    """
    Query SQLite and temporal indexes to return cumulative dashboard data.
    """
    scope = get_scope_metadata(db_path, data_loader)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 1. Fetch People (major entities), aggregating manually stitched speaker patterns
    people_rows = cur.execute(
        """
        SELECT id, name, occurrence_count, first_seen, last_seen, properties
        FROM nodes
        WHERE node_type = 'person'
        """
    ).fetchall()
    
    # Get all active manual identity stitching mappings (speaker_pattern -> person)
    mappings_rows = cur.execute(
        """
        SELECT source_id, target_id
        FROM edges
        WHERE edge_type = 'identity_evidence'
        """
    ).fetchall()
    
    target_to_sources = {}
    for mr in mappings_rows:
        target_to_sources.setdefault(mr["target_id"], []).append(mr["source_id"])
        
    node_rows = cur.execute("SELECT id, occurrence_count, first_seen, last_seen FROM nodes").fetchall()
    nodes_dict = {nr["id"]: nr for nr in node_rows}
    
    people = []
    for r in people_rows:
        person_id = r["id"]
        name = r["name"]
        
        count = int(r["occurrence_count"] or 0)
        f_seen = r["first_seen"]
        l_seen = r["last_seen"]
        
        source_ids = target_to_sources.get(person_id, [])
        for src_id in source_ids:
            src_node = nodes_dict.get(src_id)
            if src_node:
                count += int(src_node["occurrence_count"] or 0)
                src_f = src_node["first_seen"]
                src_l = src_node["last_seen"]
                if src_f is not None:
                    f_seen = src_f if f_seen is None else min(f_seen, src_f)
                if src_l is not None:
                    l_seen = src_l if l_seen is None else max(l_seen, src_l)
                    
        people.append({
            "entity_id": _get_stable_entity_id("person", name),
            "name": name,
            "occurrence_count": count,
            "first_seen": f_seen,
            "last_seen": l_seen
        })
    people.sort(key=lambda x: x["occurrence_count"], reverse=True)
        
    # 2. Fetch Places (locations)
    places_rows = cur.execute(
        """
        SELECT name, occurrence_count, first_seen, last_seen
        FROM nodes
        WHERE node_type = 'location'
        ORDER BY occurrence_count DESC
        """
    ).fetchall()
    
    places = []
    for r in places_rows:
        places.append({
            "entity_id": _get_stable_entity_id("location", r["name"]),
            "name": r["name"],
            "occurrence_count": int(r["occurrence_count"]),
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"]
        })
        
    # 3. Occasions logic
    # Select nodes from temporal_context or other types matching keywords
    all_nodes = cur.execute(
        "SELECT node_type, name, occurrence_count, properties FROM nodes"
    ).fetchall()
    
    occasions = []
    for r in all_nodes:
        name = r["name"]
        o_type = _classify_occasion_type(name)
        if o_type:
            props = json.loads(r["properties"]) if r["properties"] else {}
            occasions.append({
                "entity_id": _get_stable_entity_id(r["node_type"], name),
                "name": name,
                "occurrence_count": int(r["occurrence_count"]),
                "occasion_type": o_type,
                "source": props.get("source", "extracted"),
                "confidence": float(props.get("confidence", 1.0))
            })
            
    # Sort occasions by occurrence
    occasions.sort(key=lambda x: x["occurrence_count"], reverse=True)
    
    # 4. Sentiment & Emotion summary from all temporal indexes
    sentiment_distribution = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
    emotion_counts = {}
    
    # Built-in Highlights collections lists
    positive_moments = []
    negative_moments = []
    multi_person_gatherings = []
    
    video_ids = data_loader.list_processed_videos()
    for vid in video_ids:
        temporal_index = data_loader.load_temporal_index(vid)
        if not temporal_index:
            continue
        
        video_title = Path(temporal_index.get("video_path") or vid).stem
        
        for seg in temporal_index.get("segments", []):
            scene_id = seg.get("scene_id")
            if not scene_id:
                continue
            
            # Sentiment counts
            sent = (seg.get("sentiment_label") or "").upper()
            if sent in sentiment_distribution:
                sentiment_distribution[sent] += 1
            else:
                sentiment_distribution["NEUTRAL"] += 1
                
            # Emotion tracking
            audio_emo = seg.get("audio_emotion")
            if audio_emo:
                emotion_counts[audio_emo] = emotion_counts.get(audio_emo, 0) + 1
            
            text_emo_ranking = seg.get("text_emotion_ranking", [])
            if text_emo_ranking and isinstance(text_emo_ranking, list):
                top_text_emo = text_emo_ranking[0]
                if isinstance(top_text_emo, dict) and top_text_emo.get("label"):
                    l = top_text_emo["label"]
                    emotion_counts[l] = emotion_counts.get(l, 0) + 1
                    
            # Build scene reference payload
            scene_ref = {
                "video_id": vid,
                "video_title": video_title,
                "scene_id": str(scene_id),
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "representative_frame": seg.get("representative_frame"),
                "transcript": seg.get("full_transcript") or seg.get("transcript")
            }
            
            # Filter positive/negative built-in highlights
            if sent == "POSITIVE":
                positive_moments.append(scene_ref)
            elif sent == "NEGATIVE":
                negative_moments.append(scene_ref)
                
            # Speaker count multi-person gatherings
            speaker_count = seg.get("speaker_count") or len(seg.get("speaker_ids", []))
            visible_count = len(seg.get("visible_people", []))
            if speaker_count >= 3 or visible_count >= 3:
                multi_person_gatherings.append(scene_ref)

    # Top emotions formatting
    top_emotions = []
    for emo, count in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        top_emotions.append({"emotion": emo, "count": count})
        
    conn.close()
    
    return {
        "scope_metadata": scope,
        "people": people,
        "places": places,
        "occasions": occasions,
        "sentiment_distribution": sentiment_distribution,
        "top_emotions": top_emotions,
        "built_in_highlights": {
            "positive_moments": positive_moments[:12],  # Cap display size
            "negative_moments": negative_moments[:12],
            "multi_person_gatherings": multi_person_gatherings[:12]
        }
    }


def get_entity_profile(db_path: Path, data_loader: DataLoader, entity_id: str) -> Dict[str, Any]:
    """
    Compile detailed profile response for a major entity.
    """
    node_type, name = _parse_stable_entity_id(entity_id)
    scope = get_scope_metadata(db_path, data_loader)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Fetch node statistics from graph
    node_row = cur.execute(
        "SELECT id, occurrence_count, first_seen, last_seen FROM nodes WHERE node_type = ? AND name = ?",
        (node_type, name)
    ).fetchone()
    
    if not node_row:
        conn.close()
        raise ValueError(f"Entity profile node not found: {entity_id}")
        
    node_id = int(node_row["id"])
    occurrence_count = int(node_row["occurrence_count"] or 0)
    first_seen = node_row["first_seen"]
    last_seen = node_row["last_seen"]
    
    # Get stitched source nodes if this is a person
    source_ids = []
    raw_speaker_ids = []
    if node_type == "person":
        mappings_rows = cur.execute(
            "SELECT source_id FROM edges WHERE target_id = ? AND edge_type = 'identity_evidence'",
            (node_id,)
        ).fetchall()
        source_ids = [mr["source_id"] for mr in mappings_rows]
        
        for src_id in source_ids:
            src_row = cur.execute(
                "SELECT occurrence_count, first_seen, last_seen FROM nodes WHERE id = ?",
                (src_id,)
            ).fetchone()
            if src_row:
                occurrence_count += int(src_row["occurrence_count"] or 0)
                src_f = src_row["first_seen"]
                src_l = src_row["last_seen"]
                if src_f is not None:
                    first_seen = src_f if first_seen is None else min(first_seen, src_f)
                if src_l is not None:
                    last_seen = src_l if last_seen is None else max(last_seen, src_l)
                    
        # Fetch raw speaker nodes connected to any of the speaker patterns (source_ids)
        if source_ids:
            placeholders_src = ",".join("?" for _ in source_ids)
            speaker_rows = cur.execute(
                f"SELECT source_id FROM edges WHERE target_id IN ({placeholders_src}) AND edge_type = 'voice_pattern_match'",
                source_ids
            ).fetchall()
            raw_speaker_ids = [sr["source_id"] for sr in speaker_rows]
            
    elif node_type == "speaker_pattern":
        # If the node itself is a speaker_pattern, get raw speaker nodes matching it
        speaker_rows = cur.execute(
            "SELECT source_id FROM edges WHERE target_id = ? AND edge_type = 'voice_pattern_match'",
            (node_id,)
        ).fetchall()
        raw_speaker_ids = [sr["source_id"] for sr in speaker_rows]

    all_node_ids = [node_id] + source_ids + raw_speaker_ids
    placeholders = ",".join("?" for _ in all_node_ids)
    
    # Fetch co-occurring nodes
    co_occur_rows = cur.execute(
        f"""
        SELECT n.id, n.node_type, n.name, COUNT(*) AS co_occurrence_count
        FROM node_media nm1
        JOIN node_media nm2 ON nm1.media_id = nm2.media_id
        JOIN nodes n ON n.id = nm2.node_id
        WHERE nm1.node_id IN ({placeholders}) 
          AND nm2.node_id NOT IN ({placeholders})
          AND n.node_type IN ('person', 'location', 'concept', 'temporal_context')
        GROUP BY n.id, n.node_type, n.name
        ORDER BY co_occurrence_count DESC, n.name ASC
        LIMIT 25
        """,
        all_node_ids + all_node_ids
    ).fetchall()
    
    co_occurrences = []
    for r in co_occur_rows:
        co_occurrences.append({
            "entity_id": _get_stable_entity_id(r["node_type"], r["name"]),
            "node_type": r["node_type"],
            "name": r["name"],
            "co_occurrence_count": int(r["co_occurrence_count"])
        })
        
    # Find all media nodes / scenes where this node is present
    media_rows = cur.execute(
        f"""
        SELECT m.scene_id, m.media_path, m.properties
        FROM node_media nm
        JOIN media_nodes m ON nm.media_id = m.id
        WHERE nm.node_id IN ({placeholders})
        """,
        all_node_ids
    ).fetchall()
    
    scene_ids = {r["scene_id"] for r in media_rows if r["scene_id"]}
    
    # Scan temporal indexes to load detailed scene details
    scenes = []
    sentiment_distribution = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
    emotion_counts = {}
    
    video_ids = data_loader.list_processed_videos()
    for vid in video_ids:
        temporal_index = data_loader.load_temporal_index(vid)
        if not temporal_index:
            continue
        
        video_title = Path(temporal_index.get("video_path") or vid).stem
        for seg in temporal_index.get("segments", []):
            seg_scene_id = seg.get("scene_id")
            if seg_scene_id in scene_ids:
                # Add to playlist scenes
                scenes.append({
                    "video_id": vid,
                    "video_title": video_title,
                    "scene_id": str(seg_scene_id),
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "representative_frame": seg.get("representative_frame"),
                    "transcript": seg.get("full_transcript") or seg.get("transcript")
                })
                
                # Update profile sentiment stats
                sent = (seg.get("sentiment_label") or "").upper()
                if sent in sentiment_distribution:
                    sentiment_distribution[sent] += 1
                else:
                    sentiment_distribution["NEUTRAL"] += 1
                    
                # Update profile emotion stats
                audio_emo = seg.get("audio_emotion")
                if audio_emo:
                    emotion_counts[audio_emo] = emotion_counts.get(audio_emo, 0) + 1
                    
                text_emo_ranking = seg.get("text_emotion_ranking", [])
                if text_emo_ranking and isinstance(text_emo_ranking, list):
                    top_text_emo = text_emo_ranking[0]
                    if isinstance(top_text_emo, dict) and top_text_emo.get("label"):
                        l = top_text_emo["label"]
                        emotion_counts[l] = emotion_counts.get(l, 0) + 1

    # Sort scenes chronologically (by start time)
    scenes.sort(key=lambda x: x["start"])
    
    # Top emotions
    top_emotions = []
    for emo, count in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        top_emotions.append({"emotion": emo, "count": count})
        
    conn.close()
    
    return {
        "scope_metadata": scope,
        "entity_id": entity_id,
        "node_type": node_type,
        "name": name,
        "occurrence_count": occurrence_count,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "co_occurrences": co_occurrences,
        "scenes": scenes,
        "sentiment_distribution": sentiment_distribution,
        "top_emotions": top_emotions
    }


def _collections_file(db_path: Path) -> Path:
    return Path(db_path).parent / "saved_collections.json"


def _collections_lock(collections_file: Path) -> FileLock:
    lock_path = collections_file.with_name(f"{collections_file.name}.lock")
    return FileLock(str(lock_path))


def _validate_collections_data(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise RuntimeError("saved collections store root is invalid")
    if data.get("schema_version") != 1:
        raise RuntimeError("saved collections store schema version is invalid")
    collections = data.get("collections")
    if not isinstance(collections, list):
        raise RuntimeError("saved collections store collection list is invalid")

    collection_ids: set[str] = set()
    for collection in collections:
        if not isinstance(collection, dict):
            raise RuntimeError("saved collections store entry is invalid")
        collection_id = collection.get("collection_id")
        if not isinstance(collection_id, str) or not collection_id.strip():
            raise RuntimeError("saved collections store collection ID is invalid")
        if collection_id in collection_ids:
            raise RuntimeError(
                "saved collections store contains duplicate collection IDs"
            )
        collection_ids.add(collection_id)
        if collection.get("status") not in {"active", "deleted"}:
            raise RuntimeError("saved collections store collection status is invalid")
        if not isinstance(collection.get("history"), list):
            raise RuntimeError("saved collections store collection history is invalid")
    return data


def _load_collections_unlocked(collections_file: Path) -> Dict[str, Any]:
    if not collections_file.is_file():
        return {"schema_version": 1, "collections": []}
    try:
        with collections_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read saved collections store", exc_info=True)
        raise RuntimeError("saved collections store is malformed") from exc
    return _validate_collections_data(data)


def _fsync_directory_if_supported(directory: Path) -> bool:
    """Best-effort directory durability; Windows cannot open directories this way."""
    if os.name == "nt":
        return False
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(directory, flags)
        os.fsync(descriptor)
        return True
    except OSError:
        logger.warning("Directory fsync is unavailable for the saved collections store")
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _save_collections_unlocked(collections_file: Path, data: Dict[str, Any]) -> None:
    _validate_collections_data(data)
    collections_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = collections_file.with_name(
        f"{collections_file.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    )
    try:
        with temp_file.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_file, collections_file)
        _fsync_directory_if_supported(collections_file.parent)
    except Exception as exc:
        logger.error("Failed to save saved collections store", exc_info=True)
        raise RuntimeError("Failed to save collections") from exc
    finally:
        try:
            temp_file.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove saved collections temporary file", exc_info=True)


def load_collections(db_path: Path) -> Dict[str, Any]:
    """Load and strictly validate custom collections under the shared store lock."""
    collections_file = _collections_file(db_path)
    with _collections_lock(collections_file):
        return _load_collections_unlocked(collections_file)


def save_collections(db_path: Path, data: Dict[str, Any]) -> None:
    """Durably replace custom collections under the shared store lock."""
    collections_file = _collections_file(db_path)
    with _collections_lock(collections_file):
        _save_collections_unlocked(collections_file, data)


def add_collection(db_path: Path, col_request: Dict[str, Any], created_by: str = "operator") -> Dict[str, Any]:
    """Add a new custom collection atomically."""
    collections_file = _collections_file(db_path)
    with _collections_lock(collections_file):
        data = _load_collections_unlocked(collections_file)
        collections = data["collections"]

        timestamp = _utc_now_iso()
        collection_id = (
            f"col_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:12]}"
        )

        history_entry = {
            "action": "create",
            "timestamp_utc": timestamp,
            "operator_note": col_request.get("operator_note") or "Initial creation"
        }

        new_collection = {
            "collection_id": collection_id,
            "name": col_request["name"],
            "description": col_request.get("description"),
            "status": "active",
            "collection_type": col_request.get("collection_type", "manual_playlist"),
            "query_params": col_request.get("query_params") or {},
            "scene_refs": col_request.get("scene_refs") or [],
            "source_epoch": db_path.parent.name,
            "created_at_utc": timestamp,
            "created_by": created_by,
            "updated_at_utc": timestamp,
            "deleted_at_utc": None,
            "history": [history_entry]
        }

        collections.append(new_collection)
        _save_collections_unlocked(collections_file, data)
        return new_collection


def soft_delete_collection(db_path: Path, collection_id: str) -> bool:
    """Soft delete a custom collection atomically by setting status='deleted'."""
    collections_file = _collections_file(db_path)
    with _collections_lock(collections_file):
        data = _load_collections_unlocked(collections_file)
        collections = data["collections"]

        target = None
        for col in collections:
            if col.get("collection_id") == collection_id and col.get("status") == "active":
                target = col
                break

        if not target:
            return False

        timestamp = _utc_now_iso()
        target["status"] = "deleted"
        target["deleted_at_utc"] = timestamp
        target["updated_at_utc"] = timestamp
        target["history"].append({
            "action": "delete",
            "timestamp_utc": timestamp,
            "operator_note": "Soft-deleted by operator"
        })

        _save_collections_unlocked(collections_file, data)
        return True
