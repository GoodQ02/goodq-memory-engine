"""Bounded, passive projection of stored KG edges; never an identity decision."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3


def _object(raw: str | None) -> dict:
    value = json.loads(raw or "{}")
    if not isinstance(value, dict):
        raise ValueError("Expected stored object")
    return value


def _review(edge_type: str, edge: dict, source: dict, target: dict,
            mappings: list | None) -> str:
    if edge_type != "identity_evidence" or edge.get("source") != "operator_manual_override":
        return "unreviewed"
    if mappings is None:
        return "review_unavailable"
    if not isinstance(edge.get("mapping_id"), str) or not edge["mapping_id"].strip():
        return "review_not_matched"
    matches = [m for m in mappings if isinstance(m, dict)
               and m.get("mapping_id") == edge.get("mapping_id")
               and m.get("source_node_type") == source["type"]
               and m.get("source_node_name") == source["name"]
               and m.get("target_person_name") == target["name"]]
    if len(matches) != 1 or target["type"] != "person":
        return "review_not_matched"
    return {"active": "reviewed_active", "revoked": "reviewed_revoked"}.get(
        matches[0].get("status"), "review_not_matched")


def load_scene_relationships(kg_path: Path, *, scene_id: str, source_hash: str,
                             source_alias: str | None = None, limit: int = 100) -> dict:
    """Select only source-bound scene edges and their explicit voice-review chain.

    No inferred co-occurrence edges, label joins, model calls or writes. Review
    files are reread on every request so revocation cannot survive a cache.
    """
    result = {"status": "unavailable", "relationships": [], "truncated": False,
              "scene_id": scene_id, "source_hash": source_hash,
              "source": "stored_knowledge_graph"}
    if not kg_path.is_file():
        return result
    mapping_path = kg_path.parent / "manual_identity_mappings.json"
    mappings = []
    if mapping_path.exists():
        try:
            mappings = _object(mapping_path.read_text(encoding="utf-8")).get("mappings")
            if not isinstance(mappings, list):
                mappings = None
        except (OSError, ValueError):
            mappings = None
    with sqlite3.connect(kg_path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        scene = conn.execute("SELECT id,properties FROM nodes WHERE node_type='scene' AND name=?",
                             (scene_id,)).fetchone()
        if scene is None:
            return {**result, "status": "not_materialized"}
        props = _object(scene["properties"])
        sources = {r[0] for r in conn.execute("""
            SELECT v.name FROM edges e JOIN nodes v ON v.id=e.source_id
            WHERE e.target_id=? AND e.edge_type='video_contains_scene' AND v.node_type='video'
        """, (scene["id"],))}
        if props.get("video_id"):
            sources.add(str(props["video_id"]))
        # Promotion can retain the loader's source slug in the video node,
        # while scene properties retain its hash. The route binds both through
        # the same active manifest; unrelated aliases remain excluded.
        allowed_sources = {source_hash, source_alias} - {None, ""}
        if not sources or not sources.issubset(allowed_sources):
            return {**result, "status": "source_mismatch"}
        # Structural nodes connected by speaks_in anchor the review chain to
        # this exact scene. Shared person labels cannot expand its scope.
        rows = conn.execute("""
            WITH speakers AS (
                SELECT source_id FROM edges WHERE target_id=? AND edge_type='speaks_in'
            ), voices AS (
                SELECT id,target_id FROM edges WHERE source_id IN (SELECT source_id FROM speakers)
                  AND edge_type='voice_pattern_match'
                  AND json_valid(properties) AND json_extract(properties,'$.scene_id')=?
            )
            SELECT e.*, s.node_type AS source_type,s.name AS source_name,
                   t.node_type AS target_type,t.name AS target_name
            FROM edges e JOIN nodes s ON s.id=e.source_id JOIN nodes t ON t.id=e.target_id
            WHERE e.source_id=? OR e.target_id=?
               OR (json_valid(e.properties) AND json_extract(e.properties,'$.scene_id')=?)
               OR e.id IN (SELECT id FROM voices)
               OR (e.source_id IN (SELECT target_id FROM voices)
                   AND e.edge_type IN ('identity_candidate','identity_supported','identity_evidence'))
            ORDER BY CASE WHEN e.edge_type LIKE '%ucf_frame' THEN 1 ELSE 0 END,e.id
            LIMIT ?
        """, (scene["id"], scene_id, scene["id"], scene["id"], scene_id, limit + 1)).fetchall()
        result.update(status="ok", truncated=len(rows) > limit, review_ledger_available=mappings is not None)
        for row in rows[:limit]:
            p = _object(row["properties"])
            source = {"id": row["source_id"], "type": row["source_type"], "name": row["source_name"]}
            target = {"id": row["target_id"], "type": row["target_type"], "name": row["target_name"]}
            # Only approved scalar evidence fields are projected. Raw graph
            # properties may contain paths, embeddings and model internals.
            evidence = {"scene_id": scene_id, "source_hash": source_hash,
                        "scope": "scene", "provenance": p.get("source") or "not_recorded"}
            for key in ("mapping_id", "reason", "status", "identity_claim"):
                if isinstance(p.get(key), (str, bool, int, float)):
                    evidence[key] = p[key]
            segments = p.get("selected_segments")
            if isinstance(segments, list):
                evidence["selected_segments"] = [
                    {k: segment[k] for k in ("start", "end")}
                    for segment in segments[:20] if isinstance(segment, dict)
                    and all(type(segment.get(k)) in (int, float) and math.isfinite(segment[k])
                            for k in ("start", "end"))
                    and 0 <= segment["start"] < segment["end"]]
            result["relationships"].append({
                "id": row["id"], "type": row["edge_type"], "source": source, "target": target,
                "review_status": _review(row["edge_type"], p, source, target, mappings),
                "evidence": evidence,
            })
    return result
