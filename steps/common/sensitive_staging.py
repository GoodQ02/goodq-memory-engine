from __future__ import annotations

"""
Sensitive ingest staging contract helper (structure-only).

Contract (docs/architecture/CANONICAL_SENSITIVE_EVENTS.md):
- High-sensitivity sources must be staged from the local vault into `cfg['paths']['processing']`.
- No ingestion step may write sidecar outputs into the vault.

This helper provides a best-effort validator intended for *sensitive-source* entry points.
It performs no copying/staging and must not log absolute vault paths.
"""

import os
from pathlib import Path
from typing import Any, Mapping, Optional

_ENV_VAULT_ROOT = "GOODQ_VAULT_ROOT"


def _norm_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").lower()


def _is_under(path_value: str, root_value: str) -> bool:
    path_norm = _norm_path(path_value)
    root_norm = _norm_path(root_value)
    if not root_norm:
        return False
    return path_norm == root_norm or path_norm.startswith(root_norm + "/")


def validate_sensitive_staging(
    cfg: Mapping[str, Any],
    input_path: str | Path,
    *,
    vault_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Validate that a sensitive-source input path is staged under `cfg['paths']['processing']`
    and not under the vault root.

    Returns a small result dict (no absolute paths included).
    """
    input_path_str = str(input_path)

    paths = cfg.get("paths") if isinstance(cfg, Mapping) else None
    processing_root = None
    if isinstance(paths, Mapping):
        processing_root = paths.get("processing")

    if vault_root is None:
        vault_root = os.getenv(_ENV_VAULT_ROOT) or None

    is_under_processing = bool(processing_root) and _is_under(input_path_str, str(processing_root))
    is_under_vault = bool(vault_root) and _is_under(input_path_str, str(vault_root))

    if is_under_vault:
        return {
            "ok": False,
            "reason": "input_path_under_vault_root",
            "vault_root_configured": True,
            "processing_root_configured": bool(processing_root),
            "is_under_processing": is_under_processing,
            "is_under_vault": True,
        }

    if not processing_root:
        return {
            "ok": False,
            "reason": "processing_root_missing_in_cfg_paths",
            "vault_root_configured": bool(vault_root),
            "processing_root_configured": False,
            "is_under_processing": False,
            "is_under_vault": False,
        }

    if not is_under_processing:
        return {
            "ok": False,
            "reason": "input_path_not_under_processing_root",
            "vault_root_configured": bool(vault_root),
            "processing_root_configured": True,
            "is_under_processing": False,
            "is_under_vault": False,
        }

    return {
        "ok": True,
        "reason": "ok",
        "vault_root_configured": bool(vault_root),
        "processing_root_configured": True,
        "is_under_processing": True,
        "is_under_vault": False,
    }

