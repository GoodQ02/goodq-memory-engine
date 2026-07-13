"""Import-pure authority primitives for governed clean-memory candidate plans.

This module accepts already-resolved, injected observations. It does not load
configuration, inspect cleanup targets, contact Qdrant, create action jobs, or
authorize/execute cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
import unicodedata
from urllib.parse import urlsplit


PLAN_SCHEMA = "goodq.clean-memory-plan.v1"
PLAN_POLICY_VERSION = "goodq.clean-memory-policy.v1"
CLEAN_MEMORY_OPERATION = "clean_memory.apply"

_EPOCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_LOGICAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_SINGLETON_FILE_ROLES = (
    "memory_database",
    "memory_database_wal",
    "memory_database_shm",
    "knowledge_graph_database",
    "knowledge_graph_database_wal",
    "knowledge_graph_database_shm",
)
_FILE_ROLE_ORDER = {
    role: index for index, role in enumerate((*_SINGLETON_FILE_ROLES, "faiss_file"))
}
_QDRANT_ROLES = ("text", "clip", "dino", "audio")
_QDRANT_ROLE_ORDER = {role: index for index, role in enumerate(_QDRANT_ROLES)}
_FINGERPRINT_KINDS = {"generation_token", "point_state_sha256"}
PROTECTED_BOUNDARY_ROLES = (
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
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

_AUTHORITY_KEYS = {
    "schema",
    "policy_version",
    "operation",
    "configuration_scope_sha256",
    "epoch",
    "filesystem_targets",
    "qdrant",
    "protected_boundaries",
    "preconditions",
    "execution_order",
}
_RECORD_KEYS = {"plan_id", "plan_sha256", "authority", "observation"}


class CleanMemoryPlanError(RuntimeError):
    """Base error for candidate-plan authority failures."""


class CleanMemoryPlanConflict(CleanMemoryPlanError):
    """A digest-named immutable plan conflicts with different authority."""


class CleanMemoryPlanIntegrityError(CleanMemoryPlanError):
    """Existing candidate-plan evidence is malformed, redirected, or corrupt."""


class CleanMemoryPlanPersistenceError(CleanMemoryPlanError):
    """A first candidate-plan publication did not complete safely."""


class CleanMemoryPlanRecoveryError(CleanMemoryPlanError):
    """An untrusted first publication could not be removed safely."""


@dataclass(frozen=True)
class FilesystemTargetEvidence:
    """Injected pre-state for one exact logical filesystem target."""

    role: str
    target_type: str
    relative_path: str
    exists: bool
    size_bytes: int | None
    mtime_ns: int | None
    file_identity_json: str | None
    sha256: str | None


@dataclass(frozen=True)
class QdrantCollectionEvidence:
    """Injected pre-state for one exact configured collection."""

    role: str
    collection_name: str
    exists: bool
    configuration_json: str | None
    point_count: int | None
    fingerprint_kind: str | None
    fingerprint_value: str | None


@dataclass(frozen=True)
class ProtectedBoundaryEvidence:
    """Bounded identity for a protected logical root outside cleanup scope."""

    role: str
    logical_id: str
    identity_json: str


@dataclass(frozen=True)
class ResolvedCleanupScope:
    """Already-resolved logical scope consumed by candidate planning."""

    epoch_id: str
    config_scope_sha256: str
    epoch_root_identity_json: str
    filesystem_targets: tuple[FilesystemTargetEvidence, ...]
    qdrant_endpoint: str
    qdrant_collections: tuple[QdrantCollectionEvidence, ...]
    protected_boundaries: tuple[ProtectedBoundaryEvidence, ...]


@dataclass(frozen=True, init=False)
class CandidatePlan:
    """Immutable plan envelope with detached observational metadata."""

    _authority_json: str
    plan_sha256: str
    plan_id: str
    observed_at_utc: str

    @classmethod
    def _from_authority(
        cls,
        authority: dict[str, Any],
        *,
        observed_at_utc: str,
    ) -> "CandidatePlan":
        authority_json = _canonical_json_text(authority, label="candidate plan authority")
        digest = _authority_sha256(authority)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_authority_json", authority_json)
        object.__setattr__(instance, "plan_sha256", digest)
        object.__setattr__(instance, "plan_id", f"plan_{digest}")
        object.__setattr__(
            instance,
            "observed_at_utc",
            _canonical_utc_timestamp(observed_at_utc),
        )
        return instance

    @property
    def authority(self) -> dict[str, Any]:
        """Return a detached authority projection."""

        value = _strict_json_loads(self._authority_json, label="candidate plan authority")
        if not isinstance(value, dict):
            raise CleanMemoryPlanIntegrityError("Candidate plan authority is not an object")
        return value

    def to_record(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "authority": self.authority,
            "observation": {"observed_at_utc": self.observed_at_utc},
        }

    def record_bytes(self) -> bytes:
        return (
            json.dumps(
                self.to_record(),
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant is not allowed: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key is not allowed: {key}")
        result[key] = value
    return result


def _strict_json_loads(payload: str, *, label: str) -> Any:
    if not isinstance(payload, str):
        raise ValueError(f"{label} must be JSON text")
    try:
        return json.loads(
            payload,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not strict JSON") from exc


def _canonical_json_bytes(value: Any, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain only canonical JSON values") from exc


def _canonical_json_text(value: Any, *, label: str) -> str:
    return _canonical_json_bytes(value, label=label).decode("utf-8")


def _canonical_object_from_text(payload: str, *, label: str) -> dict[str, Any]:
    value = _strict_json_loads(payload, label=label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    canonical = _canonical_json_text(value, label=label)
    if canonical != payload:
        raise ValueError(f"{label} must use canonical compact JSON")
    return value


def _canonical_identity_from_text(payload: str, *, label: str) -> dict[str, Any]:
    identity = _canonical_object_from_text(payload, label=label)
    schema = identity.get("schema")
    if (
        len(identity) < 2
        or not isinstance(schema, str)
        or not schema
        or len(schema) > 128
        or any(ord(character) < 33 for character in schema)
    ):
        raise ValueError(f"{label} is not a complete tagged identity")
    return identity


def _authority_sha256(authority: dict[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(authority, label="candidate plan authority")
    ).hexdigest()


def _validate_digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid {label}")
    return value


def _validate_epoch_id(value: Any) -> str:
    if not isinstance(value, str) or _EPOCH_ID_RE.fullmatch(value) is None:
        raise ValueError("Invalid cleanup epoch ID")
    return value


def _validate_code(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _SAFE_CODE_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid {label}")
    return value


def _validate_logical_id(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _SAFE_LOGICAL_ID_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid {label}")
    return value


def _validate_nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid {label}")
    return value


def _canonical_utc_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid candidate-plan observation timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid candidate-plan observation timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Candidate-plan observation timestamp must be timezone-aware")
    normalized = parsed.astimezone(timezone.utc)
    if parsed.utcoffset() != timezone.utc.utcoffset(normalized):
        raise ValueError("Candidate-plan observation timestamp must be UTC")
    return normalized.isoformat()


def _validate_relative_path(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("Invalid cleanup target relative path")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError("Cleanup target path is not Unicode-canonical")
    path = PurePosixPath(value)
    if path.is_absolute() or value in {".", ".."} or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ValueError("Cleanup target must be a strict relative path")
    if path.as_posix() != value:
        raise ValueError("Cleanup target path is not canonical")
    for part in path.parts:
        if part.endswith((".", " ")):
            raise ValueError("Cleanup target path has a Windows-normalized suffix")
        reserved_base = part.split(".", 1)[0].upper()
        if reserved_base in _WINDOWS_RESERVED_NAMES:
            raise ValueError("Cleanup target path uses a reserved Windows name")
    return value


def _windows_path_identity(value: str) -> str:
    return "/".join(part.casefold() for part in PurePosixPath(value).parts)


def _validate_qdrant_endpoint(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid Qdrant endpoint")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid Qdrant endpoint") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or port is None
        or not 1 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != ""
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Qdrant endpoint must be canonical loopback HTTP")
    canonical_host = "127.0.0.1" if parsed.hostname == "127.0.0.1" else "[::1]"
    if value != f"http://{canonical_host}:{port}":
        raise ValueError("Qdrant endpoint spelling is not canonical")
    return value


def _filesystem_logical_id(role: str, relative_path: str) -> str:
    if role == "faiss_file":
        return f"filesystem:faiss:{relative_path}"
    return f"filesystem:{role}"


def _filesystem_record(target: FilesystemTargetEvidence) -> dict[str, Any]:
    if not isinstance(target, FilesystemTargetEvidence):
        raise ValueError("Invalid filesystem target evidence")
    if target.role not in _FILE_ROLE_ORDER:
        raise ValueError("Invalid filesystem target role")
    if target.target_type != "regular_file":
        raise ValueError("Cleanup filesystem target type must be regular_file")
    relative_path = _validate_relative_path(target.relative_path)
    if not isinstance(target.exists, bool):
        raise ValueError("Filesystem target existence must be boolean")

    if target.exists:
        size_bytes = _validate_nonnegative_int(target.size_bytes, label="file size")
        mtime_ns = _validate_nonnegative_int(target.mtime_ns, label="file mtime")
        identity = _canonical_identity_from_text(
            target.file_identity_json,
            label="file platform identity",
        )
        sha256 = _validate_digest(target.sha256, label="file SHA-256")
    else:
        if any(
            value is not None
            for value in (
                target.size_bytes,
                target.mtime_ns,
                target.file_identity_json,
                target.sha256,
            )
        ):
            raise ValueError("Absent filesystem target has stale pre-state")
        size_bytes = None
        mtime_ns = None
        identity = None
        sha256 = None

    logical_id = _filesystem_logical_id(target.role, relative_path)
    return {
        "role": target.role,
        "type": target.target_type,
        "logical_id": logical_id,
        "relative_path": relative_path,
        "exists": target.exists,
        "size_bytes": size_bytes,
        "mtime_ns": mtime_ns,
        "file_identity": identity,
        "sha256": sha256,
    }


def _collection_record(target: QdrantCollectionEvidence) -> dict[str, Any]:
    if not isinstance(target, QdrantCollectionEvidence):
        raise ValueError("Invalid Qdrant collection evidence")
    if target.role not in _QDRANT_ROLE_ORDER:
        raise ValueError("Invalid Qdrant collection role")
    if (
        not isinstance(target.collection_name, str)
        or _COLLECTION_NAME_RE.fullmatch(target.collection_name) is None
    ):
        raise ValueError("Invalid Qdrant collection name")
    if not isinstance(target.exists, bool):
        raise ValueError("Qdrant collection existence must be boolean")

    if target.exists:
        configuration = _canonical_object_from_text(
            target.configuration_json,
            label="Qdrant collection configuration",
        )
        point_count = _validate_nonnegative_int(
            target.point_count,
            label="Qdrant point count",
        )
        if target.fingerprint_kind not in _FINGERPRINT_KINDS:
            raise ValueError("Invalid Qdrant fingerprint kind")
        if target.fingerprint_kind == "point_state_sha256":
            fingerprint_value = _validate_digest(
                target.fingerprint_value,
                label="Qdrant point-state SHA-256",
            )
        else:
            if (
                not isinstance(target.fingerprint_value, str)
                or not target.fingerprint_value
                or target.fingerprint_value != target.fingerprint_value.strip()
                or any(ord(character) < 32 for character in target.fingerprint_value)
                or len(target.fingerprint_value) > 512
            ):
                raise ValueError("Invalid Qdrant generation token")
            fingerprint_value = target.fingerprint_value
        fingerprint: dict[str, str] | None = {
            "kind": target.fingerprint_kind,
            "value": fingerprint_value,
        }
    else:
        if any(
            value is not None
            for value in (
                target.configuration_json,
                target.point_count,
                target.fingerprint_kind,
                target.fingerprint_value,
            )
        ):
            raise ValueError("Absent Qdrant collection has stale pre-state")
        configuration = None
        point_count = None
        fingerprint = None

    return {
        "role": target.role,
        "logical_id": f"qdrant:{target.role}",
        "collection_name": target.collection_name,
        "exists": target.exists,
        "configuration": configuration,
        "point_count": point_count,
        "fingerprint": fingerprint,
    }


def _protected_boundary_record(
    boundary: ProtectedBoundaryEvidence,
) -> dict[str, Any]:
    if not isinstance(boundary, ProtectedBoundaryEvidence):
        raise ValueError("Invalid protected-boundary evidence")
    role = _validate_code(boundary.role, label="protected-boundary role")
    logical_id = _validate_logical_id(
        boundary.logical_id,
        label="protected-boundary logical ID",
    )
    identity = _canonical_identity_from_text(
        boundary.identity_json,
        label="protected-boundary identity",
    )
    return {"role": role, "logical_id": logical_id, "identity": identity}


def _build_authority(scope: ResolvedCleanupScope) -> dict[str, Any]:
    if not isinstance(scope, ResolvedCleanupScope):
        raise ValueError("Candidate plan requires a resolved cleanup scope")
    epoch_id = _validate_epoch_id(scope.epoch_id)
    config_scope_sha256 = _validate_digest(
        scope.config_scope_sha256,
        label="configuration-scope SHA-256",
    )
    epoch_root_identity = _canonical_identity_from_text(
        scope.epoch_root_identity_json,
        label="epoch-root identity",
    )
    qdrant_endpoint = _validate_qdrant_endpoint(scope.qdrant_endpoint)

    if not isinstance(scope.filesystem_targets, tuple):
        raise ValueError("Filesystem target evidence must be an immutable tuple")
    filesystem_records = [_filesystem_record(item) for item in scope.filesystem_targets]
    singleton_counts = {
        role: sum(item["role"] == role for item in filesystem_records)
        for role in _SINGLETON_FILE_ROLES
    }
    if any(count != 1 for count in singleton_counts.values()):
        raise ValueError("Filesystem target set is incomplete or duplicated")
    logical_ids = [item["logical_id"] for item in filesystem_records]
    relative_paths = [item["relative_path"] for item in filesystem_records]
    windows_path_identities = [_windows_path_identity(path) for path in relative_paths]
    present_file_identities = [
        _canonical_json_bytes(
            item["file_identity"],
            label="file platform identity",
        )
        for item in filesystem_records
        if item["exists"]
    ]
    if (
        len(set(logical_ids)) != len(logical_ids)
        or len(set(relative_paths)) != len(relative_paths)
        or len(set(windows_path_identities)) != len(windows_path_identities)
        or len(set(present_file_identities)) != len(present_file_identities)
    ):
        raise ValueError("Filesystem target identity is duplicated")
    filesystem_records.sort(
        key=lambda item: (
            _FILE_ROLE_ORDER[item["role"]],
            item["relative_path"],
        )
    )

    if not isinstance(scope.qdrant_collections, tuple):
        raise ValueError("Qdrant target evidence must be an immutable tuple")
    collection_records = [_collection_record(item) for item in scope.qdrant_collections]
    roles = [item["role"] for item in collection_records]
    names = [item["collection_name"] for item in collection_records]
    if sorted(roles) != sorted(_QDRANT_ROLES) or len(roles) != len(_QDRANT_ROLES):
        raise ValueError("Qdrant target set must contain exactly four configured roles")
    if len(set(names)) != len(names):
        raise ValueError("Qdrant collection names must be unique")
    collection_records.sort(key=lambda item: _QDRANT_ROLE_ORDER[item["role"]])

    if not isinstance(scope.protected_boundaries, tuple):
        raise ValueError("Protected-boundary evidence must be an immutable tuple")
    boundary_records = [
        _protected_boundary_record(item) for item in scope.protected_boundaries
    ]
    boundary_roles = [item["role"] for item in boundary_records]
    boundary_ids = [item["logical_id"] for item in boundary_records]
    if (
        sorted(boundary_roles) != sorted(PROTECTED_BOUNDARY_ROLES)
        or len(boundary_roles) != len(PROTECTED_BOUNDARY_ROLES)
    ):
        raise ValueError("Protected-boundary evidence set is incomplete or unexpected")
    if len(set(boundary_ids)) != len(boundary_ids):
        raise ValueError("Protected-boundary logical identity is duplicated")
    boundary_records.sort(key=lambda item: (item["role"], item["logical_id"]))

    execution_order = [item["logical_id"] for item in filesystem_records]
    execution_order.extend(item["logical_id"] for item in collection_records)
    authority = {
        "schema": PLAN_SCHEMA,
        "policy_version": PLAN_POLICY_VERSION,
        "operation": CLEAN_MEMORY_OPERATION,
        "configuration_scope_sha256": config_scope_sha256,
        "epoch": {
            "epoch_id": epoch_id,
            "root": {
                "logical_id": f"epoch:{epoch_id}",
                "identity": epoch_root_identity,
            },
        },
        "filesystem_targets": filesystem_records,
        "qdrant": {
            "endpoint": qdrant_endpoint,
            "redirects_allowed": False,
            "collections": collection_records,
        },
        "protected_boundaries": boundary_records,
        "preconditions": {
            "exclusive_cleanup_lease_required": True,
            "revalidate_exact_prestate_before_apply": True,
            "writer_quiescence_required": True,
        },
        "execution_order": execution_order,
    }
    _canonical_json_bytes(authority, label="candidate plan authority")
    return authority


def build_candidate_plan(
    scope: ResolvedCleanupScope,
    *,
    observed_at_utc: str,
) -> CandidatePlan:
    """Build an unapproved candidate plan from injected logical evidence only."""

    return CandidatePlan._from_authority(
        _build_authority(scope),
        observed_at_utc=observed_at_utc,
    )


def _scope_from_authority(authority: Any) -> ResolvedCleanupScope:
    if not isinstance(authority, dict) or set(authority) != _AUTHORITY_KEYS:
        raise ValueError("Candidate plan authority schema is invalid")
    if authority["schema"] != PLAN_SCHEMA:
        raise ValueError("Candidate plan schema is invalid")
    if authority["policy_version"] != PLAN_POLICY_VERSION:
        raise ValueError("Candidate plan policy version is invalid")
    if authority["operation"] != CLEAN_MEMORY_OPERATION:
        raise ValueError("Candidate plan operation is invalid")

    epoch = authority["epoch"]
    if not isinstance(epoch, dict) or set(epoch) != {"epoch_id", "root"}:
        raise ValueError("Candidate plan epoch schema is invalid")
    root = epoch["root"]
    if not isinstance(root, dict) or set(root) != {"logical_id", "identity"}:
        raise ValueError("Candidate plan epoch-root schema is invalid")
    expected_root_id = f"epoch:{epoch['epoch_id']}"
    if root["logical_id"] != expected_root_id:
        raise ValueError("Candidate plan epoch-root logical identity is invalid")

    raw_files = authority["filesystem_targets"]
    if not isinstance(raw_files, list):
        raise ValueError("Candidate plan filesystem targets are invalid")
    file_records: list[FilesystemTargetEvidence] = []
    file_keys = {
        "role",
        "type",
        "logical_id",
        "relative_path",
        "exists",
        "size_bytes",
        "mtime_ns",
        "file_identity",
        "sha256",
    }
    for item in raw_files:
        if not isinstance(item, dict) or set(item) != file_keys:
            raise ValueError("Candidate plan filesystem target schema is invalid")
        expected_logical_id = _filesystem_logical_id(item["role"], item["relative_path"])
        if item["logical_id"] != expected_logical_id:
            raise ValueError("Candidate plan filesystem logical identity is invalid")
        identity_json = (
            None
            if item["file_identity"] is None
            else _canonical_json_text(
                item["file_identity"], label="file platform identity"
            )
        )
        file_records.append(
            FilesystemTargetEvidence(
                role=item["role"],
                target_type=item["type"],
                relative_path=item["relative_path"],
                exists=item["exists"],
                size_bytes=item["size_bytes"],
                mtime_ns=item["mtime_ns"],
                file_identity_json=identity_json,
                sha256=item["sha256"],
            )
        )

    qdrant = authority["qdrant"]
    if not isinstance(qdrant, dict) or set(qdrant) != {
        "endpoint",
        "redirects_allowed",
        "collections",
    }:
        raise ValueError("Candidate plan Qdrant schema is invalid")
    if qdrant["redirects_allowed"] is not False:
        raise ValueError("Candidate plan Qdrant redirects must be disabled")
    raw_collections = qdrant["collections"]
    if not isinstance(raw_collections, list):
        raise ValueError("Candidate plan Qdrant collections are invalid")
    collection_keys = {
        "role",
        "logical_id",
        "collection_name",
        "exists",
        "configuration",
        "point_count",
        "fingerprint",
    }
    collection_records: list[QdrantCollectionEvidence] = []
    for item in raw_collections:
        if not isinstance(item, dict) or set(item) != collection_keys:
            raise ValueError("Candidate plan Qdrant collection schema is invalid")
        if item["logical_id"] != f"qdrant:{item['role']}":
            raise ValueError("Candidate plan Qdrant logical identity is invalid")
        fingerprint = item["fingerprint"]
        if fingerprint is None:
            fingerprint_kind = None
            fingerprint_value = None
        elif isinstance(fingerprint, dict) and set(fingerprint) == {"kind", "value"}:
            fingerprint_kind = fingerprint["kind"]
            fingerprint_value = fingerprint["value"]
        else:
            raise ValueError("Candidate plan Qdrant fingerprint schema is invalid")
        configuration_json = (
            None
            if item["configuration"] is None
            else _canonical_json_text(
                item["configuration"],
                label="Qdrant collection configuration",
            )
        )
        collection_records.append(
            QdrantCollectionEvidence(
                role=item["role"],
                collection_name=item["collection_name"],
                exists=item["exists"],
                configuration_json=configuration_json,
                point_count=item["point_count"],
                fingerprint_kind=fingerprint_kind,
                fingerprint_value=fingerprint_value,
            )
        )

    raw_boundaries = authority["protected_boundaries"]
    if not isinstance(raw_boundaries, list):
        raise ValueError("Candidate plan protected boundaries are invalid")
    boundary_records: list[ProtectedBoundaryEvidence] = []
    for item in raw_boundaries:
        if not isinstance(item, dict) or set(item) != {"role", "logical_id", "identity"}:
            raise ValueError("Candidate plan protected-boundary schema is invalid")
        boundary_records.append(
            ProtectedBoundaryEvidence(
                role=item["role"],
                logical_id=item["logical_id"],
                identity_json=_canonical_json_text(
                    item["identity"],
                    label="protected-boundary identity",
                ),
            )
        )

    scope = ResolvedCleanupScope(
        epoch_id=epoch["epoch_id"],
        config_scope_sha256=authority["configuration_scope_sha256"],
        epoch_root_identity_json=_canonical_json_text(
            root["identity"], label="epoch-root identity"
        ),
        filesystem_targets=tuple(file_records),
        qdrant_endpoint=qdrant["endpoint"],
        qdrant_collections=tuple(collection_records),
        protected_boundaries=tuple(boundary_records),
    )
    rebuilt = _build_authority(scope)
    if _canonical_json_bytes(rebuilt, label="candidate plan authority") != _canonical_json_bytes(
        authority,
        label="candidate plan authority",
    ):
        raise ValueError("Candidate plan authority is not canonical")
    return scope


def _plan_from_record(record: Any) -> CandidatePlan:
    if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
        raise ValueError("Candidate plan record schema is invalid")
    authority = record["authority"]
    _scope_from_authority(authority)
    digest = _authority_sha256(authority)
    persisted_digest = _validate_digest(record["plan_sha256"], label="plan SHA-256")
    if persisted_digest != digest:
        raise ValueError("Candidate plan digest is invalid")
    if record["plan_id"] != f"plan_{digest}":
        raise ValueError("Candidate plan ID is invalid")
    observation = record["observation"]
    if not isinstance(observation, dict) or set(observation) != {"observed_at_utc"}:
        raise ValueError("Candidate plan observation schema is invalid")
    return CandidatePlan._from_authority(
        authority,
        observed_at_utc=observation["observed_at_utc"],
    )


def _path_is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        reparse_flag and attributes & reparse_flag
    )


def _path_entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _validate_lock_entry(path: Path) -> None:
    """Reject an existing redirected or irregular lock from one metadata read."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or bool(reparse_flag and attributes & reparse_flag)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise CleanMemoryPlanIntegrityError(
            "Candidate-plan evidence lock is redirected or irregular"
        )


def _regular_file_identity(metadata: os.stat_result) -> tuple[int, int] | None:
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_ino == 0:
        return None
    return (metadata.st_dev, metadata.st_ino)


def _unlink_owned_temp(path: Path, identity: tuple[int, int] | None) -> None:
    """Remove only the exact temporary file created by this persistence call."""

    if identity is None:
        return
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if _regular_file_identity(metadata) != identity:
        return
    try:
        path.unlink()
    except OSError:
        pass


def _publish_no_replace(source: Path, destination: Path) -> None:
    """Publish one file atomically without replacing an existing first writer."""

    if os.name != "nt":
        os.link(source, destination)
        return

    # MoveFileExW without MOVEFILE_REPLACE_EXISTING is create-if-absent. The
    # WRITE_THROUGH flag makes the canonical Windows host wait for the move's
    # durable metadata update before reporting success.
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    move_file = kernel32.MoveFileExW
    move_file.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    move_file.restype = wintypes.BOOL
    movefile_write_through = 0x00000008
    if move_file(str(source), str(destination), movefile_write_through):
        return
    error = ctypes.get_last_error()
    if error in {80, 183}:  # ERROR_FILE_EXISTS / ERROR_ALREADY_EXISTS
        raise FileExistsError(error, "Candidate plan already exists", str(destination))
    raise OSError(error, "Candidate plan publication failed", str(destination))


def _sync_directory_after_publication(directory: Path) -> None:
    if os.name == "nt":
        # Windows durability is supplied by MoveFileExW(MOVEFILE_WRITE_THROUGH).
        return
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class CandidatePlanStore:
    """Immutable first-writer store beneath an injected evidence root."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _validate_root(self, *, require_directory: bool) -> None:
        if not self.root.is_absolute() or ".." in self.root.parts:
            raise CleanMemoryPlanIntegrityError(
                "Candidate-plan evidence root must be absolute and canonical"
            )
        root_exists = False
        candidates = (self.root, *self.root.parents)
        for candidate in reversed(candidates):
            try:
                metadata = candidate.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise CleanMemoryPlanIntegrityError(
                    "Candidate-plan evidence root is not a regular directory"
                ) from exc
            attributes = getattr(metadata, "st_file_attributes", 0)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if stat.S_ISLNK(metadata.st_mode) or bool(
                reparse_flag and attributes & reparse_flag
            ):
                raise CleanMemoryPlanIntegrityError(
                    "Candidate-plan evidence root is redirected by a reparse point"
                )
            if not stat.S_ISDIR(metadata.st_mode):
                raise CleanMemoryPlanIntegrityError(
                    "Candidate-plan evidence root is not a regular directory"
                )
            if candidate == self.root:
                root_exists = True
        if require_directory and not root_exists:
            raise CleanMemoryPlanIntegrityError(
                "Candidate-plan evidence root does not exist"
            )

    def record_path(self, plan_sha256: str) -> Path:
        digest = _validate_digest(plan_sha256, label="plan SHA-256")
        return self.root / f"plan_{digest}.json"

    def _load_path(
        self,
        path: Path,
        *,
        expected_digest: str,
        enforce_name: bool,
    ) -> CandidatePlan:
        if not _path_entry_exists(path):
            raise CleanMemoryPlanIntegrityError("Candidate plan evidence disappeared")
        if _path_is_reparse(path) or not path.is_file():
            raise CleanMemoryPlanIntegrityError(
                "Candidate plan evidence is not a regular file"
            )
        try:
            payload = path.read_bytes().decode("utf-8")
            record = _strict_json_loads(payload, label="candidate plan record")
            plan = _plan_from_record(record)
        except CleanMemoryPlanError:
            raise
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            raise CleanMemoryPlanIntegrityError(
                "Candidate plan evidence is malformed or corrupt"
            ) from exc
        if plan.plan_sha256 != expected_digest:
            raise CleanMemoryPlanIntegrityError("Candidate plan filename digest mismatch")
        if enforce_name and path.name != f"plan_{expected_digest}.json":
            raise CleanMemoryPlanIntegrityError("Candidate plan filename is invalid")
        return plan

    def load(self, plan_sha256: str) -> CandidatePlan | None:
        self._validate_root(require_directory=False)
        path = self.record_path(plan_sha256)
        if not _path_entry_exists(path):
            return None
        return self._load_path(
            path,
            expected_digest=plan_sha256,
            enforce_name=True,
        )

    def persist(self, plan: CandidatePlan) -> CandidatePlan:
        if not isinstance(plan, CandidatePlan):
            raise ValueError("Candidate-plan persistence requires a CandidatePlan")
        validated = _plan_from_record(plan.to_record())
        self._validate_root(require_directory=False)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CleanMemoryPlanPersistenceError(
                "Failed to create candidate-plan evidence root"
            ) from exc
        self._validate_root(require_directory=True)

        # Imported lazily so importing this pure authority module does not pull
        # process/network-oriented optional internals into planning callers.
        from filelock import FileLock

        lock_path = self.root / ".clean-memory-plan.lock"
        _validate_lock_entry(lock_path)
        target = self.record_path(validated.plan_sha256)
        with FileLock(str(lock_path)):
            _validate_lock_entry(lock_path)
            self._validate_root(require_directory=True)
            if _path_entry_exists(target):
                existing = self._load_path(
                    target,
                    expected_digest=validated.plan_sha256,
                    enforce_name=True,
                )
                if existing._authority_json == validated._authority_json:
                    return existing
                raise CleanMemoryPlanConflict(
                    "Candidate plan digest collision conflicts with immutable authority"
                )

            import uuid

            temp_path = target.with_name(
                f"{target.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
            )
            publication_completed = False
            owned_temp_identity: tuple[int, int] | None = None
            try:
                with temp_path.open("xb") as handle:
                    handle.write(validated.record_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
                    owned_temp_identity = _regular_file_identity(os.fstat(handle.fileno()))
                inspected = self._load_path(
                    temp_path,
                    expected_digest=validated.plan_sha256,
                    enforce_name=False,
                )
                if inspected != validated:
                    raise RuntimeError("Candidate plan temporary inspection mismatch")
                try:
                    _publish_no_replace(temp_path, target)
                except FileExistsError:
                    existing = self._load_path(
                        target,
                        expected_digest=validated.plan_sha256,
                        enforce_name=True,
                    )
                    if existing._authority_json == validated._authority_json:
                        return existing
                    raise CleanMemoryPlanConflict(
                        "Candidate plan digest collision conflicts with immutable authority"
                    )
                publication_completed = True
                _sync_directory_after_publication(self.root)
                published = self._load_path(
                    target,
                    expected_digest=validated.plan_sha256,
                    enforce_name=True,
                )
                if published != validated:
                    raise RuntimeError("Candidate plan publication inspection mismatch")
                return published
            except Exception as exc:
                if publication_completed:
                    raise CleanMemoryPlanRecoveryError(
                        "Candidate plan persistence failed; manual recovery required"
                    ) from exc
                if isinstance(exc, CleanMemoryPlanError):
                    raise
                raise CleanMemoryPlanPersistenceError(
                    "Failed to persist candidate plan"
                ) from exc
            finally:
                # MoveFileEx vacates the Windows source pathname. After a
                # successful move, anything appearing there belongs to another
                # writer and must never be removed. POSIX link publication
                # leaves our owned source in place, so identity-bound cleanup
                # remains necessary there.
                if not publication_completed or os.name != "nt":
                    _unlink_owned_temp(temp_path, owned_temp_identity)
