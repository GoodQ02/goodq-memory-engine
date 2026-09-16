"""Canonical semantic constants shared by GoodQ4All installer Python tools.

The profile YAML and :mod:`goodq_version` remain the authorities for the full
profile map and product version.  This module owns only the cross-component
installer contract that must project consistently into Python, Go, NSIS,
PowerShell, batch entrypoints, and CI.
"""

from __future__ import annotations


PAYLOAD_MANIFEST_SCHEMA_VERSION = 2
SELECTED_CAPABILITIES_SCHEMA_VERSION = 2
MODEL_MEMBER_MANIFEST_SCHEMA_VERSION = 2
PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION = 2

PAYLOAD_PACK_FORMAT = "zip_stored_zip64"
PAYLOAD_INSTALL_RECEIPT_STATUS = "applied_and_verified"

INSTALLER_PROFILES = (
    "PUBLIC_CPU_BASELINE",
    "PUBLIC_GPU_ENHANCED",
    "PERSONAL_AIR_GAP",
)
RELEASE_BUILD_PROFILES = (
    "PUBLIC_GPU_ENHANCED",
    "PERSONAL_AIR_GAP",
)

PAYLOAD_BINDING_FIELDS = frozenset(
    {
        "selected_capabilities_sha256",
        "selected_asset_selector_sha256",
        "selected_asset_inventory_sha256",
        "model_member_manifest_sha256",
        "model_member_inventory_sha256",
    }
)
PAYLOAD_MANIFEST_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "product_version",
        "profile",
        "pack_format",
        "max_pack_bytes",
        *PAYLOAD_BINDING_FIELDS,
        "member_inventory_sha256",
        "member_count",
        "members",
        "packs",
    }
)
PAYLOAD_PACK_REQUIRED_FIELDS = frozenset(
    {"path", "sha256", "size_bytes", "member_count"}
)
PAYLOAD_MEMBER_REQUIRED_FIELDS = frozenset(
    {"path", "pack_path", "sha256", "size_bytes", "target"}
)

SELECTED_CAPABILITIES_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "profile",
        "distribution",
        "selected_asset_ids",
        "selector_sha256",
        "asset_inventory_sha256",
        "asset_closure",
        "payload_asset_ids",
        "payloads",
        "model_member_manifest",
    }
)
MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS = frozenset(
    {"schema_version", "profile", "member_count", "inventory_sha256", "members"}
)
MODEL_MEMBER_REQUIRED_FIELDS = frozenset(
    {
        "path",
        "size_bytes",
        "sha256",
        "asset_id",
        "source_manifest_sha256",
        "provenance",
    }
)

PAYLOAD_INSTALL_RECEIPT_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "payload_manifest",
        "payload_manifest_sha256",
        "profile",
        *PAYLOAD_BINDING_FIELDS,
        "member_inventory_sha256",
        "member_count",
        "installed_members",
        "packs",
    }
)
