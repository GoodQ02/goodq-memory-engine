"""Action-specific availability of saved identity evidence; never prepares it."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from api.utils.identity_read_projection import configured_epoch_id, identity_data_path


def artifact_readiness(cfg: Mapping[str, Any], filename: str) -> dict[str, Any]:
    """Check only the artifact used by this action, including its epoch binding."""
    path = identity_data_path(cfg) / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"ready": False, "reason": "artifact_missing", "message": "Review data has not been prepared."}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"ready": False, "reason": "artifact_invalid", "message": "Review data could not be read."}
    key, kind = ("mentions", dict) if filename == "name_mentions.json" else ("clusters", list)
    if not isinstance(data, dict) or not isinstance(data.get(key), kind):
        return {"ready": False, "reason": "artifact_invalid", "message": "Review data has an invalid format."}
    if kind is list and any(not isinstance(c, dict) or not isinstance(c.get("cluster_id"), str) or not c["cluster_id"] for c in data[key]):
        return {"ready": False, "reason": "artifact_invalid", "message": "Review data has invalid candidates."}
    if kind is list and len({c["cluster_id"] for c in data[key]}) != len(data[key]):
        return {"ready": False, "reason": "artifact_invalid", "message": "Review data has duplicate candidates."}
    epoch = configured_epoch_id(cfg)
    if not epoch or data.get("epoch_id") != epoch:
        return {"ready": False, "reason": "epoch_mismatch", "message": "Review data is not bound to the active movie epoch."}
    return {"ready": True, "reason": "ready", "count": len(data[key]), "message": "Review data is available for this epoch."}


def _saved_rows(path: Path | None, query: str, args: tuple = ()) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"ready": False, "reason": "store_missing", "message": "The saved evidence store is unavailable."}
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            count = conn.execute(query, args).fetchone()[0]
    except (OSError, sqlite3.Error):
        return {"ready": False, "reason": "store_unreadable", "message": "The saved evidence store could not be read."}
    return {"ready": bool(count), "reason": "ready" if count else "evidence_missing", "count": count,
            "message": "Saved evidence is available." if count else "No applicable saved evidence is present."}


def identity_readiness_projection(cfg: Mapping[str, Any]) -> dict[str, Any]:
    epoch = configured_epoch_id(cfg)
    paths = cfg.get("paths") or {}
    db_path = paths.get("db_path")
    root = Path(db_path).resolve().parent if db_path else None
    bound = bool(epoch and root and root.name == epoch)
    unavailable = {"ready": False, "reason": "epoch_path_invalid", "message": "The active epoch store is not configured consistently."}
    roster = {"ready": True, "reason": "ready", "message": "Family facts can be edited independently of face and voice evidence."}
    roster_path = identity_data_path(cfg) / "family_roster.yaml"
    if roster_path.exists():
        import yaml

        try:
            data = yaml.safe_load(roster_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("identities"), list):
                raise ValueError("Invalid roster")
            if any(not isinstance(i, dict) or not i.get("id") for i in data["identities"]):
                raise ValueError("Invalid identity")
        except (OSError, UnicodeError, ValueError, yaml.YAMLError):
            roster = {"ready": False, "reason": "roster_invalid", "message": "The existing family roster could not be read safely."}
    faces = unavailable
    if bound:
        faces = _saved_rows(
            root / "ucf/ucf_ledger.db",
            "SELECT COUNT(*) FROM context_frames WHERE worker_name='face_embed' "
            "AND promotion_status='promoted' AND epoch_id=?",
            (epoch,),
        )
    face_artifact = artifact_readiness(cfg, "face_clusters.json")
    # Preparing candidates must not overwrite unreadable or foreign-epoch evidence.
    if face_artifact["reason"] not in {"ready", "artifact_missing"}:
        faces = face_artifact
    kg_path = Path(paths["knowledge_graph_db"]).resolve() if paths.get("knowledge_graph_db") else None
    voices = unavailable
    if bound and kg_path and kg_path.parent == root:
        voices = _saved_rows(kg_path, "SELECT COUNT(*) FROM nodes WHERE node_type='speaker_pattern'")
    return {"configured_epoch_id": epoch, "actions": {
        "family_facts": roster,
        "face_prepare": faces,
        "face_review": face_artifact,
        "speaker_review": artifact_readiness(cfg, "speaker_clusters.json"),
        "name_review": artifact_readiness(cfg, "name_mentions.json"),
        "voice_review": voices,
    }}
