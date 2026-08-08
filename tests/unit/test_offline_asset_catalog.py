"""Contract tests for the complete offline asset catalog."""

from __future__ import annotations

import ast
from pathlib import Path
import re

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "configs" / "offline_asset_catalog.yaml"
REGISTRY_PATH = REPO_ROOT / "configs" / "model_registry.yaml"
INSTALLER_PATH = REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi"
FALLBACK_REGISTRY_PATH = REPO_ROOT / "steps" / "common" / "model_provisioner.py"
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
        *dict(registry.get("lexicons", {})),
        *dict(registry.get("system_tools", {})),
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


def _fallback_model_sources() -> set[str]:
    tree = ast.parse(FALLBACK_REGISTRY_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "_FALLBACK_REGISTRY" for target in node.targets):
            return {source for source in ast.literal_eval(node.value) if "/" in source}
    raise AssertionError("_FALLBACK_REGISTRY is absent")


def _literal_from_pretrained_sources() -> set[str]:
    pattern = re.compile(r"from_pretrained\(\s*['\"]([^'\"]+/[^'\"]+)['\"]")
    sources: set[str] = set()
    for root in (REPO_ROOT / "steps", REPO_ROOT / "scripts"):
        for path in root.rglob("*.py"):
            if path.is_relative_to(REPO_ROOT / "scripts" / "install" / "staged" / "vendor"):
                continue
            sources.update(pattern.findall(path.read_text(encoding="utf-8")))
    return sources


def test_catalog_covers_every_registry_and_installer_asset() -> None:
    catalog = _load_yaml(CATALOG_PATH)
    assets = dict(catalog["assets"])
    expected = _registry_asset_ids() | _installer_asset_ids()

    assert expected <= set(assets)
    assert _fallback_model_sources() <= {record["source"] for record in assets.values()}
    assert _literal_from_pretrained_sources() <= {record["source"] for record in assets.values()}
    for asset_id, record in assets.items():
        assert REQUIRED_FIELDS <= set(record), asset_id
        assert record["status"] in VALID_STATUSES, asset_id


def test_catalog_and_runtime_registry_share_exact_model_sources_and_revisions() -> None:
    catalog = _load_yaml(CATALOG_PATH)
    registry = _load_yaml(REGISTRY_PATH)
    assets = dict(catalog["assets"])

    for asset_id, record in dict(registry.get("huggingface_models", {})).items():
        assert assets[asset_id]["source"] == record["repo_id"], asset_id
        assert assets[asset_id]["revision"] == record["revision"], asset_id
