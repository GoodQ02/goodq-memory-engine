from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from cli.clean_memory import ResolvedPlanConfiguration
from cli.clean_memory_external_pin import ExternalPinEvidence
from steps.common.clean_memory_protected_manifest import (
    CanonicalProtectedManifest,
    PROTECTED_MANIFEST_MAX_BYTES,
)
from steps.common.clean_memory_windows_reader_identity import (
    CleanMemoryWindowsReaderIdentityError,
)
from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)
from steps.common.windows_security_mechanics import (
    WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
    WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
    WindowsAce,
    WindowsMutationDenial,
    WindowsSecurityDescriptor,
    WindowsSecurityMechanicsError,
    WindowsSid,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cli" / "clean_memory_protected_manifest.py"
EPOCH_ID = "epoch_2026_07_family"
ROLE_ORDER = (
    "backup_root",
    "download_cache",
    "public_checkout",
    "qdrant_service_logs",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
)
ERRORS = {
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

SYSTEM_SID = WindowsSid(bytes.fromhex("010100000000000512000000"), "S-1-5-18")
ADMIN_SID = WindowsSid(
    bytes.fromhex("01020000000000052000000020020000"),
    "S-1-5-32-544",
)
READER_SID = WindowsSid(
    bytes.fromhex("010500000000000515000000a500000092100000b3150000"),
    "S-1-5-21-165-4242-5555",
)
CREATOR_OWNER_SID = WindowsSid(
    bytes.fromhex("010100000000000300000000"),
    "S-1-3-0",
)
MEDIUM_SID = WindowsSid(
    bytes.fromhex("010100000000001000200000"),
    "S-1-16-8192",
)

CANDIDATE_RIGHTS = (
    ("file_add_subdirectory", 0x00000004),
    ("file_write_ea", 0x00000010),
    ("file_delete_child", 0x00000040),
    ("file_write_attributes", 0x00000100),
    ("delete", 0x00010000),
    ("write_dac", 0x00040000),
    ("write_owner", 0x00080000),
)
MANIFEST_RIGHTS = (
    ("file_write_data", 0x00000002),
    ("file_append_data", 0x00000004),
    ("file_write_ea", 0x00000010),
    ("file_write_attributes", 0x00000100),
    ("delete", 0x00010000),
    ("write_dac", 0x00040000),
    ("write_owner", 0x00080000),
)


def _module():
    return importlib.import_module("cli.clean_memory_protected_manifest")


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


def _identity(number: int, *, object_kind: str) -> dict[str, str]:
    return {
        "file_id": f"{number:016x}",
        "file_id_kind": "ntfs_file_index_64",
        "object_kind": object_kind,
        "schema": "goodq.windows-file-identity.v1",
        "volume_serial": "0123456789abcdef",
    }


def _configuration(*, storage_root: str = "R:/Authority") -> ResolvedPlanConfiguration:
    data_root = f"{storage_root}/GoodQ_Data"
    projection = {
        "configured_protected_paths": [
            {"paths": [f"{data_root}/control"], "role": "control_root"},
            {"paths": [data_root], "role": "data_root"},
        ],
        "declared_faiss_paths": {},
        "epoch": {
            "epoch_id": EPOCH_ID,
            "root": f"{data_root}/epochs/{EPOCH_ID}",
        },
        "logical_paths": {
            "candidate_evidence_root": f"{data_root}/control/clean_memory",
            "data_root": data_root,
            "faiss_root": f"{data_root}/epochs/{EPOCH_ID}/faiss",
            "knowledge_graph_database": (
                f"{data_root}/epochs/{EPOCH_ID}/knowledge_graph.db"
            ),
            "knowledge_graph_database_shm": (
                f"{data_root}/epochs/{EPOCH_ID}/knowledge_graph.db-shm"
            ),
            "knowledge_graph_database_wal": (
                f"{data_root}/epochs/{EPOCH_ID}/knowledge_graph.db-wal"
            ),
            "memory_database": f"{data_root}/epochs/{EPOCH_ID}/memory.db",
            "memory_database_shm": f"{data_root}/epochs/{EPOCH_ID}/memory.db-shm",
            "memory_database_wal": f"{data_root}/epochs/{EPOCH_ID}/memory.db-wal",
            "storage_root": storage_root,
        },
        "path_flavor": "windows",
        "qdrant": {
            "collections": {},
            "embedding_dims": {},
            "enabled": False,
            "endpoint": "http://127.0.0.1:6333",
        },
        "schema": "goodq.clean-memory-configuration.v1",
        "unresolved_protected_roles": list(ROLE_ORDER),
    }
    text = _canonical_text(projection)
    instance = object.__new__(ResolvedPlanConfiguration)
    object.__setattr__(instance, "_projection_json", text)
    object.__setattr__(
        instance,
        "configuration_scope_sha256",
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    return instance


def _manifest_bytes() -> bytes:
    return _canonical_bytes(
        {
            "roles": [
                {
                    "members": [
                        {
                            "absolute_path": f"R:/Protected/{role}",
                            "member_id": "primary",
                            "object_kind": "directory",
                            "presence": "required",
                        }
                    ],
                    "role": role,
                }
                for role in ROLE_ORDER
            ],
            "schema": "goodq.clean-memory-protected-authority.v1",
        }
    )


def _external_evidence(manifest_bytes: bytes) -> ExternalPinEvidence:
    return ExternalPinEvidence._from_projection(
        {
            "anchor_identity": _identity(101, object_kind="directory"),
            "dedicated_directory_identities": [
                _identity(102, object_kind="directory"),
                _identity(103, object_kind="directory"),
                _identity(104, object_kind="directory"),
            ],
            "enrolled_reader_identity_sha256": "1" * 64,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "pin_file_identity": _identity(105, object_kind="regular_file"),
            "platform": "windows",
            "schema": "goodq.clean-memory-external-pin-evidence.v1",
            "security_policy_sha256": "2" * 64,
            "source_id": "goodq.clean-memory-protected-authority-pin.primary.v1",
            "source_schema": "goodq.clean-memory-external-pin-source.v1",
        }
    )


def _snapshot(
    number: int,
    *,
    object_kind: str,
    size_bytes: int = 0,
) -> WindowsObjectSnapshot:
    return WindowsObjectSnapshot(
        volume_serial=0x0123456789ABCDEF,
        file_id_kind="ntfs_file_index_64",
        file_id=number,
        object_kind=object_kind,
        size_bytes=size_bytes,
        mtime_ns=1000 + number,
        allocation_size=size_bytes,
        link_count=1,
        attributes=0x10 if object_kind == "directory" else 0x80,
        reparse_tag=0,
        last_write_ticks=2000 + number,
        change_ticks=3000 + number,
        streams=(
            ()
            if object_kind == "directory"
            else (("::$DATA", size_bytes, size_bytes),)
        ),
    )


def _candidate_descriptor() -> WindowsSecurityDescriptor:
    return WindowsSecurityDescriptor(
        control=0xB014,
        owner=ADMIN_SID,
        group=ADMIN_SID,
        dacl_present=True,
        dacl_null=False,
        dacl_revision=2,
        dacl_aces=(
            WindowsAce(0, 0x03, 0x001F01FF, SYSTEM_SID),
            WindowsAce(0, 0x03, 0x001F01FF, ADMIN_SID),
            WindowsAce(0, 0x00, 0x001200A3, READER_SID),
            WindowsAce(0, 0x0D, 0x0013019F, CREATOR_OWNER_SID),
        ),
        sacl_present=True,
        sacl_null=False,
        sacl_revision=2,
        mandatory_label_aces=(WindowsAce(0x11, 0x00, 0x1, MEDIUM_SID),),
    )


def _manifest_descriptor() -> WindowsSecurityDescriptor:
    return WindowsSecurityDescriptor(
        control=0xB014,
        owner=ADMIN_SID,
        group=ADMIN_SID,
        dacl_present=True,
        dacl_null=False,
        dacl_revision=2,
        dacl_aces=(
            WindowsAce(0, 0x00, 0x001F01FF, SYSTEM_SID),
            WindowsAce(0, 0x00, 0x001F01FF, ADMIN_SID),
            WindowsAce(0, 0x00, 0x00120089, READER_SID),
        ),
        sacl_present=True,
        sacl_null=False,
        sacl_revision=2,
        mandatory_label_aces=(WindowsAce(0x11, 0x00, 0x1, MEDIUM_SID),),
    )


class _FakePinnedDescriptor:
    def __init__(self, observation: WindowsSecurityDescriptor) -> None:
        self.observation = observation


class _EventLog(list[object]):
    backend: _FakeBackend
    security: _FakeSecurity


class _FakeAccessScope:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.closed = False

    def check_denial(self, *, raw_mask: int) -> WindowsMutationDenial:
        self.events.append(("deny", raw_mask))
        return WindowsMutationDenial(raw_mask, raw_mask, True)

    def close(self) -> None:
        assert not self.closed
        self.closed = True
        self.events.append("close_scope")


class _FakeSession:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.baseline_snapshot = SimpleNamespace(user_sid=READER_SID)
        self.closed = False

    def observe_effective(self):
        self.events.append("observe_token")
        return self.baseline_snapshot

    def open_access_check(self, descriptor):
        assert isinstance(descriptor, _FakePinnedDescriptor)
        self.events.append("open_access")
        return _FakeAccessScope(self.events)

    def close(self) -> None:
        assert not self.closed
        self.closed = True
        self.events.append("close_session")


class _FakeSecurity:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.session = _FakeSession(events)

    def resolve_privilege_luid(self, name: str) -> int:
        self.events.append(("resolve_luid", name))
        return 77

    def open_token_session(self, *, profile: str):
        self.events.append(("open_session", profile))
        assert profile == WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY
        return self.session

    def pin_security_descriptor(self, descriptor_bytes: bytes, *, profile: str):
        self.events.append(("pin_descriptor", descriptor_bytes, profile))
        assert profile == WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL
        if descriptor_bytes == b"candidate-descriptor":
            return _FakePinnedDescriptor(_candidate_descriptor())
        if descriptor_bytes == b"manifest-descriptor":
            return _FakePinnedDescriptor(_manifest_descriptor())
        raise AssertionError("unexpected descriptor bytes")


class _FakeBackend:
    def __init__(
        self,
        events: list[object],
        manifest_bytes: bytes,
        *,
        storage_components: tuple[str, ...],
    ) -> None:
        self.events = events
        self.manifest_bytes = manifest_bytes
        self.components = (*storage_components, "GoodQ_Data", "control", "clean_memory")
        self.handles = ("anchor", *self.components, "protected-boundaries.json")
        self.numbers = {handle: index + 1 for index, handle in enumerate(self.handles)}
        self.entered = False

    def __enter__(self):
        self.entered = True
        self.events.append("enter_backend")
        return self

    def __exit__(self, exc_type, exc, traceback):
        assert (exc_type, exc, traceback) == (None, None, None)
        self.events.append("exit_backend")
        return False

    def open_root(self, root: str):
        self.events.append(("open_root", root))
        assert root == "R:/"
        return "anchor"

    def volume_filesystem(self, handle):
        self.events.append(("filesystem", handle))
        return "NTFS"

    def enumerate_directory(self, handle, filesystem: str):
        self.events.append(("enumerate", handle))
        assert filesystem == "NTFS"
        index = self.handles.index(handle)
        if index + 1 >= len(self.handles):
            return ()
        child = self.handles[index + 1]
        is_directory = child != "protected-boundaries.json"
        return (
            WindowsDirectoryEntry(
                name=child,
                attributes=0x10 if is_directory else 0x80,
                file_id_kind="ntfs_file_index_64",
                file_id=self.numbers[child],
            ),
        )

    def open_by_id(self, volume_handle, entry, *, directory: bool):
        self.events.append(("open_by_id", volume_handle, entry.name, directory))
        assert volume_handle == "anchor"
        return entry.name

    def snapshot(
        self,
        handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        self.events.append(("snapshot", handle))
        assert filesystem == "NTFS"
        assert require_stream_contract is True
        size = len(self.manifest_bytes) if object_kind == "regular_file" else 0
        return _snapshot(self.numbers[handle], object_kind=object_kind, size_bytes=size)

    def read_security_descriptor(self, handle):
        self.events.append(("descriptor", handle))
        if handle == "clean_memory":
            return b"candidate-descriptor"
        if handle == "protected-boundaries.json":
            return b"manifest-descriptor"
        raise AssertionError("descriptor read from ungoverned object")

    def read_file_bounded(self, handle, *, maximum_bytes: int):
        self.events.append(("read", handle, maximum_bytes))
        assert handle == "protected-boundaries.json"
        assert maximum_bytes == len(self.manifest_bytes) + 1
        return self.manifest_bytes, True


def _install_happy_world(
    monkeypatch,
    *,
    storage_root: str = "R:/Authority",
    manifest_bytes: bytes | None = None,
):
    module = _module()
    payload = manifest_bytes if manifest_bytes is not None else _manifest_bytes()
    configuration = _configuration(storage_root=storage_root)
    external = _external_evidence(payload)
    events = _EventLog()
    components = tuple(storage_root.split(":/", 1)[1].split("/"))
    backend = _FakeBackend(events, payload, storage_components=components)
    security = _FakeSecurity(events)
    events.backend = backend
    events.security = security

    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(
        module,
        "_bind_security",
        lambda: events.append("bind_security") or security,
    )
    monkeypatch.setattr(
        module,
        "WindowsHeldHandleBackend",
        lambda *, access_profile: (
            events.append(("backend", access_profile)) or backend
        ),
    )
    monkeypatch.setattr(
        module,
        "validate_clean_memory_windows_reader_identity",
        lambda snapshot, *, profile, change_notify_luid: events.append(
            ("validate_identity", snapshot, profile, change_notify_luid)
        ),
    )
    monkeypatch.setattr(
        module,
        "clean_memory_windows_reader_identity_sha256",
        lambda snapshot, *, profile, change_notify_luid: (
            events.append(("digest_identity", snapshot, profile, change_notify_luid))
            or "1" * 64
        ),
    )
    real_validator = module.validate_protected_manifest

    def validating(value: bytes, *, path_flavor: str):
        events.append("validator")
        return real_validator(value, path_flavor=path_flavor)

    monkeypatch.setattr(module, "validate_protected_manifest", validating)
    return module, configuration, external, payload, events


def _walk_exception_graph(error: BaseException) -> tuple[BaseException, ...]:
    pending = [error]
    seen: set[int] = set()
    values: list[BaseException] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        values.append(current)
        if current.__context__ is not None:
            pending.append(current.__context__)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
    return tuple(values)


def _assert_public_error_graph(module, error: BaseException) -> None:
    graph = _walk_exception_graph(error)
    assert graph
    for node in graph:
        assert type(node) is module.ProtectedManifestReaderError
        assert node.code in ERRORS
        rendered = " ".join((str(node), repr(node), repr(node.args), repr(vars(node))))
        assert "secret-reader-path" not in rendered
        assert "S-1-5-21-999" not in rendered
        assert "R:/Private" not in rendered


def _assert_control_links_are_public(module, error: BaseException) -> None:
    graph = _walk_exception_graph(error)
    assert graph[0] is error
    assert len(graph) >= 2
    for node in graph[1:]:
        assert type(node) is module.ProtectedManifestReaderError
        rendered = " ".join((str(node), repr(node), repr(node.args), repr(vars(node))))
        assert "secret-reader-path" not in rendered
        assert "S-1-5-21-999" not in rendered
        assert "R:/Private" not in rendered


def _prime_control_primary(error: BaseException):
    try:
        raise error
    except BaseException as caught:
        assert caught is error
        traceback = caught.__traceback__
    assert traceback is not None
    return traceback


def _assert_original_traceback_tail(error: BaseException, original) -> None:
    current = error.__traceback__
    assert current is not None
    while current.tb_next is not None:
        current = current.tb_next
    original_tail = original
    while original_tail.tb_next is not None:
        original_tail = original_tail.tb_next
    assert current.tb_frame is original_tail.tb_frame
    assert current.tb_lineno == original_tail.tb_lineno


def _expect_code(module, configuration, external, code: str):
    with pytest.raises(module.ProtectedManifestReaderError) as exc_info:
        module.read_protected_manifest(
            configuration,
            external_pin_evidence=external,
        )
    assert exc_info.value.code == code
    return exc_info.value


def _forged_configuration(
    configuration: ResolvedPlanConfiguration,
    *,
    projection_text: object | None = None,
    digest: object | None = None,
) -> ResolvedPlanConfiguration:
    instance = object.__new__(ResolvedPlanConfiguration)
    text = (
        configuration._projection_json
        if projection_text is None
        else projection_text
    )
    value_digest = (
        hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest is None and type(text) is str
        else configuration.configuration_scope_sha256
        if digest is None
        else digest
    )
    object.__setattr__(instance, "_projection_json", text)
    object.__setattr__(instance, "configuration_scope_sha256", value_digest)
    return instance


def _forged_external(
    evidence: ExternalPinEvidence,
    *,
    projection_bytes: object | None = None,
    digest: object | None = None,
) -> ExternalPinEvidence:
    instance = object.__new__(ExternalPinEvidence)
    payload = (
        evidence._projection_bytes
        if projection_bytes is None
        else projection_bytes
    )
    value_digest = (
        hashlib.sha256(payload).hexdigest()
        if digest is None and type(payload) is bytes
        else evidence.external_pin_evidence_sha256
        if digest is None
        else digest
    )
    object.__setattr__(instance, "_projection_bytes", payload)
    object.__setattr__(instance, "external_pin_evidence_sha256", value_digest)
    return instance


def test_module_exists_with_exact_public_contract() -> None:
    assert MODULE_PATH.is_file(), "protected-manifest reader is absent"
    module = _module()
    assert module.PROTECTED_MANIFEST_EVIDENCE_SCHEMA == (
        "goodq.clean-memory-protected-manifest-evidence.v1"
    )
    assert module.__all__ == (
        "PROTECTED_MANIFEST_EVIDENCE_SCHEMA",
        "ProtectedManifestReaderError",
        "ProtectedManifestEvidence",
        "read_protected_manifest",
    )
    assert str(inspect.signature(module.read_protected_manifest)) == (
        "(configuration: 'ResolvedPlanConfiguration', *, "
        "external_pin_evidence: 'ExternalPinEvidence') -> "
        "'ProtectedManifestEvidence'"
    )


def test_error_contract_is_closed_path_free_and_immutable() -> None:
    module = _module()
    for code, message in ERRORS.items():
        error = module.ProtectedManifestReaderError(code)
        assert error.code == code
        assert str(error) == message
        assert error.args == (message,)
        assert vars(error) == {}
        with pytest.raises(AttributeError):
            error.code = "observation_failed"
        with pytest.raises(AttributeError):
            del error._code
        with pytest.raises(AttributeError):
            del error.code
        assert error.code == code
    with pytest.raises(ValueError, match="Unknown protected manifest reader error code"):
        module.ProtectedManifestReaderError("unknown")


def test_happy_path_binds_exact_bytes_route_and_direct_inputs(monkeypatch) -> None:
    module, configuration, external, payload, events = _install_happy_world(monkeypatch)

    result = module.read_protected_manifest(
        configuration,
        external_pin_evidence=external,
    )

    assert is_dataclass(result)
    assert tuple(field.name for field in fields(result)) == (
        "_manifest_bytes",
        "_projection_bytes",
        "protected_manifest_evidence_sha256",
    )
    assert result.manifest_bytes is payload
    projection = result.projection
    assert set(projection) == {
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
    assert projection["schema"] == module.PROTECTED_MANIFEST_EVIDENCE_SCHEMA
    assert projection["platform"] == "windows"
    assert projection["configuration_scope_sha256"] == (
        configuration.configuration_scope_sha256
    )
    assert projection["external_pin_evidence_sha256"] == (
        external.external_pin_evidence_sha256
    )
    assert projection["manifest_sha256"] == hashlib.sha256(payload).hexdigest()
    assert len(projection["route_directory_identities"]) == 4
    assert [
        identity["file_id"]
        for identity in projection["route_directory_identities"]
    ] == [f"{number:016x}" for number in range(2, 6)]
    assert projection["route_directory_identities"][-1]["object_kind"] == "directory"
    assert projection["manifest_file_identity"]["object_kind"] == "regular_file"
    assert "R:/" not in repr(result)
    assert "R:/" not in _canonical_text(projection)
    expected_digest = hashlib.sha256(_canonical_bytes(projection)).hexdigest()
    assert result.protected_manifest_evidence_sha256 == expected_digest
    detached = result.projection
    detached["schema"] = "changed"
    assert result.projection["schema"] == module.PROTECTED_MANIFEST_EVIDENCE_SCHEMA
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.protected_manifest_evidence_sha256 = "0" * 64
    with pytest.raises(TypeError):
        module.ProtectedManifestEvidence()

    validator_events = [event for event in events if event == "validator"]
    assert validator_events == ["validator"]
    read_index = next(
        index
        for index, event in enumerate(events)
        if isinstance(event, tuple) and event[0] == "read"
    )
    assert read_index < events.index("validator")
    assert events[-2:] == ["exit_backend", "close_session"]


def test_multi_component_storage_root_retains_complete_variable_route(monkeypatch) -> None:
    module, configuration, external, _payload, _events = _install_happy_world(
        monkeypatch,
        storage_root="R:/Authority/Nested",
    )
    result = module.read_protected_manifest(
        configuration,
        external_pin_evidence=external,
    )
    assert len(result.projection["route_directory_identities"]) == 5
    assert [
        identity["file_id"]
        for identity in result.projection["route_directory_identities"]
    ] == [f"{number:016x}" for number in range(2, 7)]


@pytest.mark.parametrize(
    "configuration",
    [None, object()],
)
def test_invalid_configuration_precedes_platform_and_native_work(
    monkeypatch,
    configuration,
) -> None:
    module = _module()
    monkeypatch.setattr(module, "os", SimpleNamespace(name="posix"))
    with pytest.raises(module.ProtectedManifestReaderError) as exc_info:
        module.read_protected_manifest(
            configuration,
            external_pin_evidence=object(),
        )
    assert exc_info.value.code == "invalid_configuration"


def test_invalid_external_evidence_precedes_platform_and_native_work(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module.os, "name", "posix")
    with pytest.raises(module.ProtectedManifestReaderError) as exc_info:
        module.read_protected_manifest(
            _configuration(),
            external_pin_evidence=object(),
        )
    assert exc_info.value.code == "invalid_external_pin_evidence"


def test_digest_mismatch_wins_before_validator(monkeypatch) -> None:
    payload = _manifest_bytes()
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch,
        manifest_bytes=payload,
    )
    projection = external.projection
    projection["manifest_sha256"] = "f" * 64
    forged = ExternalPinEvidence._from_projection(projection)

    with pytest.raises(module.ProtectedManifestReaderError) as exc_info:
        module.read_protected_manifest(
            configuration,
            external_pin_evidence=forged,
        )
    assert exc_info.value.code == "manifest_digest_mismatch"
    assert "validator" not in events


def test_parser_receives_identical_bytes_once_after_digest_match(monkeypatch) -> None:
    module, configuration, external, payload, events = _install_happy_world(monkeypatch)
    real_validator = importlib.import_module(
        "steps.common.clean_memory_protected_manifest"
    ).validate_protected_manifest
    calls: list[bytes] = []

    def validating(value: bytes, *, path_flavor: str):
        calls.append(value)
        events.append("validator")
        return real_validator(value, path_flavor=path_flavor)

    monkeypatch.setattr(module, "validate_protected_manifest", validating)
    module.read_protected_manifest(configuration, external_pin_evidence=external)
    assert calls == [payload]
    assert calls[0] is payload


@pytest.mark.parametrize(
    "exception_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_configuration_preflight_preserves_control_flow_identity_and_traceback(
    monkeypatch,
    exception_type: type[BaseException],
) -> None:
    module = _module()
    primary = exception_type()
    original_traceback = _prime_control_primary(primary)

    def interrupt(_value):
        raise primary

    monkeypatch.setattr(module, "_strict_canonical_json", interrupt)
    with pytest.raises(exception_type) as exc_info:
        module.read_protected_manifest(
            _configuration(),
            external_pin_evidence=_external_evidence(_manifest_bytes()),
        )
    assert exc_info.value is primary
    _assert_original_traceback_tail(primary, original_traceback)


@pytest.mark.parametrize(
    "exception_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_external_preflight_preserves_control_flow_identity_and_traceback(
    monkeypatch,
    exception_type: type[BaseException],
) -> None:
    module = _module()
    original = module._strict_canonical_json
    primary = exception_type()
    original_traceback = _prime_control_primary(primary)

    def interrupt(value):
        if type(value) is bytes:
            raise primary
        return original(value)

    monkeypatch.setattr(module, "_strict_canonical_json", interrupt)
    with pytest.raises(exception_type) as exc_info:
        module.read_protected_manifest(
            _configuration(),
            external_pin_evidence=_external_evidence(_manifest_bytes()),
        )
    assert exc_info.value is primary
    _assert_original_traceback_tail(primary, original_traceback)


@pytest.mark.parametrize("surface", ["configuration", "external"])
def test_preflight_control_flow_sanitizes_raw_links(
    monkeypatch,
    surface: str,
) -> None:
    module = _module()
    primary = KeyboardInterrupt()
    original_traceback = _prime_control_primary(primary)
    raw = OSError("R:/Private secret-reader-path S-1-5-21-999")
    primary.__cause__ = raw
    primary.__context__ = raw
    primary.__suppress_context__ = True
    original = module._strict_canonical_json

    def interrupt(value):
        if surface == "configuration" or type(value) is bytes:
            raise primary
        return original(value)

    monkeypatch.setattr(module, "_strict_canonical_json", interrupt)
    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_protected_manifest(
            _configuration(),
            external_pin_evidence=_external_evidence(_manifest_bytes()),
        )
    assert exc_info.value is primary
    _assert_original_traceback_tail(primary, original_traceback)
    assert primary.__cause__ is primary.__context__
    assert primary.__suppress_context__ is True
    _assert_control_links_are_public(module, primary)


@pytest.mark.parametrize(
    ("owner", "field_name", "replacement"),
    [
        ("configuration", "_projection_json", lambda value: type("S", (str,), {})(value)),
        (
            "configuration",
            "configuration_scope_sha256",
            lambda value: type("S", (str,), {})(value),
        ),
        ("external", "_projection_bytes", lambda value: type("B", (bytes,), {})(value)),
        (
            "external",
            "external_pin_evidence_sha256",
            lambda value: type("S", (str,), {})(value),
        ),
    ],
)
def test_final_input_recheck_rejects_equal_valued_type_substitution(
    monkeypatch,
    owner: str,
    field_name: str,
    replacement,
) -> None:
    module, configuration, external, _payload, _events = _install_happy_world(
        monkeypatch
    )
    original_validator = module.validate_protected_manifest

    def mutate_after_authentication(value: bytes, *, path_flavor: str):
        target = configuration if owner == "configuration" else external
        current = getattr(target, field_name)
        object.__setattr__(target, field_name, replacement(current))
        return original_validator(value, path_flavor=path_flavor)

    monkeypatch.setattr(
        module,
        "validate_protected_manifest",
        mutate_after_authentication,
    )
    _expect_code(module, configuration, external, "observation_raced")


def test_duplicate_observed_route_identity_is_duplicate_identity_before_parser(
    monkeypatch,
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original_snapshot = backend.snapshot

    def duplicate_anchor(
        handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        if handle == "Authority":
            return _snapshot(backend.numbers["anchor"], object_kind="directory")
        return original_snapshot(
            handle,
            filesystem=filesystem,
            expected=expected,
            object_kind=object_kind,
            require_stream_contract=require_stream_contract,
        )

    monkeypatch.setattr(backend, "snapshot", duplicate_anchor)
    _expect_code(module, configuration, external, "duplicate_identity")
    assert "validator" not in events


def test_evidence_constructor_binds_retained_bytes_to_manifest_digest(monkeypatch) -> None:
    module, configuration, external, payload, _events = _install_happy_world(monkeypatch)
    result = module.read_protected_manifest(
        configuration,
        external_pin_evidence=external,
    )
    with pytest.raises(ValueError, match="evidence projection is invalid"):
        module.ProtectedManifestEvidence._from_projection(
            b"different retained bytes",
            result.projection,
            expected_route_count=4,
        )
    assert result.manifest_bytes is payload


def test_nested_access_scope_cleanup_failure_survives_outer_cleanup(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )

    class FailingScope:
        def check_denial(self, *, raw_mask: int):
            return WindowsMutationDenial(raw_mask, raw_mask, False)

        def close(self) -> None:
            raise OSError("secret-reader-path")

    monkeypatch.setattr(
        events.security.session,
        "open_access_check",
        lambda _descriptor: FailingScope(),
    )
    error = _expect_code(
        module,
        configuration,
        external,
        "security_policy_mismatch",
    )
    graph = _walk_exception_graph(error)
    assert len(graph) == 2
    _assert_public_error_graph(module, error)
    assert graph[1].code == "observation_failed"


def test_upstream_held_error_chain_is_preserved_and_sanitized(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    primary = WindowsHeldHandleError("sharing_conflict")
    primary.__cause__ = WindowsHeldHandleError("observation_raced")
    primary.__cause__.__cause__ = OSError("R:/Private secret-reader-path")

    def fail_read(_handle, *, maximum_bytes: int):
        raise primary

    monkeypatch.setattr(events.backend, "read_file_bounded", fail_read)
    error = _expect_code(module, configuration, external, "sharing_conflict")
    graph = _walk_exception_graph(error)
    assert graph[0].code == "sharing_conflict"
    assert "observation_raced" in {node.code for node in graph}
    _assert_public_error_graph(module, error)


@pytest.mark.parametrize(
    "exception_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_cleanup_control_flow_is_not_swallowed_by_ordinary_primary(
    monkeypatch,
    exception_type: type[BaseException],
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    operation = WindowsHeldHandleError("sharing_conflict")
    cleanup_control = exception_type()
    original_traceback = _prime_control_primary(cleanup_control)

    def fail_read(_handle, *, maximum_bytes: int):
        raise operation

    def interrupt_exit(_exc_type, _exc, _traceback):
        raise cleanup_control

    monkeypatch.setattr(events.backend, "read_file_bounded", fail_read)
    monkeypatch.setattr(events.backend, "__exit__", interrupt_exit)

    with pytest.raises(exception_type) as exc_info:
        module.read_protected_manifest(
            configuration,
            external_pin_evidence=external,
        )
    assert exc_info.value is cleanup_control
    _assert_original_traceback_tail(cleanup_control, original_traceback)
    assert events.security.session.closed is True
    linked = cleanup_control.__cause__ or cleanup_control.__context__
    assert type(linked) is module.ProtectedManifestReaderError
    _assert_public_error_graph(module, linked)


@pytest.mark.parametrize("field_name", ["owner", "system_ace", "mandatory_label"])
def test_fixed_policy_sid_requires_matching_binary_and_numeric(field_name: str) -> None:
    module = _module()
    descriptor = _candidate_descriptor()
    forged_admin = WindowsSid(b"forged-admin", ADMIN_SID.numeric)
    forged_system = WindowsSid(b"forged-system", SYSTEM_SID.numeric)
    forged_medium = WindowsSid(b"forged-medium", MEDIUM_SID.numeric)
    if field_name == "owner":
        descriptor = replace(descriptor, owner=forged_admin)
    elif field_name == "system_ace":
        aces = list(descriptor.dacl_aces)
        aces[0] = replace(aces[0], sid=forged_system)
        descriptor = replace(descriptor, dacl_aces=tuple(aces))
    else:
        descriptor = replace(
            descriptor,
            mandatory_label_aces=(
                replace(descriptor.mandatory_label_aces[0], sid=forged_medium),
            ),
        )
    with pytest.raises(module.ProtectedManifestReaderError) as exc_info:
        module._validate_descriptor_policy(
            descriptor,
            reader_sid=READER_SID,
            role="candidate_evidence_root",
        )
    assert exc_info.value.code == "security_policy_mismatch"


def test_direct_inputs_require_exact_types_before_platform(monkeypatch) -> None:
    module = _module()
    configuration = _configuration()
    external = _external_evidence(_manifest_bytes())

    class ConfigurationSubclass(ResolvedPlanConfiguration):
        pass

    class ExternalSubclass(ExternalPinEvidence):
        pass

    configuration_subclass = object.__new__(ConfigurationSubclass)
    object.__setattr__(
        configuration_subclass,
        "_projection_json",
        configuration._projection_json,
    )
    object.__setattr__(
        configuration_subclass,
        "configuration_scope_sha256",
        configuration.configuration_scope_sha256,
    )
    external_subclass = object.__new__(ExternalSubclass)
    object.__setattr__(external_subclass, "_projection_bytes", external._projection_bytes)
    object.__setattr__(
        external_subclass,
        "external_pin_evidence_sha256",
        external.external_pin_evidence_sha256,
    )
    monkeypatch.setattr(module.os, "name", "posix")
    _expect_code(module, configuration_subclass, external, "invalid_configuration")
    _expect_code(
        module,
        configuration,
        external_subclass,
        "invalid_external_pin_evidence",
    )


@pytest.mark.parametrize(
    "case",
    [
        "projection_type",
        "digest_type",
        "digest_mismatch",
        "noncanonical",
        "duplicate_key",
        "extra_key",
        "wrong_schema",
        "wrong_path_flavor",
        "wrong_data_topology",
        "wrong_candidate_topology",
        "noncanonical_windows_path",
    ],
)
def test_configuration_forgery_matrix_fails_before_platform(monkeypatch, case: str) -> None:
    module = _module()
    base = _configuration()
    projection = json.loads(base._projection_json)
    if case == "projection_type":
        forged = _forged_configuration(base, projection_text=b"not text")
    elif case == "digest_type":
        forged = _forged_configuration(base, digest=123)
    elif case == "digest_mismatch":
        forged = _forged_configuration(base, digest="f" * 64)
    elif case == "noncanonical":
        forged = _forged_configuration(
            base,
            projection_text=json.dumps(projection, indent=2),
        )
    elif case == "duplicate_key":
        text = base._projection_json.replace(
            "{",
            '{"schema":"goodq.clean-memory-configuration.v1",',
            1,
        )
        forged = _forged_configuration(base, projection_text=text)
    else:
        if case == "extra_key":
            projection["extra"] = True
        elif case == "wrong_schema":
            projection["schema"] = "wrong"
        elif case == "wrong_path_flavor":
            projection["path_flavor"] = "posix"
        elif case == "wrong_data_topology":
            projection["logical_paths"]["data_root"] = "R:/Other/GoodQ_Data"
        elif case == "wrong_candidate_topology":
            projection["logical_paths"]["candidate_evidence_root"] = (
                "R:/Authority/GoodQ_Data/control/other"
            )
        elif case == "noncanonical_windows_path":
            projection["logical_paths"]["storage_root"] = "r:/Authority"
        forged = _forged_configuration(
            base,
            projection_text=_canonical_text(projection),
        )
    monkeypatch.setattr(module.os, "name", "posix")
    _expect_code(
        module,
        forged,
        _external_evidence(_manifest_bytes()),
        "invalid_configuration",
    )


@pytest.mark.parametrize(
    "case",
    [
        "projection_type",
        "digest_type",
        "digest_mismatch",
        "noncanonical",
        "duplicate_key",
        "extra_key",
        "wrong_schema",
        "wrong_source",
        "wrong_platform",
        "bad_sha",
        "wrong_identity_kind",
        "cross_volume_identity",
        "duplicate_identity",
        "zero_volume_identity",
        "zero_file_identity",
    ],
)
def test_external_evidence_forgery_matrix_fails_before_platform(
    monkeypatch,
    case: str,
) -> None:
    module = _module()
    base = _external_evidence(_manifest_bytes())
    projection = base.projection
    if case == "projection_type":
        forged = _forged_external(base, projection_bytes="not bytes")
    elif case == "digest_type":
        forged = _forged_external(base, digest=123)
    elif case == "digest_mismatch":
        forged = _forged_external(base, digest="f" * 64)
    elif case == "noncanonical":
        forged = _forged_external(
            base,
            projection_bytes=json.dumps(projection, indent=2).encode("utf-8"),
        )
    elif case == "duplicate_key":
        payload = base._projection_bytes.replace(
            b"{",
            b'{"schema":"goodq.clean-memory-external-pin-evidence.v1",',
            1,
        )
        forged = _forged_external(base, projection_bytes=payload)
    else:
        if case == "extra_key":
            projection["extra"] = True
        elif case == "wrong_schema":
            projection["schema"] = "wrong"
        elif case == "wrong_source":
            projection["source_id"] = "wrong"
        elif case == "wrong_platform":
            projection["platform"] = "linux"
        elif case == "bad_sha":
            projection["manifest_sha256"] = "A" * 64
        elif case == "wrong_identity_kind":
            projection["pin_file_identity"]["object_kind"] = "directory"
        elif case == "cross_volume_identity":
            projection["dedicated_directory_identities"][0]["volume_serial"] = (
                "fedcba9876543210"
            )
        elif case == "duplicate_identity":
            projection["dedicated_directory_identities"][1] = dict(
                projection["dedicated_directory_identities"][0]
            )
        elif case == "zero_volume_identity":
            identities = [
                projection["anchor_identity"],
                *projection["dedicated_directory_identities"],
                projection["pin_file_identity"],
            ]
            for identity in identities:
                identity["volume_serial"] = "0" * 16
        elif case == "zero_file_identity":
            projection["pin_file_identity"]["file_id"] = "0" * 16
        forged = _forged_external(
            base,
            projection_bytes=_canonical_bytes(projection),
        )
    monkeypatch.setattr(module, "os", SimpleNamespace(name="posix"))
    _expect_code(
        module,
        _configuration(),
        forged,
        "invalid_external_pin_evidence",
    )


@pytest.mark.parametrize("surface", ["configuration", "external"])
def test_preflight_failure_graph_contains_only_public_errors(
    monkeypatch,
    surface: str,
) -> None:
    module = _module()
    configuration = _configuration()
    external = _external_evidence(_manifest_bytes())
    secret_json = b'{"secret":"R:/Private secret-reader-path S-1-5-21-999"'
    if surface == "configuration":
        configuration = _forged_configuration(
            configuration,
            projection_text=secret_json.decode("utf-8"),
        )
        expected_code = "invalid_configuration"
    else:
        external = _forged_external(external, projection_bytes=secret_json)
        expected_code = "invalid_external_pin_evidence"
    monkeypatch.setattr(module, "os", SimpleNamespace(name="posix"))

    error = _expect_code(module, configuration, external, expected_code)
    _assert_public_error_graph(module, error)


def test_valid_inputs_on_non_windows_stop_before_native_work(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module.os, "name", "posix")
    monkeypatch.setattr(
        module,
        "_bind_security",
        lambda: pytest.fail("native security was reached"),
    )
    _expect_code(
        module,
        _configuration(),
        _external_evidence(_manifest_bytes()),
        "unsupported_platform",
    )


@pytest.mark.parametrize(
    ("shared_code", "reader_code"),
    [
        ("unsupported_security", "unsupported_security"),
        ("unsupported_descriptor", "unsupported_security"),
        ("malformed_descriptor", "observation_failed"),
        ("observation_failed", "observation_failed"),
    ],
)
def test_security_startup_error_translation_precedes_backend(
    monkeypatch,
    shared_code: str,
    reader_code: str,
) -> None:
    module = _module()
    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(
        module,
        "_bind_security",
        lambda: (_ for _ in ()).throw(WindowsSecurityMechanicsError(shared_code)),
    )
    monkeypatch.setattr(
        module,
        "WindowsHeldHandleBackend",
        lambda **_kwargs: pytest.fail("backend constructed before security bound"),
    )
    _expect_code(
        module,
        _configuration(),
        _external_evidence(_manifest_bytes()),
        reader_code,
    )


def test_startup_failure_graph_contains_only_public_errors(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(
        module,
        "_bind_security",
        lambda: (_ for _ in ()).throw(
            OSError("R:/Private secret-reader-path S-1-5-21-999")
        ),
    )

    error = _expect_code(
        module,
        _configuration(),
        _external_evidence(_manifest_bytes()),
        "observation_failed",
    )
    _assert_public_error_graph(module, error)


@pytest.mark.parametrize(
    "exception_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_security_bind_preserves_control_flow(monkeypatch, exception_type) -> None:
    module = _module()
    monkeypatch.setattr(module.os, "name", "nt")
    primary = exception_type()
    original_traceback = _prime_control_primary(primary)
    monkeypatch.setattr(
        module,
        "_bind_security",
        lambda: (_ for _ in ()).throw(primary),
    )
    with pytest.raises(exception_type) as exc_info:
        module.read_protected_manifest(
            _configuration(),
            external_pin_evidence=_external_evidence(_manifest_bytes()),
        )
    assert exc_info.value is primary
    _assert_original_traceback_tail(primary, original_traceback)


def test_startup_control_flow_sanitizes_raw_links(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module.os, "name", "nt")
    primary = SystemExit(76)
    original_traceback = _prime_control_primary(primary)
    raw = OSError("R:/Private secret-reader-path S-1-5-21-999")
    primary.__cause__ = raw
    primary.__context__ = raw
    primary.__suppress_context__ = True
    monkeypatch.setattr(
        module,
        "_bind_security",
        lambda: (_ for _ in ()).throw(primary),
    )

    with pytest.raises(SystemExit) as exc_info:
        module.read_protected_manifest(
            _configuration(),
            external_pin_evidence=_external_evidence(_manifest_bytes()),
        )
    assert exc_info.value is primary
    _assert_original_traceback_tail(primary, original_traceback)
    assert primary.__cause__ is primary.__context__
    assert primary.__suppress_context__ is True
    _assert_control_links_are_public(module, primary)


def test_security_binding_precedes_exact_backend_construction(monkeypatch) -> None:
    module, configuration, external, _payload, events = (
        _install_happy_world(monkeypatch)
    )
    module.read_protected_manifest(configuration, external_pin_evidence=external)
    assert events.index("bind_security") < events.index(
        ("backend", "security_read_label")
    )


def test_reader_identity_profile_luid_and_final_revalidation_are_exact(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    module.read_protected_manifest(configuration, external_pin_evidence=external)
    assert [(event[0], event[1]) for event in events if event[0] == "resolve_luid"] == [
        ("resolve_luid", "SeChangeNotifyPrivilege")
    ]
    assert [event for event in events if event[0] == "open_session"] == [
        ("open_session", WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY)
    ]
    assert len([event for event in events if event[0] == "validate_identity"]) == 2
    assert len([event for event in events if event[0] == "digest_identity"]) == 2


def test_baseline_thread_token_is_untrusted_reader_and_closes_session(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )

    def fail_open(*, profile: str):
        raise WindowsSecurityMechanicsError("thread_token_present")

    monkeypatch.setattr(events.security, "open_token_session", fail_open)
    _expect_code(module, configuration, external, "untrusted_reader")
    assert "enter_backend" not in events


@pytest.mark.parametrize("failure", ["identity", "digest"])
def test_baseline_reader_identity_rejection_is_untrusted_and_closes(
    monkeypatch,
    failure: str,
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    if failure == "identity":
        monkeypatch.setattr(
            module,
            "validate_clean_memory_windows_reader_identity",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                CleanMemoryWindowsReaderIdentityError()
            ),
        )
    else:
        monkeypatch.setattr(
            module,
            "clean_memory_windows_reader_identity_sha256",
            lambda *_args, **_kwargs: "f" * 64,
        )
    _expect_code(module, configuration, external, "untrusted_reader")
    assert events.security.session.closed is True
    assert "enter_backend" not in events


@pytest.mark.parametrize("mode", ["thread_token", "changed_snapshot"])
def test_effective_token_change_is_observation_raced(monkeypatch, mode: str) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    if mode == "thread_token":
        monkeypatch.setattr(
            events.security.session,
            "observe_effective",
            lambda: (_ for _ in ()).throw(
                WindowsSecurityMechanicsError("thread_token_present")
            ),
        )
    else:
        monkeypatch.setattr(
            events.security.session,
            "observe_effective",
            lambda: SimpleNamespace(user_sid=READER_SID, changed=True),
        )
    _expect_code(module, configuration, external, "observation_raced")
    assert events.security.session.closed is True


def test_final_reader_identity_rejection_is_observation_raced(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    calls = 0

    def validate(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise CleanMemoryWindowsReaderIdentityError()

    monkeypatch.setattr(
        module,
        "validate_clean_memory_windows_reader_identity",
        validate,
    )
    _expect_code(module, configuration, external, "observation_raced")
    assert calls == 2
    assert events.security.session.closed is True


def test_configuration_derived_route_has_no_reader_only_component_cap(monkeypatch) -> None:
    storage_root = "R:/" + "/".join(f"Layer{index}" for index in range(32))
    module, configuration, external, _payload, _events = _install_happy_world(
        monkeypatch,
        storage_root=storage_root,
    )
    result = module.read_protected_manifest(
        configuration,
        external_pin_evidence=external,
    )
    assert len(result.projection["route_directory_identities"]) == 35


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("missing", "manifest_missing"),
        ("casefold_duplicate", "duplicate_identity"),
        ("reparse", "redirected_boundary"),
        ("device", "unexpected_entry_type"),
        ("wrong_kind", "unexpected_entry_type"),
        ("cross_volume", "redirected_boundary"),
    ],
)
def test_route_boundary_failures_have_closed_public_codes(
    monkeypatch,
    case: str,
    expected_code: str,
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original_enumerate = backend.enumerate_directory
    original_snapshot = backend.snapshot

    def enumerate_route(handle, filesystem: str):
        values = original_enumerate(handle, filesystem)
        if handle != "anchor":
            return values
        if case == "missing":
            return ()
        entry = values[0]
        if case == "casefold_duplicate":
            return (
                entry,
                replace(entry, name=entry.name.swapcase(), file_id=999),
            )
        if case == "reparse":
            return (replace(entry, attributes=entry.attributes | 0x400),)
        if case == "device":
            return (replace(entry, attributes=entry.attributes | 0x40),)
        if case == "wrong_kind":
            return (replace(entry, attributes=0x80),)
        return values

    def snapshot_route(
        handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        value = original_snapshot(
            handle,
            filesystem=filesystem,
            expected=expected,
            object_kind=object_kind,
            require_stream_contract=require_stream_contract,
        )
        if case == "cross_volume" and handle == "Authority":
            return replace(value, volume_serial=0xFEDCBA9876543210)
        return value

    monkeypatch.setattr(backend, "enumerate_directory", enumerate_route)
    monkeypatch.setattr(backend, "snapshot", snapshot_route)
    _expect_code(module, configuration, external, expected_code)
    assert "validator" not in events


def test_final_parent_membership_change_is_observation_raced(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original = backend.enumerate_directory
    anchor_calls = 0

    def mutate_on_recheck(handle, filesystem: str):
        nonlocal anchor_calls
        values = original(handle, filesystem)
        if handle == "anchor":
            anchor_calls += 1
            if anchor_calls == 2:
                return (*values, replace(values[0], name="extra", file_id=999))
        return values

    monkeypatch.setattr(backend, "enumerate_directory", mutate_on_recheck)
    _expect_code(module, configuration, external, "observation_raced")
    assert anchor_calls == 2


@pytest.mark.parametrize(
    ("surface", "upstream_code"),
    [
        ("manifest_snapshot", "redirected_boundary"),
        ("manifest_snapshot", "unexpected_entry_type"),
        ("parent_enumeration", "duplicate_identity"),
        ("parent_enumeration", "sharing_conflict"),
    ],
)
def test_post_acceptance_held_handle_errors_are_observation_raced(
    monkeypatch,
    surface: str,
    upstream_code: str,
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original_snapshot = backend.snapshot
    original_enumerate = backend.enumerate_directory
    snapshot_calls = 0
    enumeration_calls = 0

    def snapshot_after_acceptance(
        handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        nonlocal snapshot_calls
        if handle == "protected-boundaries.json":
            snapshot_calls += 1
            if surface == "manifest_snapshot" and snapshot_calls == 2:
                raise WindowsHeldHandleError(upstream_code)
        return original_snapshot(
            handle,
            filesystem=filesystem,
            expected=expected,
            object_kind=object_kind,
            require_stream_contract=require_stream_contract,
        )

    def enumerate_after_acceptance(handle, filesystem: str):
        nonlocal enumeration_calls
        if handle == "anchor":
            enumeration_calls += 1
            if surface == "parent_enumeration" and enumeration_calls == 2:
                raise WindowsHeldHandleError(upstream_code)
        return original_enumerate(handle, filesystem)

    monkeypatch.setattr(backend, "snapshot", snapshot_after_acceptance)
    monkeypatch.setattr(backend, "enumerate_directory", enumerate_after_acceptance)
    _expect_code(module, configuration, external, "observation_raced")


@pytest.mark.parametrize(
    ("handle", "call_number", "field_name", "expected_code"),
    [
        ("anchor", 1, "volume_serial", "observation_failed"),
        ("Authority", 1, "file_id", "observation_failed"),
        (
            "protected-boundaries.json",
            2,
            "file_id",
            "observation_raced",
        ),
    ],
)
def test_live_zero_physical_identity_fails_closed(
    monkeypatch,
    handle: str,
    call_number: int,
    field_name: str,
    expected_code: str,
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original = backend.snapshot
    calls = 0

    def zero_identity_snapshot(
        current_handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        nonlocal calls
        value = original(
            current_handle,
            filesystem=filesystem,
            expected=expected,
            object_kind=object_kind,
            require_stream_contract=require_stream_contract,
        )
        if current_handle == handle:
            calls += 1
            if calls == call_number:
                return replace(value, **{field_name: 0})
        return value

    monkeypatch.setattr(backend, "snapshot", zero_identity_snapshot)
    _expect_code(module, configuration, external, expected_code)


@pytest.mark.parametrize(
    ("result", "expected_code"),
    [
        (None, "observation_failed"),
        ((b"payload",), "observation_failed"),
        (("not bytes", True), "observation_failed"),
        ((b"payload", 1), "observation_failed"),
        ((b"payload", False), "observation_raced"),
    ],
)
def test_bounded_read_shape_and_eof_fail_closed(
    monkeypatch,
    result,
    expected_code: str,
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    monkeypatch.setattr(
        events.backend,
        "read_file_bounded",
        lambda _handle, *, maximum_bytes: result,
    )
    _expect_code(module, configuration, external, expected_code)
    assert "validator" not in events


@pytest.mark.parametrize("size", [0, PROTECTED_MANIFEST_MAX_BYTES + 1])
def test_manifest_size_boundary_fails_before_read(monkeypatch, size: int) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original = backend.snapshot

    def sized_snapshot(
        handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        value = original(
            handle,
            filesystem=filesystem,
            expected=expected,
            object_kind=object_kind,
            require_stream_contract=require_stream_contract,
        )
        return replace(value, size_bytes=size) if handle == "protected-boundaries.json" else value

    monkeypatch.setattr(backend, "snapshot", sized_snapshot)
    _expect_code(module, configuration, external, "malformed_manifest")
    assert not any(isinstance(event, tuple) and event[0] == "read" for event in events)


def test_manifest_immediate_resnapshot_change_is_observation_raced(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original = backend.snapshot
    calls = 0

    def racing_snapshot(
        handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        nonlocal calls
        value = original(
            handle,
            filesystem=filesystem,
            expected=expected,
            object_kind=object_kind,
            require_stream_contract=require_stream_contract,
        )
        if handle == "protected-boundaries.json":
            calls += 1
            if calls == 2:
                return replace(value, change_ticks=value.change_ticks + 1)
        return value

    monkeypatch.setattr(backend, "snapshot", racing_snapshot)
    _expect_code(module, configuration, external, "observation_raced")
    assert "validator" not in events


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("value_error", "malformed_manifest"),
        ("unexpected_error", "observation_failed"),
        ("wrong_type", "observation_failed"),
        ("wrong_digest", "observation_failed"),
    ],
)
def test_validator_failure_and_result_integrity(
    monkeypatch,
    mode: str,
    expected_code: str,
) -> None:
    module, configuration, external, payload, _events = _install_happy_world(
        monkeypatch
    )
    if mode == "value_error":
        validator = lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError())
    elif mode == "unexpected_error":
        validator = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    elif mode == "wrong_type":
        validator = lambda *_args, **_kwargs: object()
    else:
        real = importlib.import_module(
            "steps.common.clean_memory_protected_manifest"
        ).validate_protected_manifest(payload, path_flavor="windows")
        forged = object.__new__(CanonicalProtectedManifest)
        object.__setattr__(forged, "_manifest_bytes", real._manifest_bytes)
        object.__setattr__(forged, "manifest_sha256", "f" * 64)
        validator = lambda *_args, **_kwargs: forged
    monkeypatch.setattr(module, "validate_protected_manifest", validator)
    _expect_code(module, configuration, external, expected_code)


@pytest.mark.parametrize(
    "case",
    [
        "control",
        "owner",
        "group",
        "dacl_present",
        "dacl_null",
        "dacl_revision",
        "dacl_order",
        "dacl_type",
        "dacl_flags",
        "dacl_mask",
        "sacl_present",
        "sacl_null",
        "sacl_revision",
        "label_type",
        "label_flags",
        "label_mask",
        "label_count",
    ],
)
def test_candidate_descriptor_policy_matrix_fails_closed(monkeypatch, case: str) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    descriptor = _candidate_descriptor()
    if case == "control":
        descriptor = replace(descriptor, control=0xB004)
    elif case == "owner":
        descriptor = replace(descriptor, owner=SYSTEM_SID)
    elif case == "group":
        descriptor = replace(descriptor, group=SYSTEM_SID)
    elif case == "dacl_present":
        descriptor = replace(descriptor, dacl_present=False)
    elif case == "dacl_null":
        descriptor = replace(descriptor, dacl_null=True)
    elif case == "dacl_revision":
        descriptor = replace(descriptor, dacl_revision=4)
    elif case == "dacl_order":
        descriptor = replace(
            descriptor,
            dacl_aces=(descriptor.dacl_aces[1], descriptor.dacl_aces[0], *descriptor.dacl_aces[2:]),
        )
    elif case in {"dacl_type", "dacl_flags", "dacl_mask"}:
        values = list(descriptor.dacl_aces)
        changes = {
            "dacl_type": {"ace_type": 1},
            "dacl_flags": {"flags": 0x02},
            "dacl_mask": {"mask": 0x001200A2},
        }
        values[2] = replace(values[2], **changes[case])
        descriptor = replace(descriptor, dacl_aces=tuple(values))
    elif case == "sacl_present":
        descriptor = replace(descriptor, sacl_present=False)
    elif case == "sacl_null":
        descriptor = replace(descriptor, sacl_null=True)
    elif case == "sacl_revision":
        descriptor = replace(descriptor, sacl_revision=4)
    elif case == "label_count":
        descriptor = replace(descriptor, mandatory_label_aces=())
    else:
        label = descriptor.mandatory_label_aces[0]
        changes = {
            "label_type": {"ace_type": 0x12},
            "label_flags": {"flags": 0x01},
            "label_mask": {"mask": 0x02},
        }
        descriptor = replace(
            descriptor,
            mandatory_label_aces=(replace(label, **changes[case]),),
        )
    original = events.security.pin_security_descriptor

    def pin(value: bytes, *, profile: str):
        if value == b"candidate-descriptor":
            return _FakePinnedDescriptor(descriptor)
        return original(value, profile=profile)

    monkeypatch.setattr(events.security, "pin_security_descriptor", pin)
    _expect_code(module, configuration, external, "security_policy_mismatch")
    assert "validator" not in events


def test_denial_masks_order_and_immediate_scope_closure_are_exact(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    module.read_protected_manifest(configuration, external_pin_evidence=external)
    denial_masks = [event[1] for event in events if isinstance(event, tuple) and event[0] == "deny"]
    expected = [mask for _name, mask in (*CANDIDATE_RIGHTS, *MANIFEST_RIGHTS)]
    assert denial_masks == [*expected, *expected]
    assert events.count("open_access") == 4
    assert events.count("close_scope") == 4
    for index, event in enumerate(events):
        if event == "close_scope":
            assert not (
                index + 1 < len(events)
                and isinstance(events[index + 1], tuple)
                and events[index + 1][0] == "deny"
            )


@pytest.mark.parametrize(
    ("access_call", "expected_code"),
    [(1, "security_policy_mismatch"), (3, "observation_raced")],
)
def test_denial_result_mismatch_maps_by_lifecycle_phase(
    monkeypatch,
    access_call: int,
    expected_code: str,
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    calls = 0

    class Scope(_FakeAccessScope):
        def __init__(self, event_log, *, corrupt: bool):
            super().__init__(event_log)
            self.corrupt = corrupt

        def check_denial(self, *, raw_mask: int):
            self.events.append(("deny", raw_mask))
            return WindowsMutationDenial(
                raw_mask,
                raw_mask + 1 if self.corrupt else raw_mask,
                True,
            )

    def open_scope(_descriptor):
        nonlocal calls
        calls += 1
        events.append("open_access")
        return Scope(events, corrupt=calls == access_call)

    monkeypatch.setattr(events.security.session, "open_access_check", open_scope)
    _expect_code(module, configuration, external, expected_code)
    assert events.count("close_scope") == access_call


def test_descriptor_bytes_change_during_recheck_is_observation_raced(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    original = events.backend.read_security_descriptor
    candidate_reads = 0

    def changing_descriptor(handle):
        nonlocal candidate_reads
        if handle == "clean_memory":
            candidate_reads += 1
            if candidate_reads == 2:
                return b"changed-candidate-descriptor"
        return original(handle)

    monkeypatch.setattr(events.backend, "read_security_descriptor", changing_descriptor)
    _expect_code(module, configuration, external, "observation_raced")
    assert candidate_reads == 2


def _manual_ace(ace: WindowsAce, *, label: bool = False) -> dict[str, str]:
    return {
        "flags": f"{ace.flags:02x}",
        "mask": f"{ace.mask:08x}",
        "sid": ace.sid.numeric,
        "type": "system_mandatory_label" if label else "access_allowed",
    }


def _manual_policy_object(
    descriptor: WindowsSecurityDescriptor,
    *,
    identity: dict[str, str],
    role: str,
    rights,
) -> dict[str, object]:
    return {
        "dacl": [_manual_ace(ace) for ace in descriptor.dacl_aces],
        "dacl_revision": descriptor.dacl_revision,
        "denied_access_checks": [
            {
                "denied": True,
                "mapped_mask": f"{mask:08x}",
                "name": name,
                "raw_mask": f"{mask:08x}",
            }
            for name, mask in rights
        ],
        "descriptor_control": f"{descriptor.control:04x}",
        "mandatory_label": {
            "aces": [
                _manual_ace(ace, label=True)
                for ace in descriptor.mandatory_label_aces
            ],
            "acl_revision": descriptor.sacl_revision,
        },
        "owner_sid": descriptor.owner.numeric,
        "physical_identity": identity,
        "primary_group_sid": descriptor.group.numeric,
        "role": role,
    }


def test_security_policy_digest_matches_independent_canonical_projection(monkeypatch) -> None:
    module, configuration, external, _payload, _events = _install_happy_world(
        monkeypatch
    )
    result = module.read_protected_manifest(configuration, external_pin_evidence=external)
    projection = result.projection
    policy = {
        "candidate_evidence_root": _manual_policy_object(
            _candidate_descriptor(),
            identity=projection["route_directory_identities"][-1],
            role="candidate_evidence_root",
            rights=CANDIDATE_RIGHTS,
        ),
        "manifest_file": _manual_policy_object(
            _manifest_descriptor(),
            identity=projection["manifest_file_identity"],
            role="manifest_file",
            rights=MANIFEST_RIGHTS,
        ),
        "schema": "goodq.clean-memory-protected-manifest-security-policy.v1",
    }
    assert projection["security_policy_sha256"] == hashlib.sha256(
        _canonical_bytes(policy)
    ).hexdigest()


def test_evidence_projection_is_deeply_detached_and_manifest_bytes_are_private(
    monkeypatch,
) -> None:
    module, configuration, external, payload, _events = _install_happy_world(
        monkeypatch
    )
    result = module.read_protected_manifest(configuration, external_pin_evidence=external)
    first = result.projection
    first["route_directory_identities"][0]["file_id"] = "f" * 16
    assert result.projection["route_directory_identities"][0]["file_id"] != "f" * 16
    assert result.manifest_bytes is payload
    rendered = repr(result)
    assert "_manifest_bytes" not in rendered
    assert payload.decode("utf-8") not in rendered
    assert "absolute_path" not in _canonical_text(result.projection)


def test_manifest_identity_duplicate_is_detected_before_validator(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    backend = events.backend
    original = backend.snapshot

    def duplicate_candidate(
        handle,
        *,
        filesystem: str,
        expected,
        object_kind: str,
        require_stream_contract: bool,
    ):
        value = original(
            handle,
            filesystem=filesystem,
            expected=expected,
            object_kind=object_kind,
            require_stream_contract=require_stream_contract,
        )
        if handle == "protected-boundaries.json":
            return replace(
                value,
                file_id=backend.numbers["clean_memory"],
                object_kind="regular_file",
            )
        return value

    monkeypatch.setattr(backend, "snapshot", duplicate_candidate)
    _expect_code(module, configuration, external, "duplicate_identity")
    assert "validator" not in events


def test_unsupported_filesystem_is_public_and_stops_before_traversal(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    monkeypatch.setattr(events.backend, "volume_filesystem", lambda _handle: "FAT32")
    _expect_code(module, configuration, external, "unsupported_filesystem")
    assert not any(isinstance(event, tuple) and event[0] == "open_by_id" for event in events)


def test_cleanup_only_failures_are_ordered_and_normalized(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )

    def fail_exit(_exc_type, _exc, _traceback):
        raise WindowsHeldHandleError("sharing_conflict")

    def fail_session_close():
        events.security.session.closed = True
        raise WindowsSecurityMechanicsError("unsupported_security")

    monkeypatch.setattr(events.backend, "__exit__", fail_exit)
    monkeypatch.setattr(events.security.session, "close", fail_session_close)
    error = _expect_code(module, configuration, external, "observation_failed")
    graph = _walk_exception_graph(error)
    assert len(graph) >= 2
    assert {node.code for node in graph} == {"observation_failed"}
    _assert_public_error_graph(module, error)


def test_operation_primary_keeps_code_before_all_cleanup_failures(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    monkeypatch.setattr(
        events.backend,
        "read_file_bounded",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            WindowsHeldHandleError("sharing_conflict")
        ),
    )
    monkeypatch.setattr(
        events.backend,
        "__exit__",
        lambda *_args: (_ for _ in ()).throw(OSError("secret-reader-path")),
    )
    monkeypatch.setattr(
        events.security.session,
        "close",
        lambda: (_ for _ in ()).throw(OSError("S-1-5-21-999")),
    )
    error = _expect_code(module, configuration, external, "sharing_conflict")
    graph = _walk_exception_graph(error)
    assert sum(node.code == "observation_failed" for node in graph) >= 2
    _assert_public_error_graph(module, error)


def test_cleanup_sanitizer_failure_cannot_skip_session_close(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    original = module._sanitize_error
    session_closed = False

    def fail_exit(_exc_type, _exc, _traceback):
        raise OSError("secret-reader-path")

    def fail_sanitizer(error, *, phase="observation"):
        if phase == "cleanup":
            raise MemoryError()
        return original(error, phase=phase)

    def close_session():
        nonlocal session_closed
        session_closed = True

    monkeypatch.setattr(events.backend, "__exit__", fail_exit)
    monkeypatch.setattr(module, "_sanitize_error", fail_sanitizer)
    monkeypatch.setattr(events.security.session, "close", close_session)
    _expect_code(module, configuration, external, "observation_failed")
    assert session_closed is True


@pytest.mark.parametrize(
    ("operation_type", "cleanup_type"),
    [
        (KeyboardInterrupt, SystemExit),
        (SystemExit, GeneratorExit),
        (GeneratorExit, KeyboardInterrupt),
    ],
)
def test_operation_control_flow_remains_primary_over_cleanup_control(
    monkeypatch,
    operation_type: type[BaseException],
    cleanup_type: type[BaseException],
) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    operation_control = operation_type()
    cleanup_control = cleanup_type()
    original_traceback = _prime_control_primary(operation_control)

    monkeypatch.setattr(
        events.backend,
        "read_file_bounded",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(operation_control),
    )
    monkeypatch.setattr(
        events.backend,
        "__exit__",
        lambda *_args: (_ for _ in ()).throw(cleanup_control),
    )

    with pytest.raises(operation_type) as exc_info:
        module.read_protected_manifest(
            configuration,
            external_pin_evidence=external,
        )
    assert exc_info.value is operation_control
    _assert_original_traceback_tail(operation_control, original_traceback)
    assert cleanup_control not in _walk_exception_graph(operation_control)
    linked = operation_control.__cause__ or operation_control.__context__
    assert type(linked) is module.ProtectedManifestReaderError
    _assert_public_error_graph(module, linked)
    assert events.security.session.closed is True


def test_unknown_base_exception_from_operation_is_sanitized(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )

    class SecretSignal(BaseException):
        pass

    signal = SecretSignal("R:/Private secret-reader-path S-1-5-21-999")
    monkeypatch.setattr(
        events.backend,
        "read_file_bounded",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(signal),
    )

    error = _expect_code(module, configuration, external, "observation_failed")
    assert signal not in _walk_exception_graph(error)
    _assert_public_error_graph(module, error)
    assert events.security.session.closed is True


def test_unknown_base_exception_from_cleanup_is_sanitized(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )

    class SecretSignal(BaseException):
        pass

    signal = SecretSignal("R:/Private secret-reader-path S-1-5-21-999")
    monkeypatch.setattr(
        events.backend,
        "__exit__",
        lambda *_args: (_ for _ in ()).throw(signal),
    )

    error = _expect_code(module, configuration, external, "observation_failed")
    assert signal not in _walk_exception_graph(error)
    _assert_public_error_graph(module, error)
    assert events.security.session.closed is True


def test_only_named_control_flow_families_are_preserved() -> None:
    module = _module()

    class SecretSignal(BaseException):
        pass

    assert module._is_control_flow(KeyboardInterrupt()) is True
    assert module._is_control_flow(SystemExit()) is True
    assert module._is_control_flow(GeneratorExit()) is True
    assert module._is_control_flow(SecretSignal()) is False
    assert module._is_control_flow(BaseException()) is False


def test_sanitizer_failure_cannot_replace_selected_cleanup_control(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    operation = WindowsHeldHandleError("sharing_conflict")
    cleanup_control = KeyboardInterrupt()
    sanitizer_control = SystemExit(74)
    original_traceback = _prime_control_primary(cleanup_control)
    original_sanitizer = module._sanitize_error
    cleanup_started = False
    sanitizer_branch_hit = False

    def fail_operation_sanitization(error, *, phase="observation"):
        nonlocal sanitizer_branch_hit
        if cleanup_started and not sanitizer_branch_hit:
            sanitizer_branch_hit = True
            raise sanitizer_control
        return original_sanitizer(error, phase=phase)

    def interrupt_cleanup(*_args):
        nonlocal cleanup_started
        cleanup_started = True
        raise cleanup_control

    monkeypatch.setattr(
        events.backend,
        "read_file_bounded",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(operation),
    )
    monkeypatch.setattr(
        events.backend,
        "__exit__",
        interrupt_cleanup,
    )
    monkeypatch.setattr(module, "_sanitize_error", fail_operation_sanitization)

    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_protected_manifest(
            configuration,
            external_pin_evidence=external,
        )
    assert exc_info.value is cleanup_control
    assert exc_info.value is not sanitizer_control
    _assert_original_traceback_tail(cleanup_control, original_traceback)
    linked = cleanup_control.__cause__ or cleanup_control.__context__
    assert type(linked) is module.ProtectedManifestReaderError
    _assert_public_error_graph(module, linked)
    assert events.security.session.closed is True
    assert sanitizer_branch_hit is True


@pytest.mark.parametrize(
    "exception_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_post_cleanup_sanitizer_control_becomes_primary_when_unopposed(
    monkeypatch,
    exception_type: type[BaseException],
) -> None:
    module = _module()
    operation = OSError("R:/Private secret-reader-path S-1-5-21-999")
    cleanup = module.ProtectedManifestReaderError("observation_failed")
    fallback = module.ProtectedManifestReaderError("observation_failed")
    sanitizer_control = exception_type()
    original_traceback = _prime_control_primary(sanitizer_control)
    raw = OSError("R:/Private secret-reader-path S-1-5-21-999")
    sanitizer_control.__cause__ = raw
    sanitizer_control.__context__ = raw
    sanitizer_control.__suppress_context__ = True

    def interrupt_sanitization(error, *, phase="observation"):
        assert error in {operation, raw}
        raise sanitizer_control

    monkeypatch.setattr(module, "_sanitize_error", interrupt_sanitization)

    with pytest.raises(exception_type) as exc_info:
        module._raise_after_cleanup(
            operation,
            cleanup,
            control_fallback=fallback,
        )
    assert exc_info.value is sanitizer_control
    _assert_original_traceback_tail(sanitizer_control, original_traceback)
    assert sanitizer_control.__suppress_context__ is True
    _assert_control_links_are_public(module, sanitizer_control)
    assert cleanup in _walk_exception_graph(sanitizer_control)


def test_access_scope_sanitizer_failure_preserves_cleanup_control(monkeypatch) -> None:
    module, configuration, external, _payload, events = _install_happy_world(
        monkeypatch
    )
    operation = WindowsSecurityMechanicsError("observation_failed")
    cleanup_control = KeyboardInterrupt()
    sanitizer_control = SystemExit(75)
    original_traceback = _prime_control_primary(cleanup_control)
    original_sanitizer = module._sanitize_error
    cleanup_started = False

    class FailingScope:
        def check_denial(self, *, raw_mask: int):
            raise operation

        def close(self):
            nonlocal cleanup_started
            cleanup_started = True
            raise cleanup_control

    def fail_operation_sanitization(error, *, phase="observation"):
        if cleanup_started and error is operation:
            raise sanitizer_control
        return original_sanitizer(error, phase=phase)

    monkeypatch.setattr(
        events.security.session,
        "open_access_check",
        lambda _descriptor: FailingScope(),
    )
    monkeypatch.setattr(module, "_sanitize_error", fail_operation_sanitization)

    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_protected_manifest(
            configuration,
            external_pin_evidence=external,
        )
    assert exc_info.value is cleanup_control
    assert exc_info.value is not sanitizer_control
    _assert_original_traceback_tail(cleanup_control, original_traceback)
    linked = cleanup_control.__cause__ or cleanup_control.__context__
    assert type(linked) is module.ProtectedManifestReaderError
    _assert_public_error_graph(module, linked)
    assert events.security.session.closed is True


@pytest.mark.parametrize("depth", [256, 257])
def test_cleanup_append_retains_later_failure_at_saturation(depth: int) -> None:
    module = _module()
    head = module.ProtectedManifestReaderError("observation_failed")
    current = head
    for _index in range(depth - 1):
        linked = module.ProtectedManifestReaderError("observation_failed")
        current.__cause__ = linked
        current = linked
    later = module.ProtectedManifestReaderError("observation_failed")

    assert module._append_cleanup(head, later) is head
    graph = _walk_exception_graph(head)
    assert later in graph
    assert len(graph) <= depth + 1
    _assert_public_error_graph(module, head)


def test_cleanup_append_helper_has_no_dynamic_collection_allocation() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_append_cleanup"
    )
    forbidden_nodes = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    assert not any(isinstance(node, forbidden_nodes) for node in ast.walk(function))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"dict", "list", "set"}
        for node in ast.walk(function)
    )


def test_reader_imports_and_capabilities_remain_statically_contained() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    project_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith(("cli.", "steps."))
    }
    assert project_imports == {
        "cli.clean_memory",
        "cli.clean_memory_external_pin",
        "steps.common.clean_memory_protected_manifest",
        "steps.common.clean_memory_windows_reader_identity",
        "steps.common.windows_held_handle",
        "steps.common.windows_security_mechanics",
    }
    assert not any(
        alias.name.startswith("_")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )
    forbidden_fragments = (
        "clean_memory_protected_membership",
        "clean_memory_filesystem",
        "candidate_plan",
        "miniagent",
        "approval",
        "cleanup_execution",
        "hash_file",
        "os.getenv",
        "os.environ",
    )
    assert not any(fragment in source for fragment in forbidden_fragments)
    forbidden_calls = {"open", "eval", "exec", "__import__"}
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in forbidden_calls
        for node in ast.walk(tree)
    )
