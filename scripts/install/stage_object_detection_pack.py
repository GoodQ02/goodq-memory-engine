"""Stage only verified OpenCV Zoo object-detection capability assets.

The installer compiler reads immutable source snapshots through this boundary;
it never downloads model weights and never accepts an unsealed cache copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.assets.personal_asset_vault import evaluate_pack_admission, verify_snapshot


class PackStageError(RuntimeError):
    """Raised when an object-detection asset is not safe to package."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _snapshot_for(vault_root: Path, asset_id: str, revision: str) -> Path:
    candidates = sorted((vault_root / asset_id).glob(f"{revision}-*"))
    if len(candidates) != 1:
        raise PackStageError(f"{asset_id} requires exactly one sealed snapshot for {revision}")
    return candidates[0]


def stage_pack(*, vault_root: Path, staging_root: Path) -> dict[str, Any]:
    """Materialize the two sealed OpenCV packs into a fresh staging root."""

    catalog = _read_yaml(REPO_ROOT / "configs" / "offline_asset_catalog.yaml")
    registry = _read_yaml(REPO_ROOT / "configs" / "model_registry.yaml").get("external_models", {})
    manifest = _read_json(REPO_ROOT / "configs" / "model_download_manifest.json")
    packs = manifest.get("model_packs", {})
    if set(packs) != {"object_detection_cpu", "object_detection_gpu"}:
        raise PackStageError("model manifest must declare exactly the sealed object-detection packs")

    if staging_root.exists():
        shutil.rmtree(staging_root)
    staged: list[dict[str, Any]] = []
    for pack_id, expected_asset_id in (("object_detection_cpu", "opencv_nanodet"), ("object_detection_gpu", "opencv_yolox")):
        pack = packs[pack_id]
        assets = list(pack.get("assets", []))
        if len(assets) != 1 or assets[0].get("asset_id") != expected_asset_id:
            raise PackStageError(f"{pack_id} must contain only {expected_asset_id}")
        asset = assets[0]
        catalog_record = dict(catalog.get("assets", {}).get(expected_asset_id) or {})
        registry_record = dict(registry.get(expected_asset_id) or {})
        admission = evaluate_pack_admission(catalog, asset_id=expected_asset_id, distribution="public")
        if not admission.allowed:
            raise PackStageError(f"{expected_asset_id} is not distributable: {admission.reason}")
        revision = str(catalog_record.get("revision") or "")
        snapshot = _snapshot_for(vault_root, expected_asset_id, revision)
        verified = verify_snapshot(snapshot)
        if verified.manifest_sha256 != catalog_record.get("sealed_manifest_sha256"):
            raise PackStageError(f"{expected_asset_id} sealed source manifest does not match catalog")
        if asset.get("sha256") != registry_record.get("sha256") or asset.get("sha256") != catalog_record.get("model_sha256", asset.get("sha256")):
            raise PackStageError(f"{expected_asset_id} manifest hash does not match registry")
        source = snapshot / "source" / str(asset["source_file"])
        if not source.is_file() or source.stat().st_size != int(asset["size_bytes"]) or _sha256(source) != asset["sha256"]:
            raise PackStageError(f"{expected_asset_id} source model does not match its sealed manifest")

        pack_root = staging_root / pack_id
        target = pack_root / str(asset["target_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if _sha256(target) != asset["sha256"]:
            raise PackStageError(f"{expected_asset_id} staging copy hash mismatch")
        shutil.copy2(snapshot / "terms" / "00_LICENSE", pack_root / "LICENSE.txt")
        receipt = {
            "schema_version": 1,
            "pack_id": pack_id,
            "asset_id": expected_asset_id,
            "source_revision": revision,
            "source_manifest_sha256": verified.manifest_sha256,
            "model_sha256": asset["sha256"],
            "model_size_bytes": asset["size_bytes"],
            "target_path": asset["target_path"],
            "license": asset["license"],
            "source_url": asset["source_url"],
        }
        (pack_root / "PACK_MANIFEST.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staged.append(receipt)
    return {"status": "ok", "staging_root": str(staging_root), "packs": staged}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="stage sealed OpenCV object-detection capability packs")
    parser.add_argument("--vault-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(stage_pack(vault_root=args.vault_root, staging_root=args.staging_root), indent=2, sort_keys=True))
    except (OSError, ValueError, PackStageError) as exc:
        print(f"object-detection pack staging failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
