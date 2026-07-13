from __future__ import annotations

import ast
import builtins
import ctypes
from dataclasses import fields, FrozenInstanceError
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from cli.clean_memory import ResolvedPlanConfiguration, resolve_plan_configuration
from steps.common.clean_memory import (
    FilesystemTargetEvidence,
    ProtectedBoundaryEvidence,
    QdrantCollectionEvidence,
    ResolvedCleanupScope,
    build_candidate_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cli" / "clean_memory_filesystem.py"
EPOCH_ID = "epoch_2026_07_observer"
SINGLETONS = (
    ("memory_database", "memory.db"),
    ("memory_database_wal", "memory.db-wal"),
    ("memory_database_shm", "memory.db-shm"),
    ("knowledge_graph_database", "knowledge_graph.db"),
    ("knowledge_graph_database_wal", "knowledge_graph.db-wal"),
    ("knowledge_graph_database_shm", "knowledge_graph.db-shm"),
)


def _load_module():
    assert MODULE_PATH.is_file(), "clean-memory filesystem observer has not been implemented"
    return importlib.import_module("cli.clean_memory_filesystem")


def _as_config_path(path: Path) -> str:
    return path.absolute().as_posix()


def _config(outer_root: Path, *, epoch_id: str = EPOCH_ID) -> dict[str, object]:
    data_root = outer_root / "GoodQ_Data"
    epoch_root = data_root / "epochs" / epoch_id

    def rendered(path: Path) -> str:
        return _as_config_path(path)

    collections = {
        role: f"goodq_{role}_{epoch_id}"
        for role in ("text", "clip", "dino", "audio")
    }
    paths: dict[str, object] = {
        "data_root": rendered(data_root),
        "db_dir": rendered(epoch_root),
        "db_path": rendered(epoch_root / "memory.db"),
        "knowledge_graph_db": rendered(epoch_root / "knowledge_graph.db"),
        "faiss_dir": rendered(epoch_root / "faiss"),
        "faiss_index_path": rendered(epoch_root / "faiss" / "text" / "faiss_text.index"),
        "faiss_clip_path": rendered(epoch_root / "faiss" / "clip" / "faiss_clip.index"),
        "faiss_dino_path": rendered(epoch_root / "faiss" / "dino" / "faiss_dino.index"),
        "faiss_audio_path": rendered(epoch_root / "faiss" / f"goodq_audio_{epoch_id}.index"),
        "clip_id_map_db": rendered(epoch_root / "faiss" / "clip" / "clip_id_map.sqlite"),
        "dino_id_map_db": rendered(epoch_root / "faiss" / "dino" / "dino_id_map.sqlite"),
        "clap_id_map_db": rendered(epoch_root / "faiss" / "audio" / "clap_id_map.sqlite"),
        "import_inbox": rendered(data_root / "import_inbox"),
        "processing": rendered(epoch_root / "processing"),
        "processed": rendered(data_root / "processed"),
        "failed": rendered(data_root / "failed"),
        "models_cache": rendered(outer_root / "models"),
        "qdrant_storage": rendered(outer_root / "qdrant_storage"),
        "watchdog_state_file": rendered(epoch_root / "logs" / "watchdog_state.json"),
        "watchdog_lock_file": rendered(epoch_root / "logs" / "watchdog.lock"),
        "nas_path": rendered(data_root / "archive"),
    }
    return {
        "host": {"data_root": rendered(outer_root), "profile": "BASELINE"},
        "paths": paths,
        "qdrant": {
            "enabled": True,
            "host": "http://127.0.0.1:6333",
            "collections": collections,
        },
        "phase6": {
            "clip_collection": collections["clip"],
            "dino_collection": collections["dino"],
        },
    }


def _projection(outer_root: Path) -> ResolvedPlanConfiguration:
    return resolve_plan_configuration(_config(outer_root), requested_epoch_id=EPOCH_ID)


def _clone_projection(
    source: ResolvedPlanConfiguration,
    mutate,
) -> ResolvedPlanConfiguration:
    payload = json.loads(source._projection_json)
    mutate(payload)
    projection_json = _canonical_json(payload)
    clone = object.__new__(ResolvedPlanConfiguration)
    object.__setattr__(clone, "_projection_json", projection_json)
    object.__setattr__(
        clone,
        "configuration_scope_sha256",
        hashlib.sha256(projection_json.encode("utf-8")).hexdigest(),
    )
    return clone


def _private_windows_projection(module, epoch_root: str = "L:/epoch"):
    return module._Projection(
        canonical_json="{}",
        configuration_scope_sha256="0" * 64,
        path_flavor="windows",
        epoch_id=EPOCH_ID,
        epoch_root=epoch_root,
        logical_paths={},
    )


def _epoch_root(outer_root: Path) -> Path:
    return outer_root / "GoodQ_Data" / "epochs" / EPOCH_ID


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _identity(marker: str) -> str:
    return _canonical_json({"schema": "goodq.test-identity.v1", "value": marker})


def _qdrant_evidence() -> tuple[QdrantCollectionEvidence, ...]:
    return tuple(
        QdrantCollectionEvidence(
            role=role,
            collection_name=f"goodq_{role}_{EPOCH_ID}",
            exists=False,
            configuration_json=None,
            point_count=None,
            fingerprint_kind=None,
            fingerprint_value=None,
        )
        for role in ("text", "clip", "dino", "audio")
    )


def _protected_evidence() -> tuple[ProtectedBoundaryEvidence, ...]:
    from steps.common.clean_memory import PROTECTED_BOUNDARY_ROLES

    return tuple(
        ProtectedBoundaryEvidence(
            role=role,
            logical_id=f"protected:{role}",
            identity_json=_identity(role),
        )
        for role in PROTECTED_BOUNDARY_ROLES
    )


def test_public_api_schema_and_error_contract_are_exact() -> None:
    module = _load_module()

    assert module.__all__ == (
        "FILESYSTEM_OBSERVATION_SCHEMA",
        "FilesystemObservationError",
        "FilesystemObservation",
        "observe_filesystem",
    )
    assert (
        module.FILESYSTEM_OBSERVATION_SCHEMA
        == "goodq.clean-memory-filesystem-observation.v1"
    )

    expected = {
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
    for code, message in expected.items():
        error = module.FilesystemObservationError(code)
        assert error.code == code
        assert str(error) == message
        with pytest.raises((AttributeError, TypeError)):
            error.code = "tampered"

    with pytest.raises(ValueError):
        module.FilesystemObservationError("unknown")


def test_public_result_shape_and_import_authority_are_exact() -> None:
    module = _load_module()

    assert tuple(field.name for field in fields(module.FilesystemObservation)) == (
        "schema",
        "configuration_scope_sha256",
        "epoch_id",
        "epoch_root_identity_json",
        "filesystem_targets",
    )
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    project_imports = {
        node.module: tuple(alias.name for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in {"cli.clean_memory", "steps.common.clean_memory"}
    }
    assert project_imports == {
        "cli.clean_memory": ("ResolvedPlanConfiguration",),
        "steps.common.clean_memory": ("FilesystemTargetEvidence",),
    }


def test_non_projection_and_tampered_projection_fail_before_filesystem_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("filesystem access occurred before configuration rejection")

    for name in ("open", "stat", "lstat", "scandir", "readlink"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem({})
    assert exc_info.value.code == "invalid_configuration"

    projection = _projection(tmp_path / "outer")
    object.__setattr__(projection, "_projection_json", projection._projection_json + " ")
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(projection)
    assert exc_info.value.code == "invalid_configuration"


def test_rehashed_invalid_authority_and_subclass_fail_before_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    projection = _projection(tmp_path / "outer")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("backend reached for unauthenticated projection")

    monkeypatch.setattr(module, "_observe_windows", forbidden)
    monkeypatch.setattr(module, "_observe_posix", forbidden)

    class ProjectionSubclass(ResolvedPlanConfiguration):
        pass

    subclass = object.__new__(ProjectionSubclass)
    object.__setattr__(subclass, "_projection_json", projection._projection_json)
    object.__setattr__(
        subclass,
        "configuration_scope_sha256",
        projection.configuration_scope_sha256,
    )
    invalid_cases = [
        subclass,
        _clone_projection(
            projection,
            lambda payload: payload["logical_paths"].__setitem__(
                "faiss_root", payload["epoch"]["root"] + "/redirected"
            ),
        ),
        _clone_projection(
            projection,
            lambda payload: payload["qdrant"].__setitem__("enabled", False),
        ),
    ]
    digest_mismatch = _clone_projection(projection, lambda _payload: None)
    object.__setattr__(digest_mismatch, "configuration_scope_sha256", "f" * 64)
    invalid_cases.append(digest_mismatch)

    for invalid in invalid_cases:
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            module.observe_filesystem(invalid)
        assert exc_info.value.code == "invalid_configuration"


def test_host_path_flavor_mismatch_fails_before_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    projection = _projection(tmp_path / "outer")

    def switch_to_posix(payload: dict[str, object]) -> None:
        def convert(value: str) -> str:
            _drive, remainder = value.split(":", 1)
            return remainder

        payload["path_flavor"] = "posix"
        epoch = payload["epoch"]
        assert isinstance(epoch, dict)
        epoch["root"] = convert(epoch["root"])
        logical = payload["logical_paths"]
        assert isinstance(logical, dict)
        for key, value in tuple(logical.items()):
            logical[key] = convert(value)
        declared = payload["declared_faiss_paths"]
        assert isinstance(declared, dict)
        for key, value in tuple(declared.items()):
            declared[key] = convert(value)
        protected = payload["configured_protected_paths"]
        assert isinstance(protected, list)
        for record in protected:
            record["paths"] = [convert(value) for value in record["paths"]]

    mismatched = _clone_projection(projection, switch_to_posix)
    monkeypatch.setattr(
        module,
        "_observe_windows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("backend reached for path-flavor mismatch")
        ),
    )
    monkeypatch.setattr(module, "_observe_posix", module._observe_windows)

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(mismatched)
    assert exc_info.value.code == "invalid_configuration"


def test_projection_mutation_during_observation_is_a_race(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    projection = _projection(tmp_path / "outer")

    def mutate_during_observation(_projection_value):
        object.__setattr__(projection, "_projection_json", projection._projection_json + " ")
        return _identity("epoch"), ()

    monkeypatch.setattr(module, "_observe_windows", mutate_during_observation)
    monkeypatch.setattr(module, "_observe_posix", mutate_during_observation)

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(projection)
    assert exc_info.value.code == "observation_raced"


def test_temporary_tree_observation_is_exact_deterministic_and_composable(
    tmp_path: Path,
) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    epoch = _epoch_root(outer)
    epoch.mkdir(parents=True)
    payloads = {
        "memory.db": b"memory-primary",
        "knowledge_graph.db": b"knowledge-graph",
        "faiss/.hidden": b"hidden",
        "faiss/audio/future.bin": b"future-audio",
        "faiss/text/faiss_text.index": b"text-index",
    }
    for relative, payload in payloads.items():
        _write(epoch / relative, payload)

    configuration = _projection(outer)
    first = module.observe_filesystem(configuration)
    second = module.observe_filesystem(configuration)

    assert first == second
    assert first.schema == module.FILESYSTEM_OBSERVATION_SCHEMA
    assert first.configuration_scope_sha256 == configuration.configuration_scope_sha256
    assert first.epoch_id == EPOCH_ID
    assert "outer" not in first.epoch_root_identity_json
    assert tuple((item.role, item.relative_path) for item in first.filesystem_targets) == (
        ("memory_database", "memory.db"),
        ("memory_database_wal", "memory.db-wal"),
        ("memory_database_shm", "memory.db-shm"),
        ("knowledge_graph_database", "knowledge_graph.db"),
        ("knowledge_graph_database_wal", "knowledge_graph.db-wal"),
        ("knowledge_graph_database_shm", "knowledge_graph.db-shm"),
        ("faiss_file", "faiss/.hidden"),
        ("faiss_file", "faiss/audio/future.bin"),
        ("faiss_file", "faiss/text/faiss_text.index"),
    )
    for item in first.filesystem_targets:
        assert isinstance(item, FilesystemTargetEvidence)
        assert item.target_type == "regular_file"
        if item.exists:
            payload = payloads[item.relative_path]
            assert item.size_bytes == len(payload)
            assert item.sha256 == hashlib.sha256(payload).hexdigest()
            assert item.mtime_ns is not None and item.mtime_ns >= 0
            assert item.file_identity_json is not None
            assert str(epoch) not in item.file_identity_json
        else:
            assert item.size_bytes is None
            assert item.mtime_ns is None
            assert item.file_identity_json is None
            assert item.sha256 is None

    scope = ResolvedCleanupScope(
        epoch_id=EPOCH_ID,
        config_scope_sha256=first.configuration_scope_sha256,
        epoch_root_identity_json=first.epoch_root_identity_json,
        filesystem_targets=first.filesystem_targets,
        qdrant_endpoint="http://127.0.0.1:6333",
        qdrant_collections=_qdrant_evidence(),
        protected_boundaries=_protected_evidence(),
    )
    plan = build_candidate_plan(scope, observed_at_utc="2026-07-13T00:00:00+00:00")
    assert plan.authority["epoch"]["epoch_id"] == EPOCH_ID

    with pytest.raises(FrozenInstanceError):
        first.epoch_id = "tampered"


def test_stably_absent_singletons_and_faiss_have_no_stale_state(tmp_path: Path) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    _epoch_root(outer).mkdir(parents=True)

    result = module.observe_filesystem(_projection(outer))

    assert len(result.filesystem_targets) == 6
    assert tuple((item.role, item.relative_path) for item in result.filesystem_targets) == SINGLETONS
    for item in result.filesystem_targets:
        assert item.target_type == "regular_file"
        assert item.exists is False
        assert item.size_bytes is None
        assert item.mtime_ns is None
        assert item.file_identity_json is None
        assert item.sha256 is None


def test_missing_required_epoch_root_is_not_an_empty_observation(tmp_path: Path) -> None:
    module = _load_module()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(_projection(tmp_path / "outer"))
    assert exc_info.value.code == "required_root_missing"


def test_hardlinked_faiss_member_fails_closed(tmp_path: Path) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    epoch = _epoch_root(outer)
    first = epoch / "faiss" / "first.index"
    second = epoch / "faiss" / "second.index"
    _write(first, b"same-object")
    try:
        os.link(first, second)
    except OSError as exc:
        pytest.skip(f"hardlinks unavailable on this test filesystem: {exc}")

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(_projection(outer))
    assert exc_info.value.code == "duplicate_identity"


def test_redirected_faiss_root_never_reads_outside_canary(tmp_path: Path) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    epoch = _epoch_root(outer)
    epoch.mkdir(parents=True)
    outside = tmp_path / "outside"
    canary = outside / "SECRET_OUTSIDE_CANARY.bin"
    _write(canary, b"must-never-be-read")
    try:
        os.symlink(outside, epoch / "faiss", target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(_projection(outer))
    assert exc_info.value.code == "redirected_boundary"


@pytest.mark.parametrize(
    "relative_path",
    (
        "faiss/e\u0301.index",
        "faiss/control\x01.index",
        "faiss/nul\x00.index",
        "faiss/colon:name.index",
        "faiss/back\\slash.index",
        "faiss/trailing.",
        "faiss/trailing ",
        "faiss/CON.index",
        "faiss/.",
        "faiss/..",
        "faiss//double.index",
    ),
)
def test_noncanonical_output_names_fail_closed(relative_path: str) -> None:
    module = _load_module()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._validate_relative_path(relative_path)
    assert exc_info.value.code == "unexpected_entry_type"


def test_directory_in_singleton_position_fails_closed(tmp_path: Path) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    (_epoch_root(outer) / "memory.db").mkdir(parents=True)

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(_projection(outer))
    assert exc_info.value.code == "unexpected_entry_type"


@pytest.mark.skipif(os.name != "nt", reason="NTFS alternate streams are Windows-only")
def test_named_ntfs_stream_fails_closed(tmp_path: Path) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    target = _epoch_root(outer) / "memory.db"
    _write(target, b"primary")
    try:
        with open(f"{target}:secret", "wb") as stream:
            stream.write(b"alternate")
    except OSError as exc:
        pytest.skip(f"alternate streams unavailable on this test filesystem: {exc}")

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(_projection(outer))
    assert exc_info.value.code == "unexpected_entry_type"


def test_windows_scope_rejects_case_aliases_and_duplicate_ids() -> None:
    module = _load_module()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._windows_validate_scope_entries(
            (
                module._WindowsEntry("A.index", 0, 1),
                module._WindowsEntry("a.index", 0, 2),
            ),
            relative_directory="faiss",
        )
    assert exc_info.value.code == "duplicate_identity"

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._windows_validate_scope_entries(
            (
                module._WindowsEntry("first.index", 0, 9),
                module._WindowsEntry("second.index", 0, 9),
            ),
            relative_directory="faiss",
        )
    assert exc_info.value.code == "duplicate_identity"


def test_windows_reparse_is_rejected_before_open_or_hash() -> None:
    module = _load_module()

    class ForbiddenApi:
        def __getattr__(self, name: str):
            raise AssertionError(f"{name} reached after reparse detection")

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._windows_observe_file(
            ForbiddenApi(),
            volume_handle=1,
            parent_handle=2,
            parent_initial=(),
            filesystem="NTFS",
            volume_serial=3,
            entry=module._WindowsEntry("redirected.index", 0x400, 4),
            role="faiss_file",
            relative_path="faiss/redirected.index",
        )
    assert exc_info.value.code == "redirected_boundary"


def test_windows_filetime_and_stream_contract_are_exact() -> None:
    module = _load_module()
    epoch = 116444736000000000
    assert module._windows_filetime_to_ns(epoch) == 0
    assert module._windows_filetime_to_ns(epoch + 1) == 100

    for value in (epoch - 1, epoch + ((2**63 - 1) // 100) + 1):
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            module._windows_filetime_to_ns(value)
        assert exc_info.value.code == "observation_failed"

    module._validate_windows_streams(
        (("::$DATA", 7, 8),),
        object_kind="regular_file",
        size_bytes=7,
    )
    module._validate_windows_streams((), object_kind="directory", size_bytes=0)
    for streams, object_kind, size_bytes in (
        (((":secret:$DATA", 7, 8),), "regular_file", 7),
        ((("::$DATA", 8, 8),), "regular_file", 7),
        ((("::$DATA", 0, 0),), "directory", 0),
    ):
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            module._validate_windows_streams(
                streams,
                object_kind=object_kind,
                size_bytes=size_bytes,
            )
        assert exc_info.value.code == "unexpected_entry_type"


@pytest.mark.skipif(os.name != "nt", reason="Win32 ABI is Windows-only")
def test_windows_abi_and_open_flags_are_exact() -> None:
    module = _load_module()
    api = module._WindowsApi()
    assert api.FILE_ID_BOTH_DIR_INFO_STRUCT.FileName.offset == 104
    assert ctypes.sizeof(api.FILE_ID_BOTH_DIR_INFO_STRUCT) == 112
    assert api.FILE_ID_EXTD_DIR_INFO_STRUCT.FileName.offset == 88
    assert ctypes.sizeof(api.FILE_ID_EXTD_DIR_INFO_STRUCT) == 96
    assert api.FILE_STREAM_INFO_STRUCT.StreamName.offset == 24
    assert ctypes.sizeof(api.FILE_STREAM_INFO_STRUCT) == 32
    assert ctypes.sizeof(api.FILE_ID_DESCRIPTOR_STRUCT) == 24
    assert ctypes.sizeof(api.FILE_ID_INFO_STRUCT) == 24
    assert ctypes.sizeof(api.FILE_BASIC_INFO_STRUCT) == 40
    assert ctypes.sizeof(api.FILE_STANDARD_INFO_STRUCT) == 24
    assert ctypes.sizeof(api.FILE_ATTRIBUTE_TAG_INFO_STRUCT) == 8
    assert ctypes.sizeof(api.BY_HANDLE_FILE_INFORMATION_STRUCT) == 52

    class Kernel:
        def __init__(self) -> None:
            self.root_calls: list[tuple[object, ...]] = []
            self.id_calls: list[tuple[object, ...]] = []

        def GetDriveTypeW(self, root: str) -> int:
            assert root == "L:\\"
            return api.DRIVE_FIXED

        def CreateFileW(self, *args):
            self.root_calls.append(args)
            return 101

        def OpenFileById(self, *args):
            self.id_calls.append(args)
            return 202 + len(self.id_calls)

    kernel = Kernel()
    api.kernel32 = kernel
    root_handle = api.open_root("L:\\")
    high_id = (1 << 63) + 7
    file_handle = api.open_by_id(
        root_handle,
        module._WindowsEntry("member.index", 0, high_id),
        directory=False,
    )
    directory_handle = api.open_by_id(
        root_handle,
        module._WindowsEntry("faiss", api.FILE_ATTRIBUTE_DIRECTORY, 8),
        directory=True,
    )
    refs_id = bytes(range(16))
    refs_handle = api.open_by_id(
        root_handle,
        module._WindowsEntry("refs.index", 0, refs_id),
        directory=False,
    )

    assert root_handle == 101
    assert file_handle == 203
    assert directory_handle == 204
    assert refs_handle == 205
    assert kernel.root_calls == [
        (
            "L:\\",
            0x81,
            api.FILE_SHARE_READ,
            None,
            api.OPEN_EXISTING,
            api.FILE_FLAG_OPEN_REPARSE_POINT | api.FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
    ]
    assert len(kernel.id_calls) == 3
    file_call, directory_call, refs_call = kernel.id_calls
    file_descriptor = file_call[1]._obj
    assert file_descriptor.Type == api.FILE_ID_TYPE
    assert file_descriptor.FileId == high_id - (1 << 64)
    assert file_call[2:] == (
        0x81,
        api.FILE_SHARE_READ,
        None,
        api.FILE_FLAG_OPEN_REPARSE_POINT | api.FILE_FLAG_SEQUENTIAL_SCAN,
    )
    assert directory_call[2:] == (
        0x81,
        api.FILE_SHARE_READ,
        None,
        api.FILE_FLAG_OPEN_REPARSE_POINT | api.FILE_FLAG_BACKUP_SEMANTICS,
    )
    refs_descriptor = refs_call[1]._obj
    assert refs_descriptor.Type == api.EXTENDED_FILE_ID_TYPE
    assert bytes(refs_descriptor.ExtendedFileId.Identifier) == refs_id


@pytest.mark.skipif(os.name != "nt", reason="Win32 enumeration is Windows-only")
def test_windows_enumeration_restarts_once_and_consumes_all_buffers() -> None:
    module = _load_module()
    api = module._WindowsApi()
    calls: list[int] = []
    batches = (
        ((".", api.FILE_ATTRIBUTE_DIRECTORY, 10), ("first.index", 0, 11)),
        (("second.index", 0, 12),),
    )

    def fill_ntfs(buffer_argument, records) -> None:
        base = ctypes.addressof(buffer_argument._obj)
        structure = api.FILE_ID_BOTH_DIR_INFO_STRUCT
        offset = 0
        for index, (name, attributes, file_id) in enumerate(records):
            encoded = name.encode("utf-16-le")
            record_size = structure.FileName.offset + len(encoded)
            aligned_size = (record_size + 7) & ~7
            record = structure()
            record.NextEntryOffset = aligned_size if index + 1 < len(records) else 0
            record.FileAttributes = attributes
            record.FileNameLength = len(encoded)
            record.FileId = file_id
            ctypes.memmove(base + offset, ctypes.byref(record), structure.FileName.offset)
            ctypes.memmove(base + offset + structure.FileName.offset, encoded, len(encoded))
            offset += aligned_size

    class Kernel:
        def GetFileInformationByHandleEx(
            self,
            _handle,
            info_class,
            buffer_argument,
            _buffer_size,
        ) -> int:
            calls.append(info_class)
            index = len(calls) - 1
            if index < len(batches):
                fill_ntfs(buffer_argument, batches[index])
                return 1
            ctypes.set_last_error(api.ERROR_NO_MORE_FILES)
            return 0

    api.kernel32 = Kernel()
    entries = api.enumerate_directory(55, "NTFS")

    assert calls == [
        api.FILE_ID_BOTH_DIRECTORY_RESTART_INFO,
        api.FILE_ID_BOTH_DIRECTORY_INFO,
        api.FILE_ID_BOTH_DIRECTORY_INFO,
    ]
    assert tuple((entry.name, entry.file_id) for entry in entries) == (
        ("first.index", 11),
        ("second.index", 12),
    )


@pytest.mark.skipif(os.name != "nt", reason="ReFS ABI parsing is Windows-only")
def test_refs_extended_directory_record_preserves_all_128_id_bits() -> None:
    module = _load_module()
    api = module._WindowsApi()
    calls: list[int] = []
    expected_id = bytes(range(16))

    class Kernel:
        def GetFileInformationByHandleEx(
            self,
            _handle,
            info_class,
            buffer_argument,
            _buffer_size,
        ) -> int:
            calls.append(info_class)
            if len(calls) == 1:
                structure = api.FILE_ID_EXTD_DIR_INFO_STRUCT
                record = structure()
                encoded = "member.index".encode("utf-16-le")
                record.FileNameLength = len(encoded)
                for index, byte in enumerate(expected_id):
                    record.FileId.Identifier[index] = byte
                base = ctypes.addressof(buffer_argument._obj)
                ctypes.memmove(base, ctypes.byref(record), structure.FileName.offset)
                ctypes.memmove(base + structure.FileName.offset, encoded, len(encoded))
                return 1
            ctypes.set_last_error(api.ERROR_NO_MORE_FILES)
            return 0

    api.kernel32 = Kernel()
    entries = api.enumerate_directory(55, "ReFS")

    assert calls == [
        api.FILE_ID_EXTD_DIRECTORY_RESTART_INFO,
        api.FILE_ID_EXTD_DIRECTORY_INFO,
    ]
    assert tuple((entry.name, entry.file_id) for entry in entries) == (
        ("member.index", expected_id),
    )


@pytest.mark.skipif(os.name != "nt", reason="Win32 buffer parsing is Windows-only")
def test_truncated_native_buffers_map_to_finite_observation_failure() -> None:
    module = _load_module()
    api = module._WindowsApi()

    class DirectoryKernel:
        def GetFileInformationByHandleEx(
            self,
            _handle,
            _info_class,
            buffer_argument,
            buffer_size,
        ) -> int:
            structure = api.FILE_ID_BOTH_DIR_INFO_STRUCT
            record = structure()
            encoded = "x".encode("utf-16-le")
            record.NextEntryOffset = buffer_size - structure.FileName.offset
            record.FileNameLength = len(encoded)
            record.FileId = 9
            base = ctypes.addressof(buffer_argument._obj)
            ctypes.memmove(base, ctypes.byref(record), structure.FileName.offset)
            ctypes.memmove(base + structure.FileName.offset, encoded, len(encoded))
            return 1

    api.kernel32 = DirectoryKernel()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        api.enumerate_directory(55, "NTFS")
    assert exc_info.value.code == "observation_failed"

    class StreamKernel:
        def GetFileInformationByHandleEx(
            self,
            _handle,
            _info_class,
            buffer_argument,
            buffer_size,
        ) -> int:
            structure = api.FILE_STREAM_INFO_STRUCT
            record = structure()
            encoded = "::$DATA".encode("utf-16-le")
            record.NextEntryOffset = buffer_size - structure.StreamName.offset
            record.StreamNameLength = len(encoded)
            base = ctypes.addressof(buffer_argument._obj)
            ctypes.memmove(base, ctypes.byref(record), structure.StreamName.offset)
            ctypes.memmove(base + structure.StreamName.offset, encoded, len(encoded))
            return 1

    api.kernel32 = StreamKernel()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        api.stream_inventory(55)
    assert exc_info.value.code == "observation_failed"


@pytest.mark.skipif(os.name != "nt", reason="Win32 errors are Windows-only")
def test_windows_error_mapping_preserves_internal_cause_and_close_fails_visible() -> None:
    module = _load_module()
    api = module._WindowsApi()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        api._raise_call_error(api.ERROR_ACCESS_DENIED, disappeared=True)
    assert exc_info.value.code == "observation_failed"
    assert isinstance(exc_info.value.__cause__, OSError)

    class UnsupportedOpenByIdKernel:
        def OpenFileById(self, *_args) -> int:
            ctypes.set_last_error(api.ERROR_NOT_SUPPORTED)
            return api.invalid_handle

    api.kernel32 = UnsupportedOpenByIdKernel()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        api.open_by_id(
            10,
            module._WindowsEntry("member", 0, 123),
            directory=False,
        )
    assert exc_info.value.code == "unsupported_filesystem"
    assert isinstance(exc_info.value.__cause__, OSError)
    assert "Clean-memory" not in str(exc_info.value.__cause__)

    for error in (
        api.ERROR_INVALID_FUNCTION,
        api.ERROR_NOT_SUPPORTED,
        api.ERROR_INVALID_PARAMETER,
    ):
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            api._raise_call_error(error)
        assert exc_info.value.code == "observation_failed"
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            api._raise_call_error(error, unsupported_capability=True)
        assert exc_info.value.code == "unsupported_filesystem"

    class Kernel:
        def CloseHandle(self, _handle) -> int:
            ctypes.set_last_error(api.ERROR_ACCESS_DENIED)
            return 0

    api.kernel32 = Kernel()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        api.close(99)
    assert exc_info.value.code == "observation_failed"
    assert isinstance(exc_info.value.__cause__, OSError)


def test_windows_close_all_preserves_primary_error_and_attempts_every_handle() -> None:
    module = _load_module()

    class CloseApi:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def close(self, handle: int) -> None:
            self.calls.append(handle)
            if handle in {2, 1}:
                raise module.FilesystemObservationError("observation_failed")

    successful_path = CloseApi()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._close_windows_handles(successful_path, (1, 2, 3))
    assert exc_info.value.code == "observation_failed"
    assert successful_path.calls == [3, 2, 1]

    failing_path = CloseApi()

    def fail_then_close() -> None:
        try:
            raise module.FilesystemObservationError("redirected_boundary")
        finally:
            module._close_windows_handles(failing_path, (1, 2, 3))

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        fail_then_close()
    assert exc_info.value.code == "redirected_boundary"
    assert failing_path.calls == [3, 2, 1]
    assert isinstance(exc_info.value.__cause__, module.FilesystemObservationError)
    assert exc_info.value.__cause__.code == "observation_failed"

    primary_cause = OSError(5, "primary read failed")
    primary = module.FilesystemObservationError("observation_raced")

    def fail_with_cause_then_close() -> None:
        try:
            raise primary from primary_cause
        finally:
            module._close_windows_handles(failing_path, (1, 2, 3))

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        fail_with_cause_then_close()
    assert exc_info.value is primary
    assert exc_info.value.__cause__ is primary_cause


def test_windows_device_entries_fail_before_open_and_from_handle_state() -> None:
    module = _load_module()
    device_entry = module._WindowsEntry("device.bin", 0x40, 123)

    class ForbiddenApi:
        def __init__(self) -> None:
            self.open_calls = 0

        def open_by_id(self, *_args, **_kwargs):
            self.open_calls += 1
            raise AssertionError("device entry reached OpenFileById")

    forbidden = ForbiddenApi()
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._windows_observe_file(
            forbidden,
            volume_handle=10,
            parent_handle=11,
            parent_initial=(),
            filesystem="NTFS",
            volume_serial=1,
            entry=device_entry,
            role="faiss_file",
            relative_path="faiss/device.bin",
        )
    assert exc_info.value.code == "unexpected_entry_type"
    assert forbidden.open_calls == 0

    if os.name != "nt":
        return
    api = module._WindowsApi()
    volume_serial = 1

    def query(_handle, info_class, _structure):
        if info_class == api.FILE_ATTRIBUTE_TAG_INFO:
            return SimpleNamespace(FileAttributes=api.FILE_ATTRIBUTE_DEVICE, ReparseTag=0)
        if info_class == api.FILE_ID_INFO:
            return SimpleNamespace(
                VolumeSerialNumber=volume_serial,
                FileId=SimpleNamespace(Identifier=bytes(range(16))),
            )
        if info_class == api.FILE_BASIC_INFO:
            return SimpleNamespace(
                LastWriteTime=api.FILETIME_UNIX_EPOCH,
                ChangeTime=api.FILETIME_UNIX_EPOCH,
            )
        if info_class == api.FILE_STANDARD_INFO:
            return SimpleNamespace(
                Directory=False,
                DeletePending=False,
                EndOfFile=0,
                AllocationSize=0,
                NumberOfLinks=1,
            )
        raise AssertionError(info_class)

    api._query = query
    api._by_handle = lambda _handle: SimpleNamespace(
        nFileIndexHigh=0,
        nFileIndexLow=123,
        nFileSizeHigh=0,
        nFileSizeLow=0,
        nNumberOfLinks=1,
    )
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        api.state(
            12,
            filesystem="NTFS",
            expected=device_entry,
            object_kind="regular_file",
            require_stream_contract=False,
        )
    assert exc_info.value.code == "unexpected_entry_type"


def _windows_state(module, *, file_id: int, kind: str = "directory", size: int = 0):
    return module._WindowsHandleState(
        identity_json=_canonical_json(
            {
                "file_id": f"{file_id:016x}",
                "file_id_kind": "ntfs_file_index_64",
                "object_kind": kind,
                "schema": "goodq.windows-file-identity.v1",
                "volume_serial": "0000000000000001",
            }
        ),
        volume_serial=1,
        file_id=file_id,
        object_kind=kind,
        size_bytes=size,
        mtime_ns=0 if kind == "regular_file" else None,
        fingerprint=(file_id, kind, size),
    )


def test_windows_missing_epoch_component_requires_two_equal_enumerations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()

    class MissingApi:
        def __init__(self, snapshots) -> None:
            self.snapshots = iter(snapshots)
            self.enumeration_count = 0

        def open_root(self, root: str) -> int:
            assert root == "L:\\"
            return 1

        def volume_filesystem(self, _handle: int) -> str:
            return "NTFS"

        def state(self, *_args, **kwargs):
            assert kwargs["require_stream_contract"] is True
            return _windows_state(module, file_id=1)

        def enumerate_directory(self, _handle: int, _filesystem: str):
            self.enumeration_count += 1
            return next(self.snapshots)

        def close(self, _handle: int) -> None:
            return None

    stable = MissingApi(((), ()))
    monkeypatch.setattr(module, "_load_windows_api", lambda: stable)
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))
    assert exc_info.value.code == "required_root_missing"
    assert stable.enumeration_count == 2

    changed = MissingApi(
        (
            (),
            (module._WindowsEntry("appeared", 0, 2),),
        )
    )
    monkeypatch.setattr(module, "_load_windows_api", lambda: changed)
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))
    assert exc_info.value.code == "observation_raced"
    assert changed.enumeration_count == 2


def test_windows_all_held_directories_require_stream_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()

    class DirectoryApi:
        def __init__(self) -> None:
            self.require_stream_values: list[bool] = []
            self.enumeration_count = 0

        def open_root(self, _root: str) -> int:
            return 1

        def volume_filesystem(self, _handle: int) -> str:
            return "NTFS"

        def state(self, handle: int, *_args, **kwargs):
            self.require_stream_values.append(kwargs["require_stream_contract"])
            return _windows_state(module, file_id=handle)

        def enumerate_directory(self, handle: int, _filesystem: str):
            self.enumeration_count += 1
            if handle == 1:
                return (module._WindowsEntry("epoch", 0x10, 2),)
            return ()

        def open_by_id(self, _volume: int, entry, *, directory: bool) -> int:
            assert directory is True
            assert entry.name == "epoch"
            return 2

        def close(self, _handle: int) -> None:
            return None

    api = DirectoryApi()
    monkeypatch.setattr(module, "_load_windows_api", lambda: api)
    epoch_identity, targets = module._observe_windows(
        _private_windows_projection(module)
    )

    assert epoch_identity == _windows_state(module, file_id=2).identity_json
    assert len(targets) == 6
    assert api.require_stream_values and all(api.require_stream_values)


def test_windows_file_and_parent_drift_return_no_evidence() -> None:
    module = _load_module()
    entry = module._WindowsEntry("memory.db", 0, 7)
    initial_membership = (entry.membership,)

    class DriftApi:
        def __init__(self, *, state_drift: bool, membership_drift: bool) -> None:
            self.states = iter(
                (
                    _windows_state(module, file_id=7, kind="regular_file", size=4),
                    _windows_state(
                        module,
                        file_id=7,
                        kind="regular_file",
                        size=5 if state_drift else 4,
                    ),
                )
            )
            self.membership_drift = membership_drift

        def open_by_id(self, *_args, **_kwargs) -> int:
            return 8

        def state(self, *_args, **_kwargs):
            return next(self.states)

        def hash_file(self, _handle: int):
            return hashlib.sha256(b"data").hexdigest(), 4

        def enumerate_directory(self, *_args):
            if self.membership_drift:
                return (module._WindowsEntry("renamed.db", 0, 7),)
            return (entry,)

        def close(self, _handle: int) -> None:
            return None

    for state_drift, membership_drift in ((True, False), (False, True)):
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            module._windows_observe_file(
                DriftApi(
                    state_drift=state_drift,
                    membership_drift=membership_drift,
                ),
                volume_handle=1,
                parent_handle=2,
                parent_initial=initial_membership,
                filesystem="NTFS",
                volume_serial=1,
                entry=entry,
                role="memory_database",
                relative_path="memory.db",
            )
        assert exc_info.value.code == "observation_raced"


def test_deep_windows_faiss_tree_is_iterative_not_recursion_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    deepest_directory = 1050
    leaf_id = 5000

    class DeepApi:
        def open_root(self, _root: str) -> int:
            return 1

        def volume_filesystem(self, _handle: int) -> str:
            return "NTFS"

        def state(self, handle: int, *_args, **kwargs):
            kind = kwargs["object_kind"]
            return _windows_state(
                module,
                file_id=handle,
                kind=kind,
                size=0,
            )

        def enumerate_directory(self, handle: int, _filesystem: str):
            if handle == 1:
                return (module._WindowsEntry("epoch", 0x10, 2),)
            if handle == 2:
                return (module._WindowsEntry("faiss", 0x10, 3),)
            if 3 <= handle < deepest_directory:
                return (module._WindowsEntry(f"d{handle}", 0x10, handle + 1),)
            if handle == deepest_directory:
                return (module._WindowsEntry("leaf.index", 0, leaf_id),)
            raise AssertionError(f"unexpected directory handle {handle}")

        def open_by_id(self, _volume: int, entry, *, directory: bool) -> int:
            assert directory is entry.is_directory
            return int(entry.file_id)

        def hash_file(self, _handle: int):
            return hashlib.sha256(b"").hexdigest(), 0

        def close(self, _handle: int) -> None:
            return None

    monkeypatch.setattr(module, "_load_windows_api", DeepApi)
    _identity_json_value, targets = module._observe_windows(
        _private_windows_projection(module)
    )
    assert len(targets) == 7
    assert targets[-1].relative_path.endswith("/leaf.index")
    assert targets[-1].exists is True


@pytest.mark.skipif(os.name != "nt", reason="native Windows trace is Windows-only")
def test_windows_native_trace_opens_only_drive_root_by_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    _write(_epoch_root(outer) / "memory.db", b"trace")
    native = module._WindowsApi()

    class TraceApi:
        def __init__(self) -> None:
            self.root_paths: list[str] = []
            self.opened_ids: list[int | bytes] = []

        def open_root(self, root: str) -> int:
            self.root_paths.append(root)
            return native.open_root(root)

        def open_by_id(self, volume_handle, entry, *, directory: bool):
            self.opened_ids.append(entry.file_id)
            return native.open_by_id(volume_handle, entry, directory=directory)

        def __getattr__(self, name: str):
            return getattr(native, name)

    trace = TraceApi()
    monkeypatch.setattr(module, "_load_windows_api", lambda: trace)
    result = module.observe_filesystem(_projection(outer))

    assert result.filesystem_targets[0].exists is True
    assert trace.root_paths == [f"{Path(outer).drive}\\"]
    assert trace.opened_ids
    assert all(
        isinstance(file_id, int) or isinstance(file_id, bytes)
        for file_id in trace.opened_ids
    )


@pytest.mark.skipif(os.name != "nt", reason="native share modes are Windows-only")
def test_windows_incompatible_writer_is_sharing_conflict(tmp_path: Path) -> None:
    module = _load_module()
    outer = tmp_path / "outer"
    target = _epoch_root(outer) / "memory.db"
    _write(target, b"leased")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int32
    handle = kernel32.CreateFileW(str(target), 0x80000000, 0, None, 3, 0, None)
    invalid = ctypes.c_void_p(-1).value
    if handle is None or handle == invalid:
        pytest.skip(f"exclusive fixture unavailable: {ctypes.get_last_error()}")
    try:
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            module.observe_filesystem(_projection(outer))
        assert exc_info.value.code == "sharing_conflict"
    finally:
        assert kernel32.CloseHandle(handle)


def test_exact_windows_identity_json_for_ntfs_and_refs() -> None:
    module = _load_module()
    if os.name != "nt":
        pytest.skip("Win32 state structures are Windows-only")
    api = module._WindowsApi()
    volume_serial = 0x123456789ABCDEF0
    refs_id = bytes(range(16))

    def query(_handle, info_class, _structure):
        if info_class == api.FILE_ATTRIBUTE_TAG_INFO:
            return SimpleNamespace(FileAttributes=0, ReparseTag=0)
        if info_class == api.FILE_ID_INFO:
            return SimpleNamespace(
                VolumeSerialNumber=volume_serial,
                FileId=SimpleNamespace(Identifier=refs_id),
            )
        if info_class == api.FILE_BASIC_INFO:
            return SimpleNamespace(
                LastWriteTime=api.FILETIME_UNIX_EPOCH + 5,
                ChangeTime=api.FILETIME_UNIX_EPOCH + 6,
            )
        if info_class == api.FILE_STANDARD_INFO:
            return SimpleNamespace(
                Directory=False,
                DeletePending=False,
                EndOfFile=4,
                AllocationSize=4096,
                NumberOfLinks=1,
            )
        raise AssertionError(info_class)

    api._query = query
    api._by_handle = lambda _handle: SimpleNamespace(
        nFileIndexHigh=0xFEDCBA98,
        nFileIndexLow=0x76543210,
        nFileSizeHigh=0,
        nFileSizeLow=4,
        nNumberOfLinks=1,
    )
    api.stream_inventory = lambda _handle: (("::$DATA", 4, 4096),)
    ntfs_id = 0xFEDCBA9876543210
    ntfs = api.state(
        1,
        filesystem="NTFS",
        expected=module._WindowsEntry("member", 0, ntfs_id),
        object_kind="regular_file",
        require_stream_contract=True,
    )
    refs = api.state(
        1,
        filesystem="ReFS",
        expected=module._WindowsEntry("member", 0, refs_id),
        object_kind="regular_file",
        require_stream_contract=True,
    )
    assert ntfs.identity_json == (
        '{"file_id":"fedcba9876543210","file_id_kind":"ntfs_file_index_64",'
        '"object_kind":"regular_file","schema":"goodq.windows-file-identity.v1",'
        '"volume_serial":"123456789abcdef0"}'
    )
    assert refs.identity_json == (
        '{"file_id":"000102030405060708090a0b0c0d0e0f",'
        '"file_id_kind":"refs_file_id_128","object_kind":"regular_file",'
        '"schema":"goodq.windows-file-identity.v1",'
        '"volume_serial":"123456789abcdef0"}'
    )
    assert ntfs.mtime_ns == refs.mtime_ns == 500


def test_posix_backend_uses_only_root_path_then_descriptor_relative_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    directory_mode = stat.S_IFDIR | 0o700
    file_mode = stat.S_IFREG | 0o600
    nodes = {
        10: SimpleNamespace(mode=directory_mode, inode=1, children={"GoodQ_Data": 11}),
        11: SimpleNamespace(mode=directory_mode, inode=2, children={"epochs": 12}),
        12: SimpleNamespace(mode=directory_mode, inode=3, children={EPOCH_ID: 13}),
        13: SimpleNamespace(
            mode=directory_mode,
            inode=4,
            children={"memory.db": 14, "faiss": 15},
        ),
        14: SimpleNamespace(mode=file_mode, inode=5, children={}, data=b"memory"),
        15: SimpleNamespace(mode=directory_mode, inode=6, children={"future.bin": 16}),
        16: SimpleNamespace(mode=file_mode, inode=7, children={}, data=b"future"),
    }
    open_calls: list[tuple[str, int, int | None]] = []
    read_offsets: dict[int, int] = {}

    def info(fd: int):
        node = nodes[fd]
        data = getattr(node, "data", b"")
        return SimpleNamespace(
            st_mode=node.mode,
            st_dev=99,
            st_ino=node.inode,
            st_size=len(data),
            st_mtime_ns=123,
            st_ctime_ns=456,
            st_nlink=1,
        )

    class Entry:
        def __init__(self, name: str, fd: int) -> None:
            self.name = name
            self.fd = fd

        def stat(self, *, follow_symlinks: bool):
            assert follow_symlinks is False
            return info(self.fd)

    class Scan:
        def __init__(self, fd: int) -> None:
            self.entries = [Entry(name, child) for name, child in nodes[fd].children.items()]

        def __enter__(self):
            return iter(self.entries)

        def __exit__(self, *_args):
            return False

    def open_fn(path: str, flags: int, *, dir_fd: int | None = None) -> int:
        open_calls.append((path, flags, dir_fd))
        if path == "/":
            assert dir_fd is None
            return 10
        assert dir_fd is not None
        return nodes[dir_fd].children[path]

    def scandir_fn(fd: int):
        return Scan(fd)

    def fstat_fn(fd: int):
        return info(fd)

    def read_fn(fd: int, _size: int) -> bytes:
        offset = read_offsets.get(fd, 0)
        data = getattr(nodes[fd], "data", b"")
        read_offsets[fd] = len(data)
        return data[offset:]

    fake_os = SimpleNamespace(
        O_RDONLY=0x01,
        O_DIRECTORY=0x02,
        O_NOFOLLOW=0x04,
        O_CLOEXEC=0x08,
        O_NONBLOCK=0x10,
        open=open_fn,
        scandir=scandir_fn,
        fstat=fstat_fn,
        read=read_fn,
        close=lambda _fd: None,
        supports_dir_fd={open_fn},
        supports_fd={scandir_fn},
    )
    monkeypatch.setattr(module, "os", fake_os)
    projection = module._Projection(
        canonical_json="{}",
        configuration_scope_sha256="0" * 64,
        path_flavor="posix",
        epoch_id=EPOCH_ID,
        epoch_root=f"/GoodQ_Data/epochs/{EPOCH_ID}",
        logical_paths={},
    )
    epoch_identity, targets = module._observe_posix(projection)

    assert open_calls[0] == ("/", 0x1F, None)
    assert all(not path.startswith("/") and dir_fd is not None for path, _flags, dir_fd in open_calls[1:])
    assert all(flags & 0x1C == 0x1C for _path, flags, _dir_fd in open_calls)
    assert epoch_identity == (
        '{"device":"99","inode":"4","object_kind":"directory",'
        '"schema":"goodq.posix-file-identity.v1"}'
    )
    assert tuple((target.relative_path, target.exists) for target in targets) == (
        ("memory.db", True),
        ("memory.db-wal", False),
        ("memory.db-shm", False),
        ("knowledge_graph.db", False),
        ("knowledge_graph.db-wal", False),
        ("knowledge_graph.db-shm", False),
        ("faiss/future.bin", True),
    )


def test_posix_missing_capability_and_irregular_swap_fail_before_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    projection = module._Projection(
        canonical_json="{}",
        configuration_scope_sha256="0" * 64,
        path_flavor="posix",
        epoch_id=EPOCH_ID,
        epoch_root=f"/GoodQ_Data/epochs/{EPOCH_ID}",
        logical_paths={},
    )
    monkeypatch.setattr(module, "os", SimpleNamespace())
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_posix(projection)
    assert exc_info.value.code == "unsupported_platform"

    reads: list[int] = []
    fake_os = SimpleNamespace(
        O_RDONLY=1,
        O_NOFOLLOW=2,
        O_CLOEXEC=4,
        O_NONBLOCK=8,
        O_DIRECTORY=16,
        open=lambda *_args, **_kwargs: 22,
        fstat=lambda _fd: SimpleNamespace(
            st_mode=stat.S_IFIFO | 0o600,
            st_dev=1,
            st_ino=2,
        ),
        read=lambda fd, _size: reads.append(fd),
        close=lambda _fd: None,
    )
    monkeypatch.setattr(module, "os", fake_os)
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._posix_observe_file(
            10,
            module._PosixEntry("member", stat.S_IFREG | 0o600, 1, 2),
            role="faiss_file",
            relative_path="faiss/member",
        )
    assert exc_info.value.code == "observation_raced"
    assert reads == []


def test_posix_missing_epoch_component_requires_two_equal_enumerations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    projection = module._Projection(
        canonical_json="{}",
        configuration_scope_sha256="0" * 64,
        path_flavor="posix",
        epoch_id=EPOCH_ID,
        epoch_root="/missing",
        logical_paths={},
    )

    def open_fn(path: str, _flags: int, *, dir_fd=None) -> int:
        assert path == "/" and dir_fd is None
        return 10

    def scandir_fn(_fd: int):
        raise AssertionError("scripted snapshot should replace scandir")

    fake_os = SimpleNamespace(
        O_RDONLY=1,
        O_DIRECTORY=2,
        O_NOFOLLOW=4,
        O_CLOEXEC=8,
        O_NONBLOCK=16,
        open=open_fn,
        scandir=scandir_fn,
        close=lambda _fd: None,
        supports_dir_fd={open_fn},
        supports_fd={scandir_fn},
    )
    monkeypatch.setattr(module, "os", fake_os)

    def run(snapshots):
        scripted = iter(snapshots)
        calls: list[int] = []

        def snapshot(fd: int):
            calls.append(fd)
            return next(scripted)

        monkeypatch.setattr(module, "_posix_snapshot", snapshot)
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            module._observe_posix(projection)
        return exc_info.value.code, calls

    code, calls = run((((), ()), ((), ())))
    assert code == "required_root_missing"
    assert calls == [10, 10]

    appeared = module._PosixEntry("appeared", stat.S_IFREG | 0o600, 1, 2)
    code, calls = run(
        (
            ((), ()),
            ((appeared,), (appeared.membership,)),
        )
    )
    assert code == "observation_raced"
    assert calls == [10, 10]


def test_posix_close_all_is_fail_visible_and_preserves_primary_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    calls: list[int] = []

    def close(fd: int) -> None:
        calls.append(fd)
        if fd in {1, 2}:
            raise OSError(5, "close failed")

    monkeypatch.setattr(module, "os", SimpleNamespace(close=close))
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._close_posix_fds((1, 2, 3))
    assert exc_info.value.code == "observation_failed"
    assert calls == [3, 2, 1]

    calls.clear()

    def fail_then_close() -> None:
        try:
            raise module.FilesystemObservationError("redirected_boundary")
        finally:
            module._close_posix_fds((1, 2, 3))

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        fail_then_close()
    assert exc_info.value.code == "redirected_boundary"
    assert calls == [3, 2, 1]
    assert isinstance(exc_info.value.__cause__, module.FilesystemObservationError)
    assert exc_info.value.__cause__.code == "observation_failed"

    primary_cause = OSError(5, "primary read failed")
    primary = module.FilesystemObservationError("observation_raced")

    def fail_with_cause_then_close() -> None:
        try:
            raise primary from primary_cause
        finally:
            module._close_posix_fds((1, 2, 3))

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        fail_with_cause_then_close()
    assert exc_info.value is primary
    assert exc_info.value.__cause__ is primary_cause


def test_invocation_has_no_unrelated_capabilities_and_redacts_backend_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    projection = _projection(tmp_path / "outer")
    before_modules = set(sys.modules)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unrelated capability reached")

    identity = _identity("epoch")
    backend = lambda _projection_value: (identity, ())
    guarded_os = SimpleNamespace(name=os.name)
    for name in (
        "getcwd",
        "getenv",
        "mkdir",
        "remove",
        "unlink",
        "rename",
        "replace",
        "chmod",
    ):
        setattr(guarded_os, name, forbidden)
    with monkeypatch.context() as guard:
        guard.setattr(module, "os", guarded_os)
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(subprocess, "run", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        for name in (
            "resolve",
            "open",
            "write_text",
            "write_bytes",
            "unlink",
            "rename",
            "replace",
        ):
            guard.setattr(Path, name, forbidden)
        guard.setattr(module, "_observe_windows", backend)
        guard.setattr(module, "_observe_posix", backend)
        result = module.observe_filesystem(projection)
    assert result.epoch_root_identity_json == identity
    forbidden_roots = {
        "qdrant_client",
        "requests",
        "httpx",
        "steps.common.config_loader",
        "miniagent",
    }
    assert not {
        name
        for name in set(sys.modules) - before_modules
        if name in forbidden_roots or name.split(".", 1)[0] in forbidden_roots
    }

    def leaking_backend(_projection_value):
        raise OSError(5, r"SECRET L:\private\outside")

    monkeypatch.setattr(module, "_observe_windows", leaking_backend)
    monkeypatch.setattr(module, "_observe_posix", leaking_backend)
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module.observe_filesystem(projection)
    assert exc_info.value.code == "observation_failed"
    assert str(exc_info.value) == "Clean-memory filesystem observation failed"
    assert "SECRET" not in str(exc_info.value)
    assert "SECRET" in str(exc_info.value.__cause__)


def test_import_is_capability_free(tmp_path: Path) -> None:
    script = r'''
import builtins
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

root = Path(sys.argv[1])
before_env = dict(os.environ)
before_modules = set(sys.modules)

def forbidden(*_args, **_kwargs):
    raise AssertionError("forbidden capability used during import")

class GuardedEnvironment(dict):
    __getitem__ = forbidden
    __setitem__ = forbidden
    __delitem__ = forbidden
    __iter__ = forbidden
    __len__ = forbidden
    __contains__ = forbidden
    get = forbidden
    items = forbidden
    keys = forbidden
    values = forbidden

os.environ = GuardedEnvironment(before_env)
os.getenv = forbidden
builtins.open = forbidden
for name in ("mkdir", "makedirs", "remove", "unlink", "rename", "replace", "chmod", "stat", "lstat", "scandir"):
    if hasattr(os, name):
        setattr(os, name, forbidden)
for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes", "mkdir", "unlink", "rename", "replace", "resolve", "stat", "lstat", "exists", "is_file", "is_dir"):
    if hasattr(Path, name):
        setattr(Path, name, forbidden)
socket.socket = forbidden
subprocess.run = forbidden
subprocess.Popen = forbidden
sys.path.insert(0, str(root))
module = importlib.import_module("cli.clean_memory_filesystem")
new_modules = set(sys.modules) - before_modules
forbidden_roots = {"requests", "httpx", "qdrant_client", "yaml", "steps.common.config_loader"}
print(json.dumps({
    "all": list(module.__all__),
    "forbidden": sorted(name for name in new_modules if name in forbidden_roots or name.split(".", 1)[0] in forbidden_roots),
}))
'''
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script, str(REPO_ROOT)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "all": [
            "FILESYSTEM_OBSERVATION_SCHEMA",
            "FilesystemObservationError",
            "FilesystemObservation",
            "observe_filesystem",
        ],
        "forbidden": [],
    }
