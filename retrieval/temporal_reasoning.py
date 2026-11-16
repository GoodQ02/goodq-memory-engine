from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import url2pathname

import numpy as np

from api.utils.loaders import scene_is_retired
from lib.grounding_markup import strip_grounding_markup
from scripts.ucf.ucf_ledger import read_scene_retirements
from steps.common.config_loader import get_runtime_paths, load_configs
from steps.common.qdrant_client import QdrantClient, QdrantConfig, build_qdrant_session
from steps.common.sqlite_read_authority import open_sqlite_read_connection
from steps.common.ucf_retirement import _read_scene_retirements

logger = logging.getLogger(__name__)

_SEMANTIC_DICT_LABEL_KEYS = ("label", "name", "entity", "tag", "category", "class", "text")
_RESTRICTED_TRANSCRIPT_OUTCOMES = frozenset(
    {
        "low_confidence",
        "no_speech",
        "no_intelligible_speech",
        "runtime_failure",
        "withheld_recognition_uncertainty",
    }
)
_EPISODE_MAX_TEMPORAL_GAP_SECONDS = 120.0
_EPISODE_MIN_SEMANTIC_SIMILARITY = 0.45


def _coerce_sqlite_path(target: Path | str) -> Path:
    text = str(target or "").strip()
    if text.startswith("file:"):
        parsed = urlparse(text)
        raw_path = url2pathname(parsed.path)
        return Path(raw_path)
    return Path(text)


def _extract_clean_labels(items: Any) -> List[str]:
    """Extract semantic string labels from str/dict lists without leaking paths or raw dicts."""
    if items is None:
        return []
    seq: Iterable[Any] = items if isinstance(items, (list, tuple, set)) else [items]
    cleaned: List[str] = []
    seen: set[str] = set()
    for item in seq:
        candidate: Optional[str] = None
        if isinstance(item, str):
            raw = item.strip()
            if raw.startswith("{") and raw.endswith("}"):
                continue
            candidate = raw
        elif isinstance(item, dict):
            for key in _SEMANTIC_DICT_LABEL_KEYS:
                val = item.get(key)
                if isinstance(val, str) and val.strip():
                    candidate = val.strip()
                    break
        if not candidate:
            continue
        stripped = str(strip_grounding_markup(candidate)).strip()
        if not stripped:
            continue
        if stripped not in seen:
            seen.add(stripped)
            cleaned.append(stripped)
    return cleaned


def _scene_transcript_is_restricted(meta: Dict[str, Any]) -> bool:
    """Return True when scene ASR text is withheld due to recognition uncertainty or failure."""
    if not isinstance(meta, dict):
        return False
    audio = meta.get("audio") if isinstance(meta.get("audio"), dict) else {}
    for container in (meta, audio):
        outcome = str(container.get("transcript_outcome") or "").strip().lower()
        if outcome in _RESTRICTED_TRANSCRIPT_OUTCOMES:
            return True
        for evidence_key in ("transcription_evidence", "scene_context_epistemic"):
            ev = container.get(evidence_key)
            if isinstance(ev, dict) and ev.get("text_status") == "withheld_recognition_uncertainty":
                return True
    try:
        from steps.common.context_analyzer_llm import _transcription_text_is_restricted

        if _transcription_text_is_restricted(meta):
            return True
        if audio and ("transcription_coverage" in audio or "audio_evidence" in audio):
            if _transcription_text_is_restricted(audio):
                return True
    except Exception as exc:
        logger.debug("Transcript restriction check failed closed: %s", exc)
        return True
    return False


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
                y = int(d.split("-")[0])
                years.append(y)
            except Exception:
                pass
        if years:
            return min(years), max(years), str(explicit_dates[0])

    years_in_file = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", filename)]
    if years_in_file:
        min_y = min(years_in_file)
        max_y = max(years_in_file)
        if min_y == max_y:
            return min_y, max_y, f"{min_y} (estimated)"
        return min_y, max_y, f"{min_y} - {max_y} (estimated)"

    return None, None, "unknown"


def load_scene_to_file_mapping(kg_target: Path | str) -> Dict[str, str]:
    """
    Load a mapping of scene_id to video file path from the knowledge graph using read-only authority.
    """
    mapping: Dict[str, str] = {}
    kg_path = _coerce_sqlite_path(kg_target)
    try:
        conn = open_sqlite_read_connection(kg_path)
    except FileNotFoundError:
        return mapping
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
    Retrieve promoted text vector embedding for a scene.
    Attempts loopback read-only Qdrant query first, then falls back to read-only SQLite embeddings table.
    """
    paths = get_runtime_paths(config)
    db_path = Path(paths["db_path"])
    expected_epoch = db_path.parent.name if db_path.name else None

    try:
        qdrant_cfg = config.get("qdrant", {})
        if qdrant_cfg.get("enabled", False):
            host = str(qdrant_cfg.get("host", "http://localhost:6333")).rstrip("/")
            collections = qdrant_cfg.get("collections", {})
            text_collection = collections.get("text", "goodq_text")

            client = QdrantClient(
                QdrantConfig(
                    host=host,
                    collection=text_collection,
                    dim=384,
                )
            )
            point_id = client._normalize_point_id(f"{scene_id}_text")
            if point_id:
                url = f"{host}/collections/{text_collection}/points"
                session = build_qdrant_session(host)
                try:
                    resp = session.post(
                        url,
                        json={"ids": [point_id], "with_vector": True, "with_payload": True},
                        timeout=1.5,
                    )
                finally:
                    session.close()
                if resp.status_code == 200:
                    result = resp.json().get("result")
                    if result and isinstance(result, list) and len(result) > 0:
                        point = result[0] if isinstance(result[0], dict) else {}
                        payload = point.get("payload") if isinstance(point.get("payload"), dict) else {}
                        status_val = payload.get("ucf_promotion_status")
                        payload_epoch = payload.get("epoch_id")
                        epoch_ok = (
                            expected_epoch is None
                            or payload_epoch in (None, expected_epoch)
                        )
                        if status_val == "promoted" and epoch_ok:
                            vec = point.get("vector")
                            if vec:
                                return [float(x) for x in vec]
    except Exception as e:
        logger.debug(f"Qdrant vector fetch failed for scene {scene_id}: {e}")

    try:
        conn = open_sqlite_read_connection(db_path)
        try:
            row = conn.execute(
                "SELECT vector FROM embeddings WHERE scene_id = ? AND modality = 'text' AND vector IS NOT NULL",
                (scene_id,),
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT vector FROM embeddings WHERE scene_id = ? AND vector IS NOT NULL LIMIT 1",
                    (scene_id,),
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


def _order_and_slice_candidates(
    candidates: List[Dict[str, Any]],
    *,
    grouping: str,
    max_results: int,
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Order and bound candidate scenes according to requested grouping mode."""
    if not candidates or max_results <= 0:
        return []

    mode = (grouping or "semantic_episode").strip().lower()
    if mode in {"chronological", "none", "timeline"}:
        ordered = sorted(
            candidates,
            key=lambda x: (x["start_time"], x["end_time"], x["source_file"], x["scene_id"]),
        )
        return ordered[:max_results]

    # Default: "semantic_episode" — cluster contiguous scenes per source into coherent
    # episodes using temporal gap and semantic similarity, then order episodes by their
    # earliest timestamp while keeping scenes within each episode contiguous.
    by_source = sorted(
        candidates,
        key=lambda x: (x["source_file"], x["start_time"], x["end_time"], x["scene_id"]),
    )
    episodes: List[List[Dict[str, Any]]] = []
    current_episode: List[Dict[str, Any]] = []

    for item in by_source:
        if not current_episode:
            current_episode = [item]
            continue
        prev = current_episode[-1]
        same_source = item["source_file"] == prev["source_file"]
        gap = max(0.0, float(item["start_time"]) - float(prev["end_time"]))
        if not same_source or gap > _EPISODE_MAX_TEMPORAL_GAP_SECONDS:
            episodes.append(current_episode)
            current_episode = [item]
            continue
        v_prev = get_scene_vector(prev["scene_id"], config)
        v_curr = get_scene_vector(item["scene_id"], config)
        if v_prev is not None and v_curr is not None:
            arr1 = np.array(v_prev, dtype=np.float32)
            arr2 = np.array(v_curr, dtype=np.float32)
            n1 = float(np.linalg.norm(arr1))
            n2 = float(np.linalg.norm(arr2))
            sim = float(np.dot(arr1, arr2) / (n1 * n2)) if n1 > 0.0 and n2 > 0.0 else 0.0
            if sim < _EPISODE_MIN_SEMANTIC_SIMILARITY:
                episodes.append(current_episode)
                current_episode = [item]
                continue
        current_episode.append(item)

    if current_episode:
        episodes.append(current_episode)

    episodes.sort(
        key=lambda ep: (ep[0]["start_time"], ep[0]["source_file"], ep[0]["scene_id"])
    )
    flattened: List[Dict[str, Any]] = []
    for ep in episodes:
        for scene in ep:
            flattened.append(scene)
            if len(flattened) >= max_results:
                return flattened
    return flattened


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
    Enforces read-only SQLite authority and UCF promoted/non-retired visibility.
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

    epoch_id = db_path.parent.name
    ledger_path = db_path.parent / "ucf" / "ucf_ledger.db"
    has_ledger = ledger_path.is_file()

    # 1. Identify matching scene IDs based on entity filters
    matched_scene_ids: set[str] = set()
    has_entities_filter = bool(entities)
    lower_entities = [str(e).strip().lower() for e in (entities or []) if str(e).strip()]

    if has_entities_filter and lower_entities:
        if kg_path.is_file():
            conn_kg = open_sqlite_read_connection(kg_path)
            try:
                placeholders = ",".join("?" for _ in lower_entities)
                cursor = conn_kg.execute(
                    f"""
                    SELECT DISTINCT mn.scene_id
                    FROM media_nodes mn
                    JOIN node_media nm ON mn.id = nm.media_id
                    JOIN nodes n ON nm.node_id = n.id
                    WHERE LOWER(n.name) IN ({placeholders})
                    """,
                    lower_entities,
                )
                for row in cursor:
                    if row[0]:
                        matched_scene_ids.add(str(row[0]))
            except Exception as e:
                logger.warning(f"Failed entity search in KG: {e}")
            finally:
                conn_kg.close()

        conn_mem = open_sqlite_read_connection(db_path)
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
                if not isinstance(meta, dict):
                    continue

                scene_entities: set[str] = set()
                for key in ("entities", "primary_tags", "tags", "keywords", "objects"):
                    scene_entities.update(
                        lbl.lower() for lbl in _extract_clean_labels(meta.get(key))
                    )

                audio = meta.get("audio")
                if isinstance(audio, dict):
                    for key in ("entities", "tags"):
                        scene_entities.update(
                            lbl.lower() for lbl in _extract_clean_labels(audio.get(key))
                        )

                keyframe = meta.get("keyframe")
                if isinstance(keyframe, dict):
                    for key in ("entities", "tags", "objects"):
                        scene_entities.update(
                            lbl.lower() for lbl in _extract_clean_labels(keyframe.get(key))
                        )

                if any(ent in scene_entities for ent in lower_entities):
                    matched_scene_ids.add(scene_id)
        except Exception as e:
            logger.warning(f"Failed entity search in memory metadata: {e}")
        finally:
            conn_mem.close()

    # 2. Load scene summaries map
    summaries_map: Dict[str, str] = {}
    conn_mem = open_sqlite_read_connection(db_path)
    try:
        cursor = conn_mem.execute("SELECT content FROM summaries WHERE category='scene_summary'")
        for row in cursor:
            try:
                content = json.loads(row[0])
                sid = content.get("scene_id")
                sum_text = content.get("summary")
                if sid and sum_text:
                    summaries_map[str(sid)] = str(strip_grounding_markup(str(sum_text)))
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Failed loading summaries: {e}")
    finally:
        conn_mem.close()

    # 3. Load all entities associated with each scene from KG
    kg_entities_map: Dict[str, set[str]] = {}
    if kg_path.is_file():
        conn_kg = open_sqlite_read_connection(kg_path)
        try:
            cursor = conn_kg.execute(
                """
                SELECT mn.scene_id, n.name
                FROM media_nodes mn
                JOIN node_media nm ON mn.id = nm.media_id
                JOIN nodes n ON nm.node_id = n.id
                WHERE n.node_type NOT IN ('scene', 'speaker', 'face', 'evidence', 'segment', 'video')
                """
            )
            for row in cursor:
                sid = row[0]
                name = row[1]
                if sid and name:
                    cleaned_names = _extract_clean_labels([str(name)])
                    if cleaned_names:
                        kg_entities_map.setdefault(str(sid), set()).update(cleaned_names)
        except Exception as e:
            logger.warning(f"Failed loading KG entity relations: {e}")
        finally:
            conn_kg.close()

    # 4. Load scene-to-file path mapping
    scene_files = load_scene_to_file_mapping(kg_path)

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
            q_min_year = min(years_in_hint) if q_min_year is None else min(q_min_year, min(years_in_hint))
            q_max_year = max(years_in_hint) if q_max_year is None else max(q_max_year, max(years_in_hint))

    # 6. Fetch matching scene details and apply UCF promoted + retirement + metadata filters
    candidates: List[Dict[str, Any]] = []
    conn_mem = open_sqlite_read_connection(db_path)
    conn_mem.row_factory = sqlite3.Row
    ledger_conn = open_sqlite_read_connection(ledger_path) if has_ledger else None
    ucf_cache: Dict[str, Tuple[bool, set[int], set[str], List[Tuple[float, float]], List[dict]]] = {}
    try:
        if has_entities_filter:
            if matched_scene_ids:
                placeholders = ",".join("?" for _ in matched_scene_ids)
                cursor = conn_mem.execute(
                    f"SELECT id, video_hash, start, end, meta FROM scenes WHERE id IN ({placeholders})",
                    list(matched_scene_ids),
                )
            else:
                cursor = conn_mem.execute("SELECT id, video_hash, start, end, meta FROM scenes WHERE 1=0")
        else:
            cursor = conn_mem.execute("SELECT id, video_hash, start, end, meta FROM scenes")

        for row in cursor:
            scene_id = str(row["id"])
            video_hash = str(row["video_hash"] or "")
            start_time = float(row["start"] or 0.0)
            end_time = float(row["end"] or start_time)
            meta_str = row["meta"]
            meta = json.loads(meta_str) if meta_str else {}
            if not isinstance(meta, dict):
                meta = {}

            if ledger_conn is not None:
                if not video_hash:
                    continue
                cached = ucf_cache.get(video_hash)
                if cached is None:
                    all_rows = ledger_conn.execute(
                        "SELECT frame_id, source_artifact_id, t_start, t_end, promotion_status, worker_name "
                        "FROM context_frames WHERE video_hash = ? AND epoch_id = ?",
                        (video_hash, epoch_id),
                    ).fetchall()
                    non_binding_rows = [
                        r for r in all_rows if r[5] != "transcript_outcome_binding_candidate"
                    ]
                    all_terminal = bool(all_rows) and all(
                        r[4] in {"rejected", "superseded"} for r in all_rows
                    )
                    has_any = bool(non_binding_rows) or all_terminal
                    l_rows = [r for r in non_binding_rows if r[4] == "promoted"]
                    p_fids = {int(r[0]) for r in l_rows if r[0] is not None}
                    p_sids = {str(r[1]) for r in l_rows if r[1] is not None and str(r[1])}
                    p_bounds = [
                        (float(r[2]), float(r[3]))
                        for r in l_rows
                        if isinstance(r[2], (int, float))
                        and not isinstance(r[2], bool)
                        and isinstance(r[3], (int, float))
                        and not isinstance(r[3], bool)
                    ]
                    retired_list = _read_scene_retirements(
                        ledger_conn, video_hash=video_hash, epoch_id=epoch_id
                    )
                    cached = (has_any, p_fids, p_sids, p_bounds, retired_list)
                    ucf_cache[video_hash] = cached
                has_any, p_fids, p_sids, p_bounds, retired_list = cached
                if scene_is_retired(
                    {"scene_id": scene_id, "start": start_time, "end": end_time},
                    retired_list,
                ):
                    continue
                if has_any:
                    if not p_fids:
                        continue
                    prov = meta.get("ucf_provenance")
                    if isinstance(prov, list) and prov:
                        if not any(isinstance(fid, int) and not isinstance(fid, bool) and fid in p_fids for fid in prov):
                            continue
                    elif p_sids or p_bounds:
                        id_ok = scene_id in p_sids
                        bound_ok = any(
                            start_time - 0.001 <= b_s <= b_e <= end_time + 0.001
                            for b_s, b_e in p_bounds
                        )
                        if not (id_ok or bound_ok):
                            continue
                elif (meta.get("source_kind") or "video") != "video":
                    continue
            else:
                retired = read_scene_retirements(ledger_path, video_hash=video_hash)
                if scene_is_retired(
                    {"scene_id": scene_id, "start": start_time, "end": end_time},
                    retired,
                ):
                    continue

            media_path = scene_files.get(scene_id)
            if media_path:
                filename = os.path.basename(media_path)
            else:
                filename = "unknown_video.mp4"
                kf_path = (meta.get("keyframe") or {}).get("path") if isinstance(meta.get("keyframe"), dict) else None
                if kf_path:
                    filename = os.path.basename(kf_path)

            if source_file and filename.lower() != source_file.lower():
                continue

            scene_min_year, scene_max_year, timestamp_label = get_scene_date_range(row, filename)
            if scene_min_year is not None:
                if q_min_year is not None and scene_max_year < q_min_year:
                    continue
                if q_max_year is not None and scene_min_year > q_max_year:
                    continue

            entities_set: set[str] = set()
            for key in ("entities", "primary_tags", "tags", "keywords", "objects"):
                entities_set.update(_extract_clean_labels(meta.get(key)))
            audio_sec = meta.get("audio")
            if isinstance(audio_sec, dict):
                for key in ("entities", "tags"):
                    entities_set.update(_extract_clean_labels(audio_sec.get(key)))
            kf_sec = meta.get("keyframe")
            if isinstance(kf_sec, dict):
                for key in ("entities", "tags", "objects"):
                    entities_set.update(_extract_clean_labels(kf_sec.get(key)))
            if scene_id in kg_entities_map:
                entities_set.update(kg_entities_map[scene_id])

            if _scene_transcript_is_restricted(meta):
                transcript = ""
            else:
                raw_transcript = (
                    (audio_sec.get("transcript") if isinstance(audio_sec, dict) else None)
                    or meta.get("transcript")
                    or ""
                )
                transcript = str(strip_grounding_markup(str(raw_transcript))).strip()

            visual_tags_raw = (
                (kf_sec.get("tags") if isinstance(kf_sec, dict) else None)
                or meta.get("primary_tags")
                or meta.get("tags")
                or []
            )
            objects_raw = (
                (kf_sec.get("objects") if isinstance(kf_sec, dict) else None)
                or meta.get("objects")
                or []
            )
            all_visual_tags = sorted(
                set(_extract_clean_labels(visual_tags_raw)) | set(_extract_clean_labels(objects_raw))
            )

            artifact_paths: List[str] = []
            kf_path = kf_sec.get("path") if isinstance(kf_sec, dict) else None
            if kf_path:
                artifact_paths.append(str(kf_path))

            raw_summary = summaries_map.get(scene_id) or meta.get("narrative_summary") or ""
            summary = str(strip_grounding_markup(str(raw_summary))).strip()

            candidates.append(
                {
                    "scene_id": scene_id,
                    "source_file": filename,
                    "start_time": start_time,
                    "end_time": end_time,
                    "timestamp_label": timestamp_label,
                    "entities": sorted(entities_set),
                    "summary": summary,
                    "evidence": {
                        "transcript": transcript,
                        "visual_tags": all_visual_tags,
                        "artifact_paths": artifact_paths,
                    },
                }
            )
    except Exception as e:
        logger.warning(f"Error querying matching scenes: {e}")
    finally:
        conn_mem.close()
        if ledger_conn is not None:
            ledger_conn.close()

    # 7. Order and bound results according to grouping mode
    sliced_results = _order_and_slice_candidates(
        candidates,
        grouping=grouping,
        max_results=max_results,
        config=resolved_config,
    )

    # 8. Compute distance and similarity metrics sequentially
    for i, curr in enumerate(sliced_results):
        if i == 0:
            curr["temporal_distance_from_previous"] = 0.0
            curr["semantic_similarity_from_previous"] = 0.0
        else:
            prev = sliced_results[i - 1]
            if curr["source_file"] == prev["source_file"]:
                curr["temporal_distance_from_previous"] = max(
                    0.0, round(curr["start_time"] - prev["end_time"], 2)
                )
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
            "grouping": grouping,
        },
        "results": sliced_results,
    }
