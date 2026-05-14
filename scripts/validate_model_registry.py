"""Static validation for the GoodQ4All model registry.

This check is intentionally offline. It validates registry shape, immutable
model pins, and asset metadata without downloading models or inspecting local
caches.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "configs" / "model_registry.yaml"

COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
PLACEHOLDER_MARKERS = (
    "placeholder",
    "change-me",
    "changeme",
    "example",
    "latest",
    "todo",
)
MUTABLE_REVISIONS = {"main", "master", "head", "dev"}


@dataclass(frozen=True)
class RegistryValidationResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_mapping(value: Any) -> bool:
    return isinstance(value, dict)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _looks_placeholder(value: str) -> bool:
    lowered = value.lower().strip()
    if not lowered:
        return True
    if lowered in MUTABLE_REVISIONS:
        return True
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return True
    return len(lowered) > 8 and len(set(lowered)) == 1


def _validate_huggingface_models(registry: dict[str, Any], errors: list[str]) -> None:
    models = registry.get("huggingface_models")
    if not _is_mapping(models) or not models:
        errors.append("huggingface_models must be a non-empty mapping")
        return

    for key, model_info in sorted(models.items()):
        if not _is_mapping(model_info):
            errors.append(f"huggingface_models.{key} must be a mapping")
            continue

        repo_id = _as_text(model_info.get("repo_id"))
        revision = _as_text(model_info.get("revision"))
        if "/" not in repo_id:
            errors.append(f"huggingface_models.{key}.repo_id must name an owner/repo")
        if _looks_placeholder(revision):
            errors.append(f"huggingface_models.{key}.revision must be an immutable commit SHA")
        elif not COMMIT_SHA_RE.fullmatch(revision):
            errors.append(f"huggingface_models.{key}.revision must be a 40-character commit SHA")

        if bool(model_info.get("requires_auth")) and not _as_text(model_info.get("auth_token_env")):
            errors.append(f"huggingface_models.{key}.auth_token_env is required when requires_auth is true")


def _validate_external_models(registry: dict[str, Any], errors: list[str]) -> None:
    models = registry.get("external_models") or {}
    if not _is_mapping(models):
        errors.append("external_models must be a mapping when present")
        return

    for key, model_info in sorted(models.items()):
        if not _is_mapping(model_info):
            errors.append(f"external_models.{key} must be a mapping")
            continue

        required = bool(model_info.get("required", True))
        source_url = _as_text(model_info.get("source_url"))
        local_path = _as_text(model_info.get("local_path"))
        sha256 = _as_text(model_info.get("sha256"))
        file_size = model_info.get("file_size_bytes")

        if required and not source_url:
            errors.append(f"external_models.{key}.source_url is required")
        if required and not local_path:
            errors.append(f"external_models.{key}.local_path is required")
        if sha256 and (_looks_placeholder(sha256) or not SHA256_RE.fullmatch(sha256)):
            errors.append(f"external_models.{key}.sha256 must be a 64-character SHA256")
        elif required and not sha256:
            errors.append(f"external_models.{key}.sha256 is required")
        if file_size is not None and (not isinstance(file_size, int) or file_size <= 0):
            errors.append(f"external_models.{key}.file_size_bytes must be a positive integer")
        elif required and file_size is None:
            errors.append(f"external_models.{key}.file_size_bytes is required")


def _validate_system_tools(registry: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    tools = registry.get("system_tools") or {}
    if not _is_mapping(tools):
        errors.append("system_tools must be a mapping when present")
        return

    for key, tool_info in sorted(tools.items()):
        if not _is_mapping(tool_info):
            errors.append(f"system_tools.{key} must be a mapping")
            continue

        if bool(tool_info.get("required", True)) and not _as_text(tool_info.get("binary_path")):
            errors.append(f"system_tools.{key}.binary_path is required")
        if not _as_text(tool_info.get("verify_command")):
            warnings.append(f"system_tools.{key}.verify_command is not set")


def validate_registry(path: Path) -> RegistryValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return RegistryValidationResult(errors=(f"registry file not found: {path}",), warnings=())

    try:
        registry = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return RegistryValidationResult(errors=(f"registry could not be parsed: {exc}",), warnings=())

    if not _is_mapping(registry):
        return RegistryValidationResult(errors=("registry root must be a mapping",), warnings=())

    _validate_huggingface_models(registry, errors)
    _validate_external_models(registry, errors)
    _validate_system_tools(registry, errors, warnings)

    return RegistryValidationResult(errors=tuple(errors), warnings=tuple(warnings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GoodQ4All model registry metadata without downloads.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help="Path to model_registry.yaml.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation output.")
    args = parser.parse_args(argv)

    result = validate_registry(args.registry)
    if args.json:
        print(json.dumps({"ok": result.ok, "errors": result.errors, "warnings": result.warnings}, indent=2))
    else:
        for warning in result.warnings:
            print(f"[WARN] {warning}")
        for error in result.errors:
            print(f"[FAIL] {error}")
        if result.ok:
            print("[OK] model registry static validation passed")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
