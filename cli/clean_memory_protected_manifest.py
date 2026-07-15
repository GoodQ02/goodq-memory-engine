"""Authenticate the fixed Windows clean-memory protected manifest.

This module observes one held manifest and returns immutable evidence.  It does
not enroll, publish, compose membership, plan, approve, or clean.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
import hashlib
import json
import os
import re
from typing import Any
import unicodedata

from cli.clean_memory import CONFIGURATION_SCHEMA, ResolvedPlanConfiguration
from cli.clean_memory_external_pin import (
    EXTERNAL_PIN_EVIDENCE_SCHEMA,
    ExternalPinEvidence,
)
from steps.common.clean_memory_protected_manifest import (
    PROTECTED_MANIFEST_CHILD_NAME,
    PROTECTED_MANIFEST_MAX_BYTES,
    CanonicalProtectedManifest,
    validate_protected_manifest,
)
from steps.common.clean_memory_windows_reader_identity import (
    CleanMemoryWindowsReaderIdentityError,
    clean_memory_windows_reader_identity_sha256,
    validate_clean_memory_windows_reader_identity,
)
from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleBackend,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)
from steps.common.windows_security_mechanics import (
    WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
    WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
    WindowsAce,
    WindowsMutationDenial,
    WindowsPinnedSecurityDescriptor,
    WindowsSecurityDescriptor,
    WindowsSecurityMechanics,
    WindowsSecurityMechanicsError,
    WindowsSecuritySession,
    WindowsSid,
    bind_windows_security,
    verify_windows_security_abi,
)


PROTECTED_MANIFEST_EVIDENCE_SCHEMA = (
    "goodq.clean-memory-protected-manifest-evidence.v1"
)

__all__ = (
    "PROTECTED_MANIFEST_EVIDENCE_SCHEMA",
    "ProtectedManifestReaderError",
    "ProtectedManifestEvidence",
    "read_protected_manifest",
)

_ERROR_MESSAGES = {
    "invalid_configuration": (
        "Clean-memory protected manifest configuration is invalid"
    ),
    "invalid_external_pin_evidence": (
        "Clean-memory protected manifest external pin evidence is invalid"
    ),
    "unsupported_platform": "Clean-memory protected manifest reading is unsupported",
    "unsupported_filesystem": "Clean-memory protected manifest storage is unsupported",
    "unsupported_security": (
        "Clean-memory protected manifest security inspection is unsupported"
    ),
    "untrusted_reader": (
        "Clean-memory protected manifest reader is not authorized"
    ),
    "security_policy_mismatch": (
        "Clean-memory protected manifest security policy is invalid"
    ),
    "manifest_missing": "Clean-memory protected manifest is missing",
    "malformed_manifest": "Clean-memory protected manifest payload is invalid",
    "manifest_digest_mismatch": (
        "Clean-memory protected manifest digest does not match the external pin"
    ),
    "redirected_boundary": (
        "Clean-memory protected manifest boundary is redirected"
    ),
    "unexpected_entry_type": (
        "Clean-memory protected manifest entry type is unsupported"
    ),
    "duplicate_identity": (
        "Clean-memory protected manifest identity is ambiguous"
    ),
    "sharing_conflict": "Clean-memory protected manifest is not quiescent",
    "observation_raced": (
        "Clean-memory protected manifest changed during observation"
    ),
    "observation_failed": "Clean-memory protected manifest observation failed",
}
_CONTROL_FLOW_TYPES = (KeyboardInterrupt, SystemExit, GeneratorExit)

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
_EXTERNAL_KEYS = {
    "anchor_identity",
    "dedicated_directory_identities",
    "enrolled_reader_identity_sha256",
    "manifest_sha256",
    "pin_file_identity",
    "platform",
    "schema",
    "security_policy_sha256",
    "source_id",
    "source_schema",
}
_EVIDENCE_KEYS = {
    "anchor_identity",
    "configuration_scope_sha256",
    "external_pin_evidence_sha256",
    "manifest_file_identity",
    "manifest_sha256",
    "platform",
    "route_directory_identities",
    "schema",
    "security_policy_sha256",
}
_IDENTITY_KEYS = {
    "file_id",
    "file_id_kind",
    "object_kind",
    "schema",
    "volume_serial",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_PATH_RE = re.compile(r"^([A-Z]):/(.+)$")
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

_SYSTEM_SID = "S-1-5-18"
_ADMIN_SID = "S-1-5-32-544"
_CREATOR_OWNER_SID = "S-1-3-0"
_MEDIUM_INTEGRITY_SID = "S-1-16-8192"
_FIXED_SID_BINARY = {
    _SYSTEM_SID: bytes.fromhex("010100000000000512000000"),
    _ADMIN_SID: bytes.fromhex("01020000000000052000000020020000"),
    _CREATOR_OWNER_SID: bytes.fromhex("010100000000000300000000"),
    _MEDIUM_INTEGRITY_SID: bytes.fromhex("010100000000001000200000"),
}
_ACCESS_ALLOWED_ACE_TYPE = 0
_MANDATORY_LABEL_ACE_TYPE = 0x11
_DESCRIPTOR_CONTROL = 0xB014

_CANDIDATE_DACL_TEMPLATE = (
    (_ACCESS_ALLOWED_ACE_TYPE, 0x03, 0x001F01FF, _SYSTEM_SID),
    (_ACCESS_ALLOWED_ACE_TYPE, 0x03, 0x001F01FF, _ADMIN_SID),
    (_ACCESS_ALLOWED_ACE_TYPE, 0x00, 0x001200A3, None),
    (_ACCESS_ALLOWED_ACE_TYPE, 0x0D, 0x0013019F, _CREATOR_OWNER_SID),
)
_MANIFEST_DACL_TEMPLATE = (
    (_ACCESS_ALLOWED_ACE_TYPE, 0x00, 0x001F01FF, _SYSTEM_SID),
    (_ACCESS_ALLOWED_ACE_TYPE, 0x00, 0x001F01FF, _ADMIN_SID),
    (_ACCESS_ALLOWED_ACE_TYPE, 0x00, 0x00120089, None),
)
_CANDIDATE_RIGHTS = (
    ("file_add_subdirectory", 0x00000004),
    ("file_write_ea", 0x00000010),
    ("file_delete_child", 0x00000040),
    ("file_write_attributes", 0x00000100),
    ("delete", 0x00010000),
    ("write_dac", 0x00040000),
    ("write_owner", 0x00080000),
)
_MANIFEST_RIGHTS = (
    ("file_write_data", 0x00000002),
    ("file_append_data", 0x00000004),
    ("file_write_ea", 0x00000010),
    ("file_write_attributes", 0x00000100),
    ("delete", 0x00010000),
    ("write_dac", 0x00040000),
    ("write_owner", 0x00080000),
)


class _DuplicateJsonKey(ValueError):
    pass


class ProtectedManifestReaderError(RuntimeError):
    """Fixed, path-free protected-manifest observation failure."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        try:
            message = _ERROR_MESSAGES[code]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Unknown protected manifest reader error code"
            ) from exc
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return self._code

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"code", "_code"} and hasattr(self, "_code"):
            raise AttributeError(
                "Protected manifest reader error code is immutable"
            )
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in {"code", "_code"}:
            raise AttributeError(
                "Protected manifest reader error code is immutable"
            )
        object.__delattr__(self, name)


def _raise(code: str) -> None:
    raise ProtectedManifestReaderError(code) from None


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Canonical JSON value is invalid") from exc


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey
        value[key] = item
    return value


def _reject_nonfinite(_value: str) -> None:
    raise ValueError


def _contains_control(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _validate_json_strings(value: object) -> None:
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value or _contains_control(value):
            raise ValueError
        return
    if type(value) is list:
        for item in value:
            _validate_json_strings(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError
            _validate_json_strings(key)
            _validate_json_strings(item)


def _strict_canonical_json(value: bytes | str) -> dict[str, Any]:
    try:
        text = value.decode("utf-8", "strict") if type(value) is bytes else value
        if type(text) is not str:
            raise ValueError
        parsed = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_nonfinite,
        )
        if type(parsed) is not dict:
            raise ValueError
        _validate_json_strings(parsed)
        canonical = _canonical_json_bytes(parsed).decode("utf-8")
        if canonical != text:
            raise ValueError
        return parsed
    except (
        UnicodeError,
        json.JSONDecodeError,
        _DuplicateJsonKey,
        TypeError,
        ValueError,
        RecursionError,
    ):
        raise ValueError("Canonical JSON projection is invalid") from None


def _windows_path_components(value: object) -> tuple[str, tuple[str, ...]]:
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
        raise ValueError
    match = _WINDOWS_PATH_RE.fullmatch(value)
    if match is None:
        raise ValueError
    drive, remainder = match.groups()
    components = tuple(remainder.split("/"))
    for component in components:
        if (
            component in {"", ".", ".."}
            or component.endswith((".", " "))
            or any(character in '<>:"|?*' for character in component)
            or component.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
        ):
            raise ValueError
    return f"{drive}:/", components


def _validate_identity(
    value: object,
    *,
    object_kind: str,
    volume_serial: str | None = None,
) -> dict[str, str]:
    if type(value) is not dict or set(value) != _IDENTITY_KEYS:
        raise ValueError
    if (
        value.get("schema") != "goodq.windows-file-identity.v1"
        or value.get("object_kind") != object_kind
        or type(value.get("volume_serial")) is not str
        or re.fullmatch(r"[0-9a-f]{16}", value["volume_serial"]) is None
        or int(value["volume_serial"], 16) == 0
        or type(value.get("file_id_kind")) is not str
        or type(value.get("file_id")) is not str
    ):
        raise ValueError
    if value["file_id_kind"] == "ntfs_file_index_64":
        if re.fullmatch(r"[0-9a-f]{16}", value["file_id"]) is None:
            raise ValueError
    elif value["file_id_kind"] == "refs_file_id_128":
        if re.fullmatch(r"[0-9a-f]{32}", value["file_id"]) is None:
            raise ValueError
    else:
        raise ValueError
    if int(value["file_id"], 16) == 0:
        raise ValueError
    if volume_serial is not None and value["volume_serial"] != volume_serial:
        raise ValueError
    return dict(value)


@dataclass(frozen=True)
class _ConfigurationSnapshot:
    projection_json: str
    digest: str
    drive_root: str
    route_components: tuple[str, ...]


@dataclass(frozen=True)
class _ExternalSnapshot:
    projection_bytes: bytes
    digest: str
    manifest_sha256: str
    reader_identity_sha256: str


def _configuration_snapshot(configuration: object) -> _ConfigurationSnapshot:
    if type(configuration) is not ResolvedPlanConfiguration:
        _raise("invalid_configuration")
    control: BaseException | None = None
    control_fallback = ProtectedManifestReaderError("observation_failed")
    try:
        projection_json = configuration._projection_json
        digest = configuration.configuration_scope_sha256
        if type(projection_json) is not str or type(digest) is not str:
            raise ValueError
        if _SHA256_RE.fullmatch(digest) is None:
            raise ValueError
        if hashlib.sha256(projection_json.encode("utf-8")).hexdigest() != digest:
            raise ValueError
        projection = _strict_canonical_json(projection_json)
        if (
            set(projection) != _CONFIGURATION_KEYS
            or projection.get("schema") != CONFIGURATION_SCHEMA
            or projection.get("path_flavor") != "windows"
            or type(projection.get("logical_paths")) is not dict
            or set(projection["logical_paths"]) != _LOGICAL_PATH_KEYS
        ):
            raise ValueError
        logical = projection["logical_paths"]
        drive_root, storage_components = _windows_path_components(
            logical["storage_root"]
        )
        data_drive, data_components = _windows_path_components(logical["data_root"])
        candidate_drive, candidate_components = _windows_path_components(
            logical["candidate_evidence_root"]
        )
        if (
            data_drive != drive_root
            or candidate_drive != drive_root
            or data_components != (*storage_components, "GoodQ_Data")
            or candidate_components
            != (*storage_components, "GoodQ_Data", "control", "clean_memory")
        ):
            raise ValueError
        return _ConfigurationSnapshot(
            projection_json=projection_json,
            digest=digest,
            drive_root=drive_root,
            route_components=candidate_components,
        )
    except ProtectedManifestReaderError:
        raise
    except BaseException as exc:
        if _is_control_flow(exc):
            control = exc
    if control is not None:
        _sanitize_control_links(
            control,
            phase="observation",
            fallback=control_fallback,
        )
        _reraise_preserving_graph(control)
    _raise("invalid_configuration")


def _external_snapshot(evidence: object) -> _ExternalSnapshot:
    if type(evidence) is not ExternalPinEvidence:
        _raise("invalid_external_pin_evidence")
    control: BaseException | None = None
    control_fallback = ProtectedManifestReaderError("observation_failed")
    try:
        projection_bytes = evidence._projection_bytes
        digest = evidence.external_pin_evidence_sha256
        if type(projection_bytes) is not bytes or type(digest) is not str:
            raise ValueError
        if _SHA256_RE.fullmatch(digest) is None:
            raise ValueError
        if hashlib.sha256(projection_bytes).hexdigest() != digest:
            raise ValueError
        projection = _strict_canonical_json(projection_bytes)
        if (
            set(projection) != _EXTERNAL_KEYS
            or projection.get("schema") != EXTERNAL_PIN_EVIDENCE_SCHEMA
            or projection.get("platform") != "windows"
            or projection.get("source_id")
            != "goodq.clean-memory-protected-authority-pin.primary.v1"
            or projection.get("source_schema")
            != "goodq.clean-memory-external-pin-source.v1"
        ):
            raise ValueError
        for key in (
            "enrolled_reader_identity_sha256",
            "manifest_sha256",
            "security_policy_sha256",
        ):
            if type(projection.get(key)) is not str or _SHA256_RE.fullmatch(
                projection[key]
            ) is None:
                raise ValueError
        anchor = _validate_identity(
            projection["anchor_identity"], object_kind="directory"
        )
        volume = anchor["volume_serial"]
        dedicated = projection.get("dedicated_directory_identities")
        if type(dedicated) is not list or len(dedicated) != 3:
            raise ValueError
        identities = [anchor]
        for identity in dedicated:
            identities.append(
                _validate_identity(
                    identity,
                    object_kind="directory",
                    volume_serial=volume,
                )
            )
        identities.append(
            _validate_identity(
                projection["pin_file_identity"],
                object_kind="regular_file",
                volume_serial=volume,
            )
        )
        physical = {
            (item["volume_serial"], item["file_id_kind"], item["file_id"])
            for item in identities
        }
        if len(physical) != 5:
            raise ValueError
        return _ExternalSnapshot(
            projection_bytes=projection_bytes,
            digest=digest,
            manifest_sha256=projection["manifest_sha256"],
            reader_identity_sha256=projection[
                "enrolled_reader_identity_sha256"
            ],
        )
    except ProtectedManifestReaderError:
        raise
    except BaseException as exc:
        if _is_control_flow(exc):
            control = exc
    if control is not None:
        _sanitize_control_links(
            control,
            phase="observation",
            fallback=control_fallback,
        )
        _reraise_preserving_graph(control)
    _raise("invalid_external_pin_evidence")


def _assert_inputs_unchanged(
    configuration: ResolvedPlanConfiguration,
    configuration_snapshot: _ConfigurationSnapshot,
    evidence: ExternalPinEvidence,
    external_snapshot: _ExternalSnapshot,
) -> None:
    failed = False
    try:
        if (
            type(configuration._projection_json) is not str
            or type(configuration.configuration_scope_sha256) is not str
            or type(evidence._projection_bytes) is not bytes
            or type(evidence.external_pin_evidence_sha256) is not str
            or configuration._projection_json
            != configuration_snapshot.projection_json
            or configuration.configuration_scope_sha256
            != configuration_snapshot.digest
            or evidence._projection_bytes != external_snapshot.projection_bytes
            or evidence.external_pin_evidence_sha256 != external_snapshot.digest
        ):
            _raise("observation_raced")
    except ProtectedManifestReaderError:
        raise
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        failed = True
    if failed:
        _raise("observation_raced")


@dataclass(frozen=True, init=False)
class ProtectedManifestEvidence:
    """Immutable evidence with repr-hidden exact manifest bytes."""

    _manifest_bytes: bytes = field(repr=False)
    _projection_bytes: bytes = field(repr=False)
    protected_manifest_evidence_sha256: str

    def __new__(cls):
        raise TypeError("ProtectedManifestEvidence has no public constructor")

    @classmethod
    def _from_projection(
        cls,
        manifest_bytes: bytes,
        projection: dict[str, Any],
        *,
        expected_route_count: int,
    ) -> ProtectedManifestEvidence:
        if type(manifest_bytes) is not bytes:
            raise ValueError("Protected manifest evidence bytes are invalid")
        if type(projection) is not dict or set(projection) != _EVIDENCE_KEYS:
            raise ValueError("Protected manifest evidence projection is invalid")
        if (
            projection.get("schema") != PROTECTED_MANIFEST_EVIDENCE_SCHEMA
            or projection.get("platform") != "windows"
        ):
            raise ValueError("Protected manifest evidence projection is invalid")
        for key in (
            "configuration_scope_sha256",
            "external_pin_evidence_sha256",
            "manifest_sha256",
            "security_policy_sha256",
        ):
            if type(projection.get(key)) is not str or _SHA256_RE.fullmatch(
                projection[key]
            ) is None:
                raise ValueError("Protected manifest evidence projection is invalid")
        if hashlib.sha256(manifest_bytes).hexdigest() != projection["manifest_sha256"]:
            raise ValueError("Protected manifest evidence projection is invalid")
        anchor = _validate_identity(
            projection["anchor_identity"], object_kind="directory"
        )
        route = projection.get("route_directory_identities")
        if type(route) is not list or len(route) != expected_route_count:
            raise ValueError("Protected manifest evidence projection is invalid")
        identities = [anchor]
        for item in route:
            identities.append(
                _validate_identity(
                    item,
                    object_kind="directory",
                    volume_serial=anchor["volume_serial"],
                )
            )
        identities.append(
            _validate_identity(
                projection["manifest_file_identity"],
                object_kind="regular_file",
                volume_serial=anchor["volume_serial"],
            )
        )
        physical = {
            (item["volume_serial"], item["file_id_kind"], item["file_id"])
            for item in identities
        }
        if len(physical) != len(identities):
            raise ValueError("Protected manifest evidence projection is invalid")
        projection_bytes = _canonical_json_bytes(projection)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_manifest_bytes", manifest_bytes)
        object.__setattr__(instance, "_projection_bytes", projection_bytes)
        object.__setattr__(
            instance,
            "protected_manifest_evidence_sha256",
            hashlib.sha256(projection_bytes).hexdigest(),
        )
        return instance

    @property
    def manifest_bytes(self) -> bytes:
        return self._manifest_bytes

    @property
    def projection(self) -> dict[str, Any]:
        value = json.loads(self._projection_bytes.decode("utf-8"))
        if type(value) is not dict:
            raise ValueError("Protected manifest evidence projection is invalid")
        return value


@dataclass(frozen=True)
class _HeldObject:
    role: str
    handle: object
    entry: WindowsDirectoryEntry | None
    snapshot: WindowsObjectSnapshot
    object_kind: str


@dataclass(frozen=True)
class _ParentMembership:
    handle: object
    entries: tuple[WindowsDirectoryEntry, ...]


@dataclass(frozen=True)
class _ObservedPolicy:
    role: str
    held: _HeldObject
    raw: bytes
    pinned: WindowsPinnedSecurityDescriptor | object
    denials: tuple[tuple[str, WindowsMutationDenial], ...]


@dataclass
class _ReadState:
    backend: WindowsHeldHandleBackend | object
    security: WindowsSecurityMechanics | object
    session: WindowsSecuritySession | object
    baseline_snapshot: object
    filesystem: str | None = None
    root: _HeldObject | None = None
    held: list[_HeldObject] = field(default_factory=list)
    parents: list[_ParentMembership] = field(default_factory=list)


def _bind_security() -> WindowsSecurityMechanics:
    try:
        verify_windows_security_abi()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        return bind_windows_security(kernel32=kernel32, advapi32=advapi32)
    except WindowsSecurityMechanicsError:
        raise
    except (AttributeError, OSError) as exc:
        raise WindowsSecurityMechanicsError("unsupported_security") from exc
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise WindowsSecurityMechanicsError("observation_failed") from exc


def _security_error_code(
    error: WindowsSecurityMechanicsError,
    *,
    phase: str,
) -> str:
    if error.code == "thread_token_present":
        return "untrusted_reader" if phase == "baseline" else "observation_raced"
    if error.code in {"unsupported_security", "unsupported_descriptor"}:
        return "unsupported_security"
    return "observation_failed"


def _is_control_flow(error: BaseException) -> bool:
    return isinstance(error, _CONTROL_FLOW_TYPES)


def _public_error_code(error: BaseException, *, phase: str) -> str:
    if phase == "cleanup":
        return "observation_failed"
    if type(error) is ProtectedManifestReaderError:
        return error.code if error.code in _ERROR_MESSAGES else "observation_failed"
    if isinstance(error, WindowsHeldHandleError):
        if phase == "recheck":
            return "observation_raced"
        return error.code if error.code in _ERROR_MESSAGES else "observation_failed"
    if isinstance(error, WindowsSecurityMechanicsError):
        return _security_error_code(error, phase=phase)
    if isinstance(error, CleanMemoryWindowsReaderIdentityError):
        return "untrusted_reader" if phase == "baseline" else "observation_raced"
    return "observation_failed"


def _is_sanitized_public_error_graph(error: BaseException) -> bool:
    visiting: set[int] = set()
    complete: set[int] = set()

    def visit(node: BaseException) -> bool:
        identity = id(node)
        if identity in complete:
            return True
        if identity in visiting or type(node) is not ProtectedManifestReaderError:
            return False
        try:
            message = _ERROR_MESSAGES[node.code]
        except (AttributeError, KeyError, TypeError):
            return False
        if node.args != (message,) or vars(node):
            return False
        visiting.add(identity)
        for linked in (node.__cause__, node.__context__):
            if linked is not None and not visit(linked):
                return False
        visiting.remove(identity)
        complete.add(identity)
        return True

    return visit(error)


def _clone_error_graph(
    error: BaseException,
    *,
    phase: str,
) -> ProtectedManifestReaderError:
    memo: dict[int, ProtectedManifestReaderError] = {}
    visiting: set[int] = set()

    def clone(node: BaseException, remaining: int) -> ProtectedManifestReaderError:
        identity = id(node)
        if remaining <= 0 or identity in visiting:
            return ProtectedManifestReaderError("observation_failed")
        if identity in memo:
            return memo[identity]
        public = ProtectedManifestReaderError(
            _public_error_code(node, phase=phase)
        )
        memo[identity] = public
        visiting.add(identity)
        if node.__cause__ is not None:
            public.__cause__ = clone(node.__cause__, remaining - 1)
        if node.__context__ is not None:
            public.__context__ = clone(node.__context__, remaining - 1)
        public.__suppress_context__ = bool(node.__suppress_context__)
        visiting.remove(identity)
        return public

    return clone(error, 256)


def _sanitize_error(
    error: BaseException,
    *,
    phase: str = "observation",
) -> ProtectedManifestReaderError:
    if (
        type(error) is ProtectedManifestReaderError
        and _is_sanitized_public_error_graph(error)
    ):
        return error
    return _clone_error_graph(error, phase=phase)


def _sanitize_cleanup_error(
    error: BaseException,
    *,
    fallback: ProtectedManifestReaderError,
) -> tuple[ProtectedManifestReaderError, BaseException | None]:
    try:
        return _sanitize_error(error, phase="cleanup"), None
    except BaseException as sanitization_failure:
        if _is_control_flow(sanitization_failure):
            return fallback, sanitization_failure
        return fallback, None


def _append_cleanup(
    head: ProtectedManifestReaderError | None,
    later: ProtectedManifestReaderError | None,
) -> ProtectedManifestReaderError | None:
    if later is None:
        return head
    if head is None:
        return later
    current = head
    remaining = 256
    while remaining:
        remaining -= 1
        if current is later:
            return head
        if type(current.__cause__) is ProtectedManifestReaderError:
            current = current.__cause__
            continue
        if type(current.__context__) is ProtectedManifestReaderError:
            current = current.__context__
            continue
        if current.__cause__ is None:
            current.__cause__ = later
            current.__suppress_context__ = True
        elif current.__context__ is None:
            current.__context__ = later
        return head
    if current is later:
        return head
    if current.__cause__ is None:
        current.__cause__ = later
        current.__suppress_context__ = True
    elif current.__context__ is None:
        current.__context__ = later
    else:
        current.__context__ = later
    return head


def _attach_cleanup(
    primary: BaseException,
    cleanup: ProtectedManifestReaderError | None,
) -> None:
    if cleanup is None:
        return
    if primary.__cause__ is None:
        primary.__cause__ = cleanup
        primary.__suppress_context__ = True
        return
    if primary.__context__ is None:
        primary.__context__ = cleanup
        return
    if type(primary.__context__) is ProtectedManifestReaderError:
        _append_cleanup(primary.__context__, cleanup)
        return
    if type(primary.__cause__) is ProtectedManifestReaderError:
        _append_cleanup(primary.__cause__, cleanup)
        return
    preserved = _sanitize_error(primary.__context__, phase="cleanup")
    primary.__context__ = cleanup
    _append_cleanup(cleanup, preserved)


def _sanitize_control_links(
    error: BaseException,
    *,
    phase: str,
    fallback: ProtectedManifestReaderError,
) -> None:
    raw_cause = error.__cause__
    raw_context = error.__context__
    suppress_context = bool(error.__suppress_context__)
    public_cause: ProtectedManifestReaderError | None = None
    public_context: ProtectedManifestReaderError | None = None
    if raw_cause is not None:
        try:
            public_cause = (
                fallback
                if raw_cause is error
                else _sanitize_error(raw_cause, phase=phase)
            )
        except BaseException:
            public_cause = fallback
    if raw_context is not None:
        if raw_context is raw_cause:
            public_context = public_cause
        else:
            try:
                public_context = (
                    fallback
                    if raw_context is error
                    else _sanitize_error(raw_context, phase=phase)
                )
            except BaseException:
                public_context = fallback
    error.__cause__ = public_cause
    error.__context__ = public_context
    error.__suppress_context__ = suppress_context


def _reraise_preserving_graph(error: BaseException) -> None:
    traceback = error.__traceback__
    cause = error.__cause__
    context = error.__context__
    suppress_context = bool(error.__suppress_context__)
    try:
        raise error.with_traceback(traceback)
    except BaseException:
        error.__cause__ = cause
        error.__context__ = context
        error.__suppress_context__ = suppress_context
        raise


def _raise_after_cleanup(
    primary: BaseException | None,
    cleanup: ProtectedManifestReaderError | None,
    *,
    control_fallback: ProtectedManifestReaderError,
) -> None:
    if primary is None:
        if cleanup is not None:
            _reraise_preserving_graph(cleanup)
        return
    if not _is_control_flow(primary):
        public: ProtectedManifestReaderError | None = None
        sanitization_control: BaseException | None = None
        try:
            public = _sanitize_error(primary)
        except BaseException as sanitization_failure:
            if _is_control_flow(sanitization_failure):
                sanitization_control = sanitization_failure
            else:
                public = control_fallback
        if sanitization_control is not None:
            _sanitize_control_links(
                sanitization_control,
                phase="cleanup",
                fallback=control_fallback,
            )
            _attach_cleanup(sanitization_control, control_fallback)
            _attach_cleanup(sanitization_control, cleanup)
            _reraise_preserving_graph(sanitization_control)
        if public is None:
            public = control_fallback
        _attach_cleanup(public, cleanup)
        _reraise_preserving_graph(public)
    _sanitize_control_links(
        primary,
        phase="cleanup",
        fallback=control_fallback,
    )
    _attach_cleanup(primary, cleanup)
    _reraise_preserving_graph(primary)


def _raise_resolved_cleanup(
    primary: BaseException | None,
    cleanup_control: BaseException | None,
    cleanup: ProtectedManifestReaderError | None,
    *,
    control_fallback: ProtectedManifestReaderError,
) -> None:
    if cleanup_control is None:
        _raise_after_cleanup(
            primary,
            cleanup,
            control_fallback=control_fallback,
        )
        return
    if primary is not None and _is_control_flow(primary):
        public_control, _sanitization_control = _sanitize_cleanup_error(
            cleanup_control,
            fallback=control_fallback,
        )
        linked_cleanup = _append_cleanup(public_control, cleanup)
        _raise_after_cleanup(
            primary,
            linked_cleanup,
            control_fallback=control_fallback,
        )
        return
    linked_cleanup = cleanup
    if primary is not None:
        try:
            public_primary = _sanitize_error(primary)
        except BaseException:
            public_primary = control_fallback
        linked_cleanup = _append_cleanup(public_primary, linked_cleanup)
    _raise_after_cleanup(
        cleanup_control,
        linked_cleanup,
        control_fallback=control_fallback,
    )


def _compare_effective_token(state: _ReadState) -> None:
    try:
        current = state.session.observe_effective()
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc, phase="recheck") from None
    if current != state.baseline_snapshot:
        _raise("observation_raced")


def _validate_reader_identity(
    snapshot: object,
    *,
    change_notify_luid: int,
    expected_digest: str,
    phase: str,
) -> None:
    try:
        validate_clean_memory_windows_reader_identity(
            snapshot,
            profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
            change_notify_luid=change_notify_luid,
        )
        digest = clean_memory_windows_reader_identity_sha256(
            snapshot,
            profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
            change_notify_luid=change_notify_luid,
        )
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc, phase=phase) from None
    if type(digest) is not str or _SHA256_RE.fullmatch(digest) is None:
        _raise("observation_failed")
    if digest != expected_digest:
        _raise("untrusted_reader" if phase == "baseline" else "observation_raced")


def _matching_entries(
    entries: tuple[WindowsDirectoryEntry, ...],
    component: str,
) -> tuple[WindowsDirectoryEntry, ...]:
    key = unicodedata.normalize("NFC", component).casefold()
    return tuple(
        entry
        for entry in entries
        if unicodedata.normalize("NFC", entry.name).casefold() == key
    )


def _enumerate(
    backend: object,
    handle: object,
    filesystem: str,
    *,
    phase: str = "observation",
) -> tuple[WindowsDirectoryEntry, ...]:
    try:
        entries = backend.enumerate_directory(handle, filesystem)
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc, phase=phase) from None
    if type(entries) is not tuple or any(
        type(entry) is not WindowsDirectoryEntry for entry in entries
    ):
        _raise("observation_failed")
    return entries


def _snapshot(
    state: _ReadState,
    held: _HeldObject,
    *,
    phase: str = "observation",
) -> WindowsObjectSnapshot:
    if state.filesystem is None:
        _raise("observation_failed")
    try:
        snapshot = state.backend.snapshot(
            held.handle,
            filesystem=state.filesystem,
            expected=held.entry,
            object_kind=held.object_kind,
            require_stream_contract=True,
        )
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc, phase=phase) from None
    if type(snapshot) is not WindowsObjectSnapshot:
        _raise("observation_failed")
    try:
        _validate_identity(
            snapshot.identity_projection,
            object_kind=held.object_kind,
        )
    except (AttributeError, TypeError, ValueError):
        _raise("observation_raced" if phase == "recheck" else "observation_failed")
    return snapshot


def _acquire_root(state: _ReadState, drive_root: str) -> _HeldObject:
    _compare_effective_token(state)
    try:
        handle = state.backend.open_root(drive_root)
        provisional = _HeldObject(
            "anchor",
            handle,
            None,
            WindowsObjectSnapshot(0, "", 0, "directory", 0, None, 0, 0, 0, 0, 0, 0, ()),
            "directory",
        )
        state.held.append(provisional)
        filesystem = state.backend.volume_filesystem(handle)
        if filesystem not in {"NTFS", "ReFS"}:
            _raise("unsupported_filesystem")
        state.filesystem = filesystem
        snapshot = _snapshot(state, provisional)
        root = _HeldObject("anchor", handle, None, snapshot, "directory")
        state.held[0] = root
        state.root = root
    except ProtectedManifestReaderError:
        raise
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc) from None
    _compare_effective_token(state)
    return root


def _select_child(
    state: _ReadState,
    parent: _HeldObject,
    component: str,
    *,
    role: str,
    directory: bool,
) -> _HeldObject:
    if state.root is None or state.filesystem is None:
        _raise("observation_failed")
    _compare_effective_token(state)
    entries = _enumerate(state.backend, parent.handle, state.filesystem)
    matches = _matching_entries(entries, component)
    if len(matches) > 1:
        _raise("duplicate_identity")
    if not matches:
        before = _snapshot(state, parent)
        first = _enumerate(state.backend, parent.handle, state.filesystem)
        second = _enumerate(state.backend, parent.handle, state.filesystem)
        after = _snapshot(state, parent)
        _compare_effective_token(state)
        if (
            before != after
            or entries != first
            or entries != second
            or _matching_entries(first, component)
            or _matching_entries(second, component)
        ):
            _raise("observation_raced")
        _raise("manifest_missing")
    entry = matches[0]
    if entry.is_reparse:
        _raise("redirected_boundary")
    if entry.is_device or entry.is_directory != directory:
        _raise("unexpected_entry_type")
    try:
        handle = state.backend.open_by_id(
            state.root.handle,
            entry,
            directory=directory,
        )
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc) from None
    provisional = _HeldObject(
        role,
        handle,
        entry,
        state.root.snapshot,
        "directory" if directory else "regular_file",
    )
    state.held.append(provisional)
    snapshot = _snapshot(state, provisional)
    if snapshot.volume_serial != state.root.snapshot.volume_serial:
        _raise("redirected_boundary")
    physical_identity = (
        snapshot.volume_serial,
        snapshot.file_id_kind,
        snapshot.file_id,
    )
    if any(
        (
            prior.snapshot.volume_serial,
            prior.snapshot.file_id_kind,
            prior.snapshot.file_id,
        )
        == physical_identity
        for prior in state.held[:-1]
    ):
        _raise("duplicate_identity")
    selected = _HeldObject(
        role,
        handle,
        entry,
        snapshot,
        provisional.object_kind,
    )
    state.held[-1] = selected
    state.parents.append(_ParentMembership(parent.handle, entries))
    _compare_effective_token(state)
    return selected


def _sid_equal(actual: WindowsSid, expected: WindowsSid | str) -> bool:
    if type(actual) is not WindowsSid:
        return False
    if type(expected) is WindowsSid:
        return actual.binary == expected.binary and actual.numeric == expected.numeric
    expected_binary = _FIXED_SID_BINARY.get(expected)
    return (
        expected_binary is not None
        and actual.binary == expected_binary
        and actual.numeric == expected
    )


def _ace_matches(
    ace: WindowsAce,
    expected: tuple[int, int, int, WindowsSid | str | None],
    *,
    reader_sid: WindowsSid,
) -> bool:
    ace_type, flags, mask, sid = expected
    target = reader_sid if sid is None else sid
    return (
        type(ace) is WindowsAce
        and ace.ace_type == ace_type
        and ace.flags == flags
        and ace.mask == mask
        and _sid_equal(ace.sid, target)
    )


def _validate_descriptor_policy(
    descriptor: object,
    *,
    reader_sid: WindowsSid,
    role: str,
) -> WindowsSecurityDescriptor:
    if type(descriptor) is not WindowsSecurityDescriptor:
        _raise("observation_failed")
    expected_dacl = (
        _CANDIDATE_DACL_TEMPLATE
        if role == "candidate_evidence_root"
        else _MANIFEST_DACL_TEMPLATE
    )
    if (
        descriptor.control != _DESCRIPTOR_CONTROL
        or not _sid_equal(descriptor.owner, _ADMIN_SID)
        or not _sid_equal(descriptor.group, _ADMIN_SID)
        or descriptor.dacl_present is not True
        or descriptor.dacl_null is not False
        or descriptor.dacl_revision != 2
        or len(descriptor.dacl_aces) != len(expected_dacl)
        or any(
            not _ace_matches(ace, expected, reader_sid=reader_sid)
            for ace, expected in zip(descriptor.dacl_aces, expected_dacl)
        )
        or descriptor.sacl_present is not True
        or descriptor.sacl_null is not False
        or descriptor.sacl_revision != 2
        or len(descriptor.mandatory_label_aces) != 1
        or not _ace_matches(
            descriptor.mandatory_label_aces[0],
            (_MANDATORY_LABEL_ACE_TYPE, 0x00, 0x1, _MEDIUM_INTEGRITY_SID),
            reader_sid=reader_sid,
        )
    ):
        _raise("security_policy_mismatch")
    return descriptor


def _run_denial_checks(
    state: _ReadState,
    pinned: object,
    rights: tuple[tuple[str, int], ...],
    *,
    phase: str,
) -> tuple[tuple[str, WindowsMutationDenial], ...]:
    _compare_effective_token(state)
    scope = None
    primary: BaseException | None = None
    results: list[tuple[str, WindowsMutationDenial]] = []
    cleanup_fallback = ProtectedManifestReaderError("observation_failed")
    try:
        scope = state.session.open_access_check(pinned)
        for name, raw_mask in rights:
            result = scope.check_denial(raw_mask=raw_mask)
            if (
                type(result) is not WindowsMutationDenial
                or result.raw_mask != raw_mask
                or result.mapped_mask != raw_mask
                or result.denied is not True
            ):
                _raise(
                    "security_policy_mismatch"
                    if phase == "initial"
                    else "observation_raced"
                )
            results.append((name, result))
    except BaseException as exc:
        primary = exc
    cleanup: ProtectedManifestReaderError | None = None
    cleanup_control: BaseException | None = None
    if scope is not None:
        try:
            scope.close()
        except BaseException as exc:
            if _is_control_flow(exc):
                cleanup_control = exc
            else:
                cleanup, cleanup_control = _sanitize_cleanup_error(
                    exc,
                    fallback=cleanup_fallback,
                )
    _raise_resolved_cleanup(
        primary,
        cleanup_control,
        cleanup,
        control_fallback=cleanup_fallback,
    )
    _compare_effective_token(state)
    return tuple(results)


def _observe_policy(
    state: _ReadState,
    held: _HeldObject,
    *,
    role: str,
    rights: tuple[tuple[str, int], ...],
) -> _ObservedPolicy:
    _compare_effective_token(state)
    try:
        raw = state.backend.read_security_descriptor(held.handle)
        if type(raw) is not bytes:
            _raise("observation_failed")
        pinned = state.security.pin_security_descriptor(
            raw,
            profile=WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
        )
    except ProtectedManifestReaderError:
        raise
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc, phase="descriptor") from None
    baseline_sid = state.baseline_snapshot.user_sid
    if type(baseline_sid) is not WindowsSid:
        _raise("observation_failed")
    _validate_descriptor_policy(
        pinned.observation,
        reader_sid=baseline_sid,
        role=role,
    )
    denials = _run_denial_checks(state, pinned, rights, phase="initial")
    return _ObservedPolicy(role, held, raw, pinned, denials)


def _ace_projection(ace: WindowsAce, *, label: bool = False) -> dict[str, str]:
    return {
        "flags": f"{ace.flags:02x}",
        "mask": f"{ace.mask:08x}",
        "sid": ace.sid.numeric,
        "type": "system_mandatory_label" if label else "access_allowed",
    }


def _policy_object_projection(policy: _ObservedPolicy) -> dict[str, object]:
    descriptor = policy.pinned.observation
    return {
        "dacl": [_ace_projection(ace) for ace in descriptor.dacl_aces],
        "dacl_revision": descriptor.dacl_revision,
        "denied_access_checks": [
            {
                "denied": result.denied,
                "mapped_mask": f"{result.mapped_mask:08x}",
                "name": name,
                "raw_mask": f"{result.raw_mask:08x}",
            }
            for name, result in policy.denials
        ],
        "descriptor_control": f"{descriptor.control:04x}",
        "mandatory_label": {
            "aces": [
                _ace_projection(ace, label=True)
                for ace in descriptor.mandatory_label_aces
            ],
            "acl_revision": descriptor.sacl_revision,
        },
        "owner_sid": descriptor.owner.numeric,
        "physical_identity": policy.held.snapshot.identity_projection,
        "primary_group_sid": descriptor.group.numeric,
        "role": policy.role,
    }


def _security_policy_sha256(
    candidate: _ObservedPolicy,
    manifest: _ObservedPolicy,
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "candidate_evidence_root": _policy_object_projection(candidate),
                "manifest_file": _policy_object_projection(manifest),
                "schema": (
                    "goodq.clean-memory-protected-manifest-security-policy.v1"
                ),
            }
        )
    ).hexdigest()


def _recheck_policy(
    state: _ReadState,
    policy: _ObservedPolicy,
    *,
    rights: tuple[tuple[str, int], ...],
) -> None:
    _compare_effective_token(state)
    try:
        raw = state.backend.read_security_descriptor(policy.held.handle)
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc, phase="recheck") from None
    if type(raw) is not bytes or raw != policy.raw:
        _raise("observation_raced")
    baseline_sid = state.baseline_snapshot.user_sid
    try:
        _validate_descriptor_policy(
            policy.pinned.observation,
            reader_sid=baseline_sid,
            role=policy.role,
        )
    except ProtectedManifestReaderError:
        _raise("observation_raced")
    denials = _run_denial_checks(state, policy.pinned, rights, phase="recheck")
    if denials != policy.denials:
        _raise("observation_raced")


def _read_manifest_bytes(
    state: _ReadState,
    manifest: _HeldObject,
    *,
    expected_sha256: str,
) -> tuple[bytes, str]:
    size = manifest.snapshot.size_bytes
    if type(size) is not int or not 1 <= size <= PROTECTED_MANIFEST_MAX_BYTES:
        _raise("malformed_manifest")
    _compare_effective_token(state)
    try:
        result = state.backend.read_file_bounded(
            manifest.handle,
            maximum_bytes=size + 1,
        )
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        raise _sanitize_error(exc) from None
    if (
        type(result) is not tuple
        or len(result) != 2
        or type(result[0]) is not bytes
        or type(result[1]) is not bool
    ):
        _raise("observation_failed")
    manifest_bytes, eof_observed = result
    if eof_observed is not True or len(manifest_bytes) != size:
        _raise("observation_raced")
    if _snapshot(state, manifest, phase="recheck") != manifest.snapshot:
        _raise("observation_raced")
    _compare_effective_token(state)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != expected_sha256:
        _raise("manifest_digest_mismatch")
    try:
        canonical = validate_protected_manifest(
            manifest_bytes,
            path_flavor="windows",
        )
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _raise("malformed_manifest")
    except BaseException as exc:
        if _is_control_flow(exc):
            raise
        _raise("observation_failed")
    if (
        type(canonical) is not CanonicalProtectedManifest
        or canonical.manifest_sha256 != manifest_sha256
    ):
        _raise("observation_failed")
    return manifest_bytes, manifest_sha256


def _final_recheck(
    state: _ReadState,
    candidate_policy: _ObservedPolicy,
    manifest_policy: _ObservedPolicy,
) -> None:
    _compare_effective_token(state)
    _recheck_policy(state, candidate_policy, rights=_CANDIDATE_RIGHTS)
    _recheck_policy(state, manifest_policy, rights=_MANIFEST_RIGHTS)
    for held in state.held:
        if _snapshot(state, held, phase="recheck") != held.snapshot:
            _raise("observation_raced")
    if state.filesystem is None:
        _raise("observation_failed")
    for parent in state.parents:
        if (
            _enumerate(
                state.backend,
                parent.handle,
                state.filesystem,
                phase="recheck",
            )
            != parent.entries
        ):
            _raise("observation_raced")
    _compare_effective_token(state)


def read_protected_manifest(
    configuration: ResolvedPlanConfiguration,
    *,
    external_pin_evidence: ExternalPinEvidence,
) -> ProtectedManifestEvidence:
    """Read and authenticate the fixed Windows protected manifest."""

    configuration_snapshot = _configuration_snapshot(configuration)
    external_snapshot = _external_snapshot(external_pin_evidence)
    if os.name != "nt":
        _raise("unsupported_platform")

    startup_failure: BaseException | None = None
    startup_control: BaseException | None = None
    startup_fallback = ProtectedManifestReaderError("observation_failed")
    try:
        security = _bind_security()
        backend = WindowsHeldHandleBackend(access_profile="security_read_label")
    except BaseException as exc:
        if _is_control_flow(exc):
            startup_control = exc
        else:
            startup_failure = exc
    if startup_control is not None:
        _sanitize_control_links(
            startup_control,
            phase="startup",
            fallback=startup_fallback,
        )
        _reraise_preserving_graph(startup_control)
    if startup_failure is not None:
        _raise_after_cleanup(
            startup_failure,
            None,
            control_fallback=startup_fallback,
        )

    session: WindowsSecuritySession | object | None = None
    backend_entered = False
    primary: BaseException | None = None
    candidate: ProtectedManifestEvidence | None = None
    backend_cleanup_fallback = ProtectedManifestReaderError("observation_failed")
    session_cleanup_fallback = ProtectedManifestReaderError("observation_failed")
    control_cleanup_fallback = ProtectedManifestReaderError("observation_failed")
    try:
        try:
            change_notify_luid = security.resolve_privilege_luid(
                "SeChangeNotifyPrivilege"
            )
            session = security.open_token_session(
                profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY
            )
            baseline_snapshot = session.baseline_snapshot
        except BaseException as exc:
            if _is_control_flow(exc):
                raise
            raise _sanitize_error(exc, phase="baseline") from None
        _validate_reader_identity(
            baseline_snapshot,
            change_notify_luid=change_notify_luid,
            expected_digest=external_snapshot.reader_identity_sha256,
            phase="baseline",
        )

        entered = backend.__enter__()
        backend_entered = True
        if entered is not backend:
            _raise("observation_failed")
        state = _ReadState(
            backend=backend,
            security=security,
            session=session,
            baseline_snapshot=baseline_snapshot,
        )
        root = _acquire_root(state, configuration_snapshot.drive_root)
        parent = root
        for index, component in enumerate(configuration_snapshot.route_components):
            role = (
                "candidate_evidence_root"
                if index == len(configuration_snapshot.route_components) - 1
                else f"route_directory_{index}"
            )
            parent = _select_child(
                state,
                parent,
                component,
                role=role,
                directory=True,
            )
        candidate_root = parent
        candidate_policy = _observe_policy(
            state,
            candidate_root,
            role="candidate_evidence_root",
            rights=_CANDIDATE_RIGHTS,
        )
        manifest = _select_child(
            state,
            candidate_root,
            PROTECTED_MANIFEST_CHILD_NAME,
            role="manifest_file",
            directory=False,
        )
        manifest_policy = _observe_policy(
            state,
            manifest,
            role="manifest_file",
            rights=_MANIFEST_RIGHTS,
        )
        manifest_bytes, manifest_sha256 = _read_manifest_bytes(
            state,
            manifest,
            expected_sha256=external_snapshot.manifest_sha256,
        )
        _assert_inputs_unchanged(
            configuration,
            configuration_snapshot,
            external_pin_evidence,
            external_snapshot,
        )
        _final_recheck(state, candidate_policy, manifest_policy)
        _validate_reader_identity(
            baseline_snapshot,
            change_notify_luid=change_notify_luid,
            expected_digest=external_snapshot.reader_identity_sha256,
            phase="recheck",
        )
        _assert_inputs_unchanged(
            configuration,
            configuration_snapshot,
            external_pin_evidence,
            external_snapshot,
        )
        route_identities = [
            held.snapshot.identity_projection for held in state.held[1:-1]
        ]
        candidate = ProtectedManifestEvidence._from_projection(
            manifest_bytes,
            {
                "anchor_identity": root.snapshot.identity_projection,
                "configuration_scope_sha256": configuration_snapshot.digest,
                "external_pin_evidence_sha256": external_snapshot.digest,
                "manifest_file_identity": manifest.snapshot.identity_projection,
                "manifest_sha256": manifest_sha256,
                "platform": "windows",
                "route_directory_identities": route_identities,
                "schema": PROTECTED_MANIFEST_EVIDENCE_SCHEMA,
                "security_policy_sha256": _security_policy_sha256(
                    candidate_policy,
                    manifest_policy,
                ),
            },
            expected_route_count=len(configuration_snapshot.route_components),
        )
    except BaseException as exc:
        primary = exc

    cleanup: ProtectedManifestReaderError | None = None
    cleanup_control: BaseException | None = None
    if backend_entered:
        try:
            backend.__exit__(None, None, None)
        except BaseException as exc:
            if _is_control_flow(exc):
                cleanup_control = exc
            else:
                sanitized, sanitization_control = _sanitize_cleanup_error(
                    exc,
                    fallback=backend_cleanup_fallback,
                )
                cleanup = _append_cleanup(cleanup, sanitized)
                if sanitization_control is not None and cleanup_control is None:
                    cleanup_control = sanitization_control
    if session is not None:
        try:
            session.close()
        except BaseException as exc:
            if not _is_control_flow(exc):
                sanitized, sanitization_control = _sanitize_cleanup_error(
                    exc,
                    fallback=session_cleanup_fallback,
                )
                cleanup = _append_cleanup(cleanup, sanitized)
                if sanitization_control is not None and cleanup_control is None:
                    cleanup_control = sanitization_control
            else:
                if cleanup_control is None:
                    cleanup_control = exc
                else:
                    cleanup = _append_cleanup(
                        cleanup,
                        ProtectedManifestReaderError("observation_failed"),
                    )
    _raise_resolved_cleanup(
        primary,
        cleanup_control,
        cleanup,
        control_fallback=control_cleanup_fallback,
    )
    if candidate is None:
        _raise("observation_failed")
    return candidate
