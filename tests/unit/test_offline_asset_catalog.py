"""Contract tests for the complete offline asset catalog."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "configs" / "offline_asset_catalog.yaml"
REGISTRY_PATH = REPO_ROOT / "configs" / "model_registry.yaml"
INSTALLER_PATH = REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi"
VALID_STATUSES = {"eligible", "agreement_gated", "personal_only", "excluded"}
REQUIRED_FIELDS = {
    "kind",
    "source",
    "revision",
    "license_class",
    "vault_scope",
    "pack_scope",
    "hardware_profile",
    "status",
}


def _load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _registry_asset_ids() -> set[str]:
    registry = _load_yaml(REGISTRY_PATH)
    return {
        *dict(registry.get("huggingface_models", {})),
        *dict(registry.get("external_models", {})),
    }


def _installer_asset_ids() -> set[str]:
    """Return explicit staged payload identifiers from the NSIS installer."""

    text = INSTALLER_PATH.read_text(encoding="utf-8")
    required_markers = {
        "qdrant": "staged\\qdrant\\qdrant.exe",
        "ffmpeg": "ffmpeg.exe",
        "ffprobe": "ffprobe.exe",
        "python_wheelhouse": "wheelhouse",
        "tesseract": "tesseract_setup.exe",
        "vc_redist": "vc_redist.x64.exe",
        "nssm": "staged\\nssm\\nssm.exe",
    }
    return {
        asset_id
        for asset_id, marker in required_markers.items()
        if marker.casefold() in text.casefold()
    }


def test_catalog_covers_every_registry_and_installer_asset() -> None:
    catalog = _load_yaml(CATALOG_PATH)
    assets = dict(catalog["assets"])
    expected = _registry_asset_ids() | _installer_asset_ids()

    assert expected <= set(assets)
    for asset_id, record in assets.items():
        assert REQUIRED_FIELDS <= set(record), asset_id
        assert record["status"] in VALID_STATUSES, asset_id
