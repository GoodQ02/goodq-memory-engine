"""Contract tests for the complete offline asset catalog."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re

import yaml
from lib.ingestion_capability_contract import resolve_profile_assets


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "configs" / "offline_asset_catalog.yaml"
REGISTRY_PATH = REPO_ROOT / "configs" / "model_registry.yaml"
INSTALLER_PATH = REPO_ROOT / "scripts" / "install" / "goodq4all_installer.nsi"
FALLBACK_REGISTRY_PATH = REPO_ROOT / "steps" / "common" / "model_provisioner.py"
PROFILE_CONFIG_PATH = REPO_ROOT / "configs" / "models_config.yaml"
INSTALLER_PROFILE_CONTRACT_PATH = REPO_ROOT / "configs" / "installer_profile_contract.yaml"
OFFLINE_DEPENDENCIES_MANIFEST_PATH = REPO_ROOT / "configs" / "offline_dependencies_manifest.json"
LEGACY_WSL_SETUP_PATH = REPO_ROOT / "scripts" / "setup_wsl2_audio.py"
THIRD_PARTY_NOTICES_PATH = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
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

# A manifest artifact can expand into more than one executable (FFmpeg also
# carries FFprobe), but every artifact used to build the offline payload needs a
# catalog disposition.  This prevents build-only, retired, or agreement-gated
# artifacts from becoming invisible simply because they are not model-registry
# entries.
OFFLINE_MANIFEST_CATALOG_MAP = {
    "go": {"go_toolchain"},
    "nsis": {"nsis_toolchain"},
    "python_runtime": {"python_runtime"},
    "qdrant": {"qdrant"},
    "ffmpeg": {"ffmpeg", "ffprobe"},
    "nssm": {"nssm"},
    "vc_redist": {"vc_redist"},
    "tesseract": {"tesseract"},
    "poppler": {"poppler"},
    "cublas64_12": {"cublas64_12"},
    "cublasLt64_12": {"cublasLt64_12"},
    "cacert": {"cacert"},
    "get_pip": {"get_pip"},
}


def _load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _offline_manifest_keys() -> set[str]:
    payload = json.loads(OFFLINE_DEPENDENCIES_MANIFEST_PATH.read_text(encoding="utf-8"))
    return set(payload["toolchains"]) | set(payload["dependencies"])


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


def test_catalog_disposes_every_offline_manifest_artifact() -> None:
    """The offline builder has no uncatalogued payload or build dependency."""

    catalog = _load_yaml(CATALOG_PATH)
    assets = set(dict(catalog["assets"]))

    assert _offline_manifest_keys() == set(OFFLINE_MANIFEST_CATALOG_MAP)
    for manifest_key, catalog_ids in OFFLINE_MANIFEST_CATALOG_MAP.items():
        assert catalog_ids <= assets, manifest_key


def test_catalog_and_runtime_registry_share_exact_model_sources_and_revisions() -> None:
    catalog = _load_yaml(CATALOG_PATH)
    registry = _load_yaml(REGISTRY_PATH)
    assets = dict(catalog["assets"])

    for asset_id, record in dict(registry.get("huggingface_models", {})).items():
        assert assets[asset_id]["source"] == record["repo_id"], asset_id
        assert assets[asset_id]["revision"] == record["revision"], asset_id


def test_installer_profiles_select_only_sealed_and_permitted_assets() -> None:
    catalog = _load_yaml(CATALOG_PATH)
    profiles = _load_yaml(INSTALLER_PROFILE_CONTRACT_PATH)

    cpu_assets = resolve_profile_assets(catalog, profiles, "PUBLIC_CPU_BASELINE")
    gpu_assets = resolve_profile_assets(catalog, profiles, "PUBLIC_GPU_ENHANCED")
    personal_assets = resolve_profile_assets(catalog, profiles, "PERSONAL_AIR_GAP")
    records = dict(catalog["assets"])

    assert set(cpu_assets) <= set(gpu_assets)
    assert set(gpu_assets) <= set(personal_assets)
    assert all(
        records[asset_id]["status"] == "eligible"
        and records[asset_id]["vault_scope"] == "personal_and_distributable"
        for asset_id in gpu_assets
    )
    assert "qwen2_5_vl_3b" not in gpu_assets
    assert "qwen2_5_vl_3b" in personal_assets


def test_invalid_faster_whisper_turbo_scaffold_is_absent_from_active_configuration() -> None:
    """The retired Turbo candidate must not remain selectable or provisionable."""

    retired_repo = "Systran/faster-whisper-large-v3-turbo"
    retired_key = "whisper_large_v3_turbo"
    active_paths = (CATALOG_PATH, REGISTRY_PATH, FALLBACK_REGISTRY_PATH, PROFILE_CONFIG_PATH)

    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        assert retired_repo not in text, path
        assert retired_key not in text, path


def test_unpinned_pyannote_aliases_are_absent_from_active_configuration() -> None:
    """Only the pinned 3.1/3.0 Pyannote chain may remain selectable or documented."""

    retired_aliases = (
        re.compile(r"pyannote/speaker-diarization(?!-3\.1)"),
        re.compile(r"pyannote/segmentation(?!-3\.0)"),
    )
    active_paths = (
        CATALOG_PATH,
        REGISTRY_PATH,
        FALLBACK_REGISTRY_PATH,
        LEGACY_WSL_SETUP_PATH,
        THIRD_PARTY_NOTICES_PATH,
    )

    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        for retired_alias in retired_aliases:
            assert retired_alias.search(text) is None, path
