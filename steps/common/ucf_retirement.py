"""Shared UCF retirement parsing and transactional producer admission."""
import hashlib
import json
import math


def _read_scene_retirements(conn, *, video_hash, epoch_id=None):
    """Read exact scene exclusions from the existing immutable transition audit."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ucf_status_transitions'").fetchone():
        return []
    query = ("SELECT epoch_id,scope,evidence,frame_ids FROM ucf_status_transitions "
             "WHERE video_hash=? AND scope LIKE 'scene_retirement:%'")
    args = [video_hash]
    if epoch_id is not None:
        query += " AND epoch_id=?"
        args.append(epoch_id)
    result = {}
    for epoch, scope, raw, raw_ids in conn.execute(query, args):
        try:
            evidence = json.loads(raw)
            sid = evidence["scene_id"]
            aliases = evidence["aliases"]
            ids = evidence["frame_ids"]
            valid = (
                evidence["kind"] == "scene_retirement" and evidence["version"] == 1
                and evidence["video_hash"] == video_hash and evidence["epoch_id"] == epoch
                and isinstance(sid, str) and bool(sid) and scope == f"scene_retirement:{sid}"
                and isinstance(aliases, list) and sid in aliases
                and all(isinstance(alias, str) and alias for alias in aliases)
                and isinstance(ids, list) and bool(ids)
                and all(type(fid) is int and fid > 0 for fid in ids)
                and sorted(ids) == sorted(json.loads(raw_ids))
                and all(type(evidence[k]) in (int, float) and math.isfinite(evidence[k]) for k in ("start", "end"))
                and 0 <= evidence["start"] <= evidence["end"]
                and isinstance(evidence["vectors"], list)
                and all(isinstance(v, dict) and isinstance(v.get("key"), str) and v["key"]
                        and ((isinstance(v.get("collection"), str) and v["collection"])
                             or (v.get("backend") == "faiss" and v.get("collection") is None))
                        and v.get("backend") in {"qdrant", "faiss"} and type(v.get("shared")) is bool
                        and (not v["shared"] or (isinstance(v.get("shared_with"), list) and bool(v["shared_with"])
                             and all(isinstance(owner, dict) and type(owner.get("frame_id")) is int
                                     and all(isinstance(owner.get(k), str) and owner[k] for k in ("video_hash", "epoch_id", "source_artifact_id"))
                                     for owner in v["shared_with"])))
                        for v in evidence["vectors"])
            )
            if valid:
                expected_id = hashlib.sha256(
                    f"scene{video_hash}|{evidence['start']:.3f}|{evidence['end']:.3f}|".encode()
                ).hexdigest()
                valid = sid == expected_id and len(ids) == len(set(ids)) and len(aliases) == len(set(aliases))
            if not valid:
                raise ValueError("invalid fields")
            key = (epoch, sid)
            if key in result and result[key] != evidence:
                raise ValueError("conflicting immutable scene evidence")
            result[key] = evidence
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Corrupt scene retirement evidence for {video_hash}/{epoch}") from exc
    return list(result.values())


def assert_scene_write_allowed(conn, *, video_hash, epoch_id, source_artifact_id,
                               payload=None, conflict_frame_id=None):
    """Check replay admission inside the caller's active write transaction."""
    if not conn.in_transaction:
        raise RuntimeError("Scene admission requires an active write transaction")
    for exclusion in _read_scene_retirements(conn, video_hash=video_hash, epoch_id=epoch_id):
        if (source_artifact_id in exclusion["aliases"]
                or (payload or {}).get("scene_id") in exclusion["aliases"]
                or conflict_frame_id in exclusion["frame_ids"]):
            raise ValueError(
                f"Scene {exclusion['scene_id']} is retired in epoch {epoch_id}; replay is not restoration"
            )
