from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from lib.kg_realtime_integration import update_kg_for_scene


IDENTITY_EDGE_TYPES = ("identity_candidate", "identity_supported", "identity_evidence")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _flatten_scene_payload(scene: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(scene)
    merged_entities: List[Any] = []
    existing_entities = payload.get("entities")
    if isinstance(existing_entities, list):
        merged_entities.extend(existing_entities)
    merge_list_keys = {
        "entities",
        "ner_entities",
        "entity_details",
        "tags",
        "faces",
        "objects",
        "speaker_voice_signatures",
        "speaker_transcript",
        "speakers",
        "speaker_ids",
        "diarization",
        "speaker_segments",
    }
    nested_payloads = [
        scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else None,
        scene.get("audio") if isinstance(scene.get("audio"), dict) else None,
    ]
    for nested in nested_payloads:
        if not isinstance(nested, dict):
            continue
        for key, value in nested.items():
            existing = payload.get(key)
            if key in merge_list_keys and isinstance(value, list):
                if key == "entities":
                    merged_entities.extend(value)
                    payload[key] = list(merged_entities)
                    continue
                merged: List[Any] = []
                if isinstance(existing, list):
                    merged.extend(existing)
                elif existing not in (None, "", {}, []):
                    merged.append(existing)
                merged.extend(value)
                payload[key] = merged
                continue
            if existing in (None, "", [], {}):
                payload[key] = value

        ner_entities = nested.get("ner_entities")
        if isinstance(ner_entities, list):
            merged_entities.extend(ner_entities)
        entity_details = nested.get("entity_details")
        if isinstance(entity_details, list):
            merged_entities.extend(entity_details)

    if merged_entities:
        payload["entities"] = merged_entities
    payload.setdefault("start_time", scene.get("start"))
    payload.setdefault("end_time", scene.get("end"))
    return payload


def rebuild_identity_graph_from_manifests(
    *,
    processing_root: Path,
    graph_db_path: Path,
    episode_prefix: str = "01x",
) -> Dict[str, Any]:
    processing_root = Path(processing_root)
    graph_db_path = Path(graph_db_path)
    graph_db_path.parent.mkdir(parents=True, exist_ok=True)
    if graph_db_path.exists():
        graph_db_path.unlink()

    cfg = {"paths": {"knowledge_graph_db": str(graph_db_path)}}
    episodes: List[Dict[str, Any]] = []
    scene_episode_map: Dict[str, str] = {}
    total_scenes = 0

    for episode_dir in sorted(processing_root.iterdir() if processing_root.exists() else []):
        if not episode_dir.is_dir():
            continue
        if not episode_dir.name.startswith(episode_prefix):
            continue
        manifest_path = episode_dir / "video" / "scene_manifest.json"
        if not manifest_path.exists():
            continue

        manifest = _load_json(manifest_path)
        scenes = manifest.get("scenes")
        if not isinstance(scenes, list):
            continue

        video_id = str(manifest.get("video_id") or episode_dir.name)
        video_path = str(manifest.get("video_path") or episode_dir.name)
        episodes.append(
            {
                "episode": episode_dir.name,
                "video_id": video_id,
                "scene_count": len(scenes),
                "manifest_path": str(manifest_path),
            }
        )

        for idx, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                continue
            scene_id = str(scene.get("scene_id") or f"{episode_dir.name}::scene_{idx:04d}")
            scene_episode_map[scene_id] = episode_dir.name
            update_kg_for_scene(
                scene_data=_flatten_scene_payload(scene),
                scene_id=scene_id,
                video_id=video_id,
                video_path=video_path,
                cfg=cfg,
            )
            total_scenes += 1

    from lib.knowledge_graph import KnowledgeGraph
    with KnowledgeGraph(str(graph_db_path)) as kg:
        apply_manual_mappings(kg, graph_db_path)

    return {
        "generated_at": _utc_now_iso(),
        "processing_root": str(processing_root),
        "graph_db_path": str(graph_db_path),
        "episode_count": len(episodes),
        "scene_count": total_scenes,
        "episodes": episodes,
        "scene_episode_map": scene_episode_map,
    }


def _parse_properties(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _dedupe_supporting_evidence(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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


def build_identity_ledger(
    *,
    graph_db_path: Path,
    scene_episode_map: Dict[str, str],
    episodes: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    import sqlite3

    graph_db_path = Path(graph_db_path)
    read_only_uri = f"{graph_db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(read_only_uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    edge_rows = cur.execute(
        """
        SELECT
            e.edge_type,
            e.weight,
            e.properties,
            s.name AS source_name,
            s.node_type AS source_type,
            t.name AS target_name,
            t.node_type AS target_type
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.edge_type IN ('identity_candidate', 'identity_supported', 'identity_evidence')
          AND t.node_type = 'person'
        ORDER BY t.name, e.edge_type, s.name
        """
    ).fetchall()

    totals = Counter()
    people: Dict[str, Dict[str, Any]] = {}
    pair_bundles: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for row in edge_rows:
        edge_type = str(row["edge_type"])
        totals[edge_type] += 1
        properties = _parse_properties(row["properties"])
        source_name = str(row["source_name"])
        source_type = str(row["source_type"])
        target_name = str(row["target_name"])
        scene_id = str(properties.get("scene_id") or "").strip()
        episode = scene_episode_map.get(scene_id)

        person_entry = people.setdefault(
            target_name,
            {
                "person": target_name,
                "episodes": set(),
                "scene_ids": set(),
                "edge_counts": Counter(),
                "source_type_counts": Counter(),
                "source_rule_counts": Counter(),
                "supporting_scene_ids": set(),
                "supporting_evidence": [],
            },
        )
        person_entry["edge_counts"][edge_type] += 1
        person_entry["source_type_counts"][source_type] += 1
        source_rule = properties.get("candidate_source") or properties.get("source")
        if isinstance(source_rule, str) and source_rule.strip():
            person_entry["source_rule_counts"][source_rule.strip()] += 1
        if scene_id:
            person_entry["scene_ids"].add(scene_id)
        if episode:
            person_entry["episodes"].add(episode)
        supporting_scene_ids = properties.get("supporting_scene_ids")
        if isinstance(supporting_scene_ids, list):
            for support_scene_id in supporting_scene_ids:
                if isinstance(support_scene_id, str) and support_scene_id.strip():
                    person_entry["supporting_scene_ids"].add(support_scene_id.strip())
                    support_episode = scene_episode_map.get(support_scene_id.strip())
                    if support_episode:
                        person_entry["episodes"].add(support_episode)
        supporting_evidence = properties.get("supporting_evidence")
        if isinstance(supporting_evidence, list):
            person_entry["supporting_evidence"].extend(
                evidence
                for evidence in supporting_evidence
                if isinstance(evidence, dict)
            )

        pair_key = (source_name, target_name, edge_type)
        pair_entry = pair_bundles.setdefault(
            pair_key,
            {
                "source_name": source_name,
                "source_type": source_type,
                "target_name": target_name,
                "edge_type": edge_type,
                "edge_count": 0,
                "scene_ids": set(),
                "episodes": set(),
                "sources": set(),
                "supporting_scene_ids": set(),
                "supporting_evidence": [],
            },
        )
        pair_entry["edge_count"] += 1
        if scene_id:
            pair_entry["scene_ids"].add(scene_id)
        if episode:
            pair_entry["episodes"].add(episode)
        if isinstance(properties.get("source"), str):
            pair_entry["sources"].add(properties["source"])
        if isinstance(supporting_scene_ids, list):
            for support_scene_id in supporting_scene_ids:
                if isinstance(support_scene_id, str) and support_scene_id.strip():
                    pair_entry["supporting_scene_ids"].add(support_scene_id.strip())
                    support_episode = scene_episode_map.get(support_scene_id.strip())
                    if support_episode:
                        pair_entry["episodes"].add(support_episode)
        if isinstance(supporting_evidence, list):
            pair_entry["supporting_evidence"].extend(
                evidence
                for evidence in supporting_evidence
                if isinstance(evidence, dict)
            )

    conn.close()

    person_rows = []
    for person_name, entry in sorted(people.items()):
        person_rows.append(
            {
                "person": person_name,
                "episodes": sorted(entry["episodes"]),
                "episode_count": len(entry["episodes"]),
                "scene_count": len(entry["scene_ids"]),
                "supporting_scene_count": len(entry["supporting_scene_ids"]),
                "edge_counts": dict(entry["edge_counts"]),
                "source_type_counts": dict(entry["source_type_counts"]),
                "source_rule_counts": dict(entry["source_rule_counts"]),
                "supporting_evidence": _dedupe_supporting_evidence(entry["supporting_evidence"])[:8],
            }
        )

    pair_rows = []
    for (_source_name, _target_name, _edge_type), entry in sorted(pair_bundles.items()):
        pair_rows.append(
            {
                "source_name": entry["source_name"],
                "source_type": entry["source_type"],
                "target_name": entry["target_name"],
                "edge_type": entry["edge_type"],
                "edge_count": entry["edge_count"],
                "episodes": sorted(entry["episodes"]),
                "scene_count": len(entry["scene_ids"]),
                "supporting_scene_count": len(entry["supporting_scene_ids"]),
                "sources": sorted(entry["sources"]),
                "supporting_evidence": _dedupe_supporting_evidence(entry["supporting_evidence"])[:8],
            }
        )

    recurring_people = [
        row for row in person_rows
        if row["episode_count"] >= 2 or row["supporting_scene_count"] >= 2
    ]

    return {
        "generated_at": _utc_now_iso(),
        "graph_db_path": str(graph_db_path),
        "episode_count": len(list(episodes or [])),
        "identity_edge_totals": {
            "identity_candidate": totals["identity_candidate"],
            "identity_supported": totals["identity_supported"],
            "identity_evidence": totals["identity_evidence"],
        },
        "people": person_rows,
        "pairs": pair_rows,
        "recurring_people": recurring_people,
    }


def write_identity_ledger_markdown(ledger: Dict[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    totals = ledger.get("identity_edge_totals", {})
    recurring_people = ledger.get("recurring_people", [])
    top_people = sorted(
        ledger.get("people", []),
        key=lambda row: (
            row.get("supporting_scene_count", 0),
            row.get("episode_count", 0),
            row.get("scene_count", 0),
        ),
        reverse=True,
    )[:12]

    lines = [
        "# Identity Ledger Control",
        "",
        f"- Generated: {ledger.get('generated_at')}",
        f"- Episodes: {ledger.get('episode_count')}",
        f"- identity_candidate: {totals.get('identity_candidate', 0)}",
        f"- identity_supported: {totals.get('identity_supported', 0)}",
        f"- identity_evidence: {totals.get('identity_evidence', 0)}",
        f"- recurring_people: {len(recurring_people)}",
        "",
        "## Top People",
        "",
        "| Person | Episodes | Scenes | Supporting Scenes | identity_supported | identity_candidate |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in top_people:
        edge_counts = row.get("edge_counts", {})
        lines.append(
            f"| {row.get('person')} | {row.get('episode_count', 0)} | {row.get('scene_count', 0)} | "
            f"{row.get('supporting_scene_count', 0)} | {edge_counts.get('identity_supported', 0)} | "
            f"{edge_counts.get('identity_candidate', 0)} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_manual_mappings(graph_db_path: Path) -> Dict[str, Any]:
    """Load operator manual identity mappings from a json file next to knowledge_graph.db."""
    mappings_file = Path(graph_db_path).parent / "manual_identity_mappings.json"
    if not mappings_file.is_file():
        return {"version": 1, "mappings": []}
    try:
        with mappings_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "mappings" in data:
                return data
    except Exception as e:
        logger.warning("Failed to load manual identity mappings from %s: %s", mappings_file, e)
    return {"version": 1, "mappings": []}


def save_manual_mappings(graph_db_path: Path, data: Dict[str, Any]) -> None:
    """Save operator manual identity mappings to a json file next to knowledge_graph.db."""
    mappings_file = Path(graph_db_path).parent / "manual_identity_mappings.json"
    try:
        mappings_file.parent.mkdir(parents=True, exist_ok=True)
        # Write to temporary file first and rename to ensure atomicity
        temp_file = mappings_file.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if temp_file.exists():
            if mappings_file.exists():
                mappings_file.unlink()
            temp_file.rename(mappings_file)
    except Exception as e:
        logger.error("Failed to save manual identity mappings to %s: %s", mappings_file, e)
        raise RuntimeError(f"Failed to save manual identity mappings: {e}")


def apply_manual_mappings(kg: KnowledgeGraph, graph_db_path: Path) -> int:
    """Read active manual overrides and insert them as identity_evidence edges in the knowledge graph."""
    data = load_manual_mappings(graph_db_path)
    mappings = data.get("mappings") or []
    applied_count = 0
    cur = kg.conn.cursor()

    for mapping in mappings:
        if mapping.get("status") != "active":
            continue
        source_name = mapping.get("source_node_name")
        target_name = mapping.get("target_person_name")
        source_type = mapping.get("source_node_type", "speaker_pattern")
        
        if not source_name or not target_name:
            continue
            
        # Resolve source_id in SQLite nodes
        source_row = cur.execute(
            "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
            (source_type, source_name)
        ).fetchone()
        
        if not source_row:
            continue
        source_id = int(source_row["id"])
        
        # Resolve or create target_id for the person node
        target_id = kg.add_node(
            node_type="person",
            name=target_name,
            properties={"source": "operator_manual_override"},
            timestamp=None
        )
        
        # Add the manual identity_evidence edge
        kg.add_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type="identity_evidence",
            weight=1.0,
            properties={
                "source": "operator_manual_override",
                "mapping_id": mapping.get("mapping_id"),
                "operator_note": (mapping.get("history")[-1].get("operator_note", "") if mapping.get("history") else "")
            }
        )
        applied_count += 1
        
    return applied_count
