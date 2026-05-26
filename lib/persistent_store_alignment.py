from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


def build_persistent_store_alignment(
    *,
    scene_results_path: str | Path,
    memory_db_path: str | Path | None = None,
    knowledge_graph_db_path: str | Path | None = None,
    sample_limit: int = 10,
) -> Dict[str, Any]:
    """Build a read-only alignment summary for canonical scenes, memory.db, and KG.

    The canonical input is an existing scene_ingest_results.json. This helper
    does not scan raw run roots, rebuild conduits, mutate databases, or infer
    current-run vector success from historical persistence.
    """

    canonical = _canonical_scene_scope(Path(scene_results_path), sample_limit=sample_limit)
    scene_ids = set(canonical.get("scene_ids") or [])
    memory = _memory_alignment(Path(memory_db_path) if memory_db_path else None, scene_ids, sample_limit=sample_limit)
    kg = _kg_alignment(Path(knowledge_graph_db_path) if knowledge_graph_db_path else None, scene_ids, sample_limit=sample_limit)

    warnings: List[str] = []
    if canonical.get("warnings"):
        warnings.extend(f"canonical:{warning}" for warning in canonical.get("warnings") or [])
    if memory.get("warnings"):
        warnings.extend(f"memory:{warning}" for warning in memory.get("warnings") or [])
    if kg.get("warnings"):
        warnings.extend(f"knowledge_graph:{warning}" for warning in kg.get("warnings") or [])

    memory_missing = int(memory.get("missing_scene_count") or 0)
    kg_missing = int(kg.get("missing_scene_count") or 0)
    if not scene_ids:
        status = "empty"
    elif memory_missing or kg_missing:
        status = "warn"
    else:
        status = "ok"

    return {
        "mode": "read_only_persistent_store_alignment",
        "status": status,
        "source": "scene_ingest_results.json plus existing memory.db and knowledge_graph.db",
        "canonical": _without_internal_scene_ids(canonical),
        "memory": memory,
        "knowledge_graph": kg,
        "alignment": {
            "canonical_scene_count": len(scene_ids),
            "memory_missing_scene_count": memory_missing,
            "knowledge_graph_missing_scene_count": kg_missing,
            "status": "aligned" if status == "ok" else status,
            "warnings": warnings,
        },
        "safety_boundary": {
            "read_only": True,
            "scene_results_only": True,
            "raw_run_roots_scanned": False,
            "conduits_built": False,
            "databases_mutated": False,
            "ingestion_triggered": False,
            "current_run_vector_success_inferred": False,
            "raw_paths_returned": False,
        },
    }


def _canonical_scene_scope(path: Path, *, sample_limit: int) -> Dict[str, Any]:
    obj = _read_json(path)
    items = _result_items(obj)
    videos: List[Dict[str, Any]] = []
    scene_ids: Set[str] = set()
    warnings: List[str] = []

    for item in items:
        video_id = _clean_str(item.get("video_id")) or _clean_str(item.get("video_hash")) or "unknown_video"
        scenes = _canonical_scenes_from_item(item)
        if not scenes:
            warnings.append(f"no_scenes_for_video:{video_id}")
        video_scene_ids: List[str] = []
        for scene in scenes:
            scene_id = _clean_str(scene.get("scene_id")) or _clean_str(scene.get("id"))
            if not scene_id:
                continue
            scene_ids.add(scene_id)
            video_scene_ids.append(scene_id)
        videos.append(
            {
                "video_id": video_id,
                "scene_count": len(video_scene_ids),
                "scene_id_sample": video_scene_ids[:sample_limit],
            }
        )

    return {
        "source_kind": "scene_ingest_results",
        "video_count": len(videos),
        "scene_count": len(scene_ids),
        "videos": videos,
        "scene_id_sample": sorted(scene_ids)[:sample_limit],
        "scene_ids": sorted(scene_ids),
        "warnings": sorted(set(warnings)),
    }


def _result_items(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [item for item in obj if isinstance(item, dict)]
    if isinstance(obj, dict):
        for key in ("results", "items", "videos"):
            value = obj.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [obj]
    return []


def _canonical_scenes_from_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    scenes = item.get("scenes")
    if isinstance(scenes, list):
        return [scene for scene in scenes if isinstance(scene, dict)]

    temporal_index = item.get("temporal_index")
    if isinstance(temporal_index, dict):
        segments = temporal_index.get("segments")
        if isinstance(segments, list):
            return [segment for segment in segments if isinstance(segment, dict)]

    for key, scene_key in (("scene_manifest_path", "scenes"), ("temporal_index_path", "segments")):
        raw_path = _clean_str(item.get(key))
        if not raw_path:
            continue
        data = _read_json(Path(raw_path))
        value = data.get(scene_key) if isinstance(data, dict) else None
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _memory_alignment(db_path: Optional[Path], scene_ids: Set[str], *, sample_limit: int) -> Dict[str, Any]:
    base = {
        "available": False,
        "scene_rows_present": 0,
        "missing_scene_count": len(scene_ids),
        "missing_scene_id_sample": sorted(scene_ids)[:sample_limit],
        "segment_rows": 0,
        "embedding_rows_by_modality": {},
        "commit_events_by_modality": {},
        "current_run_proof": False,
        "current_run_proof_basis": "memory_commit_events_do_not_prove_current_run_without_run_id_scope",
        "warnings": [],
    }
    if db_path is None:
        base["warnings"] = ["memory_db_path_missing"]
        return base
    if not db_path.exists():
        base["warnings"] = ["memory_db_missing"]
        return base

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        base["warnings"] = [f"memory_db_open_failed:{type(exc).__name__}"]
        return base

    try:
        tables = _tables(conn)
        if "scenes" not in tables:
            base["warnings"] = ["memory_scenes_table_missing"]
            return base

        present = _existing_scene_ids(conn, "scenes", "id", scene_ids)
        missing = sorted(scene_ids - present)
        base.update(
            {
                "available": True,
                "scene_rows_present": len(present),
                "missing_scene_count": len(missing),
                "missing_scene_id_sample": missing[:sample_limit],
            }
        )
        if "segments" in tables:
            base["segment_rows"] = _count_by_scene_ids(conn, "segments", "scene_id", scene_ids)
        if "embeddings" in tables:
            base["embedding_rows_by_modality"] = _counts_by_modality(conn, "embeddings", scene_ids)
        if "memory_commit_events" in tables:
            events = _commit_events_by_modality(conn, scene_ids)
            base["commit_events_by_modality"] = events
            if any(int(row.get("attempted") or 0) > len(scene_ids) for row in events.values()):
                base["warnings"].append("commit_events_accumulated_across_runs_possible")
        else:
            base["warnings"].append("memory_commit_events_table_missing")
    except Exception as exc:
        base["warnings"].append(f"memory_alignment_failed:{type(exc).__name__}")
    finally:
        conn.close()
    return base


def _kg_alignment(db_path: Optional[Path], scene_ids: Set[str], *, sample_limit: int) -> Dict[str, Any]:
    base = {
        "available": False,
        "scene_rows_present": 0,
        "missing_scene_count": len(scene_ids),
        "missing_scene_id_sample": sorted(scene_ids)[:sample_limit],
        "media_nodes": 0,
        "node_media_links": 0,
        "current_run_proof": False,
        "current_run_proof_basis": "knowledge_graph_scene_presence_is_persistent_scene_presence_not_current_run_vector_proof",
        "warnings": [],
    }
    if db_path is None:
        base["warnings"] = ["knowledge_graph_db_path_missing"]
        return base
    if not db_path.exists():
        base["warnings"] = ["knowledge_graph_db_missing"]
        return base

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        base["warnings"] = [f"knowledge_graph_db_open_failed:{type(exc).__name__}"]
        return base

    try:
        tables = _tables(conn)
        if "media_nodes" not in tables:
            base["warnings"] = ["kg_media_nodes_table_missing"]
            return base
        present = _existing_scene_ids(conn, "media_nodes", "scene_id", scene_ids)
        missing = sorted(scene_ids - present)
        base.update(
            {
                "available": True,
                "scene_rows_present": len(present),
                "missing_scene_count": len(missing),
                "missing_scene_id_sample": missing[:sample_limit],
                "media_nodes": _count_by_scene_ids(conn, "media_nodes", "scene_id", scene_ids),
            }
        )
        if "node_media" in tables:
            base["node_media_links"] = _count_node_media_links(conn, scene_ids)
        else:
            base["warnings"].append("kg_node_media_table_missing")
    except Exception as exc:
        base["warnings"].append(f"knowledge_graph_alignment_failed:{type(exc).__name__}")
    finally:
        conn.close()
    return base


def _tables(conn: sqlite3.Connection) -> Set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _existing_scene_ids(conn: sqlite3.Connection, table: str, column: str, scene_ids: Set[str]) -> Set[str]:
    if not scene_ids:
        return set()
    existing: Set[str] = set()
    for chunk in _chunks(sorted(scene_ids), 500):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IN ({placeholders})", chunk).fetchall()
        existing.update(str(row[0]) for row in rows if row[0] is not None)
    return existing


def _count_by_scene_ids(conn: sqlite3.Connection, table: str, column: str, scene_ids: Set[str]) -> int:
    if not scene_ids:
        return 0
    total = 0
    for chunk in _chunks(sorted(scene_ids), 500):
        placeholders = ",".join("?" for _ in chunk)
        row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IN ({placeholders})", chunk).fetchone()
        total += int(row[0] or 0)
    return total


def _counts_by_modality(conn: sqlite3.Connection, table: str, scene_ids: Set[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if not scene_ids:
        return counts
    for chunk in _chunks(sorted(scene_ids), 500):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT modality, COUNT(*) FROM {table} WHERE scene_id IN ({placeholders}) GROUP BY modality",
            chunk,
        ).fetchall()
        for modality, count in rows:
            key = _clean_str(modality) or "unknown"
            counts[key] = counts.get(key, 0) + int(count or 0)
    return dict(sorted(counts.items()))


def _commit_events_by_modality(conn: sqlite3.Connection, scene_ids: Set[str]) -> Dict[str, Dict[str, int]]:
    counts: Dict[str, Dict[str, int]] = {}
    if not scene_ids:
        return counts
    for chunk in _chunks(sorted(scene_ids), 500):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            "SELECT modality, COUNT(*) AS attempted, SUM(committed) AS committed "
            f"FROM memory_commit_events WHERE scene_id IN ({placeholders}) GROUP BY modality",
            chunk,
        ).fetchall()
        for modality, attempted, committed in rows:
            key = _clean_str(modality) or "unknown"
            bucket = counts.setdefault(key, {"attempted": 0, "committed": 0})
            bucket["attempted"] += int(attempted or 0)
            bucket["committed"] += int(committed or 0)
    return dict(sorted(counts.items()))


def _count_node_media_links(conn: sqlite3.Connection, scene_ids: Set[str]) -> int:
    if not scene_ids:
        return 0
    total = 0
    for chunk in _chunks(sorted(scene_ids), 500):
        placeholders = ",".join("?" for _ in chunk)
        row = conn.execute(
            "SELECT COUNT(*) FROM node_media nm "
            "JOIN media_nodes mn ON mn.id = nm.media_id "
            f"WHERE mn.scene_id IN ({placeholders})",
            chunk,
        ).fetchone()
        total += int(row[0] or 0)
    return total


def _chunks(values: Sequence[str], size: int) -> Iterable[Tuple[str, ...]]:
    for index in range(0, len(values), size):
        yield tuple(values[index : index + size])


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _without_internal_scene_ids(canonical: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in canonical.items() if key != "scene_ids"}


def _clean_str(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
