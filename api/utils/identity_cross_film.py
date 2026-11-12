"""Strictly read-only same-film visual grouping and cross-film face discovery.

Reads only promoted UCF face_embed observations and read-only SQLite/JSON
metadata across the active epoch and explicitly configured reviewed_source_roots.
Never writes files, directories, receipts, or graph edges.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any

import yaml

from api.utils import identity_matching as matching_projection
from api.utils.identity_read_projection import identity_data_path
from lib.identity_matching import epoch_attested_identity_dir, read_json, report_root, reviewed_source_roots, unit
from lib.identity_resolver import retired_identity_scene_ids
from scripts.identity.build_face_clusters import (
    _bbox_coordinates,
    collect_face_detections,
    load_face_ucf_provenance,
)

_EPOCH_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_DETECTION_ID_RE = re.compile(r"^([0-9]+)_([0-9]+)$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")
_EPOCH_DETECTION_CACHE: dict[tuple[Any, ...], tuple[list[dict[str, Any]], dict[int, str]]] = {}


def _active_epoch_root(cfg: dict[str, Any]) -> Path:
    db_path = str((cfg.get("paths") or {}).get("db_path") or "").strip()
    if not db_path:
        raise ValueError("Active epoch path is not configured")
    return Path(db_path).resolve().parent


def _allowed_epoch_roots(cfg: dict[str, Any]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    active = _active_epoch_root(cfg)
    if active.is_dir():
        roots[active.name] = active
    for root in sorted(reviewed_source_roots(cfg.get("identity_matching") or {})):
        resolved = Path(root).resolve()
        if resolved.is_dir():
            roots[resolved.name] = resolved
    return roots


def _configured_identity_paths_by_epoch(cfg: dict[str, Any]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    active = _active_epoch_root(cfg)
    roster_path = matching_projection.active_roster_path(cfg)
    if roster_path is not None:
        mapping[active.name] = roster_path.parent.resolve()
    else:
        data_dir = identity_data_path(cfg)
        if data_dir.is_dir():
            mapping[active.name] = data_dir.resolve()
    for source in (cfg.get("identity_matching") or {}).get("reference_sources", []):
        epoch_root = Path(source["epoch_root"]).resolve()
        ident_root = Path(source["identity_path"]).resolve()
        if ident_root.is_dir():
            mapping[epoch_root.name] = ident_root
    for root in sorted(reviewed_source_roots(cfg.get("identity_matching") or {})):
        resolved = Path(root).resolve()
        if resolved.name not in mapping and resolved.is_dir():
            att_dir = epoch_attested_identity_dir(resolved)
            if att_dir is not None:
                mapping[resolved.name] = att_dir
    return mapping


def _load_epoch_detections(
    epoch_root: Path,
    *,
    manifest_cache: dict | None = None,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    ucf_db = epoch_root / "ucf" / "ucf_ledger.db"
    if not ucf_db.is_file():
        return [], {}
    retired = retired_identity_scene_ids(ucf_db)
    stat = ucf_db.stat()
    cache_key = (str(epoch_root.resolve()), stat.st_mtime_ns, stat.st_size, tuple(sorted(retired)))
    cached = _EPOCH_DETECTION_CACHE.get(cache_key)
    if cached is not None:
        return cached
    provenance = load_face_ucf_provenance(ucf_db)
    filtered = {
        raw_path: [row for row in rows if row["source_artifact_id"] not in retired]
        for raw_path, rows in provenance.items()
    }
    filtered = {raw_path: rows for raw_path, rows in filtered.items() if rows}
    if not filtered:
        return [], {}
    frame_scenes = {
        row["frame_id"]: str(row["source_artifact_id"])
        for rows in filtered.values()
        for row in rows
    }
    detections = collect_face_detections(epoch_root, filtered, manifest_cache=manifest_cache)
    if len(_EPOCH_DETECTION_CACHE) >= 16:
        _EPOCH_DETECTION_CACHE.clear()
    _EPOCH_DETECTION_CACHE[cache_key] = (detections, frame_scenes)
    return detections, frame_scenes


def _read_epoch_kg_metadata(epoch_root: Path) -> dict[str, Any]:
    """Read video name, scene bounds, and confirmed face->person links (?mode=ro)."""
    kg_path = epoch_root / "knowledge_graph.db"
    meta: dict[str, Any] = {
        "video_id": None,
        "video_name": None,
        "scene_bounds": {},
        "face_owners": defaultdict(list),
        "person_faces": defaultdict(set),
        "person_names": {},
    }
    if not kg_path.is_file():
        return meta
    with closing(sqlite3.connect(f"{kg_path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "nodes" not in tables or "edges" not in tables:
            return meta
        video_row = conn.execute(
            "SELECT name, properties FROM nodes WHERE node_type='video' ORDER BY id LIMIT 1"
        ).fetchone()
        if video_row is not None:
            vprops = json.loads(video_row["properties"] or "{}")
            meta["video_id"] = str(video_row["name"])
            meta["video_name"] = str(
                vprops.get("video_name") or vprops.get("filename") or video_row["name"]
            )
        for row in conn.execute(
            "SELECT name, properties FROM nodes WHERE node_type='scene'"
        ):
            sprops = json.loads(row["properties"] or "{}")
            start = sprops.get("start_time", sprops.get("start"))
            end = sprops.get("end_time", sprops.get("end"))
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                meta["scene_bounds"][str(row["name"])] = (float(start), float(end))
        person_by_node_id: dict[int, tuple[str, str]] = {}
        for row in conn.execute(
            "SELECT id, name, properties FROM nodes WHERE node_type='Person'"
        ):
            pprops = json.loads(row["properties"] or "{}")
            pid = str(row["name"])
            pname = str(pprops.get("display_name") or pid)
            person_by_node_id[int(row["id"])] = (pid, pname)
            meta["person_names"][pid] = pname
        for row in conn.execute(
            "SELECT source_id, properties FROM edges WHERE edge_type='person_appears_in_scene'"
        ):
            owner = person_by_node_id.get(int(row["source_id"]))
            if owner is None:
                continue
            pid, pname = owner
            eprops = json.loads(row["properties"] or "{}")
            for fid in eprops.get("evidence_face_ids") or []:
                fid_str = str(fid)
                if pname not in meta["face_owners"][fid_str]:
                    meta["face_owners"][fid_str].append(pname)
                meta["person_faces"][pid].add(fid_str)
    return meta


def _read_cluster_annotations(epoch_root: Path, identity_dir: Path | None) -> dict[str, dict[str, Any]]:
    """Map detection_id -> {cluster_id, label} if face_clusters.json matches epoch_root."""
    if identity_dir is None:
        return {}
    cluster_path = identity_dir / "face_clusters.json"
    if not cluster_path.is_file():
        return {}
    try:
        payload = read_json(cluster_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("epoch_id") != epoch_root.name:
        return {}
    mapping: dict[str, dict[str, Any]] = {}
    for cluster in payload.get("clusters") or []:
        if not isinstance(cluster, dict):
            continue
        cid = str(cluster.get("cluster_id") or "")
        raw_label = cluster.get("label")
        label = str(raw_label).strip() if isinstance(raw_label, str) and raw_label.strip() and raw_label != "null" else None
        for fid in cluster.get("face_ids") or []:
            mapping[str(fid)] = {"cluster_id": cid, "label": label}
    return mapping


def _match_report_records_to_detections(
    report: dict[str, Any],
    detections: list[dict[str, Any]],
    frame_scenes: dict[int, str],
) -> dict[str, dict[str, Any]]:
    """Bind each face record in a frozen match report to its promoted detection."""
    by_image_and_scene: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for det in detections:
        scene_id = frame_scenes.get(det["frame_id"], "")
        if det["video_hash"] == report["video_hash"] and scene_id:
            key = (str(Path(det["image_path"]).resolve()), scene_id)
            by_image_and_scene[key].append(det)
    bound: dict[str, dict[str, Any]] = {}
    for record in report.get("records") or []:
        if record.get("modality") != "face":
            continue
        media = record.get("media") or {}
        media_path = media.get("path")
        if not media_path:
            continue
        key = (str(Path(media_path).resolve()), str(record.get("scene_id") or ""))
        candidates = []
        rec_box = _bbox_coordinates(media.get("bbox"))
        rec_ts = media.get("timestamp")
        for det in by_image_and_scene.get(key, ()):
            det_box = _bbox_coordinates(det.get("bbox"))
            if (
                rec_box is not None
                and det_box is not None
                and all(abs(a - b) <= 1e-6 for a, b in zip(rec_box, det_box))
                and isinstance(rec_ts, (int, float))
                and isinstance(det.get("t_start"), (int, float))
                and abs(float(det["t_start"]) - float(rec_ts)) < 1e-4
            ):
                candidates.append(det)
        if len(candidates) == 1:
            bound[record["id"]] = candidates[0]
    return bound


def _cosine(vec_a: list[float], vec_b: list[float]) -> float:
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(vec_a, vec_b))))


def visual_groups_for_report(
    cfg: dict[str, Any],
    report_id: str,
    *,
    min_similarity: float = 0.58,
) -> dict[str, Any]:
    """Group face observations in a comparison report by visual SFace similarity."""
    if not math.isfinite(min_similarity) or not 0.30 <= min_similarity <= 0.95:
        raise ValueError("Invalid visual grouping similarity threshold")
    report = matching_projection.read_report(cfg, report_id)
    epoch_root = _active_epoch_root(cfg)
    detections, frame_scenes = _load_epoch_detections(epoch_root)
    bound = _match_report_records_to_detections(report, detections, frame_scenes)

    face_records = [r for r in report["records"] if r.get("modality") == "face"]
    vectors: dict[str, tuple[str, list[float]]] = {}
    for rec in face_records:
        det = bound.get(rec["id"])
        if det is None:
            continue
        vectors[rec["id"]] = (str(det.get("engine") or ""), unit(det["embedding"]))

    rec_by_id = {r["id"]: r for r in face_records}
    neighbors: dict[str, list[dict[str, Any]]] = {r["id"]: [] for r in face_records}
    ordered_ids = [r["id"] for r in face_records if r["id"] in vectors]
    for idx, rid_a in enumerate(ordered_ids):
        space_a, vec_a = vectors[rid_a]
        for rid_b in ordered_ids[idx + 1 :]:
            space_b, vec_b = vectors[rid_b]
            if space_a != space_b or len(vec_a) != len(vec_b):
                continue
            sim = round(_cosine(vec_a, vec_b), 6)
            if sim >= min_similarity:
                rec_a, rec_b = rec_by_id[rid_a], rec_by_id[rid_b]
                neighbors[rid_a].append({
                    "id": rid_b,
                    "similarity": sim,
                    "scene_id": rec_b["scene_id"],
                    "timestamp": rec_b["media"]["timestamp"],
                })
                neighbors[rid_b].append({
                    "id": rid_a,
                    "similarity": sim,
                    "scene_id": rec_a["scene_id"],
                    "timestamp": rec_a["media"]["timestamp"],
                })

    for rid in neighbors:
        neighbors[rid].sort(key=lambda item: (-item["similarity"], item["timestamp"], item["id"]))

    # Centroid-guarded leader clustering prevents single-link drift across people.
    seeds = sorted(
        ordered_ids,
        key=lambda rid: (-len(neighbors[rid]), rec_by_id[rid]["media"]["timestamp"], rid),
    )
    assigned: set[str] = set()
    raw_groups: list[list[str]] = []
    min_member_avg = max(min_similarity - 0.05, 0.45)
    for seed in seeds:
        if seed in assigned:
            continue
        assigned.add(seed)
        members = [seed]
        seed_space, _ = vectors[seed]
        for cand in neighbors[seed]:
            cid = cand["id"]
            if cid in assigned:
                continue
            c_space, c_vec = vectors[cid]
            if c_space != seed_space:
                continue
            avg_sim = sum(_cosine(c_vec, vectors[m][1]) for m in members) / len(members)
            if avg_sim >= min_member_avg:
                assigned.add(cid)
                members.append(cid)
        members.sort(key=lambda rid: (rec_by_id[rid]["media"]["timestamp"], rid))
        raw_groups.append(members)

    # Append any face records without resolved embeddings as singletons so nothing disappears.
    for rec in face_records:
        if rec["id"] not in assigned:
            raw_groups.append([rec["id"]])

    raw_groups.sort(
        key=lambda members: (
            0 if len(members) > 1 else 1,
            -len(members),
            rec_by_id[members[0]]["media"]["timestamp"],
            members[0],
        )
    )

    groups = []
    for index, member_ids in enumerate(raw_groups, start=1):
        scenes = {rec_by_id[rid]["scene_id"] for rid in member_ids}
        unmatched = sum(rec_by_id[rid]["status"] != "proposed" for rid in member_ids)
        groups.append({
            "group_id": f"vgroup_{index:03d}",
            "representative_id": member_ids[0],
            "member_count": len(member_ids),
            "scene_count": len(scenes),
            "unmatched_count": unmatched,
            "record_ids": member_ids,
        })

    return {
        "report_id": report["id"],
        "epoch_id": report["epoch_id"],
        "min_similarity": min_similarity,
        "multi_face_group_count": sum(g["member_count"] > 1 for g in groups),
        "singleton_count": sum(g["member_count"] == 1 for g in groups),
        "groups": groups,
        "neighbors": neighbors,
    }


def _resolve_query_embeddings(
    cfg: dict[str, Any],
    *,
    report_id: str | None,
    evidence_id: str | None,
    cluster_id: str | None,
    person_id: str | None,
) -> tuple[dict[str, Any], list[tuple[str, list[float]]], set[tuple[str, str]]]:
    """Return (target_descriptor, [(space, unit_vec), ...], excluded_(epoch, detection_id))."""
    active_epoch = _active_epoch_root(cfg)
    detections, frame_scenes = _load_epoch_detections(active_epoch)
    det_by_id = {d["detection_id"]: d for d in detections}
    identity_dirs = _configured_identity_paths_by_epoch(cfg)
    active_ident_dir = identity_dirs.get(active_epoch.name)

    excluded: set[tuple[str, str]] = set()
    query_vectors: list[tuple[str, list[float]]] = []

    if report_id and evidence_id:
        report = matching_projection.read_report(cfg, report_id)
        bound = _match_report_records_to_detections(report, detections, frame_scenes)
        det = bound.get(evidence_id)
        if det is None:
            raise ValueError("Selected comparison face observation is unavailable")
        excluded.add((active_epoch.name, det["detection_id"]))
        query_vectors.append((str(det.get("engine") or ""), unit(det["embedding"])))
        return (
            {"kind": "match_evidence", "report_id": report_id, "evidence_id": evidence_id, "detection_id": det["detection_id"]},
            query_vectors,
            excluded,
        )

    if cluster_id:
        if not _SAFE_ID_RE.fullmatch(cluster_id):
            raise ValueError("Invalid cluster ID")
        if active_ident_dir is None or not (active_ident_dir / "face_clusters.json").is_file():
            raise FileNotFoundError("Active face_clusters.json is unavailable")
        manifest = read_json(active_ident_dir / "face_clusters.json")
        if manifest.get("epoch_id") != active_epoch.name:
            raise ValueError("Active face_clusters.json belongs to a different epoch")
        cluster = next((c for c in manifest.get("clusters") or [] if c.get("cluster_id") == cluster_id), None)
        if cluster is None:
            raise ValueError("Face cluster not found")
        for fid in cluster.get("face_ids") or []:
            det = det_by_id.get(str(fid))
            if det is not None:
                excluded.add((active_epoch.name, det["detection_id"]))
                query_vectors.append((str(det.get("engine") or ""), unit(det["embedding"])))
        if not query_vectors:
            raise ValueError("Face cluster has no promoted observations")
        return (
            {"kind": "face_cluster", "cluster_id": cluster_id, "label": cluster.get("label")},
            query_vectors[:24],
            excluded,
        )

    if person_id:
        if not _SAFE_ID_RE.fullmatch(person_id):
            raise ValueError("Invalid person ID")
        kg_meta = _read_epoch_kg_metadata(active_epoch)
        display_name = kg_meta["person_names"].get(person_id)
        for fid in sorted(kg_meta["person_faces"].get(person_id, set())):
            det = det_by_id.get(fid)
            if det is not None:
                excluded.add((active_epoch.name, det["detection_id"]))
                query_vectors.append((str(det.get("engine") or ""), unit(det["embedding"])))

        if active_ident_dir is not None and (active_ident_dir / "family_roster.yaml").is_file():
            roster = yaml.safe_load((active_ident_dir / "family_roster.yaml").read_text(encoding="utf-8")) or {}
            entry = next((i for i in roster.get("identities") or [] if i.get("id") == person_id), None)
            if entry is not None:
                display_name = display_name or entry.get("display_name")
                if entry.get("face_cluster_ids") and (active_ident_dir / "face_clusters.json").is_file():
                    manifest = read_json(active_ident_dir / "face_clusters.json")
                    if manifest.get("epoch_id") == active_epoch.name:
                        by_cid = {c["cluster_id"]: c for c in manifest.get("clusters") or []}
                        for cid in entry.get("face_cluster_ids") or []:
                            for fid in (by_cid.get(cid) or {}).get("face_ids") or []:
                                det = det_by_id.get(str(fid))
                                if det is not None and (active_epoch.name, det["detection_id"]) not in excluded:
                                    excluded.add((active_epoch.name, det["detection_id"]))
                                    query_vectors.append((str(det.get("engine") or ""), unit(det["embedding"])))

        # Also include saved reference embeddings from configured prior identity folders and reports.
        allowed_roots = _allowed_epoch_roots(cfg)
        for ep_name, ident_dir in sorted(identity_dirs.items()):
            if ep_name == active_epoch.name or ep_name not in allowed_roots:
                continue
            prior_roster_file = ident_dir / "family_roster.yaml"
            prior_clusters_file = ident_dir / "face_clusters.json"
            if not prior_roster_file.is_file() or not prior_clusters_file.is_file():
                continue
            try:
                prior_roster = yaml.safe_load(prior_roster_file.read_text(encoding="utf-8")) or {}
                prior_entry = next((i for i in prior_roster.get("identities") or [] if i.get("id") == person_id), None)
                if prior_entry is None or not prior_entry.get("face_cluster_ids"):
                    continue
                display_name = display_name or prior_entry.get("display_name")
                prior_manifest = read_json(prior_clusters_file)
                if prior_manifest.get("epoch_id") != ep_name:
                    continue
                prior_dets, _ = _load_epoch_detections(allowed_roots[ep_name])
                prior_det_by_id = {d["detection_id"]: d for d in prior_dets}
                by_cid = {c["cluster_id"]: c for c in prior_manifest.get("clusters") or []}
                for cid in prior_entry.get("face_cluster_ids") or []:
                    rep_ids = (by_cid.get(cid) or {}).get("face_ids") or []
                    if rep_ids:
                        det = prior_det_by_id.get(str(rep_ids[0]))
                        if det is not None and (ep_name, det["detection_id"]) not in excluded:
                            excluded.add((ep_name, det["detection_id"]))
                            query_vectors.append((str(det.get("engine") or ""), unit(det["embedding"])))
            except (OSError, ValueError, UnicodeError, yaml.YAMLError, json.JSONDecodeError):
                continue

        reports_dir = report_root(cfg) / "reports"
        if reports_dir.is_dir():
            for rpath in sorted(reports_dir.glob("*.json")):
                try:
                    rep = matching_projection.read_report(cfg, rpath.stem)
                except (OSError, ValueError, KeyError):
                    continue
                for p in rep.get("people") or []:
                    if p.get("id") == person_id and not display_name:
                        display_name = p.get("display_name")
                for ref in rep.get("references") or []:
                    if ref.get("person_id") == person_id and ref.get("media", {}).get("kind") == "image" and ref.get("embedding"):
                        obs_id = str(ref.get("observation_id") or "")
                        ref_epoch = str(ref.get("epoch_id") or "")
                        if obs_id and ref_epoch:
                            excluded.add((ref_epoch, obs_id))
                        query_vectors.append((str(ref.get("space") or ""), unit(ref["embedding"])))
                break

        if not query_vectors:
            raise ValueError(
                "This person does not have any linked face observations or saved face references yet. "
                "Assign at least one face or face cluster first, then scan across films."
            )
        return (
            {"kind": "person", "person_id": person_id, "display_name": display_name or person_id},
            query_vectors[:32],
            excluded,
        )

    raise ValueError("Provide report_id+evidence_id, cluster_id, or person_id to scan faces")


def _scan_single_epoch(
    epoch_root: Path,
    query_vectors: list[tuple[str, list[float]]],
    excluded: set[tuple[str, str]],
    identity_dir: Path | None,
    *,
    min_similarity: float,
    limit: int,
    report_evidence_by_det: dict[str, str] | None = None,
) -> dict[str, Any]:
    detections, frame_scenes = _load_epoch_detections(epoch_root)
    kg_meta = _read_epoch_kg_metadata(epoch_root)
    cluster_map = _read_cluster_annotations(epoch_root, identity_dir)

    inferred_video_name = kg_meta["video_name"]
    if not inferred_video_name and detections:
        try:
            inferred_video_name = Path(detections[0]["image_path"]).resolve().relative_to(
                (epoch_root / "processing").resolve()
            ).parts[0]
        except ValueError:
            inferred_video_name = epoch_root.name

    hits: list[dict[str, Any]] = []
    for det in detections:
        det_id = det["detection_id"]
        if (epoch_root.name, det_id) in excluded:
            continue
        det_space = str(det.get("engine") or "")
        det_vec = unit(det["embedding"])
        scores = [
            _cosine(det_vec, q_vec)
            for q_space, q_vec in query_vectors
            if q_space == det_space and len(q_vec) == len(det_vec)
        ]
        if not scores:
            continue
        best_sim = round(max(scores), 6)
        if best_sim < min_similarity:
            continue
        scene_id = frame_scenes.get(det["frame_id"], "")
        bounds = kg_meta["scene_bounds"].get(scene_id)
        owners = list(kg_meta["face_owners"].get(det_id, ()))
        cluster_info = cluster_map.get(det_id)
        if owners:
            curation_status = "confirmed_in_graph"
        elif cluster_info and cluster_info.get("label"):
            curation_status = "labeled_cluster_only"
        else:
            curation_status = "missed_unlabeled"
        norm_box = _bbox_coordinates(det.get("bbox"))
        hit: dict[str, Any] = {
            "epoch_id": epoch_root.name,
            "detection_id": det_id,
            "scene_id": scene_id,
            "scene_start": bounds[0] if bounds else det["t_start"],
            "scene_end": bounds[1] if bounds else det["t_start"],
            "timestamp": det["t_start"],
            "similarity": best_sim,
            "bbox": list(norm_box) if norm_box is not None else det.get("bbox"),
            "media_url": f"/api/identity/cross-film-media/{epoch_root.name}/{det_id}",
            "curation_status": curation_status,
            "missed": curation_status == "missed_unlabeled",
            "existing_names": owners,
            "cluster_id": cluster_info["cluster_id"] if cluster_info else None,
            "cluster_label": cluster_info["label"] if cluster_info else None,
        }
        if report_evidence_by_det and det_id in report_evidence_by_det:
            hit["evidence_id"] = report_evidence_by_det[det_id]
        hits.append(hit)

    hits.sort(key=lambda item: (-item["similarity"], float(item["timestamp"] or 0.0), item["detection_id"]))
    total_hits = len(hits)
    missed_hits = sum(1 for item in hits if item["missed"])
    scenes_hit = len({item["scene_id"] for item in hits if item["scene_id"]})
    return {
        "epoch_id": epoch_root.name,
        "video_id": kg_meta["video_id"] or inferred_video_name or epoch_root.name,
        "video_name": inferred_video_name or epoch_root.name,
        "total_matches": total_hits,
        "missed_unlabeled_count": missed_hits,
        "scene_count": scenes_hit,
        "matches": hits[:limit],
    }


def scan_face_across_films(
    cfg: dict[str, Any],
    *,
    report_id: str | None = None,
    evidence_id: str | None = None,
    cluster_id: str | None = None,
    person_id: str | None = None,
    min_similarity: float = 0.50,
    limit_per_movie: int = 12,
) -> dict[str, Any]:
    """Compare target face(s) against the active movie and configured other movies."""
    if not math.isfinite(min_similarity) or not 0.25 <= min_similarity <= 0.95:
        raise ValueError("Invalid cross-film similarity threshold")
    if not isinstance(limit_per_movie, int) or not 1 <= limit_per_movie <= 50:
        raise ValueError("Invalid cross-film per-movie limit")

    target, query_vectors, excluded = _resolve_query_embeddings(
        cfg,
        report_id=report_id,
        evidence_id=evidence_id,
        cluster_id=cluster_id,
        person_id=person_id,
    )
    active_epoch = _active_epoch_root(cfg)
    identity_dirs = _configured_identity_paths_by_epoch(cfg)

    report_evidence_by_det: dict[str, str] = {}
    if report_id:
        rep = matching_projection.read_report(cfg, report_id)
        active_dets, active_scenes = _load_epoch_detections(active_epoch)
        bound = _match_report_records_to_detections(rep, active_dets, active_scenes)
        report_evidence_by_det = {det["detection_id"]: rid for rid, det in bound.items()}

    current_movie = _scan_single_epoch(
        active_epoch,
        query_vectors,
        excluded,
        identity_dirs.get(active_epoch.name),
        min_similarity=min_similarity,
        limit=limit_per_movie,
        report_evidence_by_det=report_evidence_by_det,
    )

    other_movies = []
    for other_root in sorted(reviewed_source_roots(cfg.get("identity_matching") or {})):
        resolved = Path(other_root).resolve()
        if resolved == active_epoch or not resolved.is_dir():
            continue
        movie_result = _scan_single_epoch(
            resolved,
            query_vectors,
            excluded,
            identity_dirs.get(resolved.name),
            min_similarity=min_similarity,
            limit=limit_per_movie,
        )
        other_movies.append(movie_result)

    other_movies.sort(key=lambda item: (-item["total_matches"], item["video_name"], item["epoch_id"]))
    return {
        "target": target,
        "min_similarity": min_similarity,
        "query_embedding_count": len(query_vectors),
        "current_movie": current_movie,
        "other_movies": other_movies,
        "summary": {
            "current_movie_matches": current_movie["total_matches"],
            "other_movies_scanned": len(other_movies),
            "other_movies_with_matches": sum(m["total_matches"] > 0 for m in other_movies),
            "other_movie_matches": sum(m["total_matches"] for m in other_movies),
            "missed_unlabeled_in_other_movies": sum(m["missed_unlabeled_count"] for m in other_movies),
        },
    }


def cross_film_media_file(cfg: dict[str, Any], epoch_id: str, detection_id: str) -> tuple[Path, str]:
    """Resolve and verify the source keyframe image for a promoted face detection."""
    if not _EPOCH_ID_RE.fullmatch(epoch_id):
        raise ValueError("Invalid epoch ID")
    match = _DETECTION_ID_RE.fullmatch(detection_id)
    if match is None:
        raise ValueError("Invalid detection ID")
    roots = _allowed_epoch_roots(cfg)
    epoch_root = roots.get(epoch_id)
    if epoch_root is None:
        raise FileNotFoundError("Requested epoch is not an active or configured source")
    ucf_db = epoch_root / "ucf" / "ucf_ledger.db"
    if not ucf_db.is_file():
        raise FileNotFoundError("UCF ledger is unavailable for requested epoch")
    detections_list, _ = _load_epoch_detections(epoch_root)
    detections = {d["detection_id"]: d for d in detections_list}
    det = detections.get(detection_id)
    if det is None:
        raise FileNotFoundError("Requested face detection is missing or retired")
    image_path = Path(det["image_path"]).resolve(strict=True)
    processing_root = (epoch_root / "processing").resolve()
    if not image_path.is_relative_to(processing_root):
        raise ValueError("Cross-film face image escapes its processing directory")
    return image_path, "image/jpeg"
