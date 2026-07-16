"""
GoodQ4All — Identity Workbench API Router
==========================================
Serves JSON for the identity_workbench UI:

  GET  /api/identity/face-clusters
  POST /api/identity/rebuild-face-clusters?eps=0.4
  POST /api/identity/face-clusters/label
  GET  /api/identity/speaker-clusters
  POST /api/identity/speaker-clusters/confirm
  GET  /api/identity/name-mentions
  GET  /api/identity/roster
  POST /api/identity/roster/save
  POST /api/identity/roster/validate
  POST /api/identity/roster/export

All routes are read-mostly. The only writes are:
  - face cluster labels (stored in face_clusters.json, no KG writes)
  - speaker cluster confirmations (stored in speaker_clusters.json, no KG writes)
  - roster saves (stored in family_roster.yaml, no KG writes)
  - roster export (writes family_roster.yaml to data path)

No KG mutations happen here. Mutations are Phase 5A (promote_identity_layer.py),
which requires a separate confirmed CLI flow.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from steps.common.config_loader import load_configs

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/identity", tags=["identity"])

_CFG = load_configs({})

# ── Data path resolution ────────────────────────────────────────────────────

def _identity_data_path() -> Path:
    """Returns the identity data path from config or env."""
    cfg_path = (
        _CFG.get("identity_search", {}).get("roster_path")
        or os.environ.get("GOODQ_IDENTITY_PATH")
    )
    if cfg_path:
        return Path(cfg_path).parent
    return Path(os.environ.get("GOODQ_DATA_ROOT", "L:/_DATA")) / "GoodQ_Data" / "identity"


def _data_path() -> Path:
    p = _identity_data_path()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _epoch_id() -> str:
    """Returns the active epoch ID from config."""
    return _CFG.get("epoch_id", "") or ""


def _load_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json_file(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Face Clusters ───────────────────────────────────────────────────────────

@router.get("/face-clusters")
async def get_face_clusters() -> dict:
    """Returns face_clusters.json from the identity data path."""
    path = _data_path() / "face_clusters.json"
    data = _load_json_file(path)
    if data is None:
        return {"clusters": [], "message": "face_clusters.json not found. Run Phase 1."}
    return data


@router.post("/rebuild-face-clusters")
async def rebuild_face_clusters(eps: float = Query(0.4, ge=0.05, le=0.95)) -> dict:
    """
    Triggers a re-run of build_face_clusters.py with the given eps.
    Blocking — may take ~30s for large datasets.
    """
    epoch_id = _epoch_id()
    if not epoch_id:
        raise HTTPException(status_code=400, detail="epoch_id not set in config.")

    script = Path(__file__).resolve().parents[2] / "scripts" / "identity" / "build_face_clusters.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail="build_face_clusters.py not found.")

    result = subprocess.run(
        [sys.executable, str(script), "--epoch-id", epoch_id, "--eps", str(eps)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        log.error("build_face_clusters.py failed: %s", result.stderr)
        raise HTTPException(status_code=500, detail=result.stderr[-400:])

    # Reload and return the updated manifest
    path = _data_path() / "face_clusters.json"
    data = _load_json_file(path)
    return data or {"clusters": []}


class FaceClusterLabelRequest(BaseModel):
    cluster_id: str
    label: str
    operator_note: str = ""


@router.post("/face-clusters/label")
async def label_face_cluster(req: FaceClusterLabelRequest) -> dict:
    """Writes a label onto a cluster in face_clusters.json."""
    path = _data_path() / "face_clusters.json"
    data = _load_json_file(path)
    if not data or not isinstance(data.get("clusters"), list):
        raise HTTPException(status_code=404, detail="face_clusters.json not found or empty.")

    updated = False
    for cluster in data["clusters"]:
        if cluster["cluster_id"] == req.cluster_id:
            cluster["label"] = req.label
            cluster["operator_note"] = req.operator_note
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Cluster '{req.cluster_id}' not found.")

    _save_json_file(path, data)
    log.info("Face cluster %s labeled → %s", req.cluster_id, req.label)
    return {"ok": True, "cluster_id": req.cluster_id, "label": req.label}


# ── Speaker Clusters ─────────────────────────────────────────────────────────

@router.get("/speaker-clusters")
async def get_speaker_clusters() -> dict:
    path = _data_path() / "speaker_clusters.json"
    data = _load_json_file(path)
    if data is None:
        return {"clusters": [], "message": "speaker_clusters.json not found. Run Phase 2."}
    return data


class SpeakerConfirmRequest(BaseModel):
    cluster_id: str
    confirmed: bool
    identity_label: Optional[str] = None


@router.post("/speaker-clusters/confirm")
async def confirm_speaker_cluster(req: SpeakerConfirmRequest) -> dict:
    """Persists a speaker cluster confirmation + optional identity label."""
    path = _data_path() / "speaker_clusters.json"
    data = _load_json_file(path)
    if not data or not isinstance(data.get("clusters"), list):
        raise HTTPException(status_code=404, detail="speaker_clusters.json not found.")

    updated = False
    for cluster in data["clusters"]:
        if cluster["cluster_id"] == req.cluster_id:
            cluster["confirmed"] = req.confirmed
            if req.identity_label is not None:
                cluster["identity_label"] = req.identity_label
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Speaker cluster '{req.cluster_id}' not found.")

    _save_json_file(path, data)
    return {"ok": True, "cluster_id": req.cluster_id, "confirmed": req.confirmed}


# ── Name Mentions ─────────────────────────────────────────────────────────────

@router.get("/name-mentions")
async def get_name_mentions() -> dict:
    path = _data_path() / "name_mentions.json"
    data = _load_json_file(path)
    if data is None:
        return {"mentions": {}, "message": "name_mentions.json not found. Run Phase 3."}
    return data


# ── Roster ────────────────────────────────────────────────────────────────────

@router.get("/roster")
async def get_roster() -> dict:
    """Reads family_roster.yaml and returns as JSON."""
    roster_path = _data_path() / "family_roster.yaml"
    if not roster_path.exists():
        return {"identities": [], "message": "family_roster.yaml not found. Use the UI to create it."}
    try:
        import yaml
        with open(roster_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {"identities": data.get("identities", [])}
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed in the active environment.")


class RosterSaveRequest(BaseModel):
    identity: dict


@router.post("/roster/save")
async def save_roster_identity(req: RosterSaveRequest) -> dict:
    """
    Upserts a single identity into family_roster.yaml by id.
    Creates the file if it doesn't exist.
    """
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed.")

    roster_path = _data_path() / "family_roster.yaml"
    if roster_path.exists():
        with open(roster_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    identities: list = data.get("identities") or []
    identity_id = req.identity.get("id", "")
    found = False
    for i, existing in enumerate(identities):
        if existing.get("id") == identity_id:
            identities[i] = req.identity
            found = True
            break
    if not found:
        identities.append(req.identity)

    data["identities"] = identities
    with open(roster_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return {"ok": True, "id": identity_id}


@router.post("/roster/validate")
async def validate_roster() -> dict:
    """Runs validate_roster.py and returns structured results."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "identity" / "validate_roster.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail="validate_roster.py not found.")

    data_path = str(_data_path())
    result = subprocess.run(
        [sys.executable, str(script), "--data-path", data_path],
        capture_output=True, text=True, timeout=30,
    )

    passed = []
    warnings = []
    errors = []
    all_output = (result.stdout or "") + (result.stderr or "")
    for line in all_output.splitlines():
        if " ✓ " in line:
            passed.append(line.split(" ✓ ", 1)[-1].strip())
        elif " ⚠ " in line:
            warnings.append(line.split(" ⚠ ", 1)[-1].strip())
        elif " ✗ " in line:
            errors.append(line.split(" ✗ ", 1)[-1].strip())
        elif "[ERROR]" in line and "error" in line.lower():
            errors.append(line.strip())

    return {
        "ok": result.returncode == 0,
        "passed": passed,
        "warnings": warnings,
        "errors": errors,
        "raw": all_output[-1000:],
    }


class RosterExportRequest(BaseModel):
    identities: list


@router.post("/roster/export")
async def export_roster(req: RosterExportRequest) -> dict:
    """Writes the full roster as family_roster.yaml to the data path."""
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="PyYAML not installed.")

    roster_path = _data_path() / "family_roster.yaml"
    data = {"identities": req.identities}
    with open(roster_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    log.info("Roster exported: %d identities → %s", len(req.identities), roster_path)
    return {"ok": True, "path": str(roster_path), "count": len(req.identities)}
