"""Plan explicitly reviewed face appearances from an immutable comparison.

Unselected observations, voices and mentions stay held. A face marked Incorrect
may name the right saved person instead; only that person receives the link.
This planner reads saved evidence only; the existing appearance transaction
owns Apply and Undo.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path

from api.utils import identity_appearance as appearance
from api.utils import identity_matching as matching
from lib.identity_matching import (file_digest, digest, load_reference_catalog, read_reviewed_faces,
                                   reviewed_source_roots)
from lib.identity_resolver import retired_identity_scene_ids
from scripts.identity.build_face_clusters import collect_face_detections, load_face_ucf_provenance


def _same_reference_facts(cfg, report, source, pair):
    """Accept edited roster/label files only when identity facts are unchanged.

    Aliases or display-only group labels can change file bytes after a
    comparison is frozen. The current labels must still produce exactly the
    frozen references (person, name, group, representative observation, pixels
    and encoding) and the same names for every person from this source.
    """
    options = next(s for s in (cfg.get("identity_matching") or {}).get("reference_sources", [])
                   if (str(Path(s["epoch_root"]).resolve()), str(Path(s["identity_path"]).resolve())) == pair)
    try:
        current = load_reference_catalog({"reference_sources": [options]})
    except (OSError, ValueError, KeyError):
        return False
    epoch = Path(source["epoch_root"]).resolve().name
    frozen = sorted((r for r in report["references"] if r.get("epoch_id") == epoch
                     and ("group_id" in r or "pattern_name" in r)), key=lambda r: r["id"])
    names = {p["id"]: p["display_name"] for p in report["people"]}
    return (json.loads(json.dumps(frozen)) == json.loads(json.dumps(sorted(current["faces"] + current["voices"], key=lambda r: r["id"])))
            and all(names.get(p["id"]) == p["display_name"] for p in current["people"]))


def build(cfg, conn, review):
    report = matching.read_report(cfg, review["report_id"])
    if report["content_sha256"] != review["report_sha256"]:
        raise appearance.AppearanceConflict("The comparison changed. Reload and review the faces again.")
    ids = review.get("accepted_ids", [])
    records = {r["id"]: r for r in report["records"]}
    decisions = review.get("decisions")
    if decisions is not None:
        if (len(decisions) > 1000 or any(i not in records or records[i]["modality"] != "face"
                or state not in {"correct", "incorrect", "unsure", "not_accepted"} for i, state in decisions.items())):
            raise appearance.AppearanceConflict("Review each saved face as Correct, Incorrect or Unsure.")
        if set(ids) != {i for i, state in decisions.items() if state == "correct"}:
            raise appearance.AppearanceConflict("Correct decisions and selected faces disagree.")
        if "not_accepted" in decisions.values() and not review.get("completed_review"):
            raise appearance.AppearanceConflict("Not accepted is reserved for a carried-forward completed review.")
        if review.get("completed_review") and set(decisions) != {i for i, r in records.items() if r["modality"] == "face"}:
            raise appearance.AppearanceConflict("A completed review must account for every saved face.")
    elif review.get("completed_review") or review.get("reuse_confirmed_faces"):
        raise appearance.AppearanceConflict("Reusable faces require explicit Correct review decisions.")
    people = {p["id"]: p["display_name"] for p in report["people"]}
    # A correction names the right saved person for a face marked Incorrect.
    # The rejected candidate never receives the face; the decision stays Incorrect.
    corrections = review.get("corrections") or {}
    if corrections:
        if decisions is None or len(corrections) > 1000 or any(
                decisions.get(i) != "incorrect" for i in corrections):
            raise appearance.AppearanceConflict("Choose the right person only for a face marked Incorrect.")
        for i, pid in corrections.items():
            rejected = (records[i]["candidates"] or [{}])[0].get("person_id")
            if pid not in people or not rejected:
                raise appearance.AppearanceConflict("Choose a saved person for each corrected face.")
            if pid == rejected:
                raise appearance.AppearanceConflict("The chosen person is the one marked Incorrect.")
    if decisions is not None:
        for prior in appearance._history(conn):
            old = prior.get("review", {})
            if prior["status"] != "applied" or old.get("report_id") != report["id"]:
                continue
            if any(decisions.get(i) != "correct" for i in old.get("accepted_ids", [])):
                raise appearance.AppearanceConflict("Undo the saved Correct decision before changing it.")
            if any(corrections.get(i) != pid for i, pid in (old.get("corrections") or {}).items()):
                raise appearance.AppearanceConflict("Undo the saved correction before changing it.")
            if old.get("reuse_confirmed_faces") and not review.get("reuse_confirmed_faces"):
                raise appearance.AppearanceConflict("Undo the saved reusable faces before withdrawing reuse.")
    if len(ids) != len(set(ids)) or any(i not in records for i in ids):
        raise appearance.AppearanceConflict("Select each saved observation at most once.")
    selected = [records[i] for i in sorted(ids)] + [records[i] for i in sorted(corrections)]
    if any(r["modality"] != "face" or not r["candidates"] for r in selected):
        raise appearance.AppearanceConflict("Only faces with a named reference can be confirmed here.")
    epoch, kg, _ = appearance._paths(cfg)
    root = kg.parent
    refs = {r["id"]: r for r in report["references"]}
    configured = {(str(Path(s["epoch_root"]).resolve()), str(Path(s["identity_path"]).resolve()))
                  for s in (cfg.get("identity_matching") or {}).get("reference_sources", [])}
    for source in report["reference_sources"]:
        if source.get("kind") == "reviewed_faces":
            if Path(source["epoch_root"]).resolve() not in reviewed_source_roots(cfg.get("identity_matching") or {}):
                raise appearance.AppearanceConflict("The reviewed reference source is no longer configured.")
            _, current = read_reviewed_faces(Path(source["epoch_root"]), people)
            if current != source:
                raise appearance.AppearanceConflict("Reviewed references changed. Review fresh reference evidence first.")
            continue
        pair = (str(Path(source["epoch_root"]).resolve()), str(Path(source["identity_path"]).resolve()))
        if pair not in configured:
            raise appearance.AppearanceConflict("The reference source is no longer configured.")
        changed = any(file_digest(Path(pair[1]) / name) != source[key]
                      for name, key in (("family_roster.yaml", "roster_sha256"), ("face_clusters.json", "groups_sha256")))
        if changed and not _same_reference_facts(cfg, report, source, pair):
            raise appearance.AppearanceConflict("Reference names or labels changed. Review fresh reference evidence first.")
    retired = retired_identity_scene_ids(root / "ucf/ucf_ledger.db")
    scenes = {r["scene_id"] for r in selected}
    if scenes & retired:
        raise appearance.AppearanceConflict("A selected scene is retired and cannot receive a new appearance.")
    provenance = load_face_ucf_provenance(root / "ucf/ucf_ledger.db") if selected else {}
    provenance = {path: rows for path, rows in provenance.items()
                  if any(r["source_artifact_id"] in scenes for r in rows)}
    by_frame = {r["frame_id"]: r for rows in provenance.values() for r in rows}
    detections = collect_face_detections(root, provenance) if provenance else []
    nodes, edges = appearance._rows(conn, "nodes"), appearance._rows(conn, "edges")
    by_key = {(n["node_type"], n["name"]): n for n in nodes}
    owners = {n["id"]: n["name"] for n in nodes if n["node_type"] == "Person"}
    assigned = defaultdict(set)
    for edge in edges:
        if edge["edge_type"] == "person_appears_in_scene":
            for face in json.loads(edge["properties"] or "{}").get("evidence_face_ids", []):
                assigned[face].add(owners.get(edge["source_id"]))
    links, moments, verified_media, reusable = {}, set(), set(), []
    for record in selected:
        candidate = record["candidates"][0]
        corrected = record["id"] in corrections
        if corrected:
            # Only the observation's own saved pixels are needed; the rejected
            # reference is recorded, never used as identity evidence.
            pid, rid = corrections[record["id"]], candidate["reference_id"]
            if record["id"] not in verified_media:
                matching.media_file(cfg, report["id"], record["id"])
                verified_media.add(record["id"])
        else:
            pid, rid = candidate.get("person_id"), candidate["reference_id"]
            ref = refs.get(rid)
            if pid not in people or not ref or ref.get("person_id") != pid or ref["media"]["kind"] != "image":
                raise appearance.AppearanceConflict("The selected face has no consistent named reference.")
            for ident in (record["id"], rid):
                if ident not in verified_media:
                    matching.media_file(cfg, report["id"], ident)
                    verified_media.add(ident)
            # Revalidate reference promotion/retirement as well as its saved pixels.
            source = next((s for s in report["reference_sources"] if Path(s["epoch_root"]).name == ref["epoch_id"]), None)
            if source is None:
                raise appearance.AppearanceConflict("The named reference has no configured source authority.")
            ref_root = Path(source["epoch_root"])
            ref_rows = load_face_ucf_provenance(ref_root / "ucf/ucf_ledger.db")
            ref_frame = int(ref["observation_id"].split("_", 1)[0])
            authority = [r for rows in ref_rows.values() for r in rows if r["frame_id"] == ref_frame]
            if len(authority) != 1 or authority[0]["source_artifact_id"] in retired_identity_scene_ids(ref_root / "ucf/ucf_ledger.db"):
                raise appearance.AppearanceConflict("The named reference is no longer active promoted evidence.")
        media = record["media"]
        matches = [d for d in detections if Path(d["image_path"]).resolve() == Path(media["path"]).resolve()
                   and d["bbox"] == media["bbox"] and abs(d["t_start"] - media["timestamp"]) < 1e-6
                   and d["video_hash"] == report["video_hash"]
                   and by_frame[d["frame_id"]]["source_artifact_id"] == record["scene_id"]]
        if len(matches) != 1:
            raise appearance.AppearanceConflict("A selected face does not resolve to one exact promoted observation.")
        detection = matches[0]
        scene = by_key.get(("scene", record["scene_id"]))
        if not scene or detection["frame_id"] not in json.loads(scene["properties"] or "{}").get("ucf_provenance", []):
            raise appearance.AppearanceConflict("The selected face is not linked to its saved scene authority.")
        video_nodes = [n for n in nodes if n["node_type"] == "video" and any(
            e["source_id"] == n["id"] and e["target_id"] == scene["id"] and e["edge_type"] == "video_contains_scene" for e in edges)]
        if len(video_nodes) != 1 or video_nodes[0]["name"] != report["video_id"]:
            raise appearance.AppearanceConflict("The selected scene is not bound to the comparison movie.")
        moment = (pid, record["scene_id"], media["timestamp"])
        if moment in moments or assigned[detection["detection_id"]] - {pid}:
            raise appearance.AppearanceConflict("Selected observations conflict with another face or saved identity. Leave them on hold.")
        moments.add(moment)
        key = (pid, record["scene_id"])
        link = links.setdefault(key, {"person_id": pid, "display_name": people[pid], "scene_id": record["scene_id"],
            "scene_start": record["scene_start"], "scene_end": record["scene_end"], "evidence": []})
        if corrected:
            link["evidence"].append({"report_id": report["id"], "evidence_id": record["id"],
                "target_face_id": detection["detection_id"], "timestamp": media["timestamp"],
                "machine_status": record["status"], "assignment": "human_corrected",
                "rejected_person_id": candidate.get("person_id"), "rejected_reference_id": rid})
        else:
            link["evidence"].append({"report_id": report["id"], "evidence_id": record["id"], "reference_id": rid,
                "target_face_id": detection["detection_id"], "timestamp": media["timestamp"],
                "machine_status": record["status"], "similarity": candidate["similarity"]})
        if review.get("reuse_confirmed_faces"):
            spec = {"person_id": pid, "display_name": people[pid], "scene_id": record["scene_id"],
                "report_id": report["id"], "report_sha256": report["content_sha256"], "evidence_id": record["id"],
                "target_face_id": detection["detection_id"], "video_hash": detection["video_hash"],
                "media_sha256": media["sha256"], "bbox": media["bbox"], "timestamp": media["timestamp"],
                "space": detection["engine"], "embedding_sha256": digest(detection["embedding"])}
            if corrected:
                spec["assignment"] = "human_corrected"
            reusable.append(spec)
    node_specs, edge_specs, updates = [], [], []
    for pid in sorted({pid for pid, _ in links}):
        old = by_key.get(("Person", pid))
        if old and json.loads(old["properties"] or "{}").get("display_name") != people[pid]:
            raise appearance.AppearanceConflict("The destination person has different saved facts; they will not be overwritten.")
        node_specs.append({"node_type": "Person", "name": pid,
                           "properties": json.loads(old["properties"] or "{}") if old else {"display_name": people[pid]}})
    for (pid, sid), link in sorted(links.items()):
        person, scene = by_key.get(("Person", pid)), by_key[("scene", sid)]
        old = next((e for e in edges if person and e["source_id"] == person["id"] and e["target_id"] == scene["id"]
                    and e["edge_type"] == "person_appears_in_scene"), None)
        props = json.loads(old["properties"] or "{}") if old else {"confidence": "human_confirmed", "via_face_clusters": []}
        props["evidence_face_ids"] = sorted(set(props.get("evidence_face_ids", [])) | {e["target_face_id"] for e in link["evidence"]})
        reviews = {(r["report_id"], r["evidence_id"]): r for r in props.get("reviewed_matches", [])}
        reviews.update({(r["report_id"], r["evidence_id"]): r for r in link["evidence"]})
        props["reviewed_matches"] = [reviews[key] for key in sorted(reviews)]
        edge_specs.append({"source": ["Person", pid], "target": ["scene", sid], "edge_type": "person_appears_in_scene",
                           "weight": old["weight"] if old else 1.0, "properties": props, "existing": bool(old)})
        if old and json.loads(old["properties"] or "{}") != props:
            updates.append({"before": old, "properties": props})
    plan = {"version": 1, "epoch_id": epoch, "scope": "reviewed_face_appearances", "status": "preview",
        "review": review, "appearances": list(links.values()), "nodes": node_specs, "edges": edge_specs, "updates": updates,
        "summary": {"people": len(node_specs), "observations": len(selected), "appearances": len(links),
                    "scenes": len(scenes), "groups": 0, "new_nodes": sum(("Person", n["name"]) not in by_key for n in node_specs),
                    "new_edges": sum(not e["existing"] for e in edge_specs), "updated_edges": len(updates),
                    "existing_edges": sum(e["existing"] for e in edge_specs)},
        "held": {"faces": sum(r["modality"] == "face" for r in report["records"]) - len(selected),
                 "voice_links": "all", "transcript_mentions": "all"}}
    if decisions is not None:
        counts = Counter(decisions.values())
        plan["summary"]["decisions"] = {state: counts[state] for state in ("correct", "incorrect", "unsure", "not_accepted")}
        plan["summary"]["unreviewed"] = sum(r["modality"] == "face" for r in records.values()) - len(decisions)
        plan["summary"]["reusable_faces"] = len(reusable)
        plan["summary"]["corrected"] = len(corrections)
        prior = next((r for r in appearance._history(conn) if r["status"] == "applied"
                      and r.get("review", {}).get("report_id") == report["id"]), None)
        # Each receipt retains the whole reviewed batch, including explicit negatives
        # and uncertain/legacy outcomes. They never produce identity edges or examples.
        plan["review_changed"] = not prior or prior["review"] != review
        plan["previous_review"] = prior["id"] if prior else None
        plan["reference_faces"] = reusable
    plan["plan_sha256"] = appearance._digest({"plan": plan, "scope": appearance.scope(cfg), "nodes": nodes, "edges": edges})
    return plan


def preview(cfg, review):
    with appearance._connection(cfg) as conn:
        plan = build(cfg, conn, review)
        return {key: value for key, value in plan.items() if key not in {"nodes", "edges", "updates"}}
