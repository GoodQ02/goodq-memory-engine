from __future__ import annotations
import os
import re
import json
import sqlite3
import logging
import requests
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional

from steps.common.config_loader import load_configs, get_runtime_paths

logger = logging.getLogger(__name__)

def get_scene_date_range(scene_row: sqlite3.Row, filename: str) -> tuple[Optional[int], Optional[int], str]:
    """
    Extract the minimum year, maximum year, and a timestamp label for a scene.
    First tries to read explicit dates from scene metadata.
    Falls back to parsing years from the filename.
    """
    meta_str = scene_row["meta"]
    meta = json.loads(meta_str) if meta_str else {}
    
    hints = meta.get("time_hints") or meta.get("metadata_time_hints") or {}
    explicit_dates = hints.get("explicit_dates") or []
    
    if explicit_dates:
        years = []
        for d in explicit_dates:
            try:
                # e.g., "1987-08-10"
                y = int(d.split("-")[0])
                years.append(y)
            except Exception:
                pass
        if years:
            return min(years), max(years), str(explicit_dates[0])
            
    # Fallback to parsing years in the filename (e.g. "01. 1987 - 1988.mp4")
    years_in_file = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", filename)]
    if years_in_file:
        min_y = min(years_in_file)
        max_y = max(years_in_file)
        if min_y == max_y:
            return min_y, max_y, f"{min_y} (estimated)"
        return min_y, max_y, f"{min_y} - {max_y} (estimated)"
        
    return None, None, "unknown"

def load_scene_to_file_mapping(kg_uri: str) -> Dict[str, str]:
    """
    Load a mapping of scene_id to absolute video file path from the knowledge graph.
    """
    mapping = {}
    conn = sqlite3.connect(kg_uri, uri=True)
    try:
        cursor = conn.execute("SELECT scene_id, media_path FROM media_nodes WHERE scene_id IS NOT NULL")
        for row in cursor:
            mapping[str(row[0])] = str(row[1])
    except Exception as e:
        logger.debug(f"Failed to load scene to file mapping from KG: {e}")
    finally:
        conn.close()
    return mapping

def get_scene_vector(scene_id: str, config: Dict[str, Any]) -> Optional[List[float]]:
    """
    Retrieve text vector embedding for a scene.
    Attempts read-only Qdrant query first, then falls back to read-only SQLite embeddings table.
    """
    # Attempt 1: Fetch from Qdrant if enabled
    try:
        qdrant_cfg = config.get("qdrant", {})
        if qdrant_cfg.get("enabled", False):
            host = qdrant_cfg.get("host", "http://localhost:6333")
            collections = qdrant_cfg.get("collections", {})
            text_collection = collections.get("text", "goodq_text")
            
            from steps.common.qdrant_client import QdrantClient, QdrantConfig
            client = QdrantClient(QdrantConfig(
                host=host,
                collection=text_collection,
                dim=384,
            ))
            point_id = client._normalize_point_id(f"{scene_id}_text")
            if point_id:
                url = f"{host}/collections/{text_collection}/points"
                resp = requests.post(url, json={"ids": [point_id], "with_vector": True}, timeout=1.5)
                if resp.status_code == 200:
                    result = resp.json().get("result")
                    if result and isinstance(result, list) and len(result) > 0:
                        vec = result[0].get("vector")
                        if vec:
                            return [float(x) for x in vec]
    except Exception as e:
        logger.debug(f"Qdrant vector fetch failed for scene {scene_id}: {e}")
        
    # Attempt 2: Fallback to SQLite embeddings table (read-only URI)
    try:
        paths = get_runtime_paths(config)
        db_path = paths["db_path"]
        db_uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        try:
            row = conn.execute(
                "SELECT vector FROM embeddings WHERE scene_id = ? AND modality = 'text' AND vector IS NOT NULL",
                (scene_id,)
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT vector FROM embeddings WHERE scene_id = ? AND vector IS NOT NULL LIMIT 1",
                    (scene_id,)
                ).fetchone()
            if row and row[0]:
                vec = np.frombuffer(row[0], dtype=np.float32)
                return [float(x) for x in vec]
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"SQLite vector fallback failed for scene {scene_id}: {e}")
        
    return None

def compute_similarity(scene_id_1: str, scene_id_2: str, config: Dict[str, Any]) -> float:
    """
    Compute cosine similarity between two scene text embeddings.
    Defaults to 0.0 if vectors are unavailable.
    """
    v1 = get_scene_vector(scene_id_1, config)
    v2 = get_scene_vector(scene_id_2, config)
    
    if v1 is None or v2 is None:
        return 0.0
        
    try:
        arr1 = np.array(v1, dtype=np.float32)
        arr2 = np.array(v2, dtype=np.float32)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return float(np.dot(arr1, arr2) / (norm1 * norm2))
    except Exception as e:
        logger.warning(f"Error computing cosine similarity: {e}")
        return 0.0

def temporal_search(
    entities: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    time_hint: Optional[str] = None,
    source_file: Optional[str] = None,
    modality: Optional[List[str]] = None,
    max_results: int = 25,
    grouping: str = "semantic_episode",
    config: Optional[Dict[str, Any]] = None,
    expected_epoch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute chronological narrative search.
    Enforces read-only URI database access patterns.
    """
    resolved_config = config if config is not None else load_configs({})
    paths = get_runtime_paths(resolved_config)
    db_path = Path(paths["db_path"])
    kg_path = Path(paths["knowledge_graph_db"])
    if expected_epoch_id is not None and (
        db_path.parent.name != expected_epoch_id
        or kg_path.parent.name != expected_epoch_id
    ):
        raise RuntimeError("Temporal search epoch scope changed before retrieval")
    
    db_uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
    kg_uri = f"{Path(kg_path).resolve().as_uri()}?mode=ro"
    
    # 1. Identify matching scene IDs based on entity filters
    matched_scene_ids = set()
    has_entities_filter = bool(entities)
    
    if has_entities_filter and entities:
        # Search in KG
        conn_kg = sqlite3.connect(kg_uri, uri=True)
        try:
            placeholders = ",".join("?" for _ in entities)
            lower_entities = [e.lower() for e in entities]
            cursor = conn_kg.execute(
                f"""
                SELECT DISTINCT mn.scene_id
                FROM media_nodes mn
                JOIN node_media nm ON mn.id = nm.media_id
                JOIN nodes n ON nm.node_id = n.id
                WHERE LOWER(n.name) IN ({placeholders})
                """,
                lower_entities
            )
            for row in cursor:
                if row[0]:
                    matched_scene_ids.add(str(row[0]))
        except Exception as e:
            logger.warning(f"Failed entity search in KG: {e}")
        finally:
            conn_kg.close()
            
        # Search in memory.db metadata
        conn_mem = sqlite3.connect(db_uri, uri=True)
        try:
            cursor = conn_mem.execute("SELECT id, meta FROM scenes")
            for row in cursor:
                scene_id = str(row[0])
                meta_str = row[1]
                if not meta_str:
                    continue
                try:
                    meta = json.loads(meta_str)
                except Exception:
                    continue
                
                scene_entities = []
                for key in ["entities", "primary_tags", "tags", "keywords", "objects"]:
                    val = meta.get(key)
                    if isinstance(val, list):
                        scene_entities.extend([str(item).lower() for item in val if item])
                
                audio = meta.get("audio")
                if isinstance(audio, dict):
                    for key in ["entities", "tags"]:
                        val = audio.get(key)
                        if isinstance(val, list):
                            scene_entities.extend([str(item).lower() for item in val if item])
                            
                keyframe = meta.get("keyframe")
                if isinstance(keyframe, dict):
                    for key in ["entities", "tags", "objects"]:
                        val = keyframe.get(key)
                        if isinstance(val, list):
                            scene_entities.extend([str(item).lower() for item in val if item])
                            
                if any(e.lower() in scene_entities for e in entities):
                    matched_scene_ids.add(scene_id)
        except Exception as e:
            logger.warning(f"Failed entity search in memory metadata: {e}")
        finally:
            conn_mem.close()

    # 2. Load scene summaries map
    summaries_map = {}
    conn_mem = sqlite3.connect(db_uri, uri=True)
    try:
        cursor = conn_mem.execute("SELECT content FROM summaries WHERE category='scene_summary'")
        for row in cursor:
            try:
                content = json.loads(row[0])
                sid = content.get("scene_id")
                sum_text = content.get("summary")
                if sid and sum_text:
                    summaries_map[str(sid)] = sum_text
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Failed loading summaries: {e}")
    finally:
        conn_mem.close()
        
    # 3. Load all entities associated with each scene from KG
    kg_entities_map = {}
    conn_kg = sqlite3.connect(kg_uri, uri=True)
    try:
        cursor = conn_kg.execute(
            """
            SELECT mn.scene_id, n.name
            FROM media_nodes mn
            JOIN node_media nm ON mn.id = nm.media_id
            JOIN nodes n ON nm.node_id = n.id
            WHERE n.node_type NOT IN ('scene', 'speaker', 'face')
            """
        )
        for row in cursor:
            sid = row[0]
            name = row[1]
            if sid and name:
                kg_entities_map.setdefault(str(sid), set()).add(str(name))
    except Exception as e:
        logger.warning(f"Failed loading KG entity relations: {e}")
    finally:
        conn_kg.close()

    # 4. Load scene-to-file path mapping
    scene_files = load_scene_to_file_mapping(kg_uri)
    
    # 5. Extract query date constraints
    q_min_year = None
    q_max_year = None
    if start_date:
        try:
            q_min_year = int(start_date.split("-")[0])
        except Exception:
            pass
    if end_date:
        try:
            q_max_year = int(end_date.split("-")[0])
        except Exception:
            pass
    if time_hint:
        years_in_hint = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", time_hint)]
        if years_in_hint:
            if q_min_year is None:
                q_min_year = min(years_in_hint)
            else:
                q_min_year = min(q_min_year, min(years_in_hint))
            if q_max_year is None:
                q_max_year = max(years_in_hint)
            else:
                q_max_year = max(q_max_year, max(years_in_hint))

    # 6. Fetch matching scene details and apply filters
    candidates = []
    conn_mem = sqlite3.connect(db_uri, uri=True)
    conn_mem.row_factory = sqlite3.Row
    try:
        if has_entities_filter:
            if matched_scene_ids:
                placeholders = ",".join("?" for _ in matched_scene_ids)
                cursor = conn_mem.execute(
                    f"SELECT id, video_hash, start, end, meta FROM scenes WHERE id IN ({placeholders})",
                    list(matched_scene_ids)
                )
            else:
                cursor = conn_mem.execute("SELECT id, video_hash, start, end, meta FROM scenes WHERE 1=0")
        else:
            cursor = conn_mem.execute("SELECT id, video_hash, start, end, meta FROM scenes")
            
        for row in cursor:
            scene_id = str(row["id"])
            start_time = float(row["start"] or 0.0)
            end_time = float(row["end"] or start_time)
            meta_str = row["meta"]
            meta = json.loads(meta_str) if meta_str else {}
            
            # File filter
            media_path = scene_files.get(scene_id)
            if media_path:
                filename = os.path.basename(media_path)
            else:
                filename = "unknown_video.mp4"
                kf_path = meta.get("keyframe", {}).get("path")
                if kf_path:
                    filename = os.path.basename(kf_path)
                    
            if source_file:
                if filename.lower() != source_file.lower():
                    continue
                    
            # Date filter
            scene_min_year, scene_max_year, timestamp_label = get_scene_date_range(row, filename)
            if scene_min_year is not None:
                if q_min_year is not None and scene_max_year < q_min_year:
                    continue
                if q_max_year is not None and scene_min_year > q_max_year:
                    continue
                    
            # Build entity set
            entities_set = set()
            for key in ["entities", "primary_tags", "tags", "keywords", "objects"]:
                val = meta.get(key)
                if isinstance(val, list):
                    entities_set.update([str(item) for item in val if item])
            audio_sec = meta.get("audio")
            if isinstance(audio_sec, dict):
                for key in ["entities", "tags"]:
                    val = audio_sec.get(key)
                    if isinstance(val, list):
                        entities_set.update([str(item) for item in val if item])
            kf_sec = meta.get("keyframe")
            if isinstance(kf_sec, dict):
                for key in ["entities", "tags", "objects"]:
                    val = kf_sec.get(key)
                    if isinstance(val, list):
                        entities_set.update([str(item) for item in val if item])
            # Add KG nodes
            if scene_id in kg_entities_map:
                entities_set.update(kg_entities_map[scene_id])
                
            transcript = meta.get("audio", {}).get("transcript") or meta.get("transcript") or ""
            visual_tags = meta.get("keyframe", {}).get("tags") or meta.get("tags") or []
            objects = meta.get("keyframe", {}).get("objects") or meta.get("objects") or []
            all_visual_tags = sorted(list(set([str(t) for t in visual_tags if t] + [str(obj) for obj in objects if obj])))
            
            artifact_paths = []
            kf_path = meta.get("keyframe", {}).get("path")
            if kf_path:
                artifact_paths.append(kf_path)
                
            summary = summaries_map.get(scene_id) or meta.get("narrative_summary") or ""
            
            candidates.append({
                "scene_id": scene_id,
                "source_file": filename,
                "start_time": start_time,
                "end_time": end_time,
                "timestamp_label": timestamp_label,
                "entities": sorted(list(entities_set)),
                "summary": summary,
                "evidence": {
                    "transcript": transcript,
                    "visual_tags": all_visual_tags,
                    "artifact_paths": artifact_paths
                }
            })
    except Exception as e:
        logger.warning(f"Error querying matching scenes: {e}")
    finally:
        conn_mem.close()
        
    # 7. Sort chronologically (by tape filename alphabetically, then start_time)
    candidates.sort(key=lambda x: (x["source_file"], x["start_time"]))
    
    # 8. Limit results
    sliced_results = candidates[:max_results]
    
    # 9. Compute distance and similarity metrics sequentially
    for i in range(len(sliced_results)):
        curr = sliced_results[i]
        if i == 0:
            curr["temporal_distance_from_previous"] = 0.0
            curr["semantic_similarity_from_previous"] = 0.0
        else:
            prev = sliced_results[i-1]
            if curr["source_file"] == prev["source_file"]:
                # Difference in seconds between current start and previous end
                curr["temporal_distance_from_previous"] = max(0.0, round(curr["start_time"] - prev["end_time"], 2))
            else:
                curr["temporal_distance_from_previous"] = 0.0
                
            curr["semantic_similarity_from_previous"] = round(
                compute_similarity(
                    curr["scene_id"],
                    prev["scene_id"],
                    resolved_config,
                ),
                4,
            )
            
    return {
        "query": {
            "entities": entities or [],
            "grouping": grouping
        },
        "results": sliced_results
    }
