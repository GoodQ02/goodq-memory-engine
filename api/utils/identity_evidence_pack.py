"""Passive, curated identity evidence for agent-facing read models."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sqlite3
from typing import Any, Iterable


def _terms(identity: dict[str, Any]) -> list[str]:
    values = [identity.get("display_name"), *(identity.get("aliases") or []), *(identity.get("name_mention_keys") or [])]
    return [str(value).strip() for value in values if str(value).strip()]


def _public_identity(identity: dict[str, Any], matched_terms: list[str]) -> dict[str, Any]:
    return {
        "id": str(identity.get("id") or ""),
        "display_name": str(identity.get("display_name") or identity.get("id") or ""),
        "aliases": [str(value) for value in (identity.get("aliases") or []) if str(value).strip()],
        "role": identity.get("role"),
        "confirmed": bool(identity.get("confirmed", False)),
        "matched_terms": matched_terms,
        "identity_source": "curated_roster",
    }


def build_identity_evidence_pack(
    identities: Iterable[dict[str, Any]],
    subjects: Iterable[str],
) -> dict[str, Any]:
    """Resolve curated identities without deriving relationships from proximity.

    A legacy identity ``role`` remains an identity-level label. Only an explicit
    per-identity ``relationships`` record can establish a directed pairwise claim.
    """
    normalized = [str(subject).strip().lower() for subject in subjects if str(subject).strip()]
    source_identities = [item for item in identities if isinstance(item, dict)]
    matched: list[dict[str, Any]] = []
    matched_ids: set[str] = set()
    for identity in source_identities:
        terms = _terms(identity)
        matching = sorted({subject for subject in normalized if subject in {term.lower() for term in terms}})
        identity_id = str(identity.get("id") or "")
        if matching and identity_id:
            matched.append(_public_identity(identity, matching))
            matched_ids.add(identity_id)

    claims: list[dict[str, str]] = []
    for identity in source_identities:
        source_id = str(identity.get("id") or "")
        if source_id not in matched_ids:
            continue
        for relationship in identity.get("relationships") or []:
            if not isinstance(relationship, dict):
                continue
            target_id = str(relationship.get("target_id") or "")
            relationship_type = str(relationship.get("type") or "")
            if target_id in matched_ids and relationship_type:
                claims.append({
                    "source_id": source_id,
                    "target_id": target_id,
                    "type": relationship_type,
                    "authority": "curated_roster_relationship",
                })

    labels = [
        {
            "identity_id": item["id"],
            "field": "role",
            "value": item["role"],
            "scope": "identity_level_unscoped",
        }
        for item in matched
        if item.get("role") not in (None, "")
    ]
    return {
        "identities": matched,
        "identity_labels": labels,
        "relationships": claims,
        "claim_status": "established" if claims else "not_established",
        "withheld_reasons": ([] if claims else [
            "No explicit directed curated relationship record exists for the requested identities.",
            "Identity role labels and scene co-occurrence are not pairwise relationship claims.",
        ]),
    }


def load_identity_scene_evidence(
    identities: Iterable[dict[str, Any]],
    kg_path: Path,
    *,
    limit: int,
) -> dict[str, Any]:
    """Read bounded, typed Person-to-scene evidence from the promoted KG.

    Scene-node names and source video hashes are stable provenance references.
    They intentionally are not presented as timeline coordinates or relationship
    claims; callers must use a separate scene projection for scene narration.
    """
    identity_map = {
        str(identity.get("id") or ""): identity
        for identity in identities
        if isinstance(identity, dict) and str(identity.get("id") or "")
    }
    if not identity_map or not kg_path.exists():
        return {"scene_refs": [], "source": "promoted_knowledge_graph"}

    placeholders = ",".join("?" for _ in identity_map)
    query = f"""
        SELECT person.name, scene.name, edge.edge_type, video.name
        FROM edges AS edge
        JOIN nodes AS person ON person.id = edge.source_id
        JOIN nodes AS scene ON scene.id = edge.target_id
        LEFT JOIN edges AS containment
          ON containment.target_id = scene.id
         AND containment.edge_type = 'video_contains_scene'
        LEFT JOIN nodes AS video
          ON video.id = containment.source_id
         AND video.node_type = 'video'
        WHERE person.node_type = 'Person'
          AND person.name IN ({placeholders})
          AND edge.edge_type IN ('person_appears_in_scene', 'person_mentioned_in_scene')
          AND scene.node_type = 'scene'
        ORDER BY scene.name, person.name, edge.edge_type
    """
    uri = f"{kg_path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            rows = conn.execute(query, tuple(identity_map)).fetchall()
    except sqlite3.Error:
        return {"scene_refs": [], "source": "promoted_knowledge_graph_unavailable"}

    scene_rows: dict[str, dict[str, Any]] = {}
    for person_id, scene_id, edge_type, video_hash in rows:
        scene_key = str(scene_id)
        if scene_key not in scene_rows:
            if len(scene_rows) >= limit:
                break
            scene_rows[scene_key] = {
                "scene_id": scene_key,
                "video_hash": str(video_hash) if video_hash else None,
                "people": defaultdict(set),
            }
        evidence_type = "appearance" if edge_type == "person_appears_in_scene" else "mention"
        scene_rows[scene_key]["people"][str(person_id)].add(evidence_type)

    scene_refs = []
    for row in scene_rows.values():
        people = []
        for person_id, evidence_types in sorted(row["people"].items()):
            identity = identity_map[person_id]
            ordered_types = [kind for kind in ("appearance", "mention") if kind in evidence_types]
            people.append({
                "identity_id": person_id,
                "display_name": identity.get("display_name") or person_id,
                "evidence_types": ordered_types,
                "strength": "appearance" if "appearance" in evidence_types else "mention",
            })
        scene_refs.append({
            "scene_id": row["scene_id"],
            "video_hash": row["video_hash"],
            "people": people,
        })
    return {"scene_refs": scene_refs, "source": "promoted_knowledge_graph"}
