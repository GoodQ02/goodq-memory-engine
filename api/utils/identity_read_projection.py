"""Read-only projections that bind identity artifacts to one epoch authority."""
from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from contextlib import closing
import yaml

from api.utils.media_projection import frame_endpoint
from steps.common.platform_config import PlatformHelper


_IDENTITY_ARTIFACTS = {
    "face_clusters": "face_clusters.json",
    "speaker_clusters": "speaker_clusters.json",
    "name_mentions": "name_mentions.json",
}


def identity_data_path(cfg: Mapping[str, Any]) -> Path:
    roster_path = (cfg.get("identity_search") or {}).get("roster_path")
    env_path = os.environ.get("GOODQ_IDENTITY_PATH")
    if roster_path:
        return Path(str(roster_path)).parent
    if env_path:
        path = Path(env_path)
        return path.parent if path.suffix.lower() in {".yaml", ".yml", ".json"} else path
    return PlatformHelper.get_data_root() / "GoodQ_Data" / "identity"


def configured_epoch_id(cfg: Mapping[str, Any]) -> str | None:
    explicit = str(cfg.get("epoch_id") or "").strip()
    if explicit:
        return explicit
    db_path = str((cfg.get("paths") or {}).get("db_path") or "").strip()
    return Path(db_path).parent.name if db_path else None


def _artifact_epoch(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    epoch_id = payload.get("epoch_id") if isinstance(payload, dict) else None
    return str(epoch_id).strip() if epoch_id else None


def epoch_authority_projection(
    cfg: Mapping[str, Any],
    identity_root: Path | None = None,
) -> dict[str, Any]:
    root = identity_root or identity_data_path(cfg)
    configured = configured_epoch_id(cfg)
    artifact_epochs = {
        name: epoch
        for name, filename in _IDENTITY_ARTIFACTS.items()
        if (epoch := _artifact_epoch(root / filename))
    }
    distinct = sorted(set(artifact_epochs.values()))
    identity_epoch = distinct[0] if len(distinct) == 1 else None

    if len(artifact_epochs) != len(_IDENTITY_ARTIFACTS):
        state = "identity_artifacts_missing"
        message = "Identity artifacts are incomplete or do not declare an epoch."
    elif len(distinct) != 1:
        state = "identity_artifacts_conflict"
        message = "Identity artifacts declare conflicting epochs."
    elif not configured:
        state = "configured_epoch_missing"
        message = "The configured runtime does not declare an epoch."
    elif identity_epoch != configured:
        state = "epoch_mismatch"
        message = "Identity artifacts do not match the configured epoch."
    else:
        state = "ready"
        message = "Identity artifacts match the configured epoch."

    return {
        "configured_epoch_id": configured,
        "identity_epoch_id": identity_epoch,
        "identity_epoch_ids": artifact_epochs,
        "state": state,
        "ready": state == "ready",
        "message": message,
    }


def _epoch_root(cfg: Mapping[str, Any]) -> Path | None:
    db_path = str((cfg.get("paths") or {}).get("db_path") or "").strip()
    return Path(db_path).parent if db_path else None


def _context_frame(epoch_root: Path, frame_id: int) -> tuple[Path, float] | None:
    ledger = epoch_root / "ucf" / "ucf_ledger.db"
    if not ledger.is_file():
        return None
    try:
        uri = f"{ledger.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            row = conn.execute(
                "SELECT raw_ref, t_start FROM context_frames WHERE frame_id = ? LIMIT 1",
                (frame_id,),
            ).fetchone()
    except (OSError, sqlite3.Error):
        return None
    if not row or not row[0]:
        return None
    try:
        return Path(str(row[0])), float(row[1])
    except (TypeError, ValueError):
        return None


def _representative_frame(
    epoch_root: Path,
    raw_ref: Path,
    timestamp: float,
) -> tuple[str, Path] | None:
    processing_root = (epoch_root / "processing").resolve()
    try:
        relative = raw_ref.resolve().relative_to(processing_root)
    except (OSError, ValueError):
        return None
    if not relative.parts:
        return None
    video_id = relative.parts[0]
    index_path = processing_root / video_id / "temporal_index.json"
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    segments = payload.get("segments", []) if isinstance(payload, dict) else payload
    if not isinstance(segments, list):
        return None
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        try:
            contains = float(segment["start"]) <= timestamp <= float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        frame = segment.get("representative_frame")
        if not contains or not frame:
            continue
        frame_path = Path(str(frame))
        try:
            frame_path.resolve().relative_to(processing_root)
        except (OSError, ValueError):
            return None
        if frame_path.is_file():
            return video_id, frame_path
    return None


def _face_evidence(raw_ref: Path, face_id: str, face_index: int) -> dict[str, Any]:
    try:
        faces = json.loads(raw_ref.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(faces, list) or face_index < 0 or face_index >= len(faces):
        return {}
    face = faces[face_index]
    bbox = face.get("bbox") if isinstance(face, dict) else None
    return {
        "target_face_id": face_id,
        "target_face_index": face_index,
        "source_face_count": len(faces),
        "bbox": bbox if isinstance(bbox, list) and len(bbox) == 4 else None,
    }


def _sampled_representative(epoch_root: Path, frame_id: int, face_index: int | None = None,
                            manifest_cache: dict | None = None) -> tuple[str, Path, float] | None:
    from lib.face_observation import resolve_sampled_face
    ledger = epoch_root / 'ucf/ucf_ledger.db'
    try:
        with sqlite3.connect(f'{ledger.resolve().as_uri()}?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT raw_ref,t_start,payload,payload_hash,video_hash,source_artifact_id,promotion_status "
                "FROM context_frames WHERE frame_id=? AND worker_name='face_embed' "
                "AND epoch_id=?", (frame_id, epoch_root.name),
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    record = dict(row)
    record['payload'] = json.loads(record['payload'])
    if 'observation_timestamp' in record['payload'] and record['promotion_status'] != 'promoted':
        raise ValueError('Face observation is not promoted')
    raw = Path(record['raw_ref'])
    sampled = resolve_sampled_face(epoch_root, raw, [record], manifest_cache=manifest_cache)
    if sampled is None:
        return None
    if face_index is not None:
        payload = record['payload']
        evidence = _face_evidence(raw, f'{frame_id}_{face_index}', face_index)
        if payload.get('face_index') != face_index or evidence.get('bbox') != [
            payload.get(key) for key in ('x1', 'y1', 'x2', 'y2')
        ]:
            raise ValueError('Face target disagrees with saved observation')
    video_id = raw.resolve().relative_to((epoch_root / 'processing').resolve()).parts[0]
    return video_id, sampled[0], sampled[1]


def _project_face_member(epoch_root: Path, face_id: str, manifest_cache: dict) -> tuple[dict | None, dict]:
    """Keep one entry per saved member, even when its exact evidence is unavailable."""
    member = {"target_face_id": face_id, "evidence_status": "unavailable",
              "reason": "saved_evidence_unavailable"}
    try:
        raw_frame_id, raw_face_index = face_id.split("_", 1)
        frame_id, face_index = int(raw_frame_id), int(raw_face_index)
        context = _context_frame(epoch_root, frame_id)
        if context is None:
            return None, member
        sampled = _sampled_representative(epoch_root, frame_id, face_index, manifest_cache)
        representative = sampled[:2] if sampled else _representative_frame(epoch_root, *context)
        if representative is None:
            return None, member
        endpoint = frame_endpoint(representative[0], str(representative[1]))
        if not endpoint:
            return None, member
        evidence = {"frame_url": endpoint,
                    **({'timestamp': sampled[2]} if sampled else {}),
                    **_face_evidence(context[0], face_id, face_index)}
        if sampled is None:
            # Preserve historical representative compatibility, but never put its
            # unrelated midpoint image inside a claimed exact target crop.
            return evidence, {**member, "reason": "exact_source_unavailable"}
        from PIL import Image

        with Image.open(representative[1]) as image:
            width, height = image.size
        bbox = evidence.get('bbox')
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(
            type(value) in (int, float) and math.isfinite(value) for value in bbox
        ):
            raise ValueError('Invalid face box')
        x1, y1, x2, y2 = bbox
        crop = [max(0, x1), max(0, y1), min(width, x2), min(height, y2)]
        if crop[2] <= crop[0] or crop[3] <= crop[1]:
            raise ValueError('Face box lies outside its source image')
        return evidence, {**evidence, "evidence_status": "available",
                          "image_width": width, "image_height": height, "crop_bbox": crop}
    except (ValueError, OSError, TypeError, KeyError):
        return None, member


def project_face_cluster_images(
    data: Mapping[str, Any],
    cfg: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    projected = dict(data)
    clusters = [dict(cluster) for cluster in data.get("clusters", []) if isinstance(cluster, dict)]
    projected["clusters"] = clusters
    if not authority.get("ready"):
        return projected
    epoch_root = _epoch_root(cfg)
    if epoch_root is None:
        return projected
    manifest_cache: dict = {}
    for cluster in clusters:
        face_ids = cluster.get("face_ids")
        if not isinstance(face_ids, list) or not face_ids:
            continue
        members = []
        for index, face_id in enumerate(face_ids):
            evidence, member = _project_face_member(epoch_root, str(face_id), manifest_cache)
            members.append(member)
            if index == 0 and evidence:
                cluster["representative_frames"] = [evidence]
        cluster["members"] = members
        cluster["members_available"] = sum(m["evidence_status"] == "available" for m in members)
        cluster["members_unavailable"] = len(members) - cluster["members_available"]
    _attach_cluster_suggestions(clusters, epoch_root, cfg)
    return projected


def _clean_aliases(raw_aliases: Any, display_name: str) -> list[str]:
    if not isinstance(raw_aliases, list):
        return []
    seen = {display_name.casefold()}
    cleaned: list[str] = []
    for item in raw_aliases:
        text = str(item or "").strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            cleaned.append(text)
    return cleaned


def known_people_projection(
    cfg: Mapping[str, Any],
    active_identities: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Return canonical saved people from active roster and configured prior films (read-only)."""
    by_id: dict[str, dict[str, Any]] = {}
    id_by_name: dict[str, str] = {}

    def _register(
        pid: Any,
        display_name: Any,
        *,
        aliases: Any = None,
        role: Any = None,
        in_active_roster: bool = False,
    ) -> None:
        pid_str = str(pid or "").strip()
        name_str = str(display_name or "").strip()
        if not pid_str or not name_str:
            return
        alias_list = _clean_aliases(aliases, name_str)
        role_str = str(role or "").strip()
        existing_id = pid_str if pid_str in by_id else id_by_name.get(name_str.casefold())
        if existing_id and existing_id in by_id:
            entry = by_id[existing_id]
            merged_aliases = _clean_aliases(
                [*(entry.get("aliases") or []), *alias_list],
                entry["display_name"],
            )
            entry["aliases"] = merged_aliases
            if not entry.get("role") and role_str:
                entry["role"] = role_str
            if in_active_roster:
                entry["in_active_roster"] = True
                entry["source"] = "active_roster"
            for alias in merged_aliases:
                id_by_name.setdefault(alias.casefold(), existing_id)
            return
        record = {
            "id": pid_str,
            "display_name": name_str,
            "aliases": alias_list,
            "role": role_str,
            "in_active_roster": in_active_roster,
            "source": "active_roster" if in_active_roster else "prior_films",
        }
        by_id[pid_str] = record
        id_by_name.setdefault(name_str.casefold(), pid_str)
        for alias in alias_list:
            id_by_name.setdefault(alias.casefold(), pid_str)

    if active_identities is None:
        roster_file = identity_data_path(cfg) / "family_roster.yaml"
        if roster_file.is_file():
            try:
                loaded = yaml.safe_load(roster_file.read_text(encoding="utf-8")) or {}
                active_identities = loaded.get("identities") if isinstance(loaded, dict) else []
            except (OSError, UnicodeError, yaml.YAMLError):
                active_identities = []

    for person in active_identities or []:
        if isinstance(person, dict):
            _register(
                person.get("id"),
                person.get("display_name") or person.get("name"),
                aliases=person.get("aliases"),
                role=person.get("role"),
                in_active_roster=True,
            )

    matching_cfg = cfg.get("identity_matching")
    options = matching_cfg if isinstance(matching_cfg, Mapping) else {}

    for source in options.get("reference_sources") or []:
        if not isinstance(source, Mapping) or not source.get("identity_path"):
            continue
        ref_roster = Path(str(source["identity_path"])) / "family_roster.yaml"
        if not ref_roster.is_file():
            continue
        try:
            loaded = yaml.safe_load(ref_roster.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError):
            continue
        identities = loaded.get("identities") if isinstance(loaded, dict) else []
        for person in identities or []:
            if isinstance(person, dict):
                _register(
                    person.get("id"),
                    person.get("display_name") or person.get("name"),
                    aliases=person.get("aliases"),
                    role=person.get("role"),
                    in_active_roster=False,
                )

    epoch_root = _epoch_root(cfg)
    if epoch_root is not None:
        reports_dir = epoch_root / "identity_matching" / "reports"
        if reports_dir.is_dir():
            for report_path in sorted(
                reports_dir.glob("*.json"),
                key=lambda path: (-path.stat().st_mtime_ns, path.stem),
            )[:1]:
                try:
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                if isinstance(report, dict):
                    for person in report.get("people") or []:
                        if isinstance(person, dict):
                            _register(
                                person.get("id"),
                                person.get("display_name"),
                                in_active_roster=False,
                            )

    try:
        from lib.identity_matching import reviewed_source_roots

        source_roots = sorted(reviewed_source_roots(dict(options)))
    except Exception:
        source_roots = []

    for root in source_roots:
        kg_path = Path(root) / "knowledge_graph.db"
        if not kg_path.is_file():
            continue
        try:
            with closing(sqlite3.connect(f"{kg_path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
                has_nodes = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='nodes'"
                ).fetchone()
                if not has_nodes:
                    continue
                for name, raw_props in conn.execute(
                    "SELECT name, properties FROM nodes WHERE node_type='Person'"
                ):
                    props = json.loads(raw_props or "{}") if raw_props else {}
                    if not isinstance(props, dict):
                        props = {}
                    _register(
                        name,
                        props.get("display_name") or name,
                        aliases=props.get("aliases"),
                        role=props.get("role"),
                        in_active_roster=False,
                    )
        except (OSError, sqlite3.Error, UnicodeError, json.JSONDecodeError):
            continue

    return sorted(by_id.values(), key=lambda item: (item["display_name"].casefold(), item["id"]))


def _unit_vec(vector: Any) -> list[float] | None:
    if not isinstance(vector, list) or not vector:
        return None
    try:
        vals = [float(x) for x in vector]
    except (TypeError, ValueError):
        return None
    if any(not math.isfinite(x) for x in vals):
        return None
    norm = math.sqrt(sum(x * x for x in vals))
    if not math.isfinite(norm) or norm <= 1e-8:
        return None
    return [x / norm for x in vals]


def _collect_reference_face_vectors(
    cfg: Mapping[str, Any],
    active_epoch_root: Path,
    active_clusters: list[dict[str, Any]],
    active_det_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], float]:
    """Gather unit-normalized reference face embeddings from prior films and active roster."""
    matching_cfg = cfg.get("identity_matching")
    options = dict(matching_cfg) if isinstance(matching_cfg, Mapping) else {}
    threshold = float(options.get("face_min_similarity", 0.60) or 0.60)
    refs: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    def _add_ref(
        person_id: Any,
        display_name: Any,
        space: Any,
        embedding: Any,
        *,
        source: str,
        origin_key: str,
        exclude_cluster_id: str | None = None,
    ) -> None:
        pid = str(person_id or "").strip()
        name = str(display_name or "").strip()
        space_str = str(space or "opencv-yunet-sface").strip().lower().replace("_", "-")
        vec = _unit_vec(embedding)
        if not pid or not name or vec is None:
            return
        dedup = (pid, source, origin_key)
        if dedup in seen_keys:
            return
        seen_keys.add(dedup)
        refs.append({
            "person_id": pid,
            "display_name": name,
            "space": space_str,
            "embedding": vec,
            "source": source,
            "exclude_cluster_id": exclude_cluster_id,
        })

    reports_dir = active_epoch_root / "identity_matching" / "reports"
    if reports_dir.is_dir():
        for report_path in sorted(
            reports_dir.glob("*.json"),
            key=lambda path: (-path.stat().st_mtime_ns, path.stem),
        )[:1]:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                report = None
            if isinstance(report, dict):
                policy_sim = (report.get("policy") or {}).get("face_similarity")
                if isinstance(policy_sim, (int, float)) and math.isfinite(policy_sim):
                    threshold = float(policy_sim)
                for ref in report.get("references") or []:
                    if not isinstance(ref, dict):
                        continue
                    if (ref.get("media") or {}).get("kind") != "image":
                        continue
                    _add_ref(
                        ref.get("person_id"),
                        ref.get("display_name"),
                        ref.get("space"),
                        ref.get("embedding"),
                        source="prior_films",
                        origin_key=f"{ref.get('epoch_id')}:{ref.get('observation_id') or ref.get('id')}",
                    )

    had_report_refs = bool(refs)
    ref_source_epochs = {
        Path(str(s.get("epoch_root") or "")).resolve()
        for s in (options.get("reference_sources") or [])
        if isinstance(s, Mapping) and s.get("epoch_root")
    }
    try:
        from api.utils.identity_cross_film import _load_epoch_detections, _read_epoch_kg_metadata
        from lib.identity_matching import reviewed_source_roots

        if not had_report_refs:
            for source in options.get("reference_sources") or []:
                if not isinstance(source, Mapping):
                    continue
                src_epoch = Path(str(source.get("epoch_root") or "")).resolve()
                src_ident = Path(str(source.get("identity_path") or "")).resolve()
                roster_file = src_ident / "family_roster.yaml"
                clusters_file = src_ident / "face_clusters.json"
                if not src_epoch.is_dir() or not roster_file.is_file() or not clusters_file.is_file():
                    continue
                roster_doc = yaml.safe_load(roster_file.read_text(encoding="utf-8")) or {}
                clusters_doc = json.loads(clusters_file.read_text(encoding="utf-8"))
                if clusters_doc.get("epoch_id") != src_epoch.name:
                    continue
                group_map = {
                    str(c.get("cluster_id")): c
                    for c in (clusters_doc.get("clusters") or [])
                    if isinstance(c, dict) and c.get("cluster_id")
                }
                src_dets, _ = _load_epoch_detections(src_epoch)
                src_det_by_id = {d["detection_id"]: d for d in src_dets}
                for person in (roster_doc.get("identities") if isinstance(roster_doc, dict) else []) or []:
                    if not isinstance(person, dict):
                        continue
                    pid, name = person.get("id"), person.get("display_name")
                    for group_id in person.get("face_cluster_ids") or []:
                        group = group_map.get(str(group_id))
                        face_ids = (group or {}).get("face_ids") or []
                        det = src_det_by_id.get(str(face_ids[0])) if face_ids else None
                        if det is not None:
                            _add_ref(
                                pid,
                                name,
                                det.get("engine"),
                                det.get("embedding"),
                                source="prior_films",
                                origin_key=f"{src_epoch.name}:{det['detection_id']}",
                            )

        for other_root in sorted(reviewed_source_roots(options)):
            resolved = Path(other_root).resolve()
            if resolved == active_epoch_root.resolve() or not resolved.is_dir():
                continue
            if had_report_refs and resolved in ref_source_epochs:
                continue
            meta = _read_epoch_kg_metadata(resolved)
            if not meta.get("person_faces"):
                continue
            other_dets, _ = _load_epoch_detections(resolved)
            other_det_by_id = {d["detection_id"]: d for d in other_dets}
            for pid, face_ids in meta["person_faces"].items():
                name = meta["person_names"].get(pid, pid)
                for fid in sorted(face_ids):
                    det = other_det_by_id.get(str(fid))
                    if det is not None:
                        _add_ref(
                            pid,
                            name,
                            det.get("engine"),
                            det.get("embedding"),
                            source="prior_films",
                            origin_key=f"{resolved.name}:{det['detection_id']}",
                        )
    except Exception:
        pass

    active_roster_file = identity_data_path(cfg) / "family_roster.yaml"
    if active_roster_file.is_file() and active_det_by_id:
        try:
            active_roster = yaml.safe_load(active_roster_file.read_text(encoding="utf-8")) or {}
            cluster_by_id = {
                str(c.get("cluster_id")): c
                for c in active_clusters
                if isinstance(c, dict) and c.get("cluster_id")
            }
            for person in (active_roster.get("identities") if isinstance(active_roster, dict) else []) or []:
                if not isinstance(person, dict):
                    continue
                pid, name = person.get("id"), person.get("display_name")
                for cid in person.get("face_cluster_ids") or []:
                    cid_str = str(cid)
                    cluster = cluster_by_id.get(cid_str)
                    face_ids = (cluster or {}).get("face_ids") or []
                    det = active_det_by_id.get(str(face_ids[0])) if face_ids else None
                    if det is not None:
                        _add_ref(
                            pid,
                            name,
                            det.get("engine"),
                            det.get("embedding"),
                            source="active_roster",
                            origin_key=f"{active_epoch_root.name}:{det['detection_id']}",
                            exclude_cluster_id=cid_str,
                        )
        except (OSError, UnicodeError, yaml.YAMLError):
            pass

    return refs, threshold


def _attach_cluster_suggestions(
    clusters: list[dict[str, Any]],
    epoch_root: Path,
    cfg: Mapping[str, Any],
) -> None:
    """Attach read-only top similarity suggestions from saved people onto each face cluster."""
    if not clusters:
        return
    try:
        from api.utils.identity_cross_film import _load_epoch_detections

        active_dets, _ = _load_epoch_detections(epoch_root)
    except Exception:
        return
    if not active_dets:
        return
    det_by_id = {d["detection_id"]: d for d in active_dets}
    refs, threshold = _collect_reference_face_vectors(cfg, epoch_root, clusters, det_by_id)
    if not refs:
        return

    for cluster in clusters:
        cluster["suggested_matches"] = []
        cid = str(cluster.get("cluster_id") or "")
        face_ids = cluster.get("face_ids")
        if not isinstance(face_ids, list) or not face_ids:
            continue
        member_vecs: list[tuple[str, list[float]]] = []
        for fid in face_ids:
            det = det_by_id.get(str(fid))
            if det is None:
                continue
            vec = _unit_vec(det.get("embedding"))
            if vec is not None:
                norm_space = str(det.get("engine") or "opencv-yunet-sface").strip().lower().replace("_", "-")
                member_vecs.append((norm_space, vec))
        if not member_vecs:
            continue

        by_person: dict[str, dict[str, Any]] = {}
        for ref in refs:
            if ref.get("exclude_cluster_id") and ref["exclude_cluster_id"] == cid:
                continue
            ref_space = ref["space"]
            ref_vec = ref["embedding"]
            best_sim = -1.0
            for m_space, m_vec in member_vecs:
                if m_space == ref_space and len(m_vec) == len(ref_vec):
                    sim = max(-1.0, min(1.0, sum(a * b for a, b in zip(m_vec, ref_vec))))
                    if sim > best_sim:
                        best_sim = sim
            if best_sim < 0.38:
                continue
            pid = ref["person_id"]
            existing = by_person.get(pid)
            if existing is None or best_sim > existing["similarity"]:
                by_person[pid] = {
                    "person_id": pid,
                    "display_name": ref["display_name"],
                    "similarity": best_sim,
                    "above_threshold": best_sim >= threshold,
                    "source": ref["source"],
                }

        if by_person:
            ranked = sorted(
                by_person.values(),
                key=lambda item: (-item["similarity"], item["display_name"].casefold(), item["person_id"]),
            )[:3]
            for item in ranked:
                item["similarity"] = round(float(item["similarity"]), 4)
            cluster["suggested_matches"] = ranked
