"""Reusable, review-only identity comparisons in the normal ingestion path.

The roster owns person IDs. References come from explicitly labeled group
representatives and reviewed voice mappings; predictions never become references.
This module writes only versioned comparison receipts, never identities or indexes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import uuid

import yaml

from wsl2_audio import speaker_signature

SCHEMA = "identity_matching_v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def report_root(cfg):
    return Path(cfg["paths"]["db_path"]).resolve().parent / "identity_matching"


def _write_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read_json(path) != value:
            raise ValueError("Identity comparison receipt already exists with different inputs")
        return
    # A partial file is never published under a report name.
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     suffix=".tmp", delete=False) as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        temporary = Path(handle.name)
    try:
        # Hard-link publication refuses an existing destination on both platforms.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def unit(vector):
    if not isinstance(vector, list) or not vector or any(
        type(x) not in (int, float) or not math.isfinite(x) for x in vector
    ):
        raise ValueError("Invalid identity embedding")
    norm = math.sqrt(sum(x * x for x in vector))
    if not math.isfinite(norm) or norm <= 1e-8:
        raise ValueError("Empty identity embedding")
    return [x / norm for x in vector]


def _media(path, root, **details):
    path, root = Path(path).resolve(strict=True), Path(root).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Identity evidence escapes its configured source")
    return {"path": str(path), "sha256": file_digest(path), **details}


def voice_clip(scene, signature, root):
    if 'review_evidence' in signature:
        from wsl2_audio.scene_consumers import validate_review, _digest as audio_digest
        if (signature.get('owner_scene_id') != scene['scene_id'] or
                audio_digest({k: v for k, v in signature.items() if k != 'content_sha256'}) != signature.get('content_sha256')):
            raise ValueError('Voice contribution changed or belongs to another scene')
        reviews = signature['review_evidence']
        if not reviews or {r['utterance_id'] for r in reviews} != set(signature['utterance_ids']):
            raise ValueError('Voice contribution lacks full review evidence')
        for review in reviews:
            if review['eligibility']['voice_sample']['status'] != 'eligible':
                raise ValueError('Ineligible source entered voice contribution')
            validate_review(review, signature['source'], root=root)
        review = max(reviews, key=lambda row: row['sample_count'])
        path = validate_review(review, signature['source'], root=root)
        source = signature['source']
        return _media(path, root, kind='audio', start=0., end=review['sample_count']/source['sample_rate'],
            timestamp=source['origin_num']/source['origin_den']+review['span']['start']/source['sample_rate'],
            source_span=review['span'], source_sha256=source['sha256'],
            utterance_id=review['utterance_id'], contribution_id=signature['contribution_id'],
            review_schema=review['schema'])
    audio = scene["audio"]
    segments = signature.get("selected_segments") or []
    valid = [s for s in segments if s.get("speaker") == signature.get("speaker")
             and all(type(s.get(k)) in (int, float) and math.isfinite(s[k]) for k in ("start", "end"))
             and 0 <= s["start"] < s["end"] <= scene["end"] - scene["start"] + .1]
    if not valid:
        raise ValueError("Voice signature has no bound review interval")
    segment = max(valid, key=lambda s: s["end"] - s["start"])
    return _media(audio["path"], root, kind="audio", start=segment["start"],
                  end=min(segment["end"], segment["start"] + 12),
                  timestamp=scene["start"] + segment["start"])


def reviewed_source_roots(options):
    """Explicit source roots only; never discover private movies by scanning disks."""
    return {Path(s["epoch_root"]).resolve() for s in options.get("reference_sources", [])} | {
        Path(p).resolve() for p in options.get("reviewed_face_sources", [])}


def read_reviewed_faces(epoch, people):
    """Materialize only applied, explicitly reusable Correct faces from saved evidence.

    The existing appearance receipt is the admission record. Undo revokes it;
    incorrect, uncertain and legacy non-acceptances are never reference examples
    for the rejected person; an Incorrect face explicitly assigned to another
    saved person is admitted only for that person.
    No model or vector-store operation is performed here.
    """
    from lib.identity_resolver import retired_identity_scene_ids
    from scripts.identity.build_face_clusters import collect_face_detections, load_face_ucf_provenance

    epoch = Path(epoch).resolve(strict=True)
    kg = epoch / "knowledge_graph.db"
    admitted, bindings = {}, {}
    with sqlite3.connect(kg.as_uri() + "?mode=ro", uri=True) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='identity_appearance_receipts' AND type='table'").fetchone():
            return [], None
        kg_people = {
            name: (json.loads(raw or "{}") if raw else {}).get("display_name")
            for name, raw in conn.execute("SELECT name, properties FROM nodes WHERE node_type='Person'")
        }
        for (raw,) in conn.execute("SELECT receipt FROM identity_appearance_receipts ORDER BY rowid"):
            receipt = json.loads(raw)
            if receipt["status"] != "applied" or not receipt.get("reference_faces"):
                continue
            if digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}) != receipt["receipt_sha256"]:
                raise ValueError("Reviewed face receipt changed")
            review = receipt["review"]
            if receipt["epoch_id"] != epoch.name or not review.get("reuse_confirmed_faces"):
                raise ValueError("Reviewed face reuse was not approved for this epoch")
            for spec in receipt["reference_faces"]:
                # Correct faces keep their named candidate; corrected faces were
                # marked Incorrect and explicitly assigned to the saved person.
                state = review.get("decisions", {}).get(spec["evidence_id"])
                if spec.get("assignment") == "human_corrected":
                    admitted_by_review = (state == "incorrect" and (review.get("corrections") or {})
                                          .get(spec["evidence_id"]) == spec["person_id"])
                else:
                    admitted_by_review = state == "correct" and spec["evidence_id"] in review["accepted_ids"]
                pid, display_name = spec.get("person_id"), spec.get("display_name")
                if pid in people:
                    person_ok = people.get(pid) == display_name
                else:
                    person_ok = (
                        spec.get("assignment") == "human_corrected"
                        and isinstance(pid, str) and bool(pid)
                        and isinstance(display_name, str) and bool(display_name)
                        and kg_people.get(pid) == display_name
                    )
                    if person_ok:
                        people[pid] = display_name
                if (not admitted_by_review
                        or spec["report_id"] != review["report_id"] or spec["report_sha256"] != review["report_sha256"]
                        or not person_ok):
                    raise ValueError("Reviewed reference conflicts with its named person or Correct decision")
                fid = spec["target_face_id"]
                if fid in admitted and admitted[fid] != spec:
                    raise ValueError("Conflicting reusable face identity")
                admitted[fid] = spec
        for pid, sid, raw in conn.execute("""SELECT p.name,s.name,e.properties FROM edges e
            JOIN nodes p ON p.id=e.source_id JOIN nodes s ON s.id=e.target_id
            WHERE p.node_type='Person' AND s.node_type='scene' AND e.edge_type='person_appears_in_scene'"""):
            bindings[(pid, sid)] = json.loads(raw or "{}")
    if not admitted:
        return [], None
    retired = retired_identity_scene_ids(epoch / "ucf/ucf_ledger.db")
    active = {fid: spec for fid, spec in admitted.items() if spec["scene_id"] not in retired}
    frames = {int(fid.split("_", 1)[0]) for fid in active}
    provenance = load_face_ucf_provenance(epoch / "ucf/ucf_ledger.db")
    provenance = {path: rows for path, rows in provenance.items() if any(r["frame_id"] in frames for r in rows)}
    frame_scenes = {r["frame_id"]: r["source_artifact_id"] for rows in provenance.values() for r in rows}
    detections = {d["detection_id"]: d for d in collect_face_detections(epoch, provenance)} if active else {}
    faces = []
    for fid, spec in sorted(active.items()):
        detection = detections.get(fid)
        edge = bindings.get((spec["person_id"], spec["scene_id"]), {})
        if (not detection or frame_scenes.get(detection["frame_id"]) != spec["scene_id"]
                or fid not in edge.get("evidence_face_ids", [])
                or not any(r.get("evidence_id") == spec["evidence_id"] and r.get("report_id") == spec["report_id"]
                           and r.get("target_face_id") == fid for r in edge.get("reviewed_matches", []))):
            raise ValueError("Reusable face no longer has its promoted observation and reviewed scene link")
        media = _media(detection["image_path"], epoch / "processing", kind="image",
                       bbox=detection["bbox"], timestamp=detection["t_start"])
        if (detection["video_hash"] != spec["video_hash"] or detection["engine"] != spec["space"]
                or digest(detection["embedding"]) != spec["embedding_sha256"]
                or media["sha256"] != spec["media_sha256"] or media["bbox"] != spec["bbox"]
                or media["timestamp"] != spec["timestamp"]):
            raise ValueError("Reusable face pixels or saved encoding changed")
        faces.append({"id": digest([epoch.name, "reviewed_face", fid]), "person_id": spec["person_id"],
            "display_name": people[spec["person_id"]], "epoch_id": epoch.name, "observation_id": fid,
            "scene_id": spec["scene_id"], "video_hash": detection["video_hash"],
            "video_name": Path(detection["image_path"]).relative_to(epoch / "processing").parts[0],
            "space": detection["engine"], "embedding": unit(detection["embedding"]), "media": media,
            "review": {"report_id": spec["report_id"], "evidence_id": spec["evidence_id"]}})
    return faces, {"kind": "reviewed_faces", "epoch_root": str(epoch), "reviews_sha256": digest(active)}


def load_reference_catalog(options):
    """Read configured family evidence without changing any source artifact."""
    from scripts.identity.build_face_clusters import load_face_ucf_provenance, collect_face_detections

    people, faces, voices, sources = {}, [], [], []
    for source in options.get("reference_sources", []):
        epoch = Path(source["epoch_root"]).resolve(strict=True)
        identity = Path(source["identity_path"]).resolve(strict=True)
        kg_path = epoch / "knowledge_graph.db"
        from lib.identity_resolver import retired_identity_scene_ids
        retired = retired_identity_scene_ids(epoch / "ucf/ucf_ledger.db")
        roster_path, cluster_path = identity / "family_roster.yaml", identity / "face_clusters.json"
        roster = yaml.safe_load(roster_path.read_text(encoding="utf-8")) or {}
        has_group_refs = any(person.get("face_cluster_ids") for person in roster.get("identities", []))
        if cluster_path.is_file() or has_group_refs:
            clusters = read_json(cluster_path)
            if clusters.get("epoch_id") != epoch.name:
                raise ValueError("Reference labels belong to a different epoch")
            group_map = {c["cluster_id"]: c for c in clusters["clusters"]}
            groups_sha256 = file_digest(cluster_path)
        else:
            group_map = {}
            groups_sha256 = None
        provenance = load_face_ucf_provenance(epoch / "ucf/ucf_ledger.db")
        required = {int(group_map[group_id]["face_ids"][0].split("_", 1)[0])
                    for person in roster.get("identities", []) for group_id in person.get("face_cluster_ids", [])}
        retired_frames = {r["frame_id"] for rows in provenance.values() for r in rows if r["source_artifact_id"] in retired}
        # Only the explicitly selected references need image/raw verification.
        # Keep all rows for each selected image to preserve multi-face authority.
        provenance = {path: [r for r in rows if r["source_artifact_id"] not in retired]
                      for path, rows in provenance.items() if any(r["frame_id"] in required for r in rows)}
        provenance = {path: rows for path, rows in provenance.items() if rows}
        detections = {d["detection_id"]: d for d in collect_face_detections(epoch, provenance)}
        owners = {}
        source_people = {}
        for person in roster.get("identities", []):
            pid, name = person["id"], person["display_name"]
            if not isinstance(pid, str) or not pid or not isinstance(name, str) or not name:
                raise ValueError("Reference people need stable IDs and display names")
            if pid in source_people or (pid in people and people[pid] != name):
                raise ValueError("Conflicting reference person identity")
            people[pid] = source_people[pid] = name
            for group_id in person.get("face_cluster_ids", []):
                group = group_map[group_id]
                if group_id in owners or not isinstance(group.get("label"), str) or not group["label"].strip():
                    raise ValueError("Face group ownership or label conflicts with the roster")
                owners[group_id] = pid
                # The displayed representative was named by the operator. Other
                # group members are not independently confirmed training examples.
                if group["face_ids"][0] not in detections:
                    if int(group["face_ids"][0].split("_", 1)[0]) in retired_frames:
                        continue  # A retired reference must not train later films.
                    raise ValueError("The labeled reference has no promoted source observation")
                detection = detections[group["face_ids"][0]]
                faces.append({"id": digest([epoch.name, group_id, detection["detection_id"]]),
                              "person_id": pid, "display_name": name, "epoch_id": epoch.name,
                              "group_id": group_id, "observation_id": detection["detection_id"],
                              "video_hash": detection["video_hash"],
                              "video_name": Path(detection["image_path"]).relative_to(epoch / "processing").parts[0],
                              "space": detection["engine"], "embedding": unit(detection["embedding"]),
                              "media": _media(detection["image_path"], epoch / "processing", kind="image",
                                              bbox=detection["bbox"], timestamp=detection["t_start"])})

        results_path = Path(source["results_path"]).resolve(strict=True)
        videos = read_json(results_path)
        scenes = {s["scene_id"]: (v, s) for v in videos for s in v.get("scenes", []) if s["scene_id"] not in retired}
        mappings_path = epoch / "manual_identity_mappings.json"
        mappings = read_json(mappings_path).get("mappings", []) if mappings_path.is_file() else []
        with sqlite3.connect(kg_path.as_uri() + "?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT id,name,properties FROM nodes WHERE node_type='speaker_pattern' ORDER BY id"):
                props = json.loads(row["properties"] or "{}")
                space = speaker_signature.validate_metadata(props)
                if not space:
                    continue  # Untagged legacy spaces cannot seed the current recognizer.
                clips = []
                for edge in conn.execute("SELECT properties FROM edges WHERE target_id=? AND edge_type='voice_pattern_match'", (row["id"],)):
                    evidence = json.loads(edge[0] or "{}")
                    if evidence.get("scene_id") not in scenes:
                        continue
                    video, scene = scenes[evidence["scene_id"]]
                    for signature in scene.get("audio", {}).get("speaker_voice_signatures", []):
                        if (str(signature.get("speaker", "")).casefold() == str(evidence.get("speaker_label", "")).casefold()
                                and speaker_signature.validate_metadata(signature) == space):
                            clips.append((signature.get("voiced_seconds", 0), video, scene, signature))
                if not clips:
                    continue
                _, video, scene, signature = max(clips, key=lambda x: x[0])
                names = set()
                for mapping in mappings:
                    if (mapping.get("status") != "active" or mapping.get("source_node_type") != "speaker_pattern"
                            or mapping.get("source_node_name") != row["name"]):
                        continue
                    for edge in conn.execute("""SELECT e.properties FROM edges e JOIN nodes n ON n.id=e.target_id
                        WHERE e.source_id=? AND e.edge_type='identity_evidence' AND n.node_type='person' AND n.name=?""",
                                             (row["id"], mapping.get("target_person_name"))):
                        review = json.loads(edge[0] or "{}")
                        if review.get("source") == "operator_manual_override" and review.get("mapping_id") == mapping.get("mapping_id"):
                            names.add(mapping["target_person_name"])
                person_ids = [pid for pid, name in source_people.items() if name in names]
                if len(names) > 1 or len(person_ids) > 1:
                    raise ValueError("Conflicting reviewed voice identity")
                pid = person_ids[0] if person_ids else None
                voices.append({"id": digest([epoch.name, row["name"]]), "pattern_name": row["name"],
                               "person_id": pid, "display_name": people.get(pid), "epoch_id": epoch.name,
                               "video_hash": video["video_hash"], "scene_id": scene["scene_id"],
                               "video_name": video["video_name"],
                               "speaker_label": signature["speaker"], "space": space,
                               "embedding": unit(props["embedding"]),
                               "media": voice_clip(scene, signature, epoch / "processing")})
        sources.append({"epoch_root": str(epoch), "identity_path": str(identity),
                        "roster_sha256": file_digest(roster_path), "groups_sha256": groups_sha256,
                        "results_path": str(results_path), "results_sha256": file_digest(results_path),
                        "voice_mappings_sha256": file_digest(mappings_path) if mappings_path.is_file() else None})
    if not sources:
        raise ValueError("Enable identity matching with at least one reviewed reference source")
    for epoch in sorted(reviewed_source_roots(options)):
        reviewed, source = read_reviewed_faces(epoch, people)
        if source:
            faces.extend(reviewed)
            sources.append(source)
    return {"schema": SCHEMA, "people": [{"id": pid, "display_name": name} for pid, name in sorted(people.items())],
            "faces": faces, "voices": voices, "sources": sources}


def prepare_matching(cfg, run_id):
    options = cfg.get("identity_matching") or {}
    if not options.get("enabled"):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", str(run_id)):
        raise ValueError("Invalid identity comparison run ID")
    path = report_root(cfg) / "references" / f"{run_id}.json"
    if path.exists():
        return read_json(path)  # Resume retains the original prediction references.
    catalog = load_reference_catalog(options)
    policy = {"face_similarity": float(options.get("face_min_similarity", .6)),
              "voice_similarity": float(options.get("voice_min_similarity", speaker_signature.THRESHOLD)),
              "minimum_margin": float(options.get("minimum_margin", .05)),
              "score_meaning": "cosine_similarity_not_identity_probability"}
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in policy.values() if isinstance(v, float)):
        raise ValueError("Invalid identity matching thresholds")
    frozen = {"catalog": catalog, "catalog_sha256": digest(catalog), "policy": policy, "run_id": run_id}
    _write_once(path, frozen)
    return frozen


def compare(vector, space, references, threshold, margin):
    query = unit(vector)
    best = {}
    for reference in references:
        if reference["space"] != space or len(reference["embedding"]) != len(query):
            continue
        score = sum(a * b for a, b in zip(query, reference["embedding"]))
        owner = reference.get("person_id") or reference["id"]
        candidate = {"reference_id": reference["id"], "person_id": reference.get("person_id"),
                     "display_name": reference.get("display_name"), "similarity": round(max(-1, min(1, score)), 6)}
        if owner not in best or candidate["similarity"] > best[owner]["similarity"]:
            best[owner] = candidate
    ranked = sorted(best.values(), key=lambda r: (-r["similarity"], r["reference_id"]))[:2]
    gap = ranked[0]["similarity"] - ranked[1]["similarity"] if len(ranked) > 1 else None
    status = ("no_reference" if not ranked else "no_match" if ranked[0]["similarity"] < threshold
              else "ambiguous" if gap is not None and gap < margin else "proposed")
    return {"status": status, "candidates": ranked, "margin": round(gap, 6) if gap is not None else None}


def write_video_matches(cfg, frozen, video):
    """Persist initial comparisons from the real pipeline's emitted observations."""
    epoch = Path(cfg["paths"]["db_path"]).resolve().parent
    catalog, policy = frozen["catalog"], frozen["policy"]
    records, errors = [], []
    media_cache = {}
    for scene in video["scenes"]:
        common = {"scene_id": scene["scene_id"], "scene_start": scene["start"], "scene_end": scene["end"]}
        for observation in scene.get("keyframe", {}).get("face_observations", []):
            for index, face in enumerate(observation.get("faces", [])):
                ident = digest([epoch.name, video["video_hash"], scene["scene_id"], "face", observation["timestamp"], index])
                try:
                    path = observation["source_path"]
                    if path not in media_cache:
                        media_cache[path] = _media(path, epoch / "processing", kind="image")
                    media = {**media_cache[path], "bbox": face["bbox"], "timestamp": observation["timestamp"]}
                    result = compare(face["encoding"], face.get("engine"), catalog["faces"],
                                     policy["face_similarity"], policy["minimum_margin"])
                    records.append({"id": ident, "modality": "face", **common, "media": media, **result})
                except (KeyError, ValueError, OSError) as exc:
                    errors.append({"id": ident, "modality": "face", **common, "reason": str(exc)})
        for signature in scene.get("audio", {}).get("speaker_voice_signatures", []):
            ident = digest([epoch.name, video["video_hash"], scene["scene_id"], "voice", signature.get("speaker")])
            try:
                space = speaker_signature.validate_metadata(signature)
                if not space:
                    raise ValueError("Voice signature has no qualified embedding space")
                media = voice_clip(scene, signature, epoch / "processing")
                result = compare(signature["embedding"], space, catalog["voices"],
                                 policy["voice_similarity"], policy["minimum_margin"])
                records.append({"id": ident, "modality": "voice", **common, "media": media,
                                "speaker_label": signature["speaker"],
                                "admission_policy": signature.get("admission_policy"),
                                "excluded_segment_count": len(signature.get("excluded_segments", [])), **result})
            except (KeyError, ValueError, OSError) as exc:
                errors.append({"id": ident, "modality": "voice", **common, "reason": str(exc)})
    # Two simultaneous faces/diarization tracks cannot silently claim one person.
    collisions = defaultdict(list)
    for record in records:
        if record["status"] == "proposed":
            candidate = record["candidates"][0]
            owner = candidate["person_id"] or candidate["reference_id"]
            interval = record["media"]["timestamp"] if record["modality"] == "face" else record["scene_id"]
            collisions[(record["modality"], record["scene_id"], interval, owner)].append(record)
    for group in collisions.values():
        if len(group) > 1:
            for record in group:
                record.update(status="ambiguous", hold_reason="competing_observations_in_same_frame_or_scene")
    report_id = digest([epoch.name, video["video_hash"], frozen["run_id"]])
    report = {"schema": SCHEMA, "id": report_id, "run_id": frozen["run_id"], "epoch_id": epoch.name,
              "video_hash": video["video_hash"], "video_id": Path(video["video_path"]).stem,
              "video_name": video["video_name"], "source_path": video["video_path"],
              "status": "partial" if errors else "ready_for_review", "applied": False,
              "references_sha256": frozen["catalog_sha256"], "policy": policy,
              "people": catalog["people"], "references": catalog["faces"] + catalog["voices"],
              "reference_sources": catalog["sources"], "records": records, "errors": errors,
              "summary": {modality: dict(Counter(r["status"] for r in records if r["modality"] == modality))
                          for modality in ("face", "voice")}}
    report["content_sha256"] = digest(report)
    _write_once(report_root(cfg) / "reports" / f"{report_id}.json", report)
    return {k: report[k] for k in ("id", "status", "applied", "summary", "references_sha256", "content_sha256")}


def refresh_epoch_matches(cfg):
    """Re-compare saved epoch observations against the latest configured reference catalog.

    Writes append-only comparison receipts without mutating prior reports or
    re-running media inference. Refuses when an appearance review is already
    applied to the epoch so competing reports cannot diverge from saved links.
    """
    options = cfg.get("identity_matching") or {}
    if not options.get("enabled"):
        raise ValueError("Identity matching is not enabled for this epoch")
    epoch = Path(cfg["paths"]["db_path"]).resolve().parent
    out_dir = Path(cfg["paths"].get("output_directory") or (epoch / "output"))
    results_path = out_dir / "scene_ingest_results.json"
    if not results_path.is_file():
        raise FileNotFoundError("Completed scene_ingest_results.json is unavailable for this epoch")
    raw_results = read_json(results_path)
    videos = raw_results if isinstance(raw_results, list) else (raw_results.get("videos") or raw_results.get("results") or [])
    if not isinstance(videos, list) or not videos:
        raise ValueError("No ingested video entries found in scene_ingest_results.json")

    kg_path = Path(cfg["paths"].get("knowledge_graph_db") or (epoch / "knowledge_graph.db"))
    if kg_path.is_file():
        with sqlite3.connect(kg_path.as_uri() + "?mode=ro", uri=True) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='identity_appearance_receipts' AND type='table'"
            ).fetchone()
            if has_table:
                for (raw,) in conn.execute("SELECT receipt FROM identity_appearance_receipts ORDER BY rowid"):
                    receipt = json.loads(raw)
                    if receipt.get("status") == "applied" and receipt.get("epoch_id") == epoch.name:
                        raise ValueError(
                            "An appearance review is already applied for this movie. "
                            "Undo that review before refreshing prior-film comparisons."
                        )

    catalog = load_reference_catalog(options)
    catalog_sha256 = digest(catalog)
    reports_dir = report_root(cfg) / "reports"
    existing_by_video: dict[str, dict] = {}
    if reports_dir.is_dir():
        for rpath in sorted(reports_dir.glob("*.json")):
            rep = read_json(rpath)
            if rep.get("epoch_id") == epoch.name and rep.get("references_sha256") == catalog_sha256:
                existing_by_video[str(rep.get("video_hash") or "")] = rep

    target_hashes = [str(v.get("video_hash") or "") for v in videos]
    if target_hashes and all(vhash in existing_by_video for vhash in target_hashes):
        matched_ids = [existing_by_video[vhash]["id"] for vhash in target_hashes]
        return {
            "refreshed": False,
            "mutated": False,
            "reports": matched_ids,
            "latest_report_id": matched_ids[-1],
            "references_sha256": catalog_sha256,
            "people_count": len(catalog["people"]),
            "face_reference_count": len(catalog["faces"]),
            "message": "Saved comparison already includes all latest prior-film references.",
        }

    run_id = f"refresh_{uuid.uuid4().hex[:12]}"
    frozen = prepare_matching(cfg, run_id)
    summaries = [write_video_matches(cfg, frozen, video) for video in videos]
    return {
        "refreshed": True,
        "mutated": True,
        "run_id": run_id,
        "reports": [item["id"] for item in summaries],
        "latest_report_id": summaries[-1]["id"],
        "references_sha256": frozen["catalog_sha256"],
        "people_count": len(catalog["people"]),
        "face_reference_count": len(catalog["faces"]),
        "summaries": summaries,
    }
