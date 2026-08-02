"""Passive, fail-closed filesystem observation for clean-memory planning.

The module accepts only the immutable configuration projection produced by
``cli.clean_memory``.  It performs no configuration loading, service access,
evidence persistence, planning, approval, or cleanup mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
import sys
from typing import Any
import unicodedata

from cli.clean_memory import ResolvedPlanConfiguration
from steps.common.clean_memory import FilesystemTargetEvidence
from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleBackend,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)


FILESYSTEM_OBSERVATION_SCHEMA = "goodq.clean-memory-filesystem-observation.v1"
_CONFIGURATION_SCHEMA = "goodq.clean-memory-configuration.v1"

__all__ = (
    "FILESYSTEM_OBSERVATION_SCHEMA",
    "FilesystemObservationError",
    "FilesystemObservation",
    "observe_filesystem",
)

_ERROR_MESSAGES = {
    "invalid_configuration": "Clean-memory filesystem configuration is invalid",
    "unsupported_platform": "Clean-memory filesystem observation is unsupported",
    "unsupported_filesystem": "Clean-memory filesystem does not support the configured storage",
    "required_root_missing": "Clean-memory epoch root is missing",
    "redirected_boundary": "Clean-memory filesystem boundary is redirected",
    "unexpected_entry_type": "Clean-memory filesystem entry type is unsupported",
    "duplicate_identity": "Clean-memory filesystem identity is ambiguous",
    "sharing_conflict": "Clean-memory filesystem target is not quiescent",
    "observation_raced": "Clean-memory filesystem changed during observation",
    "observation_failed": "Clean-memory filesystem observation failed",
}

_TOP_LEVEL_KEYS = {
    "schema",
    "path_flavor",
    "epoch",
    "logical_paths",
    "declared_faiss_paths",
    "qdrant",
    "configured_protected_paths",
    "unresolved_protected_roles",
}
_LOGICAL_PATH_KEYS = {
    "storage_root",
    "data_root",
    "memory_database",
    "memory_database_wal",
    "memory_database_shm",
    "knowledge_graph_database",
    "knowledge_graph_database_wal",
    "knowledge_graph_database_shm",
    "faiss_root",
    "candidate_evidence_root",
}
_SINGLETONS = (
    ("memory_database", "memory.db"),
    ("memory_database_wal", "memory.db-wal"),
    ("memory_database_shm", "memory.db-shm"),
    ("knowledge_graph_database", "knowledge_graph.db"),
    ("knowledge_graph_database_wal", "knowledge_graph.db-wal"),
    ("knowledge_graph_database_shm", "knowledge_graph.db-shm"),
)
_DECLARED_FAISS_KEYS = (
    "clap_id_map_db",
    "clip_id_map_db",
    "dino_id_map_db",
    "faiss_audio_path",
    "faiss_clip_path",
    "faiss_dino_path",
    "faiss_index_path",
)
_QDRANT_ROLES = ("text", "clip", "dino", "audio")
_CONFIGURED_PROTECTED_ROLES = (
    "archive_root",
    "control_root",
    "data_root",
    "failed_media",
    "import_media",
    "model_cache",
    "processed_media",
    "processing_media",
    "qdrant_storage",
    "watchdog_state",
)
_PROTECTED_ROLES = (
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
_WINDOWS_ABSOLUTE_RE = re.compile(r"^([A-Z]):/(.+)$")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class FilesystemObservationError(RuntimeError):
    """Bounded, path-free filesystem observation failure."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        try:
            message = _ERROR_MESSAGES[code]
        except (KeyError, TypeError) as exc:
            raise ValueError("Unknown filesystem observation error code") from exc
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return self._code

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"code", "_code"} and hasattr(self, "_code"):
            raise AttributeError("Filesystem observation error code is immutable")
        object.__setattr__(self, name, value)


@dataclass(frozen=True)
class FilesystemObservation:
    """Immutable path-free filesystem evidence for one configured epoch."""

    schema: str
    configuration_scope_sha256: str
    epoch_id: str
    epoch_root_identity_json: str
    filesystem_targets: tuple[FilesystemTargetEvidence, ...]


@dataclass(frozen=True)
class _Projection:
    canonical_json: str
    configuration_scope_sha256: str
    path_flavor: str
    epoch_id: str
    epoch_root: str
    logical_paths: dict[str, str]


def _raise(code: str, cause: BaseException | None = None) -> None:
    error = FilesystemObservationError(code)
    if cause is None:
        raise error
    raise error from cause


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate projection key")
        result[key] = value
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _strict_json_object(payload: str) -> dict[str, Any]:
    value = json.loads(
        payload,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise ValueError("Projection is not an object")
    if _canonical_json(value) != payload:
        raise ValueError("Projection is not canonical")
    return value


def _validate_component(component: str, *, windows: bool) -> None:
    if (
        not component
        or component in {".", ".."}
        or component != component.strip()
        or unicodedata.normalize("NFC", component) != component
        or "\x00" in component
        or any(ord(character) < 32 or ord(character) == 127 for character in component)
    ):
        raise ValueError("Invalid path component")
    if windows:
        if component.endswith((".", " ")) or any(
            character in '<>:"|?*\\' for character in component
        ):
            raise ValueError("Ambiguous Windows path component")
        if component.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise ValueError("Reserved Windows path component")
    elif "/" in component:
        raise ValueError("Invalid POSIX path component")


def _absolute_components(value: object, *, flavor: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Invalid absolute path")
    if unicodedata.normalize("NFC", value) != value or "\\" in value:
        raise ValueError("Noncanonical absolute path")
    if flavor == "windows":
        match = _WINDOWS_ABSOLUTE_RE.fullmatch(value)
        if match is None:
            raise ValueError("Invalid Windows absolute path")
        parts = tuple(match.group(2).split("/"))
        for part in parts:
            _validate_component(part, windows=True)
        return (f"{match.group(1)}:", *parts)
    if flavor == "posix":
        if not value.startswith("/") or value == "/" or value.endswith("/") or "//" in value:
            raise ValueError("Invalid POSIX absolute path")
        parts = tuple(value[1:].split("/"))
        for part in parts:
            _validate_component(part, windows=False)
        return parts
    raise ValueError("Unknown path flavor")


def _join(root: str, *parts: str) -> str:
    return f"{root}/{'/'.join(parts)}"


def _validate_projected_authority(
    projection: dict[str, Any],
    *,
    flavor: str,
    epoch_id: str,
    epoch_root: str,
    logical: dict[str, str],
) -> None:
    storage_root = logical["storage_root"]
    data_root = logical["data_root"]
    if data_root != _join(storage_root, "GoodQ_Data"):
        raise ValueError("Data-root topology is invalid")
    if epoch_root != _join(data_root, "epochs", epoch_id):
        raise ValueError("Epoch-root topology is invalid")
    if logical["candidate_evidence_root"] != _join(
        data_root, "control", "clean_memory"
    ):
        raise ValueError("Candidate-evidence topology is invalid")

    declared = projection.get("declared_faiss_paths")
    if not isinstance(declared, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in declared.items()
    ):
        raise ValueError("Declared FAISS authority is invalid")
    if not set(declared).issubset(_DECLARED_FAISS_KEYS):
        raise ValueError("Declared FAISS authority is invalid")
    for value in declared.values():
        _absolute_components(value, flavor=flavor)
        if not value.startswith(f"{logical['faiss_root']}/"):
            raise ValueError("Declared FAISS authority escapes its root")

    qdrant = projection.get("qdrant")
    if not isinstance(qdrant, dict) or set(qdrant) != {
        "enabled",
        "endpoint",
        "port",
        "collections",
    }:
        raise ValueError("Qdrant authority is invalid")
    port = qdrant.get("port")
    endpoint = qdrant.get("endpoint")
    if (
        qdrant.get("enabled") is not True
        or isinstance(port, bool)
        or not isinstance(port, int)
        or not 1 <= port <= 65535
        or endpoint not in {
            f"http://127.0.0.1:{port}",
            f"http://[::1]:{port}",
        }
    ):
        raise ValueError("Qdrant authority is invalid")
    collections = qdrant.get("collections")
    expected_collections = [
        {
            "role": role,
            "collection_name": f"goodq_{role}_{epoch_id}",
        }
        for role in _QDRANT_ROLES
    ]
    if collections != expected_collections:
        raise ValueError("Qdrant collection authority is invalid")

    protected = projection.get("configured_protected_paths")
    if not isinstance(protected, list) or len(protected) != len(
        _CONFIGURED_PROTECTED_ROLES
    ):
        raise ValueError("Protected-path authority is invalid")
    observed_roles: list[str] = []
    observed_paths: set[str] = set()
    for record in protected:
        if not isinstance(record, dict) or set(record) != {"role", "paths"}:
            raise ValueError("Protected-path authority is invalid")
        role = record.get("role")
        paths = record.get("paths")
        if (
            not isinstance(role, str)
            or not isinstance(paths, list)
            or not paths
            or any(not isinstance(value, str) for value in paths)
        ):
            raise ValueError("Protected-path authority is invalid")
        observed_roles.append(role)
        for value in paths:
            _absolute_components(value, flavor=flavor)
            comparison = value.casefold() if flavor == "windows" else value
            if comparison in observed_paths:
                raise ValueError("Protected-path authority is ambiguous")
            observed_paths.add(comparison)
    if tuple(observed_roles) != _CONFIGURED_PROTECTED_ROLES:
        raise ValueError("Protected-path role authority is invalid")

    unresolved = projection.get("unresolved_protected_roles")
    expected_unresolved = sorted(
        set(_PROTECTED_ROLES) - set(_CONFIGURED_PROTECTED_ROLES)
    )
    if unresolved != expected_unresolved:
        raise ValueError("Unresolved protected-role authority is invalid")


def _authenticated_projection(configuration: object) -> _Projection:
    if type(configuration) is not ResolvedPlanConfiguration:
        _raise("invalid_configuration")
    try:
        payload = configuration._projection_json
        digest = configuration.configuration_scope_sha256
        if not isinstance(payload, str):
            raise ValueError("Projection payload is not text")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Projection digest is invalid")
        projection = _strict_json_object(payload)
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
            raise ValueError("Projection digest mismatch")
        if set(projection) != _TOP_LEVEL_KEYS or projection.get("schema") != _CONFIGURATION_SCHEMA:
            raise ValueError("Projection schema is invalid")
        flavor = projection.get("path_flavor")
        if flavor not in {"windows", "posix"}:
            raise ValueError("Projection path flavor is invalid")
        epoch = projection.get("epoch")
        logical = projection.get("logical_paths")
        if not isinstance(epoch, dict) or set(epoch) != {"epoch_id", "root"}:
            raise ValueError("Projection epoch is invalid")
        if not isinstance(logical, dict) or set(logical) != _LOGICAL_PATH_KEYS:
            raise ValueError("Projection logical paths are invalid")
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in logical.items()):
            raise ValueError("Projection logical paths are invalid")
        epoch_id = epoch.get("epoch_id")
        epoch_root = epoch.get("root")
        if not isinstance(epoch_id, str) or not re.fullmatch(
            r"epoch_[A-Za-z0-9][A-Za-z0-9._-]{0,121}", epoch_id
        ):
            raise ValueError("Projection epoch ID is invalid")
        _absolute_components(epoch_root, flavor=flavor)
        for value in logical.values():
            _absolute_components(value, flavor=flavor)
        if logical["memory_database"] != _join(epoch_root, "memory.db"):
            raise ValueError("Memory database topology is invalid")
        if logical["memory_database_wal"] != _join(epoch_root, "memory.db-wal"):
            raise ValueError("Memory WAL topology is invalid")
        if logical["memory_database_shm"] != _join(epoch_root, "memory.db-shm"):
            raise ValueError("Memory SHM topology is invalid")
        if logical["knowledge_graph_database"] != _join(epoch_root, "knowledge_graph.db"):
            raise ValueError("Knowledge graph topology is invalid")
        if logical["knowledge_graph_database_wal"] != _join(epoch_root, "knowledge_graph.db-wal"):
            raise ValueError("Knowledge graph WAL topology is invalid")
        if logical["knowledge_graph_database_shm"] != _join(epoch_root, "knowledge_graph.db-shm"):
            raise ValueError("Knowledge graph SHM topology is invalid")
        if logical["faiss_root"] != _join(epoch_root, "faiss"):
            raise ValueError("FAISS topology is invalid")
        _validate_projected_authority(
            projection,
            flavor=flavor,
            epoch_id=epoch_id,
            epoch_root=epoch_root,
            logical=logical,
        )
        if flavor == "windows" and os.name != "nt":
            raise ValueError("Projection path flavor does not match host")
        if flavor == "posix" and os.name != "posix":
            raise ValueError("Projection path flavor does not match host")
    except FilesystemObservationError:
        raise
    except Exception as exc:
        _raise("invalid_configuration", exc)
    return _Projection(
        canonical_json=payload,
        configuration_scope_sha256=digest,
        path_flavor=flavor,
        epoch_id=epoch_id,
        epoch_root=epoch_root,
        logical_paths=dict(logical),
    )


def _assert_projection_unchanged(configuration: ResolvedPlanConfiguration, expected: _Projection) -> None:
    try:
        if (
            configuration._projection_json != expected.canonical_json
            or configuration.configuration_scope_sha256 != expected.configuration_scope_sha256
        ):
            _raise("observation_raced")
    except FilesystemObservationError:
        raise
    except Exception as exc:
        _raise("observation_raced", exc)


def _runtime_platform() -> str:
    if os.name == "nt":
        return "windows"
    if os.name == "posix":
        return "posix"
    return "unsupported"


def _validate_relative_path(value: str) -> None:
    if (
        not value
        or value != value.strip()
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or unicodedata.normalize("NFC", value) != value
    ):
        _raise("unexpected_entry_type")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value in {".", ".."}
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        _raise("unexpected_entry_type")
    for part in path.parts:
        if part.endswith((".", " ")):
            _raise("unexpected_entry_type")
        if part.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            _raise("unexpected_entry_type")


def _identity_json(value: dict[str, str]) -> str:
    return _canonical_json(value)


@dataclass(frozen=True)
class _PosixEntry:
    name: str
    mode: int
    device: int
    inode: int

    @property
    def membership(self) -> tuple[str, int, int, int]:
        return (self.name, stat.S_IFMT(self.mode), self.device, self.inode)


@dataclass
class _PosixDirectory:
    fd: int
    initial: tuple[tuple[str, int, int, int], ...]


def _posix_snapshot(fd: int) -> tuple[tuple[_PosixEntry, ...], tuple[tuple[str, int, int, int], ...]]:
    try:
        with os.scandir(fd) as iterator:
            entries: list[_PosixEntry] = []
            for directory_entry in iterator:
                if directory_entry.name in {".", ".."}:
                    continue
                info = directory_entry.stat(follow_symlinks=False)
                entries.append(
                    _PosixEntry(
                        name=directory_entry.name,
                        mode=info.st_mode,
                        device=info.st_dev,
                        inode=info.st_ino,
                    )
                )
    except OSError as exc:
        _raise("observation_failed", exc)
    entries.sort(key=lambda item: item.name)
    membership = tuple(item.membership for item in entries)
    return tuple(entries), membership


def _posix_find(entries: tuple[_PosixEntry, ...], name: str) -> _PosixEntry | None:
    matches = [entry for entry in entries if entry.name == name]
    if len(matches) > 1:
        _raise("duplicate_identity")
    return matches[0] if matches else None


def _posix_open_child(parent_fd: int, entry: _PosixEntry, *, directory: bool) -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(entry.name, flags, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            _raise("redirected_boundary", exc)
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            _raise("observation_raced", exc)
        _raise("observation_failed", exc)
    try:
        info = os.fstat(fd)
        expected_kind = stat.S_IFDIR if directory else stat.S_IFREG
        if stat.S_IFMT(info.st_mode) != expected_kind:
            _raise("observation_raced")
        if (info.st_dev, info.st_ino) != (entry.device, entry.inode):
            _raise("observation_raced")
    except BaseException:
        _close_posix_fds((fd,))
        raise
    return fd


def _posix_identity(info: os.stat_result, *, object_kind: str) -> str:
    if (
        isinstance(info.st_dev, bool)
        or isinstance(info.st_ino, bool)
        or not isinstance(info.st_dev, int)
        or not isinstance(info.st_ino, int)
        or info.st_dev < 0
        or info.st_ino <= 0
    ):
        _raise("duplicate_identity")
    return _identity_json(
        {
            "device": str(info.st_dev),
            "inode": str(info.st_ino),
            "object_kind": object_kind,
            "schema": "goodq.posix-file-identity.v1",
        }
    )


def _close_posix_fds(fds: tuple[int, ...]) -> None:
    active_type, active_error, active_traceback = sys.exc_info()
    first_close_error: FilesystemObservationError | None = None
    for fd in reversed(fds):
        try:
            os.close(fd)
        except OSError as exc:
            if first_close_error is None:
                first_close_error = FilesystemObservationError("observation_failed")
                first_close_error.__cause__ = exc
    if first_close_error is None:
        return
    if active_type is None or active_error is None:
        raise first_close_error
    first_close_error.__context__ = active_error.__context__
    if active_error.__cause__ is None:
        active_error.__cause__ = first_close_error
        active_error.__suppress_context__ = True
    else:
        active_error.__context__ = first_close_error
    raise active_error.with_traceback(active_traceback)


def _posix_observe_file(
    parent_fd: int,
    entry: _PosixEntry,
    *,
    role: str,
    relative_path: str,
) -> FilesystemTargetEvidence:
    _validate_relative_path(relative_path)
    if stat.S_ISLNK(entry.mode):
        _raise("redirected_boundary")
    if not stat.S_ISREG(entry.mode):
        _raise("unexpected_entry_type")
    fd = _posix_open_child(parent_fd, entry, directory=False)
    try:
        before = os.fstat(fd)
        if before.st_nlink != 1:
            _raise("duplicate_identity")
        if (
            isinstance(before.st_size, bool)
            or not isinstance(before.st_size, int)
            or before.st_size < 0
            or isinstance(before.st_mtime_ns, bool)
            or not isinstance(before.st_mtime_ns, int)
            or before.st_mtime_ns < 0
        ):
            _raise("observation_failed")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
        after = os.fstat(fd)
        before_state = (
            stat.S_IFMT(before.st_mode),
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
        )
        after_state = (
            stat.S_IFMT(after.st_mode),
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
        )
        if before_state != after_state or total != before.st_size:
            _raise("observation_raced")
        identity = _posix_identity(before, object_kind="regular_file")
        return FilesystemTargetEvidence(
            role=role,
            target_type="regular_file",
            relative_path=relative_path,
            exists=True,
            size_bytes=before.st_size,
            mtime_ns=before.st_mtime_ns,
            file_identity_json=identity,
            sha256=digest.hexdigest(),
        )
    except FilesystemObservationError:
        raise
    except OSError as exc:
        _raise("observation_failed", exc)
    finally:
        _close_posix_fds((fd,))


def _absent(role: str, relative_path: str) -> FilesystemTargetEvidence:
    return FilesystemTargetEvidence(
        role=role,
        target_type="regular_file",
        relative_path=relative_path,
        exists=False,
        size_bytes=None,
        mtime_ns=None,
        file_identity_json=None,
        sha256=None,
    )


def _observe_posix(projection: _Projection) -> tuple[str, tuple[FilesystemTargetEvidence, ...]]:
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if (
        any(not hasattr(os, name) for name in required)
        or os.open not in os.supports_dir_fd
        or os.scandir not in os.supports_fd
    ):
        _raise("unsupported_platform")
    components = _absolute_components(projection.epoch_root, flavor="posix")
    root_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    try:
        root_fd = os.open("/", root_flags)
    except OSError as exc:
        _raise("observation_failed", exc)
    directories: list[_PosixDirectory] = []
    open_fds: list[int] = [root_fd]
    try:
        current_fd = root_fd
        for component in components:
            entries, membership = _posix_snapshot(current_fd)
            directories.append(_PosixDirectory(current_fd, membership))
            entry = _posix_find(entries, component)
            if entry is None:
                _second_entries, second_membership = _posix_snapshot(current_fd)
                if second_membership != membership:
                    _raise("observation_raced")
                _raise("required_root_missing")
            if stat.S_ISLNK(entry.mode):
                _raise("redirected_boundary")
            if not stat.S_ISDIR(entry.mode):
                _raise("unexpected_entry_type")
            child_fd = _posix_open_child(current_fd, entry, directory=True)
            open_fds.append(child_fd)
            current_fd = child_fd

        epoch_fd = current_fd
        epoch_info = os.fstat(epoch_fd)
        epoch_identity = _posix_identity(epoch_info, object_kind="directory")
        epoch_entries, epoch_membership = _posix_snapshot(epoch_fd)
        directories.append(_PosixDirectory(epoch_fd, epoch_membership))
        targets: list[FilesystemTargetEvidence] = []
        seen_identities: set[str] = set()

        for role, relative_path in _SINGLETONS:
            entry = _posix_find(epoch_entries, relative_path)
            if entry is None:
                targets.append(_absent(role, relative_path))
                continue
            target = _posix_observe_file(
                epoch_fd,
                entry,
                role=role,
                relative_path=relative_path,
            )
            assert target.file_identity_json is not None
            if target.file_identity_json in seen_identities:
                _raise("duplicate_identity")
            seen_identities.add(target.file_identity_json)
            targets.append(target)

        faiss_entry = _posix_find(epoch_entries, "faiss")
        if faiss_entry is not None:
            if stat.S_ISLNK(faiss_entry.mode):
                _raise("redirected_boundary")
            if not stat.S_ISDIR(faiss_entry.mode):
                _raise("unexpected_entry_type")
            faiss_fd = _posix_open_child(epoch_fd, faiss_entry, directory=True)
            open_fds.append(faiss_fd)

            pending_directories = [(faiss_fd, "faiss")]
            while pending_directories:
                directory_fd, relative_directory = pending_directories.pop()
                entries, membership = _posix_snapshot(directory_fd)
                directories.append(_PosixDirectory(directory_fd, membership))
                child_directories: list[tuple[int, str]] = []
                for entry in entries:
                    relative_path = f"{relative_directory}/{entry.name}"
                    _validate_relative_path(relative_path)
                    if stat.S_ISLNK(entry.mode):
                        _raise("redirected_boundary")
                    if stat.S_ISDIR(entry.mode):
                        child_fd = _posix_open_child(directory_fd, entry, directory=True)
                        open_fds.append(child_fd)
                        child_directories.append((child_fd, relative_path))
                    elif stat.S_ISREG(entry.mode):
                        target = _posix_observe_file(
                            directory_fd,
                            entry,
                            role="faiss_file",
                            relative_path=relative_path,
                        )
                        assert target.file_identity_json is not None
                        if target.file_identity_json in seen_identities:
                            _raise("duplicate_identity")
                        seen_identities.add(target.file_identity_json)
                        targets.append(target)
                    else:
                        _raise("unexpected_entry_type")
                pending_directories.extend(reversed(child_directories))

        for held in directories:
            _entries, membership = _posix_snapshot(held.fd)
            if membership != held.initial:
                _raise("observation_raced")
        singleton_targets = targets[:6]
        faiss_targets = sorted(targets[6:], key=lambda item: item.relative_path)
        return epoch_identity, tuple((*singleton_targets, *faiss_targets))
    finally:
        _close_posix_fds(tuple(open_fds))


@dataclass
class _WindowsDirectory:
    handle: object
    initial: tuple[tuple[str, str, str], ...]


def _filesystem_error_from_windows(
    exc: WindowsHeldHandleError,
) -> FilesystemObservationError:
    error = FilesystemObservationError(exc.code)
    cause = exc.__cause__
    if isinstance(cause, WindowsHeldHandleError):
        cause = _filesystem_error_from_windows(cause)
    if cause is not None:
        error.__cause__ = cause
        error.__suppress_context__ = True
    context = exc.__context__
    if isinstance(context, WindowsHeldHandleError):
        context = _filesystem_error_from_windows(context)
    if context is not None:
        error.__context__ = context
    return error


def _translate_nested_windows_errors(
    exc: FilesystemObservationError,
    seen: set[int] | None = None,
) -> None:
    if seen is None:
        seen = set()
    if id(exc) in seen:
        return
    seen.add(id(exc))
    if isinstance(exc.__cause__, WindowsHeldHandleError):
        exc.__cause__ = _filesystem_error_from_windows(exc.__cause__)
    elif isinstance(exc.__cause__, FilesystemObservationError):
        _translate_nested_windows_errors(exc.__cause__, seen)
    if isinstance(exc.__context__, WindowsHeldHandleError):
        exc.__context__ = _filesystem_error_from_windows(exc.__context__)
    elif isinstance(exc.__context__, FilesystemObservationError):
        _translate_nested_windows_errors(exc.__context__, seen)


def _close_windows_handle(
    api: WindowsHeldHandleBackend,
    handle: object,
) -> None:
    active_type, active_error, active_traceback = sys.exc_info()
    try:
        api.close(handle)
    except WindowsHeldHandleError as exc:
        close_error = _filesystem_error_from_windows(exc)
        if active_type is None or active_error is None:
            raise close_error from close_error.__cause__
        close_error.__context__ = active_error.__context__
        if active_error.__cause__ is None:
            active_error.__cause__ = close_error
            active_error.__suppress_context__ = True
        else:
            active_error.__context__ = close_error
        raise active_error.with_traceback(active_traceback)




def _load_windows_backend() -> WindowsHeldHandleBackend:
    if os.name != "nt":
        _raise("unsupported_platform")
    try:
        return WindowsHeldHandleBackend()
    except WindowsHeldHandleError as exc:
        if exc.__cause__ is None:
            raise FilesystemObservationError(exc.code) from None
        _raise(exc.code, exc.__cause__)
    except Exception as exc:
        _raise("unsupported_platform", exc)


def _windows_membership(
    entries: tuple[WindowsDirectoryEntry, ...],
) -> tuple[tuple[str, str, str], ...]:
    if any(entry.is_device for entry in entries):
        _raise("unexpected_entry_type")
    membership: list[tuple[str, str, str]] = []
    for entry in entries:
        kind = (
            "device"
            if entry.is_device
            else (
                "reparse"
                if entry.is_reparse
                else ("directory" if entry.is_directory else "regular_file")
            )
        )
        rendered_file_id = (
            f"{entry.file_id:016x}"
            if entry.file_id_kind == "ntfs_file_index_64"
            and isinstance(entry.file_id, int)
            else entry.file_id.hex()
            if entry.file_id_kind == "refs_file_id_128"
            and isinstance(entry.file_id, bytes)
            else None
        )
        if rendered_file_id is None:
            _raise("observation_failed")
        membership.append((entry.name, kind, rendered_file_id))
    return tuple(membership)


def _windows_find(
    entries: tuple[WindowsDirectoryEntry, ...],
    name: str,
) -> WindowsDirectoryEntry | None:
    folded = [entry for entry in entries if entry.name.casefold() == name.casefold()]
    exact = [entry for entry in folded if entry.name == name]
    if len(folded) > 1 or (folded and not exact):
        _raise("duplicate_identity")
    return exact[0] if exact else None


def _open_windows_projected_directory(
    api: WindowsHeldHandleBackend,
    *,
    volume_handle: object,
    entry: WindowsDirectoryEntry,
    path: str,
) -> object:
    """Prefer the projected namespace path; retain legacy fake-backend support."""
    opener = getattr(api, "open_directory", None)
    if callable(opener):
        return opener(path)
    return api.open_by_id(volume_handle, entry, directory=True)


def _windows_validate_scope_entries(
    entries: tuple[WindowsDirectoryEntry, ...],
    *,
    relative_directory: str,
) -> None:
    seen_names: set[str] = set()
    seen_identities: set[tuple[str, int | bytes]] = set()
    for entry in entries:
        relative_path = f"{relative_directory}/{entry.name}"
        _validate_relative_path(relative_path)
        folded = entry.name.casefold()
        if folded in seen_names:
            _raise("duplicate_identity")
        seen_names.add(folded)
        identity = (entry.file_id_kind, entry.file_id)
        if identity in seen_identities:
            _raise("duplicate_identity")
        seen_identities.add(identity)


def _windows_observe_file(
    api: WindowsHeldHandleBackend,
    *,
    volume_handle: object,
    parent_handle: object,
    parent_initial: tuple[tuple[str, str, str], ...],
    filesystem: str,
    volume_serial: int,
    entry: WindowsDirectoryEntry,
    role: str,
    relative_path: str,
) -> FilesystemTargetEvidence:
    _validate_relative_path(relative_path)
    if entry.is_reparse:
        _raise("redirected_boundary")
    if entry.is_device:
        _raise("unexpected_entry_type")
    if entry.is_directory:
        _raise("unexpected_entry_type")
    handle = api.open_by_id(volume_handle, entry, directory=False)
    try:
        before = api.snapshot(
            handle,
            filesystem=filesystem,
            expected=entry,
            object_kind="regular_file",
            require_stream_contract=True,
        )
        if before.volume_serial != volume_serial:
            _raise("observation_raced")
        sha256, total = api.hash_file(handle)
        after = api.snapshot(
            handle,
            filesystem=filesystem,
            expected=entry,
            object_kind="regular_file",
            require_stream_contract=True,
        )
        if before != after or total != before.size_bytes:
            _raise("observation_raced")
        if _windows_membership(api.enumerate_directory(parent_handle, filesystem)) != parent_initial:
            _raise("observation_raced")
        return FilesystemTargetEvidence(
            role=role,
            target_type="regular_file",
            relative_path=relative_path,
            exists=True,
            size_bytes=before.size_bytes,
            mtime_ns=before.mtime_ns,
            file_identity_json=before.identity_json,
            sha256=sha256,
        )
    finally:
        _close_windows_handle(api, handle)


def _observe_windows_backend(
    projection: _Projection,
) -> tuple[str, tuple[FilesystemTargetEvidence, ...]]:
    # Keep every opened directory handle. Windows may resolve an otherwise valid
    # file ID through an AppContainer namespace alias, so projected path opens
    # are used for the authority chain and snapshots reject reparse boundaries.
    components = _absolute_components(projection.epoch_root, flavor="windows")
    root = f"{components[0]}\\"
    with _load_windows_backend() as api:
        root_handle = api.open_root(root)
        directories: list[_WindowsDirectory] = []
        filesystem = api.volume_filesystem(root_handle)
        root_state = api.snapshot(
            root_handle,
            filesystem=filesystem,
            expected=None,
            object_kind="directory",
            require_stream_contract=True,
        )
        current_handle = root_handle
        current_path = root
        for component in components[1:]:
            entries = api.enumerate_directory(current_handle, filesystem)
            membership = _windows_membership(entries)
            entry = _windows_find(entries, component)
            if entry is None:
                if _windows_membership(
                    api.enumerate_directory(current_handle, filesystem)
                ) != membership:
                    _raise("observation_raced")
                _raise("required_root_missing")
            if entry.is_reparse:
                _raise("redirected_boundary")
            if not entry.is_directory:
                _raise("unexpected_entry_type")
            current_path = f"{current_path}{component}\\"
            child_handle = _open_windows_projected_directory(
                api,
                volume_handle=root_handle,
                entry=entry,
                path=current_path,
            )
            child_state = api.snapshot(
                child_handle,
                filesystem=filesystem,
                expected=entry,
                object_kind="directory",
                require_stream_contract=True,
            )
            if child_state.volume_serial != root_state.volume_serial:
                _raise("observation_raced")
            current_handle = child_handle

        epoch_handle = current_handle
        epoch_state = api.snapshot(
            epoch_handle,
            filesystem=filesystem,
            expected=None,
            object_kind="directory",
            require_stream_contract=True,
        )
        if epoch_state.volume_serial != root_state.volume_serial:
            _raise("observation_raced")
        epoch_entries = api.enumerate_directory(epoch_handle, filesystem)
        epoch_membership = _windows_membership(epoch_entries)
        directories.append(_WindowsDirectory(epoch_handle, epoch_membership))
        targets: list[FilesystemTargetEvidence] = []
        seen_identities: set[str] = set()

        for role, relative_path in _SINGLETONS:
            entry = _windows_find(epoch_entries, relative_path)
            if entry is None:
                targets.append(_absent(role, relative_path))
                continue
            target = _windows_observe_file(
                api,
                volume_handle=root_handle,
                parent_handle=epoch_handle,
                parent_initial=epoch_membership,
                filesystem=filesystem,
                volume_serial=root_state.volume_serial,
                entry=entry,
                role=role,
                relative_path=relative_path,
            )
            assert target.file_identity_json is not None
            if target.file_identity_json in seen_identities:
                _raise("duplicate_identity")
            seen_identities.add(target.file_identity_json)
            targets.append(target)

        faiss_entry = _windows_find(epoch_entries, "faiss")
        if faiss_entry is not None:
            if faiss_entry.is_reparse:
                _raise("redirected_boundary")
            if not faiss_entry.is_directory:
                _raise("unexpected_entry_type")
            faiss_handle = api.open_by_id(root_handle, faiss_entry, directory=True)
            faiss_state = api.snapshot(
                faiss_handle,
                filesystem=filesystem,
                expected=faiss_entry,
                object_kind="directory",
                require_stream_contract=True,
            )
            if faiss_state.volume_serial != root_state.volume_serial:
                _raise("observation_raced")

            pending_directories = [(faiss_handle, "faiss")]
            while pending_directories:
                directory_handle, relative_directory = pending_directories.pop()
                entries = api.enumerate_directory(directory_handle, filesystem)
                _windows_validate_scope_entries(entries, relative_directory=relative_directory)
                membership = _windows_membership(entries)
                directories.append(_WindowsDirectory(directory_handle, membership))
                child_directories: list[tuple[object, str]] = []
                for entry in entries:
                    relative_path = f"{relative_directory}/{entry.name}"
                    if entry.is_reparse:
                        _raise("redirected_boundary")
                    if entry.is_directory:
                        child_handle = api.open_by_id(root_handle, entry, directory=True)
                        child_state = api.snapshot(
                            child_handle,
                            filesystem=filesystem,
                            expected=entry,
                            object_kind="directory",
                            require_stream_contract=True,
                        )
                        if child_state.volume_serial != root_state.volume_serial:
                            _raise("observation_raced")
                        child_directories.append((child_handle, relative_path))
                    else:
                        target = _windows_observe_file(
                            api,
                            volume_handle=root_handle,
                            parent_handle=directory_handle,
                            parent_initial=membership,
                            filesystem=filesystem,
                            volume_serial=root_state.volume_serial,
                            entry=entry,
                            role="faiss_file",
                            relative_path=relative_path,
                        )
                        assert target.file_identity_json is not None
                        if target.file_identity_json in seen_identities:
                            _raise("duplicate_identity")
                        seen_identities.add(target.file_identity_json)
                        targets.append(target)
                pending_directories.extend(reversed(child_directories))

        for held in directories:
            if _windows_membership(api.enumerate_directory(held.handle, filesystem)) != held.initial:
                _raise("observation_raced")
        singleton_targets = targets[:6]
        faiss_targets = sorted(
            targets[6:],
            key=lambda item: (item.relative_path.casefold(), item.relative_path),
        )
        return epoch_state.identity_json, tuple((*singleton_targets, *faiss_targets))


def _observe_windows(
    projection: _Projection,
) -> tuple[str, tuple[FilesystemTargetEvidence, ...]]:
    translated_error: FilesystemObservationError | None = None
    try:
        return _observe_windows_backend(projection)
    except WindowsHeldHandleError as exc:
        translated_error = _filesystem_error_from_windows(exc)
    except FilesystemObservationError as exc:
        _translate_nested_windows_errors(exc)
        raise
    assert translated_error is not None
    raise translated_error from translated_error.__cause__


def observe_filesystem(configuration: ResolvedPlanConfiguration) -> FilesystemObservation:
    """Observe one exact configured epoch without acquiring cleanup authority."""

    projection = _authenticated_projection(configuration)
    platform = _runtime_platform()
    try:
        if platform == "windows":
            epoch_identity, targets = _observe_windows(projection)
        elif platform == "posix":
            epoch_identity, targets = _observe_posix(projection)
        else:
            _raise("unsupported_platform")
    except FilesystemObservationError:
        raise
    except OSError as exc:
        _raise("observation_failed", exc)
    _assert_projection_unchanged(configuration, projection)
    return FilesystemObservation(
        schema=FILESYSTEM_OBSERVATION_SCHEMA,
        configuration_scope_sha256=projection.configuration_scope_sha256,
        epoch_id=projection.epoch_id,
        epoch_root_identity_json=epoch_identity,
        filesystem_targets=targets,
    )
