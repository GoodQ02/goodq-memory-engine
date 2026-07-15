from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import types
from typing import Any
import unicodedata

import pytest

from cli.clean_memory_external_pin import ExternalPinEvidence
from cli.clean_memory_protected_membership import ProtectedMembershipProjection
from steps.common.clean_memory import (
    FilesystemTargetEvidence,
    PROTECTED_BOUNDARY_ROLES,
    ProtectedBoundaryEvidence,
    QdrantCollectionEvidence,
    ResolvedCleanupScope,
    build_candidate_plan,
)
from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cli" / "clean_memory_protected_boundary.py"

ERRORS = {
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

CONFIGURED_POLICIES = {
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


def _module():
    return importlib.import_module("cli.clean_memory_protected_boundary")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_text(value: object) -> str:
    return _canonical_bytes(value).decode("utf-8")


def _membership_projection() -> dict[str, Any]:
    role_records = []
    for index, role in enumerate(PROTECTED_BOUNDARY_ROLES):
        if role in CONFIGURED_POLICIES:
            object_kind, presence, count = CONFIGURED_POLICIES[role]
            members = [
                {
                    "absolute_path": f"C:/Scope/N{index:02d}{member_index}",
                    "member_id": f"configured_{member_index:02d}",
                    "object_kind": object_kind,
                    "presence": presence,
                }
                for member_index in range(count)
            ]
        else:
            members = [
                {
                    "absolute_path": f"C:/Scope/N{index:02d}",
                    "member_id": "primary",
                    "object_kind": "directory",
                    "presence": "required",
                }
            ]
        role_records.append({"members": members, "role": role})
    return {
        "configuration_scope_sha256": "1" * 64,
        "manifest": {
            "child_name": "protected-boundaries.json",
            "sha256": "2" * 64,
        },
        "path_flavor": "windows",
        "protected_roles": role_records,
        "schema": "goodq.clean-memory-protected-membership.v1",
    }


def _membership(
    projection: dict[str, Any] | None = None,
) -> ProtectedMembershipProjection:
    return ProtectedMembershipProjection._from_projection(
        copy.deepcopy(projection or _membership_projection())
    )


def _identity(
    file_id: int,
    *,
    object_kind: str,
    filesystem: str = "NTFS",
    volume_serial: int = 0x99,
) -> dict[str, str]:
    if filesystem == "NTFS":
        file_id_kind = "ntfs_file_index_64"
        rendered_file_id = f"{file_id:016x}"
    else:
        file_id_kind = "refs_file_id_128"
        rendered_file_id = f"{file_id:032x}"
    return {
        "file_id": rendered_file_id,
        "file_id_kind": file_id_kind,
        "object_kind": object_kind,
        "schema": "goodq.windows-file-identity.v1",
        "volume_serial": f"{volume_serial:016x}",
    }


def _pin_projection(*, filesystem: str = "NTFS") -> dict[str, Any]:
    return {
        "anchor_identity": _identity(
            0x900,
            object_kind="directory",
            filesystem=filesystem,
        ),
        "dedicated_directory_identities": [
            _identity(
                0x901 + index,
                object_kind="directory",
                filesystem=filesystem,
            )
            for index in range(3)
        ],
        "enrolled_reader_identity_sha256": "3" * 64,
        "manifest_sha256": "4" * 64,
        "pin_file_identity": _identity(
            0x904,
            object_kind="regular_file",
            filesystem=filesystem,
        ),
        "platform": "windows",
        "schema": "goodq.clean-memory-external-pin-evidence.v1",
        "security_policy_sha256": "5" * 64,
        "source_id": "goodq.clean-memory-protected-authority-pin.primary.v1",
        "source_schema": "goodq.clean-memory-external-pin-source.v1",
    }


def _forge_pin(projection: dict[str, Any]) -> ExternalPinEvidence:
    payload = _canonical_bytes(projection)
    instance = object.__new__(ExternalPinEvidence)
    object.__setattr__(instance, "_projection_bytes", payload)
    object.__setattr__(
        instance,
        "external_pin_evidence_sha256",
        hashlib.sha256(payload).hexdigest(),
    )
    return instance


def _pin(*, filesystem: str = "NTFS") -> ExternalPinEvidence:
    return ExternalPinEvidence._from_projection(
        _pin_projection(filesystem=filesystem)
    )


def _forbid_backend(monkeypatch: pytest.MonkeyPatch, module) -> list[str]:
    calls: list[str] = []

    def forbidden_backend(*_args: object, **_kwargs: object) -> None:
        calls.append("constructed")
        raise AssertionError("backend constructed before complete preflight")

    monkeypatch.setattr(
        module,
        "WindowsHeldHandleBackend",
        forbidden_backend,
        raising=False,
    )
    return calls


def _assert_preflight_error(
    monkeypatch: pytest.MonkeyPatch,
    *,
    membership: object,
    pin: object,
    code: str,
) -> None:
    module = _module()
    calls = _forbid_backend(monkeypatch, module)
    with pytest.raises(module.ProtectedBoundaryObservationError) as exc_info:
        module.observe_protected_boundaries(
            membership,
            external_pin_evidence=pin,
        )
    assert exc_info.value.code == code
    assert str(exc_info.value) == ERRORS[code]
    assert calls == []


@dataclasses.dataclass(frozen=True)
class _Held:
    path: str


@dataclasses.dataclass
class _Node:
    path: str
    object_kind: str
    snapshot: WindowsObjectSnapshot


def _parent_path(path: str) -> str:
    if path.endswith("/"):
        raise AssertionError("drive root has no parent")
    parent, _separator, _name = path.rpartition("/")
    return f"{parent}/" if len(parent) == 2 else parent


def _final_name(path: str) -> str:
    return path.rsplit("/", 1)[1]


class _World:
    def __init__(
        self,
        membership: ProtectedMembershipProjection,
        *,
        absent_paths: set[str] | None = None,
        filesystems: dict[str, str] | None = None,
    ) -> None:
        self.membership = membership
        self.absent_paths = set(absent_paths or ())
        self.filesystems = dict(filesystems or {"C:": "NTFS"})
        self.nodes: dict[str, _Node] = {}
        self.children: dict[str, dict[str, str]] = {}
        self.events: list[tuple[Any, ...]] = []
        self.backends: list[_FakeBackend] = []
        self.constructor_error: BaseException | None = None
        self.enter_error: BaseException | None = None
        self.enter_result: object | None = None
        self.event_hook = None
        self.failures: dict[tuple[str, str, int], BaseException] = {}
        self.close_failures: dict[str, BaseException] = {}
        self.enumeration_overrides: dict[str, Any] = {}
        self.snapshot_overrides: dict[str, Any] = {}
        self.entry_attribute_overrides: dict[str, int] = {}
        self._next_file_id = 0x100

        projection = membership.projection
        for record in projection["protected_roles"]:
            for member in record["members"]:
                self._add_member(
                    member["absolute_path"],
                    member["object_kind"],
                    absent=member["absolute_path"] in self.absent_paths,
                )

    def _record(self, *event: Any) -> None:
        value = tuple(event)
        self.events.append(value)
        if self.event_hook is not None:
            self.event_hook(value)

    def _file_identity(self, drive: str) -> tuple[str, int | bytes]:
        value = self._next_file_id
        self._next_file_id += 1
        if self.filesystems[drive] == "NTFS":
            return "ntfs_file_index_64", value
        return "refs_file_id_128", value.to_bytes(16, "big")

    def _new_node(self, path: str, object_kind: str) -> None:
        drive = path[:2]
        file_id_kind, file_id = self._file_identity(drive)
        serial = 0x1000 + ord(drive[0])
        attributes = 0x10 if object_kind == "directory" else 0
        size = 0 if object_kind == "directory" else 17
        streams = () if object_kind == "directory" else (("::$DATA", size, size),)
        snapshot = WindowsObjectSnapshot(
            volume_serial=serial,
            file_id_kind=file_id_kind,
            file_id=file_id,
            object_kind=object_kind,
            size_bytes=size,
            mtime_ns=None if object_kind == "directory" else 1_700_000_000_000,
            allocation_size=size,
            link_count=1,
            attributes=attributes,
            reparse_tag=0,
            last_write_ticks=116_444_736_000_000_000 + self._next_file_id,
            change_ticks=116_444_736_000_000_000 + self._next_file_id,
            streams=streams,
        )
        self.nodes[path] = _Node(path, object_kind, snapshot)
        self.children.setdefault(path, {})

    def _ensure_root(self, drive: str) -> str:
        root = f"{drive}/"
        if root not in self.nodes:
            self._new_node(root, "directory")
        return root

    def _add_member(self, path: str, object_kind: str, *, absent: bool) -> None:
        drive = path[:2]
        current = self._ensure_root(drive)
        components = path[3:].split("/")
        for index, component in enumerate(components):
            child = (
                f"{current}{component}"
                if current.endswith("/")
                else f"{current}/{component}"
            )
            final = index == len(components) - 1
            if final and absent:
                return
            kind = object_kind if final else "directory"
            if child not in self.nodes:
                self._new_node(child, kind)
                self.children[current][component] = child
            elif self.nodes[child].object_kind != kind:
                raise AssertionError("fake world path has conflicting kinds")
            current = child

    def member(self, role: str, index: int = 0) -> dict[str, str]:
        record = next(
            item
            for item in self.membership.projection["protected_roles"]
            if item["role"] == role
        )
        return record["members"][index]

    def member_path(self, role: str, index: int = 0) -> str:
        return self.member(role, index)["absolute_path"]

    def entry(self, path: str, *, name: str | None = None) -> WindowsDirectoryEntry:
        node = self.nodes[path]
        snapshot = node.snapshot
        attributes = self.entry_attribute_overrides.get(path, snapshot.attributes)
        return WindowsDirectoryEntry(
            name=_final_name(path) if name is None else name,
            attributes=attributes,
            file_id_kind=snapshot.file_id_kind,
            file_id=snapshot.file_id,
        )

    def normal_entries(self, parent: str) -> tuple[WindowsDirectoryEntry, ...]:
        entries = [
            self.entry(path, name=name)
            for name, path in self.children[parent].items()
            if path in self.nodes
        ]
        entries.sort(key=lambda item: (item.name.casefold(), item.name))
        return tuple(entries)

    def alias_identity(self, target: str, source: str) -> None:
        target_node = self.nodes[target]
        source_snapshot = self.nodes[source].snapshot
        target_node.snapshot = dataclasses.replace(
            target_node.snapshot,
            volume_serial=source_snapshot.volume_serial,
            file_id_kind=source_snapshot.file_id_kind,
            file_id=source_snapshot.file_id,
        )

    def replace_snapshot(self, path: str, **changes: object) -> None:
        self.nodes[path].snapshot = dataclasses.replace(
            self.nodes[path].snapshot,
            **changes,
        )

    def construct(self, *, access_profile: str):
        self._record("construct", access_profile)
        if self.constructor_error is not None:
            raise self.constructor_error
        backend = _FakeBackend(self)
        self.backends.append(backend)
        return backend


class _FakeBackend:
    def __init__(self, world: _World) -> None:
        self.world = world
        self.handles: list[_Held] = []
        self.enumeration_counts: dict[str, int] = {}
        self.snapshot_counts: dict[str, int] = {}
        self._entry_targets: dict[int, str] = {}

    def _count(self, values: dict[str, int], path: str) -> int:
        count = values.get(path, 0) + 1
        values[path] = count
        return count

    def _fail(self, method: str, path: str, count: int) -> None:
        error = self.world.failures.get((method, path, count))
        if error is not None:
            raise error

    def __enter__(self):
        self.world._record("enter")
        if self.world.enter_error is not None:
            raise self.world.enter_error
        return self if self.world.enter_result is None else self.world.enter_result

    @staticmethod
    def _append_cleanup(
        head: WindowsHeldHandleError | None,
        later: WindowsHeldHandleError,
    ) -> WindowsHeldHandleError:
        if head is None:
            return later
        tail = head
        seen: set[int] = set()
        while id(tail) not in seen:
            seen.add(id(tail))
            if type(tail.__cause__) is WindowsHeldHandleError:
                tail = tail.__cause__
                continue
            tail.__cause__ = later
            tail.__suppress_context__ = True
            break
        return head

    def __exit__(self, exc_type, exc, traceback):
        self.world._record("exit", exc_type is not None)
        cleanup: WindowsHeldHandleError | None = None
        while self.handles:
            handle = self.handles[-1]
            try:
                self.close(handle)
            except BaseException as error:
                if self.handles and self.handles[-1] is handle:
                    self.handles.pop()
                normalized = (
                    error
                    if type(error) is WindowsHeldHandleError
                    else WindowsHeldHandleError("observation_failed")
                )
                if isinstance(error, Exception) and error is not normalized:
                    normalized.__cause__ = error
                    normalized.__suppress_context__ = True
                cleanup = self._append_cleanup(cleanup, normalized)
        if exc is None and cleanup is not None:
            raise cleanup
        if exc is not None and cleanup is not None:
            if exc.__cause__ is None:
                exc.__cause__ = cleanup
                exc.__suppress_context__ = True
            elif exc.__context__ is None:
                exc.__context__ = cleanup
            raise exc.with_traceback(traceback)
        return False

    def open_root(self, root: str) -> object:
        self.world._record("open_root", root)
        drive = root[:2]
        path = f"{drive}/"
        count = sum(
            event[:2] == ("open_root", root) for event in self.world.events
        )
        self._fail("open_root", path, count)
        if root != f"{drive}\\" or path not in self.world.nodes:
            raise AssertionError("only a synthetic drive root may be opened by path")
        handle = _Held(path)
        self.handles.append(handle)
        return handle

    def volume_filesystem(self, handle: object) -> str:
        assert type(handle) is _Held
        self.world._record("filesystem", handle.path)
        self._fail("volume_filesystem", handle.path, 1)
        return self.world.filesystems[handle.path[:2]]

    def enumerate_directory(
        self,
        handle: object,
        filesystem: str,
    ) -> tuple[WindowsDirectoryEntry, ...]:
        assert type(handle) is _Held
        count = self._count(self.enumeration_counts, handle.path)
        self.world._record("enumerate", handle.path, filesystem, count)
        self._fail("enumerate_directory", handle.path, count)
        entries = self.world.normal_entries(handle.path)
        override = self.world.enumeration_overrides.get(handle.path)
        if override is not None:
            entries = tuple(override(count, entries))
        for entry in entries:
            for name, path in self.world.children.get(handle.path, {}).items():
                snapshot = self.world.nodes[path].snapshot
                if (
                    name == entry.name
                    and snapshot.file_id_kind == entry.file_id_kind
                    and snapshot.file_id == entry.file_id
                ):
                    self._entry_targets[id(entry)] = path
                    break
        return entries

    def open_by_id(
        self,
        volume_handle: object,
        entry: WindowsDirectoryEntry,
        *,
        directory: bool,
    ) -> object:
        assert type(volume_handle) is _Held
        path = self._entry_targets.get(id(entry))
        if path is None:
            raise AssertionError("fake entry does not identify a synthetic child")
        self.world._record("open_by_id", volume_handle.path, path, directory)
        count = sum(
            event[:3] == ("open_by_id", volume_handle.path, path)
            for event in self.world.events
        )
        self._fail("open_by_id", path, count)
        handle = _Held(path)
        self.handles.append(handle)
        return handle

    def snapshot(
        self,
        handle: object,
        *,
        filesystem: str,
        expected: WindowsDirectoryEntry | None,
        object_kind: str,
        require_stream_contract: bool,
    ) -> WindowsObjectSnapshot:
        assert type(handle) is _Held
        count = self._count(self.snapshot_counts, handle.path)
        self.world._record(
            "snapshot",
            handle.path,
            filesystem,
            None if expected is None else expected.file_id,
            object_kind,
            require_stream_contract,
            count,
        )
        self._fail("snapshot", handle.path, count)
        snapshot = self.world.nodes[handle.path].snapshot
        override = self.world.snapshot_overrides.get(handle.path)
        return snapshot if override is None else override(count, snapshot)

    def close(self, handle: object) -> None:
        assert type(handle) is _Held
        self.world._record("close", handle.path)
        try:
            self.handles.remove(handle)
        except ValueError:
            raise AssertionError("fake handle closed more than once") from None
        error = self.world.close_failures.get(handle.path)
        if error is not None:
            raise error

    def hash_file(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("protected observer must not hash member contents")

    def read_file_bounded(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("protected observer must not read member contents")

    def read_security_descriptor(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("protected observer must not read descriptors")


def _install_world(monkeypatch: pytest.MonkeyPatch, world: _World):
    module = _module()
    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(module, "WindowsHeldHandleBackend", world.construct)
    return module


def _observe_world(
    monkeypatch: pytest.MonkeyPatch,
    world: _World,
    *,
    pin: ExternalPinEvidence | None = None,
) -> tuple[ProtectedBoundaryEvidence, ...]:
    module = _install_world(monkeypatch, world)
    return module.observe_protected_boundaries(
        world.membership,
        external_pin_evidence=pin or _pin(),
    )


def _expect_world_error(
    monkeypatch: pytest.MonkeyPatch,
    world: _World,
    code: str,
    *,
    pin: ExternalPinEvidence | None = None,
):
    module = _install_world(monkeypatch, world)
    with pytest.raises(module.ProtectedBoundaryObservationError) as exc_info:
        module.observe_protected_boundaries(
            world.membership,
            external_pin_evidence=pin or _pin(),
        )
    assert exc_info.value.code == code
    assert str(exc_info.value) == ERRORS[code]
    return module, exc_info.value


def _assert_sanitized_error_graph(module, error: BaseException) -> None:
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        assert type(current) is module.ProtectedBoundaryObservationError
        assert current.code in ERRORS
        rendered = " ".join(
            (str(current), repr(current), repr(current.args), repr(vars(current)))
        )
        assert "C:\\private" not in rendered
        assert "secret-child" not in rendered
        assert "native failure 5" not in rendered
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    assert len(seen) <= 193


def _comparison_sha256(name: str) -> str:
    comparison = unicodedata.normalize("NFC", name).casefold().encode("utf-8")
    return hashlib.sha256(comparison).hexdigest()


def _entry_kind(entry: WindowsDirectoryEntry) -> str:
    if entry.is_reparse:
        return "redirect"
    if entry.is_device:
        return "device"
    return "directory" if entry.is_directory else "regular_file"


def _entry_projection(
    entry: WindowsDirectoryEntry,
    *,
    volume_serial: int,
) -> dict[str, str]:
    file_id = (
        f"{entry.file_id:016x}"
        if isinstance(entry.file_id, int)
        else entry.file_id.hex()
    )
    return {
        "file_id": file_id,
        "file_id_kind": entry.file_id_kind,
        "platform": "windows",
        "schema": "goodq.clean-memory-directory-entry-identity.v1",
        "volume_serial": f"{volume_serial:016x}",
    }


def _parent_membership_projection(world: _World, path: str) -> dict[str, Any]:
    parent_snapshot = world.nodes[path].snapshot
    entries = [
        {
            "comparison_name_sha256": _comparison_sha256(entry.name),
            "entry_identity": _entry_projection(
                entry,
                volume_serial=parent_snapshot.volume_serial,
            ),
            "entry_kind": _entry_kind(entry),
        }
        for entry in world.normal_entries(path)
    ]
    entries.sort(key=lambda item: item["comparison_name_sha256"])
    return {
        "entries": entries,
        "schema": "goodq.clean-memory-parent-membership.v1",
    }


def test_module_exists_with_exact_public_surface_and_import_boundary() -> None:
    assert MODULE_PATH.is_file(), "protected-boundary observer is not implemented"

    module = importlib.import_module("cli.clean_memory_protected_boundary")
    assert module.__all__ == (
        "PROTECTED_BOUNDARY_IDENTITY_SCHEMA",
        "ProtectedBoundaryObservationError",
        "observe_protected_boundaries",
    )
    assert module.PROTECTED_BOUNDARY_IDENTITY_SCHEMA == (
        "goodq.clean-memory-protected-boundary-identity.v1"
    )
    assert tuple(inspect.signature(module.observe_protected_boundaries).parameters) == (
        "protected_membership",
        "external_pin_evidence",
    )
    assert inspect.signature(module.observe_protected_boundaries).parameters[
        "external_pin_evidence"
    ].kind is inspect.Parameter.KEYWORD_ONLY
    signature = inspect.signature(module.observe_protected_boundaries)
    assert signature.parameters["protected_membership"].kind is (
        inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    assert signature.parameters["protected_membership"].default is (
        inspect.Parameter.empty
    )
    assert signature.parameters["external_pin_evidence"].default is (
        inspect.Parameter.empty
    )
    assert signature.parameters["protected_membership"].annotation in {
        "ProtectedMembershipProjection",
        ProtectedMembershipProjection,
    }
    assert signature.parameters["external_pin_evidence"].annotation in {
        "ExternalPinEvidence",
        ExternalPinEvidence,
    }
    assert signature.return_annotation in {
        "tuple[ProtectedBoundaryEvidence, ...]",
        tuple[ProtectedBoundaryEvidence, ...],
    }

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    allowed_project_modules = {
        "cli.clean_memory_external_pin",
        "cli.clean_memory_protected_membership",
        "steps.common.clean_memory",
        "steps.common.windows_held_handle",
    }
    project_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (
            node.module.startswith("cli.")
            or node.module.startswith("steps.")
        )
    }
    assert project_imports <= allowed_project_modules
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module in allowed_project_modules
        and any(alias.name.startswith("_") for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"__import__", "eval", "exec", "open"}
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Import)
        and any(
            alias.name.startswith(("cli.", "steps."))
            and alias.name not in allowed_project_modules
            for alias in node.names
        )
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
        and node.func.attr == "import_module"
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize(("code", "message"), tuple(ERRORS.items()))
def test_error_contract_is_closed_path_free_and_immutable(
    code: str,
    message: str,
) -> None:
    module = _module()
    error = module.ProtectedBoundaryObservationError(code)

    assert type(error) is module.ProtectedBoundaryObservationError
    assert isinstance(error, RuntimeError)
    assert error.code == code
    assert str(error) == message
    assert error.args == (message,)
    with pytest.raises(AttributeError):
        error.code = "observation_failed"
    with pytest.raises(AttributeError):
        error._code = "observation_failed"


@pytest.mark.parametrize("value", [None, "", "unknown", 1, True])
def test_error_rejects_unknown_codes(value: object) -> None:
    module = _module()
    with pytest.raises(
        ValueError,
        match="Unknown protected-boundary observation error code",
    ):
        module.ProtectedBoundaryObservationError(value)


def test_exact_input_types_are_required_before_backend_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = _membership()
    pin = _pin()

    class MembershipSubclass(ProtectedMembershipProjection):
        pass

    membership_subclass = object.__new__(MembershipSubclass)
    object.__setattr__(
        membership_subclass,
        "_projection_json",
        membership._projection_json,
    )
    object.__setattr__(
        membership_subclass,
        "protected_membership_scope_sha256",
        membership.protected_membership_scope_sha256,
    )

    class PinSubclass(ExternalPinEvidence):
        pass

    pin_subclass = object.__new__(PinSubclass)
    object.__setattr__(pin_subclass, "_projection_bytes", pin._projection_bytes)
    object.__setattr__(
        pin_subclass,
        "external_pin_evidence_sha256",
        pin.external_pin_evidence_sha256,
    )

    for invalid in (object(), membership_subclass):
        _assert_preflight_error(
            monkeypatch,
            membership=invalid,
            pin=pin,
            code="invalid_protected_membership",
        )
    for invalid in (object(), pin_subclass):
        _assert_preflight_error(
            monkeypatch,
            membership=membership,
            pin=invalid,
            code="invalid_external_pin_evidence",
        )


def _mutate_membership(projection: dict[str, Any], mutation: str) -> None:
    roles = projection["protected_roles"]
    first_member = roles[0]["members"][0]
    if mutation == "extra_top_key":
        projection["extra"] = None
    elif mutation == "schema":
        projection["schema"] = "goodq.clean-memory-protected-membership.v2"
    elif mutation == "configuration_digest":
        projection["configuration_scope_sha256"] = "A" * 64
    elif mutation == "manifest_shape":
        projection["manifest"]["extra"] = None
    elif mutation == "manifest_child":
        projection["manifest"]["child_name"] = "other.json"
    elif mutation == "manifest_digest":
        projection["manifest"]["sha256"] = "B" * 64
    elif mutation == "path_flavor":
        projection["path_flavor"] = "posix"
    elif mutation == "role_order":
        roles[0], roles[1] = roles[1], roles[0]
    elif mutation == "role_shape":
        roles[0]["extra"] = None
    elif mutation == "role_name":
        roles[0]["role"] = "other"
    elif mutation == "member_shape":
        first_member["extra"] = None
    elif mutation == "configured_member_id":
        first_member["member_id"] = "primary"
    elif mutation == "configured_kind":
        first_member["object_kind"] = "regular_file"
    elif mutation == "configured_presence":
        first_member["presence"] = "required"
    elif mutation == "configured_count":
        roles[0]["members"].append(copy.deepcopy(first_member))
    elif mutation == "manifest_member_id":
        roles[1]["members"][0]["member_id"] = "Bad-ID"
    elif mutation == "manifest_kind":
        roles[1]["members"][0]["object_kind"] = "regular_file"
    elif mutation == "manifest_count":
        roles[1]["members"] = []
    elif mutation == "watchdog_count":
        roles[-1]["members"].pop()
    elif mutation == "member_order":
        roles[-1]["members"].reverse()
    elif mutation == "noncanonical_path":
        first_member["absolute_path"] = r"C:\Scope\N000"
    elif mutation == "path_alias":
        roles[1]["members"][0]["absolute_path"] = first_member[
            "absolute_path"
        ].swapcase()
    else:
        raise AssertionError(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_top_key",
        "schema",
        "configuration_digest",
        "manifest_shape",
        "manifest_child",
        "manifest_digest",
        "path_flavor",
        "role_order",
        "role_shape",
        "role_name",
        "member_shape",
        "configured_member_id",
        "configured_kind",
        "configured_presence",
        "configured_count",
        "manifest_member_id",
        "manifest_kind",
        "manifest_count",
        "watchdog_count",
        "member_order",
        "noncanonical_path",
        "path_alias",
    ],
)
def test_self_consistent_membership_forgeries_fail_preflight(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    projection = _membership_projection()
    _mutate_membership(projection, mutation)
    forged = _membership(projection)

    _assert_preflight_error(
        monkeypatch,
        membership=forged,
        pin=_pin(),
        code="invalid_protected_membership",
    )


@pytest.mark.parametrize("mutation", ["noncanonical_bytes", "digest_mismatch"])
def test_membership_private_bytes_and_digest_are_authenticated(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    forged = _membership()
    if mutation == "noncanonical_bytes":
        object.__setattr__(
            forged,
            "_projection_json",
            f"{forged._projection_json}\n",
        )
        object.__setattr__(
            forged,
            "protected_membership_scope_sha256",
            hashlib.sha256(forged._projection_json.encode("utf-8")).hexdigest(),
        )
    else:
        object.__setattr__(
            forged,
            "protected_membership_scope_sha256",
            "0" * 64,
        )

    _assert_preflight_error(
        monkeypatch,
        membership=forged,
        pin=_pin(),
        code="invalid_protected_membership",
    )


def _mutate_pin(projection: dict[str, Any], mutation: str) -> None:
    identities = [
        projection["anchor_identity"],
        *projection["dedicated_directory_identities"],
        projection["pin_file_identity"],
    ]
    if mutation == "extra_top_key":
        projection["extra"] = None
    elif mutation == "schema":
        projection["schema"] = "goodq.clean-memory-external-pin-evidence.v2"
    elif mutation == "platform":
        projection["platform"] = "posix"
    elif mutation == "source_id":
        projection["source_id"] = "other"
    elif mutation == "source_schema":
        projection["source_schema"] = "other"
    elif mutation == "manifest_digest":
        projection["manifest_sha256"] = "A" * 64
    elif mutation == "reader_digest":
        projection["enrolled_reader_identity_sha256"] = "B" * 64
    elif mutation == "security_digest":
        projection["security_policy_sha256"] = "C" * 64
    elif mutation == "identity_census":
        projection["dedicated_directory_identities"].pop()
    elif mutation == "identity_shape":
        identities[0]["extra"] = None
    elif mutation == "identity_schema":
        identities[0]["schema"] = "other"
    elif mutation == "volume_zero":
        identities[0]["volume_serial"] = "0" * 16
    elif mutation == "volume_upper":
        identities[0]["volume_serial"] = "A" * 16
    elif mutation == "file_id_zero":
        identities[0]["file_id"] = "0" * len(identities[0]["file_id"])
    elif mutation == "file_id_upper":
        identities[0]["file_id"] = "A" * len(identities[0]["file_id"])
    elif mutation == "file_id_length":
        identities[0]["file_id"] = "1"
    elif mutation == "file_id_kind":
        identities[0]["file_id_kind"] = "other"
    elif mutation == "directory_kind":
        identities[0]["object_kind"] = "regular_file"
    elif mutation == "pin_kind":
        identities[-1]["object_kind"] = "directory"
    elif mutation == "duplicate":
        projection["dedicated_directory_identities"][0] = copy.deepcopy(
            projection["anchor_identity"]
        )
    elif mutation == "cross_volume":
        identities[1]["volume_serial"] = "0000000000000098"
    elif mutation == "mixed_filesystem":
        identities[1]["file_id_kind"] = "refs_file_id_128"
        identities[1]["file_id"] = "1" * 32
    else:
        raise AssertionError(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_top_key",
        "schema",
        "platform",
        "source_id",
        "source_schema",
        "manifest_digest",
        "reader_digest",
        "security_digest",
        "identity_census",
        "identity_shape",
        "identity_schema",
        "volume_zero",
        "volume_upper",
        "file_id_zero",
        "file_id_upper",
        "file_id_length",
        "file_id_kind",
        "directory_kind",
        "pin_kind",
        "duplicate",
        "cross_volume",
        "mixed_filesystem",
    ],
)
def test_self_consistent_pin_forgeries_fail_preflight(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    projection = _pin_projection()
    _mutate_pin(projection, mutation)
    forged = _forge_pin(projection)

    _assert_preflight_error(
        monkeypatch,
        membership=_membership(),
        pin=forged,
        code="invalid_external_pin_evidence",
    )


@pytest.mark.parametrize("mutation", ["noncanonical_bytes", "digest_mismatch"])
def test_pin_private_bytes_and_digest_are_authenticated(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    forged = _pin()
    if mutation == "noncanonical_bytes":
        object.__setattr__(
            forged,
            "_projection_bytes",
            forged._projection_bytes + b"\n",
        )
        object.__setattr__(
            forged,
            "external_pin_evidence_sha256",
            hashlib.sha256(forged._projection_bytes).hexdigest(),
        )
    else:
        object.__setattr__(
            forged,
            "external_pin_evidence_sha256",
            "0" * 64,
        )

    _assert_preflight_error(
        monkeypatch,
        membership=_membership(),
        pin=forged,
        code="invalid_external_pin_evidence",
    )


@pytest.mark.parametrize("filesystem", ["NTFS", "ReFS"])
def test_both_selected_pin_identity_forms_reach_platform_gate(
    monkeypatch: pytest.MonkeyPatch,
    filesystem: str,
) -> None:
    module = _module()
    calls = _forbid_backend(monkeypatch, module)
    monkeypatch.setattr(module.os, "name", "posix")

    with pytest.raises(module.ProtectedBoundaryObservationError) as exc_info:
        module.observe_protected_boundaries(
            _membership(),
            external_pin_evidence=_pin(filesystem=filesystem),
        )

    assert exc_info.value.code == "unsupported_platform"
    assert calls == []


def test_configured_membership_path_has_no_unselected_utf8_length_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _membership_projection()
    projection["protected_roles"][0]["members"][0]["absolute_path"] = (
        "C:/" + "/".join(f"Segment{index:04d}" for index in range(400))
    )
    assert len(
        projection["protected_roles"][0]["members"][0][
            "absolute_path"
        ].encode("utf-8")
    ) > 4096
    module = _module()
    calls = _forbid_backend(monkeypatch, module)
    monkeypatch.setattr(module, "os", types.SimpleNamespace(name="posix"))

    with pytest.raises(module.ProtectedBoundaryObservationError) as exc_info:
        module.observe_protected_boundaries(
            _membership(projection),
            external_pin_evidence=_pin(),
        )

    assert exc_info.value.code == "unsupported_platform"
    assert calls == []


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("path", "C:/forbidden"),
        ("identity", (1, "ntfs_file_index_64", 2)),
        ("locator", object()),
        ("configuration", object()),
        ("manifest", b"{}"),
        ("backend", object()),
        ("digest", "0" * 64),
        ("override", object()),
    ],
)
def test_caller_cannot_supply_path_identity_or_backend_authority(
    keyword: str,
    value: object,
) -> None:
    module = _module()
    with pytest.raises(TypeError):
        module.observe_protected_boundaries(
            _membership(),
            external_pin_evidence=_pin(),
            **{keyword: value},
        )


def test_backend_enter_identity_is_checked_and_context_still_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    world.enter_result = object()

    _expect_world_error(monkeypatch, world, "observation_failed")

    assert [event for event in world.events if event[0] == "construct"] == [
        ("construct", "observation")
    ]
    assert ("exit", True) in world.events


def test_observation_returns_exact_atomic_18_role_evidence_from_held_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = _membership()
    archive_path = next(
        record["members"][0]["absolute_path"]
        for record in membership.projection["protected_roles"]
        if record["role"] == "archive_root"
    )
    world = _World(membership, absent_paths={archive_path})

    evidence = _observe_world(monkeypatch, world)

    assert type(evidence) is tuple
    assert len(evidence) == 18
    assert tuple(item.role for item in evidence) == tuple(PROTECTED_BOUNDARY_ROLES)
    assert all(type(item) is ProtectedBoundaryEvidence for item in evidence)
    assert sum(
        len(json.loads(item.identity_json)["members"]) for item in evidence
    ) == 19
    assert world.events[0] == ("construct", "observation")
    assert world.events[1] == ("enter",)
    assert [event for event in world.events if event[0] == "open_root"] == [
        ("open_root", "C:\\")
    ]
    assert all(
        event[2].startswith("C:/")
        for event in world.events
        if event[0] == "open_by_id"
    )
    assert sum(
        event[0] == "open_by_id" and event[2] == "C:/Scope"
        for event in world.events
    ) == 1
    assert world.events[-1][0] == "close"
    assert ("exit", False) in world.events

    for item, role_record in zip(
        evidence,
        membership.projection["protected_roles"],
    ):
        envelope = json.loads(item.identity_json)
        assert item.logical_id == f"protected:{item.role}"
        assert item.identity_json == _canonical_text(envelope)
        assert set(envelope) == {
            "logical_id",
            "members",
            "protected_membership_scope_sha256",
            "role",
            "schema",
        }
        assert envelope["schema"] == (
            "goodq.clean-memory-protected-boundary-identity.v1"
        )
        assert envelope["role"] == item.role == role_record["role"]
        assert envelope["logical_id"] == item.logical_id
        assert envelope["protected_membership_scope_sha256"] == (
            membership.protected_membership_scope_sha256
        )
        assert [member["member_id"] for member in envelope["members"]] == [
            member["member_id"] for member in role_record["members"]
        ]
        for observed, selected in zip(envelope["members"], role_record["members"]):
            assert set(observed) == {
                "absence",
                "child_comparison_sha256",
                "logical_id",
                "member_id",
                "object_identity",
                "object_kind",
                "parent_identity",
                "state",
            }
            assert observed["logical_id"] == (
                f"protected:{item.role}:{selected['member_id']}"
            )
            assert observed["object_kind"] == selected["object_kind"]
            assert observed["child_comparison_sha256"] == _comparison_sha256(
                _final_name(selected["absolute_path"])
            )
            assert observed["parent_identity"]["schema"] == (
                "goodq.windows-file-identity.v1"
            )
            if selected["absolute_path"] == archive_path:
                assert observed["state"] == "absent"
                assert observed["object_identity"] is None
                parent = _parent_path(selected["absolute_path"])
                membership_projection = _parent_membership_projection(world, parent)
                digest = hashlib.sha256(
                    _canonical_bytes(membership_projection)
                ).hexdigest()
                assert observed["absence"] == {
                    "after_membership_sha256": digest,
                    "before_membership_sha256": digest,
                    "schema": "goodq.clean-memory-stable-absence.v1",
                }
            else:
                assert observed["state"] == "present"
                assert observed["absence"] is None
                assert observed["object_identity"]["schema"] == (
                    "goodq.windows-file-identity.v1"
                )

    serialized = repr(evidence)
    assert "C:/Scope" not in serialized
    assert "N000" not in serialized


def test_every_descendant_is_opened_by_id_and_exact_prefix_is_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _membership_projection()
    projection["protected_roles"][0]["members"][0]["absolute_path"] = (
        "C:/Shared/Container"
    )
    projection["protected_roles"][1]["members"][0]["absolute_path"] = (
        "C:/Shared/Container/Child"
    )
    membership = _membership(projection)
    world = _World(membership)

    evidence = _observe_world(monkeypatch, world)

    assert len(evidence) == 18
    assert [event for event in world.events if event[0] == "open_root"] == [
        ("open_root", "C:\\")
    ]
    assert sum(
        event[0] == "open_by_id" and event[2] == "C:/Shared/Container"
        for event in world.events
    ) == 1


def test_distinct_drives_are_each_opened_once_by_root_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _membership_projection()
    projection["protected_roles"][1]["members"][0]["absolute_path"] = (
        "D:/Other/Member"
    )
    membership = _membership(projection)
    world = _World(
        membership,
        filesystems={"C:": "NTFS", "D:": "ReFS"},
    )

    evidence = _observe_world(monkeypatch, world)

    assert len(evidence) == 18
    assert [event for event in world.events if event[0] == "open_root"] == [
        ("open_root", "C:\\"),
        ("open_root", "D:\\"),
    ]


def test_required_final_child_and_missing_ancestor_are_member_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = _membership()
    required_path = next(
        record["members"][0]["absolute_path"]
        for record in membership.projection["protected_roles"]
        if record["role"] == "backup_root"
    )
    _expect_world_error(
        monkeypatch,
        _World(membership, absent_paths={required_path}),
        "member_missing",
    )

    missing_ancestor = _World(membership)
    missing_ancestor.enumeration_overrides["C:/"] = lambda _count, entries: (
        entry for entry in entries if entry.name != "Scope"
    )
    _expect_world_error(monkeypatch, missing_ancestor, "member_missing")


def test_allow_absent_uses_exactly_two_complete_equal_parent_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = _membership()
    path = next(
        record["members"][0]["absolute_path"]
        for record in membership.projection["protected_roles"]
        if record["role"] == "archive_root"
    )
    world = _World(membership, absent_paths={path})

    evidence = _observe_world(monkeypatch, world)

    parent = _parent_path(path)
    assert world.backends[0].enumeration_counts[parent] == 2
    observed = json.loads(evidence[0].identity_json)["members"][0]
    assert observed["state"] == "absent"
    assert observed["absence"]["before_membership_sha256"] == (
        observed["absence"]["after_membership_sha256"]
    )


@pytest.mark.parametrize(
    "mutation",
    ["appearance", "disappearance", "same_count_replacement"],
)
def test_parent_membership_changes_after_initial_acceptance_are_races(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    membership = _membership()
    path = next(
        record["members"][0]["absolute_path"]
        for record in membership.projection["protected_roles"]
        if record["role"] == "archive_root"
    )
    world = _World(membership)
    parent = _parent_path(path)
    target_name = _final_name(path)

    def mutate(count: int, entries: tuple[WindowsDirectoryEntry, ...]):
        target = next(entry for entry in entries if entry.name == target_name)
        if mutation == "appearance":
            return tuple(
                entry
                for entry in entries
                if count != 1 or entry.name != target_name
            )
        if mutation == "disappearance":
            return tuple(
                entry
                for entry in entries
                if count != 2 or entry.name != target_name
            )
        if count == 2:
            replacement = dataclasses.replace(target, file_id=target.file_id + 700)
            return tuple(
                replacement if entry is target else entry for entry in entries
            )
        return entries

    world.enumeration_overrides[parent] = mutate
    _expect_world_error(monkeypatch, world, "observation_raced")


def test_snapshot_change_after_acceptance_is_observation_raced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = _membership()
    world = _World(membership)
    path = world.member_path("backup_root")
    world.snapshot_overrides[path] = lambda count, snapshot: (
        dataclasses.replace(snapshot, change_ticks=snapshot.change_ticks + 1)
        if count == 2
        else snapshot
    )

    _expect_world_error(monkeypatch, world, "observation_raced")


@pytest.mark.parametrize(
    "target",
    [
        "membership_initial",
        "pin_initial",
        "membership_final",
        "pin_final",
    ],
)
def test_exact_inputs_are_rechecked_at_both_global_fences(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    membership = _membership()
    pin = _pin()
    world = _World(membership)

    def mutate(event: tuple[Any, ...]) -> None:
        initial = target.endswith("_initial") and event == ("enter",)
        final = (
            target.endswith("_final")
            and event[0] == "enumerate"
            and event[-1] == 2
        )
        if not (initial or final):
            return
        if target.startswith("membership_"):
            object.__setattr__(
                membership,
                "protected_membership_scope_sha256",
                "0" * 64,
            )
        else:
            object.__setattr__(pin, "external_pin_evidence_sha256", "0" * 64)
        world.event_hook = None

    world.event_hook = mutate
    _expect_world_error(
        monkeypatch,
        world,
        "observation_raced",
        pin=pin,
    )


def _initial_fault_world(mutation: str) -> _World:
    membership = _membership()
    world = _World(membership)
    directory_path = world.member_path("backup_root")
    file_path = world.member_path("watchdog_state")
    if mutation == "unsupported_filesystem":
        world.filesystems["C:"] = "FAT32"
    elif mutation == "redirect":
        world.entry_attribute_overrides[directory_path] = 0x410
    elif mutation == "device":
        world.entry_attribute_overrides[directory_path] = 0x50
    elif mutation == "wrong_kind":
        world.entry_attribute_overrides[directory_path] = 0
    elif mutation == "cross_volume":
        world.replace_snapshot(
            directory_path,
            volume_serial=world.nodes[directory_path].snapshot.volume_serial + 1,
        )
    elif mutation == "zero_identity":
        world.replace_snapshot(directory_path, file_id=0)
    elif mutation == "hardlink":
        world.replace_snapshot(file_path, link_count=2)
    elif mutation == "stream_violation":
        world.replace_snapshot(
            directory_path,
            streams=(("::$DATA", 0, 0),),
        )
    elif mutation == "case_ambiguity":
        parent = _parent_path(directory_path)
        target_name = _final_name(directory_path)

        def duplicate(_count: int, entries: tuple[WindowsDirectoryEntry, ...]):
            target = next(entry for entry in entries if entry.name == target_name)
            return (
                *entries,
                dataclasses.replace(
                    target,
                    name=target.name.swapcase(),
                    file_id=target.file_id + 800,
                ),
            )

        world.enumeration_overrides[parent] = duplicate
    elif mutation == "nfc_ambiguity":
        parent = _parent_path(directory_path)

        def duplicate_nfc(
            _count: int,
            entries: tuple[WindowsDirectoryEntry, ...],
        ) -> tuple[WindowsDirectoryEntry, ...]:
            return (
                *entries,
                WindowsDirectoryEntry(
                    name="\u00c9",
                    attributes=0x10,
                    file_id_kind="ntfs_file_index_64",
                    file_id=0xF01,
                ),
                WindowsDirectoryEntry(
                    name="E\u0301",
                    attributes=0x10,
                    file_id_kind="ntfs_file_index_64",
                    file_id=0xF02,
                ),
            )

        world.enumeration_overrides[parent] = duplicate_nfc
    elif mutation == "delete_pending":
        world.failures[("snapshot", directory_path, 1)] = WindowsHeldHandleError(
            "observation_raced"
        )
    else:
        raise AssertionError(mutation)
    return world


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("unsupported_filesystem", "unsupported_filesystem"),
        ("redirect", "redirected_boundary"),
        ("device", "unexpected_entry_type"),
        ("wrong_kind", "unexpected_entry_type"),
        ("cross_volume", "unsupported_filesystem"),
        ("zero_identity", "duplicate_identity"),
        ("hardlink", "duplicate_identity"),
        ("stream_violation", "unexpected_entry_type"),
        ("case_ambiguity", "duplicate_identity"),
        ("nfc_ambiguity", "duplicate_identity"),
        ("delete_pending", "observation_raced"),
    ],
)
def test_initial_boundary_faults_fail_closed_with_selected_code(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    code: str,
) -> None:
    _expect_world_error(monkeypatch, _initial_fault_world(mutation), code)


def test_different_paths_with_one_physical_identity_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = _membership()
    world = _World(membership)
    world.alias_identity(
        world.member_path("backup_root"),
        world.member_path("archive_root"),
    )
    _expect_world_error(monkeypatch, world, "duplicate_identity")


def test_aliased_parents_with_same_child_comparison_key_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _membership_projection()
    projection["protected_roles"][0]["members"][0]["absolute_path"] = (
        "C:/ParentA/Child"
    )
    projection["protected_roles"][1]["members"][0]["absolute_path"] = (
        "C:/ParentB/Child"
    )
    membership = _membership(projection)
    world = _World(membership)
    world.alias_identity("C:/ParentB", "C:/ParentA")

    _expect_world_error(monkeypatch, world, "duplicate_identity")


def _pin_colliding_with(
    world: _World,
    *,
    slot: int,
    path: str,
) -> ExternalPinEvidence:
    target = dict(world.nodes[path].snapshot.identity_projection)
    target["object_kind"] = "regular_file" if slot == 4 else "directory"
    serial = world.nodes["C:/"].snapshot.volume_serial
    projection = _pin_projection()
    projection["anchor_identity"] = _identity(
        0x900,
        object_kind="directory",
        volume_serial=serial,
    )
    projection["dedicated_directory_identities"] = [
        _identity(
            0x901 + index,
            object_kind="directory",
            volume_serial=serial,
        )
        for index in range(3)
    ]
    projection["pin_file_identity"] = _identity(
        0x904,
        object_kind="regular_file",
        volume_serial=serial,
    )
    if slot == 0:
        projection["anchor_identity"] = target
    elif 1 <= slot <= 3:
        projection["dedicated_directory_identities"][slot - 1] = target
    else:
        projection["pin_file_identity"] = target
    return _forge_pin(projection)


@pytest.mark.parametrize("slot", range(5))
@pytest.mark.parametrize(
    "category",
    ["root", "ancestor", "parent", "member", "file_member"],
)
def test_every_pin_identity_collides_with_retained_protected_identity(
    monkeypatch: pytest.MonkeyPatch,
    slot: int,
    category: str,
) -> None:
    projection = _membership_projection()
    projection["protected_roles"][0]["members"][0]["absolute_path"] = (
        "C:/Outer/Inner/Member"
    )
    membership = _membership(projection)
    world = _World(membership)
    paths = {
        "root": "C:/",
        "ancestor": "C:/Outer",
        "parent": "C:/Outer/Inner",
        "member": world.member_path("backup_root"),
        "file_member": world.member_path("watchdog_state"),
    }
    pin = _pin_colliding_with(world, slot=slot, path=paths[category])

    _expect_world_error(
        monkeypatch,
        world,
        "pin_chain_collision",
        pin=pin,
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("volume_serial", lambda value: value + 1),
        ("file_id_kind", lambda _value: "refs_file_id_128"),
        ("file_id", lambda value: value + 1),
        ("object_kind", lambda _value: "regular_file"),
        ("size_bytes", lambda value: value + 1),
        ("mtime_ns", lambda _value: 1),
        ("allocation_size", lambda value: value + 1),
        ("link_count", lambda value: value + 1),
        ("attributes", lambda value: value | 0x400),
        ("reparse_tag", lambda _value: 0xA0000003),
        ("last_write_ticks", lambda value: value + 1),
        ("change_ticks", lambda value: value + 1),
        ("streams", lambda _value: (("::$DATA", 0, 0),)),
    ],
)
def test_every_snapshot_field_change_at_final_fence_is_a_race(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement,
) -> None:
    world = _World(_membership())
    path = world.member_path("backup_root")

    def mutate(count: int, snapshot: WindowsObjectSnapshot):
        if count != 2:
            return snapshot
        return dataclasses.replace(
            snapshot,
            **{field: replacement(getattr(snapshot, field))},
        )

    world.snapshot_overrides[path] = mutate
    _expect_world_error(monkeypatch, world, "observation_raced")


@pytest.mark.parametrize(
    "field",
    ["comparison_name", "entry_identity", "entry_kind"],
)
def test_every_parent_membership_field_change_at_final_fence_is_a_race(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    world = _World(_membership())
    path = world.member_path("backup_root")
    parent = _parent_path(path)
    target_name = _final_name(path)

    def mutate(count: int, entries: tuple[WindowsDirectoryEntry, ...]):
        if count != 2:
            return entries
        target = next(entry for entry in entries if entry.name == target_name)
        if field == "comparison_name":
            changed = dataclasses.replace(target, name=f"{target.name}x")
        elif field == "entry_identity":
            changed = dataclasses.replace(target, file_id=target.file_id + 1)
        else:
            changed = dataclasses.replace(target, attributes=target.attributes & ~0x10)
        return tuple(changed if entry is target else entry for entry in entries)

    world.enumeration_overrides[parent] = mutate
    _expect_world_error(monkeypatch, world, "observation_raced")


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", ""), ("attributes", True)],
)
def test_newly_invalid_exact_entry_field_at_final_fence_is_a_race(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    world = _World(_membership())
    path = world.member_path("backup_root")
    parent = _parent_path(path)
    target_name = _final_name(path)

    def mutate(count: int, entries: tuple[WindowsDirectoryEntry, ...]):
        if count != 2:
            return entries
        target = next(entry for entry in entries if entry.name == target_name)
        changed = dataclasses.replace(target, **{field: value})
        return tuple(changed if entry is target else entry for entry in entries)

    world.enumeration_overrides[parent] = mutate
    _expect_world_error(monkeypatch, world, "observation_raced")


def test_parent_enumeration_order_is_canonicalized_before_final_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    parent = "C:/Scope"
    world.enumeration_overrides[parent] = lambda count, entries: (
        tuple(reversed(entries)) if count == 2 else entries
    )

    evidence = _observe_world(monkeypatch, world)

    assert len(evidence) == 18


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("redirected_boundary", "observation_raced"),
        ("unexpected_entry_type", "observation_raced"),
        ("duplicate_identity", "observation_raced"),
        ("sharing_conflict", "observation_raced"),
        ("unsupported_filesystem", "observation_raced"),
        ("observation_raced", "observation_raced"),
        ("observation_failed", "observation_failed"),
    ],
)
def test_final_backend_failure_precedence_requires_positive_change_evidence(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    expected: str,
) -> None:
    membership = _membership()
    world = _World(membership)
    path = world.member_path("backup_root")
    world.failures[("snapshot", path, 2)] = WindowsHeldHandleError(code)

    _expect_world_error(monkeypatch, world, expected)


def test_final_explicit_boundary_change_is_never_downgraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = _membership()
    world = _World(membership)
    path = world.member_path("backup_root")
    world.snapshot_overrides[path] = lambda count, snapshot: (
        dataclasses.replace(
            snapshot,
            attributes=snapshot.attributes | 0x400,
            reparse_tag=0xA0000003,
        )
        if count == 2
        else snapshot
    )

    _expect_world_error(monkeypatch, world, "observation_raced")


@pytest.mark.parametrize(
    "code",
    [
        "unsupported_platform",
        "unsupported_filesystem",
        "redirected_boundary",
        "unexpected_entry_type",
        "duplicate_identity",
        "sharing_conflict",
        "observation_raced",
        "observation_failed",
    ],
)
def test_initial_known_backend_codes_are_translated_exactly(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
) -> None:
    world = _World(_membership())
    path = world.member_path("backup_root")
    native = OSError(r"C:\private\secret-child native failure 5")
    failure = WindowsHeldHandleError(code)
    failure.__cause__ = native
    failure.__suppress_context__ = True
    world.failures[("open_by_id", path, 1)] = failure

    module, error = _expect_world_error(monkeypatch, world, code)
    _assert_sanitized_error_graph(module, error)


def test_unknown_startup_and_operation_failures_are_closed_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    startup = _World(_membership())
    startup.constructor_error = OSError(
        r"C:\private\secret-child native failure 5"
    )
    module, error = _expect_world_error(
        monkeypatch,
        startup,
        "observation_failed",
    )
    _assert_sanitized_error_graph(module, error)

    operation = _World(_membership())
    path = operation.member_path("backup_root")
    operation.failures[("enumerate_directory", "C:/Scope", 1)] = RuntimeError(
        r"C:\private\secret-child native failure 5"
    )
    module, error = _expect_world_error(
        monkeypatch,
        operation,
        "observation_failed",
    )
    _assert_sanitized_error_graph(module, error)


def test_cleanup_only_failure_prevents_return_and_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    world.close_failures[world.member_path("watchdog_state", 1)] = OSError(
        r"C:\private\secret-child native failure 5"
    )

    module, error = _expect_world_error(
        monkeypatch,
        world,
        "observation_failed",
    )
    _assert_sanitized_error_graph(module, error)
    assert len([event for event in world.events if event[0] == "close"]) == len(
        [event for event in world.events if event[0] in {"open_root", "open_by_id"}]
    )


def test_cleanup_only_control_flow_is_normalized_and_all_handles_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    world.close_failures[world.member_path("watchdog_state", 1)] = (
        KeyboardInterrupt(r"C:\private\cleanup control")
    )

    module, error = _expect_world_error(
        monkeypatch,
        world,
        "observation_failed",
    )
    _assert_sanitized_error_graph(module, error)
    assert len([event for event in world.events if event[0] == "close"]) == len(
        [event for event in world.events if event[0] in {"open_root", "open_by_id"}]
    )


def test_ordinary_operation_primary_precedes_cleanup_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    path = world.member_path("backup_root")
    primary = WindowsHeldHandleError("redirected_boundary")
    primary.__cause__ = OSError(
        r"C:\private\secret-child native failure 5"
    )
    primary.__suppress_context__ = True
    world.failures[("open_by_id", path, 1)] = primary
    world.close_failures["C:/Scope"] = RuntimeError(
        r"C:\private\cleanup native failure 5"
    )

    module, error = _expect_world_error(
        monkeypatch,
        world,
        "redirected_boundary",
    )
    _assert_sanitized_error_graph(module, error)
    assert error.__cause__ is not None or error.__context__ is not None


def _prime_control(error: BaseException):
    try:
        raise error
    except BaseException as caught:
        assert caught is error
        traceback = caught.__traceback__
    assert traceback is not None
    return traceback


def _traceback_contains(error: BaseException, expected) -> bool:
    traceback = error.__traceback__
    while traceback is not None:
        if traceback is expected:
            return True
        traceback = traceback.tb_next
    return False


@pytest.mark.parametrize("control_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_exact_operation_control_flow_primary_identity_and_traceback_survive_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    control_type: type[BaseException],
) -> None:
    world = _World(_membership())
    path = world.member_path("backup_root")
    primary = control_type("control")
    original_tail = _prime_control(primary)
    world.failures[("open_by_id", path, 1)] = primary
    world.close_failures["C:/Scope"] = KeyboardInterrupt(
        r"C:\private\cleanup control"
    )
    module = _install_world(monkeypatch, world)

    with pytest.raises(control_type) as exc_info:
        module.observe_protected_boundaries(
            world.membership,
            external_pin_evidence=_pin(),
        )

    assert exc_info.value is primary
    assert _traceback_contains(primary, original_tail)
    assert type(primary.__cause__) is module.ProtectedBoundaryObservationError
    assert primary.__cause__.code == "observation_failed"
    assert primary.__context__ is None
    assert primary.__suppress_context__ is True
    _assert_sanitized_error_graph(module, primary.__cause__)


def test_unknown_base_exception_and_cyclic_error_graph_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnknownControl(BaseException):
        pass

    for failure in (
        UnknownControl(r"C:\private\secret-child"),
        WindowsHeldHandleError("observation_failed"),
    ):
        world = _World(_membership())
        path = world.member_path("backup_root")
        if type(failure) is WindowsHeldHandleError:
            failure.__cause__ = failure
        world.failures[("open_by_id", path, 1)] = failure
        module, error = _expect_world_error(
            monkeypatch,
            world,
            "observation_failed",
        )
        _assert_sanitized_error_graph(module, error)


def test_deep_native_error_graph_is_bounded_and_path_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = WindowsHeldHandleError("observation_failed")
    tail: BaseException = head
    for index in range(300):
        linked = OSError(
            rf"C:\private\secret-child native failure 5 depth {index}"
        )
        tail.__cause__ = linked
        tail.__suppress_context__ = True
        tail = linked
    world = _World(_membership())
    path = world.member_path("backup_root")
    world.failures[("open_by_id", path, 1)] = head

    module, error = _expect_world_error(
        monkeypatch,
        world,
        "observation_failed",
    )
    _assert_sanitized_error_graph(module, error)


def test_error_sanitizer_uses_preallocated_terminal_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    path = world.member_path("backup_root")
    world.failures[("open_by_id", path, 1)] = RuntimeError(
        r"C:\private\secret-child native failure 5"
    )
    module = _install_world(monkeypatch, world)
    original_error_type = module.ProtectedBoundaryObservationError

    def exhaust_allocation(_code: str):
        raise MemoryError("synthetic allocation exhaustion")

    def install_failure(event: tuple[Any, ...]) -> None:
        if event[:3] == ("open_by_id", "C:/", path):
            monkeypatch.setattr(
                module,
                "ProtectedBoundaryObservationError",
                exhaust_allocation,
            )
            world.event_hook = None

    world.event_hook = install_failure
    with pytest.raises(original_error_type) as exc_info:
        module.observe_protected_boundaries(
            world.membership,
            external_pin_evidence=_pin(),
        )
    assert exc_info.value.code == "observation_failed"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_backend_exit_closes_reverse_and_attempts_all_after_multiple_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    world.close_failures[world.member_path("backup_root")] = RuntimeError("one")
    world.close_failures[world.member_path("watchdog_state", 1)] = RuntimeError(
        "two"
    )

    _expect_world_error(monkeypatch, world, "observation_failed")

    opened = [
        "C:/" if event[0] == "open_root" else event[2]
        for event in world.events
        if event[0] in {"open_root", "open_by_id"}
    ]
    closed = [event[1] for event in world.events if event[0] == "close"]
    assert closed == list(reversed(opened))


@pytest.mark.parametrize("role", ["archive_root", "processing_media", "watchdog_state"])
def test_first_middle_and_final_traversal_failures_construct_no_partial_evidence(
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    world = _World(_membership())
    path = world.member_path(role)
    world.failures[("open_by_id", path, 1)] = RuntimeError("synthetic failure")
    module = _install_world(monkeypatch, world)
    constructed: list[object] = []

    def forbidden_evidence(*_args: object, **_kwargs: object) -> None:
        constructed.append(object())
        raise AssertionError("partial evidence construction")

    monkeypatch.setattr(module, "ProtectedBoundaryEvidence", forbidden_evidence)
    with pytest.raises(module.ProtectedBoundaryObservationError):
        module.observe_protected_boundaries(
            world.membership,
            external_pin_evidence=_pin(),
        )
    assert constructed == []


def test_middle_evidence_construction_failure_returns_no_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    module = _install_world(monkeypatch, world)
    original = ProtectedBoundaryEvidence
    constructed: list[ProtectedBoundaryEvidence] = []

    def fail_middle(**values: str):
        if len(constructed) == 8:
            raise RuntimeError(r"C:\private\secret-child")
        value = original(**values)
        constructed.append(value)
        return value

    monkeypatch.setattr(module, "ProtectedBoundaryEvidence", fail_middle)
    with pytest.raises(module.ProtectedBoundaryObservationError) as exc_info:
        module.observe_protected_boundaries(
            world.membership,
            external_pin_evidence=_pin(),
        )
    assert exc_info.value.code == "observation_failed"
    assert len(constructed) == 8
    assert ("exit", True) in world.events


def _candidate_scope(
    boundaries: tuple[ProtectedBoundaryEvidence, ...],
) -> ResolvedCleanupScope:
    singleton_roles = (
        "memory_database",
        "memory_database_wal",
        "memory_database_shm",
        "knowledge_graph_database",
        "knowledge_graph_database_wal",
        "knowledge_graph_database_shm",
        "faiss_file",
    )
    filesystem = tuple(
        FilesystemTargetEvidence(
            role=role,
            target_type="regular_file",
            relative_path=f"memory/{index}.bin",
            exists=False,
            size_bytes=None,
            mtime_ns=None,
            file_identity_json=None,
            sha256=None,
        )
        for index, role in enumerate(singleton_roles)
    )
    qdrant = tuple(
        QdrantCollectionEvidence(
            role=role,
            collection_name=f"goodq_{role}_epoch_test",
            exists=False,
            configuration_json=None,
            point_count=None,
            fingerprint_kind=None,
            fingerprint_value=None,
        )
        for role in ("text", "clip", "dino", "audio")
    )
    return ResolvedCleanupScope(
        epoch_id="epoch_test",
        config_scope_sha256="a" * 64,
        epoch_root_identity_json=_canonical_text(
            {"schema": "goodq.test-identity.v1", "value": "epoch"}
        ),
        filesystem_targets=filesystem,
        qdrant_endpoint="http://127.0.0.1:6333",
        qdrant_collections=qdrant,
        protected_boundaries=boundaries,
    )


def test_observer_output_converts_directly_to_existing_candidate_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(_membership())
    boundaries = _observe_world(monkeypatch, world)

    plan = build_candidate_plan(
        _candidate_scope(boundaries),
        observed_at_utc="2026-07-15T00:00:00+00:00",
    )

    records = plan.authority["protected_boundaries"]
    assert len(records) == 18
    assert [record["role"] for record in records] == list(
        PROTECTED_BOUNDARY_ROLES
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        boundaries[0].identity_json = "{}"


def test_module_exposes_no_reader_locator_plan_or_mutation_capability() -> None:
    module = _module()
    forbidden = {
        "read_external_pin",
        "read_protected_manifest",
        "project_protected_membership",
        "resolve_plan_configuration",
        "build_candidate_plan",
        "CandidatePlanStore",
        "CleanMemoryWindowsProgramDataLocator",
    }
    assert forbidden.isdisjoint(vars(module))
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        "ProgramData",
        "Qdrant",
        "MiniAgent",
        "approval",
        "cleanup_target",
        "read_file_bounded(",
        "read_security_descriptor(",
        "hash_file(",
    ):
        assert token not in source
