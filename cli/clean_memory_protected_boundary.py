"""Read-only physical observation of authenticated protected membership."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
from typing import Any
import unicodedata

from cli.clean_memory_external_pin import (
    EXTERNAL_PIN_EVIDENCE_SCHEMA,
    ExternalPinEvidence,
)
from cli.clean_memory_protected_membership import (
    PROTECTED_MEMBERSHIP_SCHEMA,
    ProtectedMembershipProjection,
)
from steps.common.clean_memory import (
    PROTECTED_BOUNDARY_ROLES,
    ProtectedBoundaryEvidence,
)
from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleBackend,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)


PROTECTED_BOUNDARY_IDENTITY_SCHEMA = (
    "goodq.clean-memory-protected-boundary-identity.v1"
)

__all__ = (
    "PROTECTED_BOUNDARY_IDENTITY_SCHEMA",
    "ProtectedBoundaryObservationError",
    "observe_protected_boundaries",
)

_ERROR_MESSAGES = {
    "invalid_protected_membership": "Clean-memory protected membership is invalid",
    "invalid_external_pin_evidence": (
        "Clean-memory protected-boundary external pin evidence is invalid"
    ),
    "unsupported_platform": (
        "Clean-memory protected-boundary observation is unsupported"
    ),
    "unsupported_filesystem": (
        "Clean-memory protected-boundary storage is unsupported"
    ),
    "member_missing": "Clean-memory protected-boundary member is missing",
    "redirected_boundary": "Clean-memory protected boundary is redirected",
    "unexpected_entry_type": (
        "Clean-memory protected-boundary entry type is unsupported"
    ),
    "duplicate_identity": (
        "Clean-memory protected-boundary identity is ambiguous"
    ),
    "pin_chain_collision": (
        "Clean-memory protected boundary collides with the external pin chain"
    ),
    "sharing_conflict": "Clean-memory protected boundary is not quiescent",
    "observation_raced": (
        "Clean-memory protected boundary changed during observation"
    ),
    "observation_failed": (
        "Clean-memory protected-boundary observation failed"
    ),
}

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
_MEMBERSHIP_KEYS = {
    "configuration_scope_sha256",
    "manifest",
    "path_flavor",
    "protected_roles",
    "schema",
}
_PIN_KEYS = {
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
_IDENTITY_KEYS = {
    "file_id",
    "file_id_kind",
    "object_kind",
    "schema",
    "volume_serial",
}
_CONFIGURED_POLICIES = {
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


class _DuplicateJsonKey(ValueError):
    pass


@dataclass(frozen=True)
class _MembershipInput:
    projection_json: str
    digest: str
    projection: dict[str, Any]


@dataclass(frozen=True)
class _PinInput:
    projection_bytes: bytes
    digest: str
    projection: dict[str, Any]
    identity_keys: frozenset[tuple[int, str, int | bytes]]


@dataclass(frozen=True)
class _HeldObject:
    path: str
    handle: object
    filesystem: str
    entry: WindowsDirectoryEntry | None
    snapshot: WindowsObjectSnapshot
    object_kind: str


@dataclass
class _ParentState:
    held: _HeldObject
    entries: tuple[WindowsDirectoryEntry, ...]
    before_bytes: bytes
    after_entries: tuple[WindowsDirectoryEntry, ...] | None = None
    after_bytes: bytes | None = None


@dataclass(frozen=True)
class _MemberState:
    role: str
    member_id: str
    object_kind: str
    parent: _ParentState
    component: str
    child_comparison_sha256: str
    held: _HeldObject | None


@dataclass
class _ObservationState:
    backend: object
    membership: _MembershipInput
    pin: _PinInput
    drives: dict[str, _HeldObject]
    objects: dict[str, _HeldObject]
    identity_paths: dict[tuple[int, str, int | bytes], str]
    parents: dict[str, _ParentState]
    members: list[_MemberState]
    member_aliases: set[
        tuple[tuple[int, str, int | bytes], str]
    ]


class ProtectedBoundaryObservationError(RuntimeError):
    """Closed protected-boundary observation failure."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        try:
            message = _ERROR_MESSAGES[code]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Unknown protected-boundary observation error code"
            ) from exc
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return self._code

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"code", "_code"} and hasattr(self, "_code"):
            raise AttributeError(
                "Protected-boundary observation error code is immutable"
            )
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in {"code", "_code"}:
            raise AttributeError(
                "Protected-boundary observation error code is immutable"
            )
        object.__delattr__(self, name)


def _raise(code: str) -> None:
    raise ProtectedBoundaryObservationError(code) from None


def _canonical_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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
            _validate_json_strings(key)
            _validate_json_strings(item)


def _strict_json_text(value: str) -> dict[str, Any]:
    if type(value) is not str:
        raise ValueError
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_nonfinite,
        )
        _validate_json_strings(parsed)
        canonical = _canonical_text(parsed)
    except (
        UnicodeError,
        json.JSONDecodeError,
        _DuplicateJsonKey,
        TypeError,
        ValueError,
        RecursionError,
    ):
        raise ValueError from None
    if type(parsed) is not dict or canonical != value:
        raise ValueError
    return parsed


def _canonical_windows_path(value: object) -> str:
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
    match = _WINDOWS_ABSOLUTE_RE.fullmatch(value)
    if match is None:
        raise ValueError
    for component in match.group(2).split("/"):
        if (
            component in {"", ".", ".."}
            or component.endswith((".", " "))
            or any(character in '<>:"|?*' for character in component)
            or component.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
        ):
            raise ValueError
    return value


def _validate_membership_projection(projection: object) -> dict[str, Any]:
    if type(projection) is not dict or set(projection) != _MEMBERSHIP_KEYS:
        raise ValueError
    if (
        projection.get("schema") != PROTECTED_MEMBERSHIP_SCHEMA
        or projection.get("path_flavor") != "windows"
        or not _SHA256_RE.fullmatch(
            projection.get("configuration_scope_sha256", "")
            if type(projection.get("configuration_scope_sha256")) is str
            else ""
        )
    ):
        raise ValueError
    manifest = projection.get("manifest")
    if (
        type(manifest) is not dict
        or set(manifest) != {"child_name", "sha256"}
        or manifest.get("child_name") != "protected-boundaries.json"
        or type(manifest.get("sha256")) is not str
        or not _SHA256_RE.fullmatch(manifest["sha256"])
    ):
        raise ValueError
    roles = projection.get("protected_roles")
    if (
        type(roles) is not list
        or len(roles) != len(PROTECTED_BOUNDARY_ROLES)
        or tuple(
            record.get("role") if type(record) is dict else None
            for record in roles
        )
        != tuple(PROTECTED_BOUNDARY_ROLES)
    ):
        raise ValueError

    full_paths: set[str] = set()
    prefix_spellings: dict[str, str] = {}
    manifest_members = 0
    for record in roles:
        if type(record) is not dict or set(record) != {"members", "role"}:
            raise ValueError
        role = record["role"]
        members = record["members"]
        if type(members) is not list:
            raise ValueError
        policy = _CONFIGURED_POLICIES.get(role)
        if policy is None:
            if not 1 <= len(members) <= 64:
                raise ValueError
            manifest_members += len(members)
            if manifest_members > 512:
                raise ValueError
        elif len(members) != policy[2]:
            raise ValueError

        previous_id: str | None = None
        for index, member in enumerate(members):
            if type(member) is not dict or set(member) != {
                "absolute_path",
                "member_id",
                "object_kind",
                "presence",
            }:
                raise ValueError
            member_id = member["member_id"]
            if type(member_id) is not str or not _MEMBER_ID_RE.fullmatch(member_id):
                raise ValueError
            if previous_id is not None and member_id <= previous_id:
                raise ValueError
            previous_id = member_id
            if policy is None:
                if (
                    member["object_kind"] != "directory"
                    or member["presence"] not in {"required", "allow_absent"}
                ):
                    raise ValueError
            elif (
                member_id != f"configured_{index:02d}"
                or member["object_kind"] != policy[0]
                or member["presence"] != policy[1]
            ):
                raise ValueError

            path = _canonical_windows_path(member["absolute_path"])
            comparison = unicodedata.normalize("NFC", path).casefold()
            if comparison in full_paths:
                raise ValueError
            full_paths.add(comparison)
            drive = path[:2]
            components = path[3:].split("/")
            for component_index in range(1, len(components) + 1):
                prefix = f"{drive}/{'/'.join(components[:component_index])}"
                prefix_key = unicodedata.normalize("NFC", prefix).casefold()
                prior = prefix_spellings.setdefault(prefix_key, prefix)
                if prior != prefix:
                    raise ValueError
    return projection


def _membership_input(value: object) -> _MembershipInput:
    if type(value) is not ProtectedMembershipProjection:
        raise ValueError
    projection_json = value._projection_json
    digest = value.protected_membership_scope_sha256
    if (
        type(projection_json) is not str
        or type(digest) is not str
        or not _SHA256_RE.fullmatch(digest)
        or hashlib.sha256(projection_json.encode("utf-8")).hexdigest() != digest
    ):
        raise ValueError
    projection = _validate_membership_projection(
        _strict_json_text(projection_json)
    )
    if (
        value._projection_json != projection_json
        or value.protected_membership_scope_sha256 != digest
    ):
        raise ValueError
    return _MembershipInput(projection_json, digest, projection)


def _identity_key(
    value: object,
    *,
    object_kind: str,
) -> tuple[int, str, int | bytes]:
    if (
        type(value) is not dict
        or set(value) != _IDENTITY_KEYS
        or value.get("schema") != "goodq.windows-file-identity.v1"
        or value.get("object_kind") != object_kind
    ):
        raise ValueError
    volume_text = value.get("volume_serial")
    file_id_text = value.get("file_id")
    file_id_kind = value.get("file_id_kind")
    if (
        type(volume_text) is not str
        or not re.fullmatch(r"[0-9a-f]{16}", volume_text)
        or int(volume_text, 16) == 0
        or type(file_id_text) is not str
        or type(file_id_kind) is not str
    ):
        raise ValueError
    if file_id_kind == "ntfs_file_index_64":
        if not re.fullmatch(r"[0-9a-f]{16}", file_id_text):
            raise ValueError
        file_id: int | bytes = int(file_id_text, 16)
        if file_id == 0:
            raise ValueError
    elif file_id_kind == "refs_file_id_128":
        if not re.fullmatch(r"[0-9a-f]{32}", file_id_text):
            raise ValueError
        file_id = bytes.fromhex(file_id_text)
        if file_id == b"\x00" * 16:
            raise ValueError
    else:
        raise ValueError
    return int(volume_text, 16), file_id_kind, file_id


def _validate_pin_projection(
    projection: object,
) -> tuple[dict[str, Any], frozenset[tuple[int, str, int | bytes]]]:
    if type(projection) is not dict or set(projection) != _PIN_KEYS:
        raise ValueError
    if (
        projection.get("schema") != EXTERNAL_PIN_EVIDENCE_SCHEMA
        or projection.get("platform") != "windows"
        or projection.get("source_id")
        != "goodq.clean-memory-protected-authority-pin.primary.v1"
        or projection.get("source_schema")
        != "goodq.clean-memory-external-pin-source.v1"
    ):
        raise ValueError
    for key in (
        "manifest_sha256",
        "enrolled_reader_identity_sha256",
        "security_policy_sha256",
    ):
        digest = projection.get(key)
        if type(digest) is not str or not _SHA256_RE.fullmatch(digest):
            raise ValueError
    dedicated = projection.get("dedicated_directory_identities")
    if type(dedicated) is not list or len(dedicated) != 3:
        raise ValueError
    identity_keys = [
        _identity_key(projection.get("anchor_identity"), object_kind="directory"),
        *(
            _identity_key(item, object_kind="directory")
            for item in dedicated
        ),
        _identity_key(
            projection.get("pin_file_identity"),
            object_kind="regular_file",
        ),
    ]
    if (
        len(set(identity_keys)) != 5
        or len({item[0] for item in identity_keys}) != 1
        or len({item[1] for item in identity_keys}) != 1
    ):
        raise ValueError
    return projection, frozenset(identity_keys)


def _pin_input(value: object) -> _PinInput:
    if type(value) is not ExternalPinEvidence:
        raise ValueError
    projection_bytes = value._projection_bytes
    digest = value.external_pin_evidence_sha256
    if (
        type(projection_bytes) is not bytes
        or type(digest) is not str
        or not _SHA256_RE.fullmatch(digest)
        or hashlib.sha256(projection_bytes).hexdigest() != digest
    ):
        raise ValueError
    try:
        projection_text = projection_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ValueError from None
    projection, identities = _validate_pin_projection(
        _strict_json_text(projection_text)
    )
    if projection_text.encode("utf-8") != projection_bytes:
        raise ValueError
    if (
        value._projection_bytes != projection_bytes
        or value.external_pin_evidence_sha256 != digest
    ):
        raise ValueError
    return _PinInput(projection_bytes, digest, projection, identities)


def _snapshot_identity(
    snapshot: WindowsObjectSnapshot,
) -> tuple[int, str, int | bytes]:
    return snapshot.volume_serial, snapshot.file_id_kind, snapshot.file_id


def _validate_snapshot(
    value: object,
    *,
    filesystem: str,
    entry: WindowsDirectoryEntry | None,
    object_kind: str,
    volume_serial: int | None,
) -> WindowsObjectSnapshot:
    if type(value) is not WindowsObjectSnapshot:
        _raise("observation_failed")
    snapshot = value
    if (
        isinstance(snapshot.volume_serial, bool)
        or type(snapshot.volume_serial) is not int
        or not 0 < snapshot.volume_serial < (1 << 64)
        or snapshot.object_kind != object_kind
        or isinstance(snapshot.size_bytes, bool)
        or type(snapshot.size_bytes) is not int
        or snapshot.size_bytes < 0
        or isinstance(snapshot.allocation_size, bool)
        or type(snapshot.allocation_size) is not int
        or snapshot.allocation_size < 0
        or isinstance(snapshot.link_count, bool)
        or type(snapshot.link_count) is not int
        or snapshot.link_count < 1
        or isinstance(snapshot.attributes, bool)
        or type(snapshot.attributes) is not int
        or not 0 <= snapshot.attributes < (1 << 32)
        or isinstance(snapshot.reparse_tag, bool)
        or type(snapshot.reparse_tag) is not int
        or not 0 <= snapshot.reparse_tag < (1 << 32)
        or isinstance(snapshot.last_write_ticks, bool)
        or type(snapshot.last_write_ticks) is not int
        or isinstance(snapshot.change_ticks, bool)
        or type(snapshot.change_ticks) is not int
        or type(snapshot.streams) is not tuple
    ):
        _raise("observation_failed")
    if snapshot.attributes & 0x400 or snapshot.reparse_tag != 0:
        _raise("redirected_boundary")
    if snapshot.attributes & 0x40:
        _raise("unexpected_entry_type")
    if bool(snapshot.attributes & 0x10) != (object_kind == "directory"):
        _raise("unexpected_entry_type")
    if volume_serial is not None and snapshot.volume_serial != volume_serial:
        _raise("unsupported_filesystem")
    if filesystem == "NTFS":
        if (
            snapshot.file_id_kind != "ntfs_file_index_64"
            or isinstance(snapshot.file_id, bool)
            or type(snapshot.file_id) is not int
            or not 0 < snapshot.file_id < (1 << 64)
        ):
            _raise("duplicate_identity")
    elif filesystem == "ReFS":
        if (
            snapshot.file_id_kind != "refs_file_id_128"
            or type(snapshot.file_id) is not bytes
            or len(snapshot.file_id) != 16
            or snapshot.file_id == b"\x00" * 16
        ):
            _raise("duplicate_identity")
    else:
        _raise("unsupported_filesystem")
    if entry is not None and (
        entry.file_id_kind != snapshot.file_id_kind
        or entry.file_id != snapshot.file_id
    ):
        _raise("observation_raced")
    if object_kind == "directory":
        if snapshot.mtime_ns is not None or snapshot.streams:
            _raise("unexpected_entry_type")
    else:
        if (
            isinstance(snapshot.mtime_ns, bool)
            or type(snapshot.mtime_ns) is not int
            or snapshot.mtime_ns < 0
            or snapshot.link_count != 1
            or len(snapshot.streams) != 1
            or type(snapshot.streams[0]) is not tuple
            or len(snapshot.streams[0]) != 3
            or snapshot.streams[0][0] != "::$DATA"
            or snapshot.streams[0][1] != snapshot.size_bytes
        ):
            _raise(
                "duplicate_identity"
                if snapshot.link_count != 1
                else "unexpected_entry_type"
            )
    for stream in snapshot.streams:
        if (
            type(stream) is not tuple
            or len(stream) != 3
            or type(stream[0]) is not str
            or isinstance(stream[1], bool)
            or type(stream[1]) is not int
            or stream[1] < 0
            or isinstance(stream[2], bool)
            or type(stream[2]) is not int
            or stream[2] < 0
        ):
            _raise("unexpected_entry_type")
    return snapshot


def _comparison_bytes(name: object) -> bytes:
    if (
        type(name) is not str
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or _contains_control(name)
    ):
        _raise("observation_failed")
    return unicodedata.normalize("NFC", name).casefold().encode("utf-8")


def _comparison_sha256(name: object) -> str:
    return hashlib.sha256(_comparison_bytes(name)).hexdigest()


def _entry_kind(entry: WindowsDirectoryEntry) -> str:
    if entry.is_reparse:
        return "redirect"
    if entry.is_device:
        return "device"
    if entry.is_directory:
        return "directory"
    return "regular_file"


def _validate_entry(
    value: object,
    *,
    filesystem: str,
) -> WindowsDirectoryEntry:
    if type(value) is not WindowsDirectoryEntry:
        _raise("observation_failed")
    entry = value
    _comparison_bytes(entry.name)
    if (
        isinstance(entry.attributes, bool)
        or type(entry.attributes) is not int
        or not 0 <= entry.attributes < (1 << 32)
    ):
        _raise("observation_failed")
    if filesystem == "NTFS":
        if (
            entry.file_id_kind != "ntfs_file_index_64"
            or isinstance(entry.file_id, bool)
            or type(entry.file_id) is not int
            or not 0 < entry.file_id < (1 << 64)
        ):
            _raise("duplicate_identity")
    elif filesystem == "ReFS":
        if (
            entry.file_id_kind != "refs_file_id_128"
            or type(entry.file_id) is not bytes
            or len(entry.file_id) != 16
            or entry.file_id == b"\x00" * 16
        ):
            _raise("duplicate_identity")
    else:
        _raise("unsupported_filesystem")
    return entry


def _directory_entry_identity(
    entry: WindowsDirectoryEntry,
    *,
    volume_serial: int,
) -> dict[str, str]:
    rendered_file_id = (
        f"{entry.file_id:016x}"
        if isinstance(entry.file_id, int)
        else entry.file_id.hex()
    )
    return {
        "file_id": rendered_file_id,
        "file_id_kind": entry.file_id_kind,
        "platform": "windows",
        "schema": "goodq.clean-memory-directory-entry-identity.v1",
        "volume_serial": f"{volume_serial:016x}",
    }


def _parent_membership_bytes(
    value: object,
    *,
    filesystem: str,
    volume_serial: int,
) -> tuple[tuple[WindowsDirectoryEntry, ...], bytes]:
    if type(value) is not tuple:
        _raise("observation_failed")
    entries: list[WindowsDirectoryEntry] = []
    projections: list[dict[str, Any]] = []
    comparison_hashes: set[str] = set()
    for raw_entry in value:
        entry = _validate_entry(raw_entry, filesystem=filesystem)
        comparison_digest = _comparison_sha256(entry.name)
        if comparison_digest in comparison_hashes:
            _raise("duplicate_identity")
        comparison_hashes.add(comparison_digest)
        entries.append(entry)
        projections.append(
            {
                "comparison_name_sha256": comparison_digest,
                "entry_identity": _directory_entry_identity(
                    entry,
                    volume_serial=volume_serial,
                ),
                "entry_kind": _entry_kind(entry),
            }
        )
    projections.sort(key=lambda item: item["comparison_name_sha256"])
    membership = {
        "entries": projections,
        "schema": "goodq.clean-memory-parent-membership.v1",
    }
    return tuple(entries), _canonical_text(membership).encode("utf-8")


def _select_entry(
    entries: tuple[WindowsDirectoryEntry, ...],
    component: str,
) -> WindowsDirectoryEntry | None:
    expected = _comparison_bytes(component)
    matches = [
        entry for entry in entries if _comparison_bytes(entry.name) == expected
    ]
    if len(matches) > 1:
        _raise("duplicate_identity")
    return matches[0] if matches else None


def _same_entry_multiset(
    initial: tuple[WindowsDirectoryEntry, ...],
    candidate: object,
) -> bool | None:
    if type(candidate) is not tuple or any(
        type(entry) is not WindowsDirectoryEntry for entry in candidate
    ):
        return None
    remaining = list(candidate)
    for expected in initial:
        for index, observed in enumerate(remaining):
            if observed == expected:
                remaining.pop(index)
                break
        else:
            return False
    return not remaining


def _register_object(state: _ObservationState, held: _HeldObject) -> None:
    identity = _snapshot_identity(held.snapshot)
    if identity in state.pin.identity_keys:
        _raise("pin_chain_collision")
    prior = state.identity_paths.get(identity)
    if prior is not None and prior != held.path:
        _raise("duplicate_identity")
    state.identity_paths[identity] = held.path
    state.objects[held.path] = held


def _drive(state: _ObservationState, drive: str) -> _HeldObject:
    cached = state.drives.get(drive)
    if cached is not None:
        return cached
    handle = state.backend.open_root(f"{drive}\\")
    filesystem = state.backend.volume_filesystem(handle)
    if filesystem not in {"NTFS", "ReFS"}:
        _raise("unsupported_filesystem")
    snapshot = _validate_snapshot(
        state.backend.snapshot(
            handle,
            filesystem=filesystem,
            expected=None,
            object_kind="directory",
            require_stream_contract=True,
        ),
        filesystem=filesystem,
        entry=None,
        object_kind="directory",
        volume_serial=None,
    )
    held = _HeldObject(
        path=f"{drive}/",
        handle=handle,
        filesystem=filesystem,
        entry=None,
        snapshot=snapshot,
        object_kind="directory",
    )
    state.drives[drive] = held
    _register_object(state, held)
    return held


def _parent(state: _ObservationState, held: _HeldObject) -> _ParentState:
    cached = state.parents.get(held.path)
    if cached is not None:
        return cached
    entries, membership_bytes = _parent_membership_bytes(
        state.backend.enumerate_directory(held.handle, held.filesystem),
        filesystem=held.filesystem,
        volume_serial=held.snapshot.volume_serial,
    )
    parent = _ParentState(held, entries, membership_bytes)
    state.parents[held.path] = parent
    return parent


def _open_child(
    state: _ObservationState,
    *,
    drive: _HeldObject,
    parent: _ParentState,
    entry: WindowsDirectoryEntry,
    path: str,
    object_kind: str,
) -> _HeldObject:
    entry_kind = _entry_kind(entry)
    if entry_kind == "redirect":
        _raise("redirected_boundary")
    if entry_kind == "device":
        _raise("unexpected_entry_type")
    if entry_kind != object_kind:
        _raise("unexpected_entry_type")
    handle = state.backend.open_by_id(
        drive.handle,
        entry,
        directory=object_kind == "directory",
    )
    snapshot = _validate_snapshot(
        state.backend.snapshot(
            handle,
            filesystem=drive.filesystem,
            expected=entry,
            object_kind=object_kind,
            require_stream_contract=True,
        ),
        filesystem=drive.filesystem,
        entry=entry,
        object_kind=object_kind,
        volume_serial=drive.snapshot.volume_serial,
    )
    held = _HeldObject(
        path=path,
        handle=handle,
        filesystem=drive.filesystem,
        entry=entry,
        snapshot=snapshot,
        object_kind=object_kind,
    )
    _register_object(state, held)
    return held


def _observe_member(
    state: _ObservationState,
    *,
    role: str,
    member: dict[str, str],
) -> None:
    path = member["absolute_path"]
    drive_name = path[:2]
    drive = _drive(state, drive_name)
    current = drive
    components = path[3:].split("/")
    selected_parent: _ParentState | None = None
    selected: _HeldObject | None = None
    for index, component in enumerate(components):
        final = index == len(components) - 1
        prefix = f"{drive_name}/{'/'.join(components[: index + 1])}"
        expected_kind = member["object_kind"] if final else "directory"
        cached = state.objects.get(prefix)
        if cached is not None:
            if cached.object_kind != expected_kind:
                _raise("unexpected_entry_type")
            if final:
                selected_parent = _parent(state, current)
                selected = cached
            current = cached
            continue
        parent = _parent(state, current)
        entry = _select_entry(parent.entries, component)
        if entry is None:
            if final and member["presence"] == "allow_absent":
                selected_parent = parent
                selected = None
                break
            _raise("member_missing")
        opened = _open_child(
            state,
            drive=drive,
            parent=parent,
            entry=entry,
            path=prefix,
            object_kind=expected_kind,
        )
        if final:
            selected_parent = parent
            selected = opened
        current = opened
    if selected_parent is None:
        _raise("observation_failed")
    child_digest = _comparison_sha256(components[-1])
    alias = (_snapshot_identity(selected_parent.held.snapshot), child_digest)
    if alias in state.member_aliases:
        _raise("duplicate_identity")
    state.member_aliases.add(alias)
    state.members.append(
        _MemberState(
            role=role,
            member_id=member["member_id"],
            object_kind=member["object_kind"],
            parent=selected_parent,
            component=components[-1],
            child_comparison_sha256=child_digest,
            held=selected,
        )
    )


def _inputs_unchanged(
    protected_membership: ProtectedMembershipProjection,
    external_pin_evidence: ExternalPinEvidence,
    membership: _MembershipInput,
    pin: _PinInput,
) -> None:
    try:
        membership_now = _membership_input(protected_membership)
        pin_now = _pin_input(external_pin_evidence)
    except Exception:
        _raise("observation_raced")
    if membership_now != membership or pin_now != pin:
        _raise("observation_raced")


def _final_fence(state: _ObservationState) -> None:
    final_identities: dict[tuple[int, str, int | bytes], str] = {}
    for path, held in state.objects.items():
        raw_snapshot = state.backend.snapshot(
            held.handle,
            filesystem=held.filesystem,
            expected=held.entry,
            object_kind=held.object_kind,
            require_stream_contract=True,
        )
        if (
            type(raw_snapshot) is WindowsObjectSnapshot
            and raw_snapshot != held.snapshot
        ):
            _raise("observation_raced")
        snapshot = _validate_snapshot(
            raw_snapshot,
            filesystem=held.filesystem,
            entry=held.entry,
            object_kind=held.object_kind,
            volume_serial=held.snapshot.volume_serial,
        )
        if snapshot != held.snapshot:
            _raise("observation_raced")
        identity = _snapshot_identity(snapshot)
        if identity in state.pin.identity_keys:
            _raise("observation_raced")
        prior = final_identities.get(identity)
        if prior is not None and prior != path:
            _raise("observation_raced")
        final_identities[identity] = path
    if final_identities != state.identity_paths:
        _raise("observation_raced")

    for parent in state.parents.values():
        raw_entries = state.backend.enumerate_directory(
            parent.held.handle,
            parent.held.filesystem,
        )
        same_entries = _same_entry_multiset(parent.entries, raw_entries)
        if same_entries is False:
            _raise("observation_raced")
        entries, membership_bytes = _parent_membership_bytes(
            raw_entries,
            filesystem=parent.held.filesystem,
            volume_serial=parent.held.snapshot.volume_serial,
        )
        if membership_bytes != parent.before_bytes:
            _raise("observation_raced")
        parent.after_entries = entries
        parent.after_bytes = membership_bytes

    final_aliases: set[tuple[tuple[int, str, int | bytes], str]] = set()
    for member in state.members:
        alias = (
            _snapshot_identity(member.parent.held.snapshot),
            member.child_comparison_sha256,
        )
        if alias in final_aliases:
            _raise("observation_raced")
        final_aliases.add(alias)
        if member.parent.after_entries is None:
            _raise("observation_failed")
        match = _select_entry(member.parent.after_entries, member.component)
        if (member.held is None) != (match is None):
            _raise("observation_raced")
    if final_aliases != state.member_aliases:
        _raise("observation_raced")


def _identity_projection(snapshot: WindowsObjectSnapshot) -> dict[str, str]:
    return dict(snapshot.identity_projection)


def _build_evidence(state: _ObservationState) -> tuple[ProtectedBoundaryEvidence, ...]:
    members_by_role: dict[str, list[dict[str, Any]]] = {
        role: [] for role in PROTECTED_BOUNDARY_ROLES
    }
    for member in state.members:
        absence: dict[str, str] | None = None
        object_identity: dict[str, str] | None = None
        state_value = "present"
        if member.held is None:
            if (
                member.parent.after_bytes is None
                or member.parent.after_bytes != member.parent.before_bytes
            ):
                _raise("observation_raced")
            digest = hashlib.sha256(member.parent.before_bytes).hexdigest()
            absence = {
                "after_membership_sha256": digest,
                "before_membership_sha256": digest,
                "schema": "goodq.clean-memory-stable-absence.v1",
            }
            state_value = "absent"
        else:
            object_identity = _identity_projection(member.held.snapshot)
        members_by_role[member.role].append(
            {
                "absence": absence,
                "child_comparison_sha256": member.child_comparison_sha256,
                "logical_id": f"protected:{member.role}:{member.member_id}",
                "member_id": member.member_id,
                "object_identity": object_identity,
                "object_kind": member.object_kind,
                "parent_identity": _identity_projection(
                    member.parent.held.snapshot
                ),
                "state": state_value,
            }
        )
    result: list[ProtectedBoundaryEvidence] = []
    for role in PROTECTED_BOUNDARY_ROLES:
        logical_id = f"protected:{role}"
        envelope = {
            "logical_id": logical_id,
            "members": members_by_role[role],
            "protected_membership_scope_sha256": state.membership.digest,
            "role": role,
            "schema": PROTECTED_BOUNDARY_IDENTITY_SCHEMA,
        }
        result.append(
            ProtectedBoundaryEvidence(
                role=role,
                logical_id=logical_id,
                identity_json=_canonical_text(envelope),
            )
        )
    return tuple(result)


def _held_code(error: WindowsHeldHandleError, *, phase: str) -> str:
    code = error.code
    selected = {
        "unsupported_platform",
        "unsupported_filesystem",
        "redirected_boundary",
        "unexpected_entry_type",
        "duplicate_identity",
        "sharing_conflict",
        "observation_raced",
        "observation_failed",
    }
    if code not in selected:
        return "observation_failed"
    if phase == "final" and code in {
        "unsupported_filesystem",
        "redirected_boundary",
        "unexpected_entry_type",
        "duplicate_identity",
        "sharing_conflict",
        "observation_raced",
    }:
        return "observation_raced"
    return code


def _closed_code(error: BaseException, *, phase: str) -> str:
    if type(error) is ProtectedBoundaryObservationError:
        if phase == "final" and error.code in {
            "unsupported_filesystem",
            "member_missing",
            "redirected_boundary",
            "unexpected_entry_type",
            "duplicate_identity",
            "pin_chain_collision",
            "sharing_conflict",
        }:
            return "observation_raced"
        return error.code
    if type(error) is WindowsHeldHandleError:
        return _held_code(error, phase=phase)
    return "observation_failed"


def _sanitize_graph(
    error: BaseException,
    *,
    phase: str,
    limit: int = 192,
    fallback: ProtectedBoundaryObservationError | None = None,
) -> ProtectedBoundaryObservationError:
    terminal = (
        ProtectedBoundaryObservationError("observation_failed")
        if fallback is None
        else fallback
    )
    remaining = [limit]
    visiting: set[int] = set()
    complete: dict[int, ProtectedBoundaryObservationError] = {}

    def clone(node: BaseException) -> ProtectedBoundaryObservationError:
        if remaining[0] <= 0 or id(node) in visiting:
            return terminal
        cached = complete.get(id(node))
        if cached is not None:
            return cached
        remaining[0] -= 1
        visiting.add(id(node))
        result = ProtectedBoundaryObservationError(
            _closed_code(node, phase=phase)
        )
        cause = node.__cause__
        context = node.__context__
        if cause is not None:
            result.__cause__ = clone(cause)
            result.__suppress_context__ = True
        if context is not None and context is not cause:
            result.__context__ = clone(context)
        visiting.remove(id(node))
        complete[id(node)] = result
        return result

    try:
        return clone(error)
    except BaseException:
        return terminal


def _sanitize_control_links(
    error: BaseException,
    *,
    phase: str,
    cause_fallback: ProtectedBoundaryObservationError,
    context_fallback: ProtectedBoundaryObservationError,
) -> None:
    cause = error.__cause__
    context = error.__context__
    sanitized_cause = (
        None
        if cause is None
        else _sanitize_graph(cause, phase=phase, fallback=cause_fallback)
    )
    sanitized_context = (
        None
        if context is None
        else sanitized_cause
        if context is cause
        else _sanitize_graph(
            context,
            phase=phase,
            fallback=context_fallback,
        )
    )
    error.__cause__ = sanitized_cause
    error.__context__ = sanitized_context
    if error.__cause__ is not None:
        error.__suppress_context__ = True


def observe_protected_boundaries(
    protected_membership: ProtectedMembershipProjection,
    *,
    external_pin_evidence: ExternalPinEvidence,
) -> tuple[ProtectedBoundaryEvidence, ...]:
    """Observe protected membership without granting cleanup authority."""

    membership: _MembershipInput | None = None
    membership_invalid = False
    try:
        membership = _membership_input(protected_membership)
    except Exception:
        membership_invalid = True
    if membership_invalid or membership is None:
        _raise("invalid_protected_membership")

    pin: _PinInput | None = None
    pin_invalid = False
    try:
        pin = _pin_input(external_pin_evidence)
    except Exception:
        pin_invalid = True
    if pin_invalid or pin is None:
        _raise("invalid_external_pin_evidence")
    if os.name != "nt":
        _raise("unsupported_platform")

    terminal_fallback = ProtectedBoundaryObservationError("observation_failed")
    control_cause_fallback = ProtectedBoundaryObservationError(
        "observation_failed"
    )
    control_context_fallback = ProtectedBoundaryObservationError(
        "observation_failed"
    )
    candidate: tuple[ProtectedBoundaryEvidence, ...] | None = None
    primary: BaseException | None = None
    primary_traceback = None
    phase = "initial"
    try:
        backend = WindowsHeldHandleBackend(access_profile="observation")
        with backend as entered:
            if entered is not backend:
                _raise("observation_failed")
            state = _ObservationState(
                backend=backend,
                membership=membership,
                pin=pin,
                drives={},
                objects={},
                identity_paths={},
                parents={},
                members=[],
                member_aliases=set(),
            )
            for role_record in membership.projection["protected_roles"]:
                for member in role_record["members"]:
                    _observe_member(
                        state,
                        role=role_record["role"],
                        member=member,
                    )
            _inputs_unchanged(
                protected_membership,
                external_pin_evidence,
                membership,
                pin,
            )
            phase = "final"
            _final_fence(state)
            _inputs_unchanged(
                protected_membership,
                external_pin_evidence,
                membership,
                pin,
            )
            phase = "construction"
            candidate = _build_evidence(state)
    except BaseException as error:
        primary = error
        primary_traceback = error.__traceback__

    if primary is not None:
        if type(primary) in {KeyboardInterrupt, SystemExit, GeneratorExit}:
            _sanitize_control_links(
                primary,
                phase=phase,
                cause_fallback=control_cause_fallback,
                context_fallback=control_context_fallback,
            )
            raise primary.with_traceback(primary_traceback)
        sanitized = _sanitize_graph(
            primary,
            phase=phase,
            fallback=terminal_fallback,
        )
        raise sanitized from None
    if candidate is None:
        _raise("observation_failed")
    return candidate
