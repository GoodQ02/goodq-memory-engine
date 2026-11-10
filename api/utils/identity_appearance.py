"""Reviewed, appearance-only graph additions. Preview is strictly read-only.

The graph transaction also stores its durable receipt and exact inserted rows.
Undo removes only those rows, refuses later edits/dependencies, and retains the
receipt. No media, vector, roster, voice or transcript writer is involved.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from filelock import FileLock
import yaml

from api.utils.identity_read_projection import (
    configured_epoch_id, identity_data_path, project_face_cluster_images,
)
from api.utils.identity_readiness import artifact_readiness
from scripts.identity.promote_identity_layer import promote


TABLE = "identity_appearance_receipts"


class AppearanceConflict(ValueError):
    """A visible, non-mutating refusal; the operator must review fresh evidence."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _paths(cfg):
    epoch = configured_epoch_id(cfg)
    paths = cfg.get("paths") or {}
    root = Path(paths.get("db_path") or "").resolve().parent
    kg = Path((cfg.get("identity_search") or {}).get("kg_db_path")
              or paths.get("knowledge_graph_db") or "").resolve()
    if not epoch or root.name != epoch or kg.parent != root or not kg.is_file():
        raise AppearanceConflict("The active movie and graph are not bound to the same epoch.")
    return epoch, kg, identity_data_path(cfg)


def scope(cfg):
    epoch, kg, _ = _paths(cfg)
    return {"epoch_id": epoch, "store_sha256": _digest(str(kg))}


@contextmanager
def _connection(cfg, *, write=False):
    _, kg, root = _paths(cfg)
    # Match the existing label/roster writers. Preview never creates lock files.
    if write:
        with FileLock(str(root / "family_roster.yaml") + ".lock", timeout=10), \
             FileLock(str(root / "face_clusters.json") + ".lock", timeout=10):
            conn = sqlite3.connect(kg.as_uri() + "?mode=rw", uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
    else:
        conn = sqlite3.connect(kg.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN")
            yield conn
        finally:
            conn.close()


def _rows(conn, table):
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def _history(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return []
    return [json.loads(r[0]) for r in conn.execute(f"SELECT receipt FROM {TABLE} ORDER BY rowid DESC")]


def _public_receipt(receipt):
    result = {k: receipt[k] for k in (
        "id", "plan_sha256", "receipt_sha256", "status", "created_at", "undone_at", "summary",
    )}
    if receipt.get("review"):
        result["review"] = receipt["review"]
    return result


def _build(cfg, conn):
    epoch, kg, root = _paths(cfg)
    ready = artifact_readiness(cfg, "face_clusters.json")
    if not ready["ready"]:
        raise AppearanceConflict(ready["message"])
    source_bytes = {name: (root / name).read_bytes()
                    for name in ("family_roster.yaml", "face_clusters.json")}
    roster = yaml.safe_load(source_bytes["family_roster.yaml"])
    faces = json.loads(source_bytes["face_clusters.json"])
    identities = roster.get("identities") if isinstance(roster, dict) else None
    if not isinstance(identities, list) or not identities:
        raise AppearanceConflict("Save a family roster before previewing scene connections.")
    clusters = {c["cluster_id"]: c for c in faces["clusters"]}
    owners, people, seen_faces = {}, set(), set()
    for person in identities:
        if not isinstance(person, dict) or not person.get("id") or person["id"] in people:
            raise AppearanceConflict("Roster entries need unique, non-empty identities.")
        people.add(person["id"])
        for cid in person.get("face_cluster_ids") or []:
            if cid in owners or cid not in clusters:
                raise AppearanceConflict("Each saved face group must belong to one roster entry.")
            owners[cid] = person["id"]
            cluster = clusters[cid]
            members = cluster.get("face_ids")
            if not cluster.get("label") or not isinstance(members, list) or not members:
                raise AppearanceConflict("Label each selected face group and retain its saved members first.")
            for face in members:
                if face in seen_faces:
                    raise AppearanceConflict("A saved observation occurs in more than one selected group.")
                seen_faces.add(face)
    # Reuse the exact target validation already used by the face-review API.
    projected = project_face_cluster_images(
        {**faces, "clusters": [clusters[cid] for cid in owners]}, cfg, {"ready": True},
    )
    members = {m["target_face_id"]: m for c in projected["clusters"] for m in c.get("members", [])}
    if set(members) != seen_faces or any(m["evidence_status"] != "available" for m in members.values()):
        raise AppearanceConflict("Some exact face evidence is unavailable. Review those group members first.")
    plan = promote(epoch, kg, root, kg.parent / "memory.db", True,
                   appearance_only=True, projection_connection=conn)
    if plan["errors"]:
        raise AppearanceConflict("Some faces do not map to exactly one saved scene. Review the source evidence.")
    nodes, edges = _rows(conn, "nodes"), _rows(conn, "edges")
    by_key = {(n["node_type"], n["name"]): n for n in nodes}
    by_edge = {(e["source_id"], e["target_id"], e["edge_type"]): e for e in edges}
    node_specs = plan["nodes_created"]
    desired_keys = {(n["node_type"], n["name"]) for n in node_specs}
    relevant_ids = {n["id"] for n in nodes if (n["node_type"], n["name"]) in desired_keys or n["node_type"] == "scene"}
    relevant_edges = [e for e in edges if e["source_id"] in relevant_ids or e["target_id"] in relevant_ids]
    for node in node_specs:
        old = by_key.get((node["node_type"], node["name"]))
        if old and json.loads(old["properties"] or "{}") != node["properties"]:
            raise AppearanceConflict("An existing person or group has different graph facts; it will not be overwritten.")
    edge_specs, appearances = [], []
    for edge in plan["edges_created"]:
        kind = edge["edge"]
        if kind not in {"person_has_face_cluster", "person_appears_in_scene"}:
            raise AppearanceConflict("The appearance plan contains an unsupported evidence type.")
        source = by_key.get(("Person", edge["from"]))
        target_key = ("scene" if kind == "person_appears_in_scene" else "FaceCluster", edge["to"])
        target = by_key.get(target_key)
        props = {"confidence": "candidate"}
        if kind == "person_appears_in_scene":
            props.update(via_face_clusters=edge["via_face_clusters"], evidence_face_ids=edge["evidence_face_ids"])
            appearances.append({
                "person_id": edge["from"], "scene_id": edge["to"],
                "scene_node_id": edge["target_node_id"], "cluster_ids": edge["via_face_clusters"],
                "evidence": [members[f] for f in edge["evidence_face_ids"]],
            })
        elif target and any(e["target_id"] == target["id"] and e["edge_type"] == kind
                            and (not source or e["source_id"] != source["id"]) for e in edges):
            raise AppearanceConflict("A selected group is already connected to another person in the graph.")
        old = by_edge.get((source["id"], target["id"], kind)) if source and target else None
        weight = 0.7 if kind == "person_appears_in_scene" else 1.0
        if old and (json.loads(old["properties"] or "{}") != props or old["weight"] != weight):
            raise AppearanceConflict("An existing scene connection has different evidence; it will not be overwritten.")
        edge_specs.append({"source": ["Person", edge["from"]], "target": list(target_key),
                           "edge_type": kind, "weight": weight, "properties": props, "existing": bool(old)})
    if any((root / name).read_bytes() != content for name, content in source_bytes.items()):
        raise AppearanceConflict("The roster or labels changed while previewing. Preview again.")
    shared = {}
    for p in identities:
        for term in {str(x).strip().casefold() for x in [p.get("display_name", ""), *(p.get("aliases") or []), *(p.get("name_mention_keys") or [])] if str(x).strip()}:
            shared.setdefault(term, []).append(p.get("display_name") or p["id"])
    person_rows = [{"id": p["id"], "display_name": p.get("display_name") or p["id"],
                    "cluster_ids": p.get("face_cluster_ids") or [],
                    "scene_count": sum(a["person_id"] == p["id"] for a in appearances),
                    "observation_count": sum(len(a["evidence"]) for a in appearances if a["person_id"] == p["id"])} for p in identities]
    result = {"version": 1, "epoch_id": epoch, "scope": "appearance_only", "status": "preview",
              "summary": {"people": len({a["person_id"] for a in appearances}), "groups": len(owners),
                          "appearances": len(appearances), "scenes": len({a["scene_id"] for a in appearances}),
                          "observations": len(seen_faces), "new_nodes": sum((n["node_type"], n["name"]) not in by_key for n in node_specs),
                          "new_edges": sum(not e["existing"] for e in edge_specs),
                          "existing_edges": sum(e["existing"] for e in edge_specs)},
              "people": person_rows, "appearances": appearances,
              "held": {"transcript_mentions": "all", "voice_links": "all", "shared_aliases": [
                  {"term": term, "people": names} for term, names in sorted(shared.items()) if len(names) > 1]},
              "nodes": node_specs, "edges": edge_specs}
    result["plan_sha256"] = _digest({"plan": result, "scope": scope(cfg),
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in source_bytes.items()},
        "graph_nodes": [n for n in nodes if n["id"] in relevant_ids], "graph_edges": relevant_edges})
    return result


def preview(cfg):
    with _connection(cfg) as conn:
        result = _build(cfg, conn)
        result["history"] = [_public_receipt(r) for r in _history(conn)]
        return result


def history(cfg):
    with _connection(cfg) as conn:
        return [_public_receipt(r) for r in _history(conn)]


def saved(cfg, person_id=None):
    """Browse persisted appearance edges, independently of a pending roster plan.

    Names, membership and face IDs come from the applied graph. Projecting the
    original face evidence is passive; a missing image never invents a match or
    removes an otherwise saved connection. Timeline/media readers own playback.
    """
    epoch, kg, _ = _paths(cfg)
    from lib.identity_resolver import retired_identity_scene_ids

    retired = retired_identity_scene_ids(kg.parent / "ucf/ucf_ledger.db")
    with _connection(cfg) as conn:
        rows = conn.execute("""
            SELECT p.name person_id, p.properties person_properties,
                   s.name scene_id, e.properties evidence, v.name video_id
            FROM edges e JOIN nodes p ON p.id=e.source_id
            JOIN nodes s ON s.id=e.target_id
            LEFT JOIN edges containment ON containment.target_id=s.id
                AND containment.edge_type='video_contains_scene'
            LEFT JOIN nodes v ON v.id=containment.source_id AND v.node_type='video'
            WHERE p.node_type='Person' AND s.node_type='scene'
              AND e.edge_type='person_appears_in_scene'
              AND (? IS NULL OR p.name=?)
            ORDER BY p.name, s.name
        """, (person_id, person_id)).fetchall()
    people, connections = {}, {}
    for row in rows:
        if row["scene_id"] in retired:
            continue
        pid = row["person_id"]
        props = json.loads(row["person_properties"] or "{}")
        evidence = json.loads(row["evidence"] or "{}")
        people.setdefault(pid, {"id": pid, "display_name": props.get("display_name") or pid})
        key = (pid, row["scene_id"])
        item = connections.setdefault(key, {
            "person_id": pid, "scene_id": row["scene_id"], "video_ids": set(),
            "cluster_ids": evidence.get("via_face_clusters") or [],
            "face_ids": evidence.get("evidence_face_ids") or [],
            "confidence": evidence.get("confidence", "candidate"),
        })
        if row["video_id"]:
            item["video_ids"].add(row["video_id"])
    face_ids = sorted({str(fid) for a in connections.values() for fid in a["face_ids"]})
    projected = project_face_cluster_images(
        {"clusters": [{"face_ids": face_ids}]}, cfg, {"ready": True},
    )
    members = {m["target_face_id"]: m for c in projected["clusters"] for m in c.get("members", [])}
    appearances = []
    for item in connections.values():
        videos = item.pop("video_ids")
        item["video_id"] = next(iter(videos)) if len(videos) == 1 else None
        item["evidence"] = [members.get(str(fid), {
            "target_face_id": str(fid), "evidence_status": "unavailable",
            "reason": "saved_evidence_unavailable",
        }) for fid in item.pop("face_ids")]
        appearances.append(item)
    for person in people.values():
        scenes = [a for a in appearances if a["person_id"] == person["id"]]
        person.update(scene_count=len(scenes), observation_count=sum(len(a["evidence"]) for a in scenes))
    return {
        "epoch_id": epoch, "scope": "appearance_only", "status": "saved",
        "source": "promoted_knowledge_graph",
        "people": sorted(people.values(), key=lambda p: (p["display_name"].casefold(), p["id"])),
        "appearances": appearances,
        "summary": {"people": len(people), "appearances": len(appearances),
                    "scenes": len({a["scene_id"] for a in appearances})},
        "held": {"transcript_mentions": "all", "voice_links": "all"},
    }


def _persist(conn, receipt):
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY, receipt TEXT NOT NULL)")
    conn.execute(f"INSERT INTO {TABLE} (id, receipt) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET receipt=excluded.receipt",
                 (receipt["id"], _json(receipt)))


def apply(cfg, plan_sha256, *, plan_builder=None):
    with _connection(cfg, write=True) as conn:
        previous = next((r for r in _history(conn) if r["plan_sha256"] == plan_sha256 and r["status"] == "applied"), None)
        if previous:
            return {**_public_receipt(previous), "mutated": False}
        plan = (plan_builder or _build)(cfg, conn)
        if plan["plan_sha256"] != plan_sha256:
            raise AppearanceConflict("The saved inputs changed. Preview again before applying.")
        if not plan["summary"]["new_edges"] and not plan.get("updates") and not plan.get("review_changed"):
            raise AppearanceConflict("There are no new appearance connections to apply.")
        inserted = {"nodes": [], "edges": []}
        now = datetime.now(timezone.utc).isoformat()
        node_ids = {(n["node_type"], n["name"]): n["id"] for n in _rows(conn, "nodes")}
        for node in plan["nodes"]:
            key = (node["node_type"], node["name"])
            if key in node_ids:
                continue
            cursor = conn.execute("INSERT INTO nodes (node_type,name,properties,occurrence_count,created_at) VALUES (?,?,?,1,?)",
                                  (*key, _json(node["properties"]), now))
            node_ids[key] = cursor.lastrowid
            inserted["nodes"].append(dict(conn.execute("SELECT * FROM nodes WHERE id=?", (cursor.lastrowid,)).fetchone()))
        for edge in plan["edges"]:
            if edge["existing"]:
                continue
            cursor = conn.execute("INSERT INTO edges (source_id,target_id,edge_type,weight,properties,created_at) VALUES (?,?,?,?,?,?)",
                (node_ids[tuple(edge["source"])], node_ids[tuple(edge["target"])], edge["edge_type"], edge["weight"], _json(edge["properties"]), now))
            inserted["edges"].append(dict(conn.execute("SELECT * FROM edges WHERE id=?", (cursor.lastrowid,)).fetchone()))
        updated = []
        for update in plan.get("updates", []):
            original = update["before"]
            conn.execute("UPDATE edges SET properties=? WHERE id=?", (_json(update["properties"]), original["id"]))
            updated.append({"before": original, "after": dict(conn.execute("SELECT * FROM edges WHERE id=?", (original["id"],)).fetchone())})
        receipt = {"id": uuid.uuid4().hex, "plan_sha256": plan_sha256, "status": "applied",
                   "created_at": now, "undone_at": None, "summary": plan["summary"], "inserted": inserted,
                   "epoch_id": plan["epoch_id"]}
        if updated:
            receipt["updated_edges"] = updated
        if plan.get("review"):
            receipt["review"] = plan["review"]
        if "reference_faces" in plan:
            receipt["reference_faces"] = plan["reference_faces"]
        receipt["receipt_sha256"] = _digest(receipt)
        _persist(conn, receipt)
        return {**_public_receipt(receipt), "mutated": True}


def undo(cfg, receipt_id, receipt_sha256):
    with _connection(cfg, write=True) as conn:
        receipt = next((r for r in _history(conn) if r["id"] == receipt_id), None)
        if receipt is None or receipt["receipt_sha256"] != receipt_sha256:
            raise AppearanceConflict("The applied receipt changed or is unavailable. Reload scene connections.")
        if receipt["status"] == "undone":
            return {**_public_receipt(receipt), "mutated": False}
        for later in _history(conn):
            if later["id"] == receipt_id:
                break
            if (later["status"] == "applied" and receipt.get("review")
                    and later.get("review", {}).get("report_id") == receipt["review"]["report_id"]):
                raise AppearanceConflict("A later review depends on this batch. Undo the later review first.")
        for update in receipt.get("updated_edges", []):
            current = conn.execute("SELECT * FROM edges WHERE id=?", (update["after"]["id"],)).fetchone()
            if current is None or dict(current) != update["after"]:
                raise AppearanceConflict("Later face reviews changed this connection. Undo stopped to preserve them.")
        for table, rows in receipt["inserted"].items():
            for original in rows:
                current = conn.execute(f"SELECT * FROM {table} WHERE id=?", (original["id"],)).fetchone()
                if current is None or dict(current) != original:
                    raise AppearanceConflict("A connection has changed since Apply. Undo stopped to preserve later work.")
        owned_edges = {e["id"] for e in receipt["inserted"]["edges"]}
        owned_nodes = {n["id"] for n in receipt["inserted"]["nodes"]}
        if any(e["id"] not in owned_edges and (e["source_id"] in owned_nodes or e["target_id"] in owned_nodes)
               for e in _rows(conn, "edges")):
            raise AppearanceConflict("Later connections depend on these people or groups. Undo stopped to preserve them.")
        for update in receipt.get("updated_edges", []):
            conn.execute("UPDATE edges SET properties=? WHERE id=?", (update["before"]["properties"], update["before"]["id"]))
        for table in ("edges", "nodes"):
            conn.executemany(f"DELETE FROM {table} WHERE id=?", [(r["id"],) for r in receipt["inserted"][table]])
        receipt.update(status="undone", undone_at=datetime.now(timezone.utc).isoformat())
        _persist(conn, receipt)
        return {**_public_receipt(receipt), "mutated": True}
