"""Pure structural membership projection for governed clean-memory planning.

This module validates supplied canonical bytes only.  It does not locate, read,
or authenticate a manifest or external pin, and it grants no planning or
cleanup authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any
import unicodedata

from cli.clean_memory import CONFIGURATION_SCHEMA, ResolvedPlanConfiguration
from steps.common.clean_memory import (
    PROTECTED_BOUNDARY_ROLES as _PROTECTED_BOUNDARY_ROLES,
)


PROTECTED_MEMBERSHIP_SCHEMA = "goodq.clean-memory-protected-membership.v1"

__all__ = (
    "PROTECTED_MEMBERSHIP_SCHEMA",
    "ProtectedMembershipProjection",
    "project_protected_membership",
)

_MANIFEST_SCHEMA = "goodq.clean-memory-protected-authority.v1"
_MANIFEST_CHILD_NAME = "protected-boundaries.json"
_MAX_MANIFEST_BYTES = 4_194_304
_MAX_PATH_BYTES = 4_096
_MAX_MEMBERS_PER_ROLE = 64
_MAX_MEMBERS_TOTAL = 512
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MEMBER_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^([A-Z]):/(.+)$")
_UNRESOLVED_ENV_RE = re.compile(
    r"(?:\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%)"
)
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
    *(f"COM{index}" for index in ("¹", "²", "³")),
    *(f"LPT{index}" for index in ("¹", "²", "³")),
}
_FULL_ROLE_ORDER = (
    "archive_root",
    "backup_root",
    "control_root",
    "data_root",
    "download_cache",
    "failed_media",
    "import_media",
    "model_cache",
    "processed_media",
    "processing_media",
    "public_checkout",
    "qdrant_service_logs",
    "qdrant_storage",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
    "watchdog_state",
)
_MANIFEST_ROLE_ORDER = (
    "backup_root",
    "download_cache",
    "public_checkout",
    "qdrant_service_logs",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
)
_CONFIGURED_MEMBER_POLICY = {
    "archive_root": ("directory", "allow_absent", 1),
    "control_root": ("directory", "required", 1),
    "data_root": ("directory", "required", 1),
    "failed_media": ("directory", "allow_absent", 1),
    "import_media": ("directory", "allow_absent", 1),
    "model_cache": ("directory", "allow_absent", 1),
    "processed_media": ("directory", "allow_absent", 1),
    "processing_media": ("directory", "allow_absent", 1),
    "qdrant_storage": ("directory", "allow_absent", 1),
    "watchdog_state": ("regular_file", "allow_absent", 2),
}
_CONFIGURED_ROLE_ORDER = tuple(_CONFIGURED_MEMBER_POLICY)
_CONFIGURATION_KEYS = {
    "configured_protected_paths",
    "declared_faiss_paths",
    "epoch",
    "logical_paths",
    "path_flavor",
    "qdrant",
    "schema",
    "unresolved_protected_roles",
}
_LOGICAL_PATH_KEYS = {
    "candidate_evidence_root",
    "data_root",
    "faiss_root",
    "knowledge_graph_database",
    "knowledge_graph_database_shm",
    "knowledge_graph_database_wal",
    "memory_database",
    "memory_database_shm",
    "memory_database_wal",
    "storage_root",
}


class _DuplicateJsonKey(ValueError):
    pass


@dataclass(frozen=True, init=False)
class ProtectedMembershipProjection:
    """Immutable structural projection with a detached public view."""

    _projection_json: str = field(repr=False)
    protected_membership_scope_sha256: str

    @classmethod
    def _from_projection(
        cls, projection: dict[str, Any]
    ) -> "ProtectedMembershipProjection":
        projection_json = _canonical_json_text(projection)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_projection_json", projection_json)
        object.__setattr__(
            instance,
            "protected_membership_scope_sha256",
            hashlib.sha256(projection_json.encode("utf-8")).hexdigest(),
        )
        return instance

    @property
    def projection(self) -> dict[str, Any]:
        """Return a detached membership projection."""

        value = json.loads(self._projection_json)
        if type(value) is not dict:
            raise ValueError("Protected-membership projection is not an object")
        return value


def _canonical_json_text(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("Protected-membership value is not canonical JSON") from exc


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey
        value[key] = item
    return value


def _reject_nonfinite(_value: str) -> None:
    raise ValueError


def _strict_json_text(value: str, *, source: str) -> dict[str, Any]:
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_nonfinite,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        _DuplicateJsonKey,
        ValueError,
        RecursionError,
    ):
        raise ValueError(f"{source} is not canonical JSON") from None
    if type(parsed) is not dict:
        raise ValueError(f"{source} is not a JSON object")
    try:
        _validate_json_strings(parsed, source=source)
        canonical_value = _canonical_json_text(parsed)
    except RecursionError:
        raise ValueError(f"{source} is not canonical JSON") from None
    if canonical_value != value:
        raise ValueError(f"{source} bytes are not canonical")
    return parsed


def _validate_json_strings(value: object, *, source: str) -> None:
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value or _contains_control(value):
            raise ValueError(f"{source} contains a noncanonical string")
        return
    if type(value) is list:
        for item in value:
            _validate_json_strings(item, source=source)
        return
    if type(value) is dict:
        for key, item in value.items():
            _validate_json_strings(key, source=source)
            _validate_json_strings(item, source=source)


def _contains_control(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _canonical_absolute_path(value: object, *, expected_flavor: str) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or "\\" in value
        or value.endswith("/")
        or "//" in value
        or unicodedata.normalize("NFC", value) != value
        or _contains_control(value)
        or _UNRESOLVED_ENV_RE.search(value)
    ):
        raise ValueError("Protected-membership path is not canonical")

    windows_match = _WINDOWS_ABSOLUTE_RE.fullmatch(value)
    if windows_match is not None:
        if expected_flavor != "windows":
            raise ValueError("Protected-membership path uses the wrong flavor")
        parts = windows_match.group(2).split("/")
        for component in parts:
            if (
                component in {"", ".", ".."}
                or component.endswith((".", " "))
                or any(character in '<>:"|?*' for character in component)
                or component.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
            ):
                raise ValueError("Protected-membership path is not canonical")
        return value

    if value.startswith("/") and value != "/":
        if expected_flavor != "posix":
            raise ValueError("Protected-membership path uses the wrong flavor")
        if any(component in {"", ".", ".."} for component in value[1:].split("/")):
            raise ValueError("Protected-membership path is not canonical")
        return value

    raise ValueError("Protected-membership path is not a canonical local absolute path")


def _comparison_key(path: str, *, flavor: str) -> str:
    return path.casefold() if flavor == "windows" else path


def _paths_overlap(left: str, right: str, *, flavor: str) -> bool:
    left_key = _comparison_key(left, flavor=flavor)
    right_key = _comparison_key(right, flavor=flavor)
    return (
        left_key == right_key
        or left_key.startswith(f"{right_key}/")
        or right_key.startswith(f"{left_key}/")
    )


def _configuration_snapshot(
    configuration: ResolvedPlanConfiguration,
) -> tuple[str, str, dict[str, Any]]:
    if type(configuration) is not ResolvedPlanConfiguration:
        raise TypeError("configuration must be an exact ResolvedPlanConfiguration")

    projection_json = configuration._projection_json
    digest = configuration.configuration_scope_sha256
    if type(projection_json) is not str or type(digest) is not str:
        raise ValueError("Configuration projection is invalid")
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError("Configuration projection digest is invalid")
    projection = _strict_json_text(projection_json, source="Configuration projection")
    if hashlib.sha256(projection_json.encode("utf-8")).hexdigest() != digest:
        raise ValueError("Configuration projection digest does not match")
    return projection_json, digest, projection


def _configured_members(
    projection: dict[str, Any],
) -> tuple[str, dict[str, list[dict[str, str]]], tuple[str, ...]]:
    if set(projection) != _CONFIGURATION_KEYS:
        raise ValueError("Configuration projection has an invalid shape")
    if projection.get("schema") != CONFIGURATION_SCHEMA:
        raise ValueError("Configuration projection has the wrong schema")
    flavor = projection.get("path_flavor")
    if flavor not in {"windows", "posix"}:
        raise ValueError("Configuration projection has an invalid path flavor")
    if projection.get("unresolved_protected_roles") != list(_MANIFEST_ROLE_ORDER):
        raise ValueError("Configuration projection has an invalid unresolved-role census")

    logical_paths = projection.get("logical_paths")
    if type(logical_paths) is not dict or set(logical_paths) != _LOGICAL_PATH_KEYS:
        raise ValueError("Configuration projection has an invalid logical-path shape")
    canonical_logical_paths = {
        key: _canonical_absolute_path(value, expected_flavor=flavor)
        for key, value in logical_paths.items()
    }
    if canonical_logical_paths["memory_database_wal"] != (
        f"{canonical_logical_paths['memory_database']}-wal"
    ) or canonical_logical_paths["memory_database_shm"] != (
        f"{canonical_logical_paths['memory_database']}-shm"
    ):
        raise ValueError("Configuration projection has invalid memory-database topology")
    if canonical_logical_paths["knowledge_graph_database_wal"] != (
        f"{canonical_logical_paths['knowledge_graph_database']}-wal"
    ) or canonical_logical_paths["knowledge_graph_database_shm"] != (
        f"{canonical_logical_paths['knowledge_graph_database']}-shm"
    ):
        raise ValueError("Configuration projection has invalid knowledge-graph topology")

    records = projection.get("configured_protected_paths")
    if type(records) is not list or len(records) != len(_CONFIGURED_ROLE_ORDER):
        raise ValueError("Configuration projection has an invalid configured-role census")
    if tuple(
        record.get("role") if type(record) is dict else None for record in records
    ) != _CONFIGURED_ROLE_ORDER:
        raise ValueError("Configuration projection has an invalid configured-role order")

    members_by_role: dict[str, list[dict[str, str]]] = {}
    configured_paths_by_role: dict[str, tuple[str, ...]] = {}
    for record in records:
        if type(record) is not dict or set(record) != {"paths", "role"}:
            raise ValueError("Configuration projection has an invalid role record")
        role = record["role"]
        kind, presence, expected_count = _CONFIGURED_MEMBER_POLICY[role]
        paths = record["paths"]
        if type(paths) is not list or len(paths) != expected_count:
            raise ValueError("Configuration projection has invalid configured cardinality")
        canonical_paths = tuple(
            _canonical_absolute_path(path, expected_flavor=flavor) for path in paths
        )
        configured_paths_by_role[role] = canonical_paths
        members_by_role[role] = [
            {
                "absolute_path": path,
                "member_id": f"configured_{index:02d}",
                "object_kind": kind,
                "presence": presence,
            }
            for index, path in enumerate(canonical_paths)
        ]

    if configured_paths_by_role["data_root"] != (
        canonical_logical_paths["data_root"],
    ):
        raise ValueError("Configuration projection has inconsistent data-root authority")
    control_root = configured_paths_by_role["control_root"][0]
    if control_root != f"{canonical_logical_paths['data_root']}/control":
        raise ValueError("Configuration projection has inconsistent control-root authority")
    if canonical_logical_paths["candidate_evidence_root"] != f"{control_root}/clean_memory":
        raise ValueError("Configuration projection has inconsistent evidence-root authority")
    watchdog_paths = configured_paths_by_role["watchdog_state"]
    if watchdog_paths != tuple(sorted(watchdog_paths)):
        raise ValueError("Configuration projection has reordered watchdog authority")

    cleanup_scope = (
        canonical_logical_paths["memory_database"],
        canonical_logical_paths["memory_database_wal"],
        canonical_logical_paths["memory_database_shm"],
        canonical_logical_paths["knowledge_graph_database"],
        canonical_logical_paths["knowledge_graph_database_wal"],
        canonical_logical_paths["knowledge_graph_database_shm"],
        canonical_logical_paths["faiss_root"],
        canonical_logical_paths["candidate_evidence_root"],
    )
    for role, paths in configured_paths_by_role.items():
        if role in {"control_root", "data_root"}:
            continue
        if any(
            _paths_overlap(path, target, flavor=flavor)
            for path in paths
            for target in cleanup_scope
        ):
            raise ValueError("Configuration protected membership overlaps cleanup scope")
    return flavor, members_by_role, cleanup_scope


def _manifest_members(
    manifest_bytes: bytes,
    *,
    flavor: str,
) -> tuple[dict[str, list[dict[str, str]]], str]:
    if type(manifest_bytes) is not bytes:
        raise TypeError("manifest_bytes must be exact bytes")
    if not 1 <= len(manifest_bytes) <= _MAX_MANIFEST_BYTES:
        raise ValueError("Manifest bytes exceed the protocol size boundary")
    try:
        manifest_text = manifest_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ValueError("Manifest bytes are not canonical UTF-8") from None
    manifest = _strict_json_text(manifest_text, source="Manifest")
    if manifest_text.encode("utf-8") != manifest_bytes:
        raise ValueError("Manifest bytes are not canonical UTF-8")
    if set(manifest) != {"roles", "schema"} or manifest.get("schema") != _MANIFEST_SCHEMA:
        raise ValueError("Manifest has an invalid schema envelope")
    roles = manifest.get("roles")
    if type(roles) is not list or len(roles) != len(_MANIFEST_ROLE_ORDER):
        raise ValueError("Manifest has an invalid role census")
    if tuple(record.get("role") if type(record) is dict else None for record in roles) != (
        _MANIFEST_ROLE_ORDER
    ):
        raise ValueError("Manifest has an invalid role order")

    total_members = 0
    members_by_role: dict[str, list[dict[str, str]]] = {}
    for record in roles:
        if type(record) is not dict or set(record) != {"members", "role"}:
            raise ValueError("Manifest has an invalid role record")
        role = record["role"]
        members = record["members"]
        if type(members) is not list or not 1 <= len(members) <= _MAX_MEMBERS_PER_ROLE:
            raise ValueError("Manifest has an invalid member count")
        total_members += len(members)
        if total_members > _MAX_MEMBERS_TOTAL:
            raise ValueError("Manifest has too many members")
        previous_id: str | None = None
        canonical_members: list[dict[str, str]] = []
        for member in members:
            if type(member) is not dict or set(member) != {
                "absolute_path",
                "member_id",
                "object_kind",
                "presence",
            }:
                raise ValueError("Manifest has an invalid member record")
            member_id = member["member_id"]
            if type(member_id) is not str or not _MEMBER_ID_RE.fullmatch(member_id):
                raise ValueError("Manifest has an invalid member identifier")
            if previous_id is not None and member_id <= previous_id:
                raise ValueError("Manifest member identifiers are not strictly ordered")
            previous_id = member_id
            if member["object_kind"] != "directory" or member["presence"] not in {
                "required",
                "allow_absent",
            }:
                raise ValueError("Manifest has an invalid member policy")
            path = _canonical_absolute_path(
                member["absolute_path"], expected_flavor=flavor
            )
            if len(path.encode("utf-8")) > _MAX_PATH_BYTES:
                raise ValueError("Manifest member path exceeds the protocol boundary")
            canonical_members.append(
                {
                    "absolute_path": path,
                    "member_id": member_id,
                    "object_kind": "directory",
                    "presence": member["presence"],
                }
            )
        members_by_role[role] = canonical_members
    return members_by_role, hashlib.sha256(manifest_bytes).hexdigest()


def _validate_combined_scope(
    members_by_role: dict[str, list[dict[str, str]]],
    *,
    flavor: str,
    cleanup_scope: tuple[str, ...],
) -> None:
    seen: set[str] = set()
    for role in _FULL_ROLE_ORDER:
        for member in members_by_role[role]:
            path = member["absolute_path"]
            comparison_key = _comparison_key(path, flavor=flavor)
            if comparison_key in seen:
                raise ValueError("Protected membership contains a path alias")
            seen.add(comparison_key)
            if role not in {"control_root", "data_root"} and any(
                _paths_overlap(path, target, flavor=flavor)
                for target in cleanup_scope
            ):
                raise ValueError("Protected membership overlaps cleanup scope")


def project_protected_membership(
    configuration: ResolvedPlanConfiguration,
    *,
    manifest_bytes: bytes,
) -> ProtectedMembershipProjection:
    """Project deterministic structural membership without authenticating it."""

    if type(manifest_bytes) is not bytes:
        raise TypeError("manifest_bytes must be exact bytes")
    if not 1 <= len(manifest_bytes) <= _MAX_MANIFEST_BYTES:
        raise ValueError("Manifest bytes exceed the protocol size boundary")
    if tuple(_PROTECTED_BOUNDARY_ROLES) != _FULL_ROLE_ORDER:
        raise ValueError("Protected role authority does not match the selected contract")
    configuration_json, configuration_digest, configuration_projection = (
        _configuration_snapshot(configuration)
    )
    flavor, configured_members, cleanup_scope = _configured_members(
        configuration_projection
    )
    manifest_members, manifest_digest = _manifest_members(
        manifest_bytes, flavor=flavor
    )
    members_by_role = {**configured_members, **manifest_members}
    if set(members_by_role) != set(_FULL_ROLE_ORDER):
        raise ValueError("Protected membership has an invalid role census")
    _validate_combined_scope(
        members_by_role,
        flavor=flavor,
        cleanup_scope=cleanup_scope,
    )
    projection = {
        "configuration_scope_sha256": configuration_digest,
        "manifest": {
            "child_name": _MANIFEST_CHILD_NAME,
            "sha256": manifest_digest,
        },
        "path_flavor": flavor,
        "protected_roles": [
            {"members": members_by_role[role], "role": role}
            for role in _FULL_ROLE_ORDER
        ],
        "schema": PROTECTED_MEMBERSHIP_SCHEMA,
    }
    result = ProtectedMembershipProjection._from_projection(projection)
    if (
        configuration._projection_json != configuration_json
        or configuration.configuration_scope_sha256 != configuration_digest
    ):
        raise ValueError("Configuration projection changed during membership projection")
    return result
