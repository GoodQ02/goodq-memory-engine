"""
GoodQ4All — Phase 4: Roster Validator
======================================
Validates family_roster.yaml against face_clusters.json and
speaker_clusters.json before any KG promotion is attempted.

Must exit 0 before promote_identity_layer.py will run.

Usage:
    conda run -n goodq_core python scripts/identity/validate_roster.py \\
        [--data-path L:/_DATA/GoodQ_Data/identity]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_DATA_PATH = "L:/_DATA/GoodQ_Data/identity"


def _load_yaml(path: Path) -> dict:
    """Load YAML with PyYAML or minimal fallback."""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        import re
        # Very minimal — just confirms it's parseable; full validation uses JSON manifests
        with open(path, encoding="utf-8") as f:
            content = f.read()
        log.warning("PyYAML not installed — using minimal roster reader. Install PyYAML for full validation.")
        return {"_raw": content, "identities": []}


def _load_json(path: Path, name: str) -> dict | None:
    if not path.exists():
        log.warning("%s not found at %s — skipping that validation pass", name, path)
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(data_path: Path) -> bool:
    """
    Runs all validation checks. Returns True if all pass, False on any failure.
    """
    roster_path        = data_path / "family_roster.yaml"
    face_manifest_path = data_path / "face_clusters.json"
    spk_manifest_path  = data_path / "speaker_clusters.json"

    errors   = []
    warnings = []
    passed   = []

    # ── 1. Roster exists ──────────────────────────────────────────────────────
    if not roster_path.exists():
        log.error("family_roster.yaml not found at %s", roster_path)
        log.error("Copy configs/identity/family_roster.template.yaml, populate it, and place it here.")
        return False

    roster = _load_yaml(roster_path)
    identities = roster.get("identities", [])
    if not identities:
        errors.append("family_roster.yaml has no identities defined.")
    else:
        passed.append(f"Roster loaded: {len(identities)} identities")

    # ── 2. No duplicate IDs ───────────────────────────────────────────────────
    ids_seen: set[str] = set()
    for identity in identities:
        iid = identity.get("id", "")
        if iid in ids_seen:
            errors.append(f"Duplicate identity id: '{iid}'")
        ids_seen.add(iid)
    if not errors:
        passed.append("No duplicate identity IDs")

    # ── 3. Face cluster cross-reference ──────────────────────────────────────
    face_manifest = _load_json(face_manifest_path, "face_clusters.json")
    if face_manifest:
        known_face_clusters = {c["cluster_id"] for c in face_manifest.get("clusters", [])}
        claimed_face_clusters: set[str] = set()
        for identity in identities:
            for fc_id in (identity.get("face_cluster_ids") or []):
                if fc_id not in known_face_clusters:
                    errors.append(
                        f"Identity '{identity.get('id')}' references unknown face cluster '{fc_id}'"
                    )
                if fc_id in claimed_face_clusters:
                    errors.append(
                        f"Face cluster '{fc_id}' is assigned to multiple identities — conflict"
                    )
                claimed_face_clusters.add(fc_id)

        # Check that referenced clusters are labeled (not null)
        labeled_clusters = {
            c["cluster_id"] for c in face_manifest.get("clusters", [])
            if c.get("label") is not None
        }
        for identity in identities:
            for fc_id in (identity.get("face_cluster_ids") or []):
                if fc_id not in labeled_clusters:
                    warnings.append(
                        f"Face cluster '{fc_id}' used by '{identity.get('id')}' "
                        f"has label=null in face_clusters.json — set label there for traceability"
                    )

        total_face_detections = sum(
            c["face_count"] for c in face_manifest.get("clusters", [])
        )
        linked_detections = sum(
            c["face_count"]
            for c in face_manifest.get("clusters", [])
            if c["cluster_id"] in claimed_face_clusters
        )
        coverage = (linked_detections / total_face_detections * 100) if total_face_detections else 0
        passed.append(
            f"Face coverage: {linked_detections}/{total_face_detections} detections "
            f"({coverage:.1f}%) identity-linked"
        )

    # ── 4. Speaker cluster cross-reference ────────────────────────────────────
    spk_manifest = _load_json(spk_manifest_path, "speaker_clusters.json")
    if spk_manifest:
        known_spk_clusters = {c["cluster_id"] for c in spk_manifest.get("clusters", [])}
        claimed_spk_clusters: set[str] = set()
        for identity in identities:
            for sc_id in (identity.get("speaker_cluster_ids") or []):
                if sc_id not in known_spk_clusters:
                    errors.append(
                        f"Identity '{identity.get('id')}' references unknown speaker cluster '{sc_id}'"
                    )
                if sc_id in claimed_spk_clusters:
                    errors.append(
                        f"Speaker cluster '{sc_id}' assigned to multiple identities — conflict"
                    )
                claimed_spk_clusters.add(sc_id)

        # All referenced speaker clusters must have confirmed=True (hypothesis hard gate)
        for identity in identities:
            for sc_id in (identity.get("speaker_cluster_ids") or []):
                cluster_info = next(
                    (c for c in spk_manifest.get("clusters", []) if c["cluster_id"] == sc_id),
                    None,
                )
                if cluster_info and not cluster_info.get("confirmed", False):
                    errors.append(
                        f"Speaker cluster '{sc_id}' (used by '{identity.get('id')}') "
                        f"has confirmed=false — speaker clusters MUST be manually confirmed "
                        f"before identity promotion. Set confirmed=true in the roster only "
                        f"after you are certain of the mapping."
                    )

    # ── 5. Display names present ──────────────────────────────────────────────
    for identity in identities:
        if not identity.get("display_name"):
            warnings.append(f"Identity '{identity.get('id')}' has no display_name")

    # ── Report ────────────────────────────────────────────────────────────────
    log.info("=== Roster Validation Report ===")
    for msg in passed:
        log.info("  ✓ %s", msg)
    for msg in warnings:
        log.warning("  ⚠ %s", msg)
    for msg in errors:
        log.error("  ✗ %s", msg)

    if errors:
        log.error("Validation FAILED — %d error(s). Fix the roster before running Phase 5A.", len(errors))
        return False

    log.info("Validation PASSED — roster is consistent. Ready for Phase 5A dry-run.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GoodQ4All Phase 4: Roster Validator"
    )
    parser.add_argument("--data-path", default=DEFAULT_DATA_PATH)
    args = parser.parse_args()
    ok = validate(Path(args.data_path))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
