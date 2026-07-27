from __future__ import annotations

import ast
import builtins
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
    project_imports = tuple(
        (
            node.level,
            node.module,
            tuple((alias.name, alias.asname) for alias in node.names),
        )
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ImportFrom)
            and (
                node.level != 0
                or (
                    node.module
                    and node.module.split(".", 1)[0] in {"api", "cli", "steps"}
                )
            )
        )
    )
    assert sorted(project_imports) == sorted(
        (
            (0, "cli.clean_memory", (("ResolvedPlanConfiguration", None),)),
            (
                0,
                "steps.common.clean_memory",
                (("FilesystemTargetEvidence", None),),
            ),
            (
                0,
                "steps.common.windows_held_handle",
                (
                    ("WindowsDirectoryEntry", None),
                    ("WindowsHeldHandleBackend", None),
                    ("WindowsHeldHandleError", None),
                    ("WindowsObjectSnapshot", None),
                ),
            ),
        ),
    )
    assert not any(
        isinstance(node, ast.Import)
        and any(
            alias.name.split(".", 1)[0] in {"api", "cli", "steps"}
            for alias in node.names
        )
        for node in ast.walk(tree)
    )
    assert not any(
        (isinstance(node, ast.Name) and node.id == "__import__")
        or (
            isinstance(node, ast.Attribute)
            and node.attr in {"__import__", "import_module"}
        )
        or (
            isinstance(node, ast.ImportFrom)
            and node.module in {"builtins", "importlib"}
            and any(
                alias.name in {"__import__", "import_module"}
                for alias in node.names
            )
        )
        for node in ast.walk(tree)
    )


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
                module.WindowsDirectoryEntry(
                    "A.index", 0, "ntfs_file_index_64", 1
                ),
                module.WindowsDirectoryEntry(
                    "a.index", 0, "ntfs_file_index_64", 2
                ),
            ),
            relative_directory="faiss",
        )
    assert exc_info.value.code == "duplicate_identity"

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._windows_validate_scope_entries(
            (
                module.WindowsDirectoryEntry(
                    "first.index", 0, "ntfs_file_index_64", 9
                ),
                module.WindowsDirectoryEntry(
                    "second.index", 0, "ntfs_file_index_64", 9
                ),
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
            entry=module.WindowsDirectoryEntry(
                "redirected.index",
                0x400,
                "ntfs_file_index_64",
                4,
            ),
            role="faiss_file",
            relative_path="faiss/redirected.index",
        )
    assert exc_info.value.code == "redirected_boundary"




def test_windows_device_entry_fails_before_open_or_hash() -> None:
    module = _load_module()
    device_entry = module.WindowsDirectoryEntry(
        "device.bin",
        0x40,
        "ntfs_file_index_64",
        123,
    )

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


def _shared_windows_snapshot(
    module,
    *,
    file_id: int,
    kind: str = "directory",
    size: int = 0,
):
    return module.WindowsObjectSnapshot(
        volume_serial=1,
        file_id_kind="ntfs_file_index_64",
        file_id=file_id,
        object_kind=kind,
        size_bytes=size,
        mtime_ns=0 if kind == "regular_file" else None,
        allocation_size=size,
        link_count=1,
        attributes=0x10 if kind == "directory" else 0,
        reparse_tag=0,
        last_write_ticks=116444736000000000,
        change_ticks=116444736000000000,
        streams=() if kind == "directory" else (("::$DATA", size, size),),
    )


class _ContextManagedBackendDouble:
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False


def test_windows_observer_uses_context_managed_shared_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()

    class MissingBackend:
        def __init__(self) -> None:
            self.entered = False
            self.exited = False
            self.enumeration_count = 0

        def __enter__(self):
            self.entered = True
            return self

        def __exit__(self, *_args) -> bool:
            self.exited = True
            return False

        def open_root(self, root: str) -> object:
            assert self.entered is True
            assert root == "L:\\"
            return object()

        def volume_filesystem(self, _handle: object) -> str:
            return "NTFS"

        def snapshot(self, *_args, **kwargs):
            assert kwargs["require_stream_contract"] is True
            return _shared_windows_snapshot(module, file_id=1)

        def enumerate_directory(self, _handle: object, _filesystem: str):
            self.enumeration_count += 1
            return ()

    backend = MissingBackend()
    monkeypatch.setattr(module, "_load_windows_backend", lambda: backend)

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))

    assert exc_info.value.code == "required_root_missing"
    assert backend.enumeration_count == 2
    assert backend.entered is True
    assert backend.exited is True


def test_windows_observer_translates_shared_error_and_preserves_os_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    cause = OSError(32, "native sharing conflict")

    class FailingBackend(_ContextManagedBackendDouble):
        def open_root(self, _root: str) -> object:
            raise module.WindowsHeldHandleError("sharing_conflict") from cause

    monkeypatch.setattr(module, "_load_windows_backend", FailingBackend)

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))

    assert exc_info.value.code == "sharing_conflict"
    assert exc_info.value.__cause__ is cause


def test_windows_missing_epoch_component_requires_two_equal_enumerations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()

    class MissingApi(_ContextManagedBackendDouble):
        def __init__(self, snapshots) -> None:
            self.snapshots = iter(snapshots)
            self.enumeration_count = 0
            self.root_handle = object()

        def open_root(self, root: str) -> object:
            assert root == "L:\\"
            return self.root_handle

        def volume_filesystem(self, handle: object) -> str:
            assert handle is self.root_handle
            return "NTFS"

        def snapshot(self, *_args, **kwargs):
            assert kwargs["require_stream_contract"] is True
            return _shared_windows_snapshot(module, file_id=1)

        def enumerate_directory(self, handle: object, _filesystem: str):
            assert handle is self.root_handle
            self.enumeration_count += 1
            return next(self.snapshots)

        def close(self, _handle: object) -> None:
            return None

    stable = MissingApi(((), ()))
    monkeypatch.setattr(module, "_load_windows_backend", lambda: stable)
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))
    assert exc_info.value.code == "required_root_missing"
    assert stable.enumeration_count == 2

    changed = MissingApi(
        (
            (),
            (
                module.WindowsDirectoryEntry(
                    "appeared",
                    0,
                    "ntfs_file_index_64",
                    2,
                ),
            ),
        )
    )
    monkeypatch.setattr(module, "_load_windows_backend", lambda: changed)
    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))
    assert exc_info.value.code == "observation_raced"
    assert changed.enumeration_count == 2


def test_windows_all_held_directories_require_stream_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()

    class DirectoryApi(_ContextManagedBackendDouble):
        def __init__(self) -> None:
            self.require_stream_values: list[bool] = []
            self.enumeration_count = 0
            self.root_handle = object()
            self.epoch_handle = object()

        def open_root(self, _root: str) -> object:
            return self.root_handle

        def volume_filesystem(self, handle: object) -> str:
            assert handle is self.root_handle
            return "NTFS"

        def snapshot(self, handle: object, *_args, **kwargs):
            self.require_stream_values.append(kwargs["require_stream_contract"])
            file_id = 1 if handle is self.root_handle else 2
            assert handle in {self.root_handle, self.epoch_handle}
            return _shared_windows_snapshot(module, file_id=file_id)

        def enumerate_directory(self, handle: object, _filesystem: str):
            self.enumeration_count += 1
            if handle is self.root_handle:
                return (
                    module.WindowsDirectoryEntry(
                        "epoch",
                        0x10,
                        "ntfs_file_index_64",
                        2,
                    ),
                )
            return ()

        def open_by_id(self, volume: object, entry, *, directory: bool) -> object:
            assert volume is self.root_handle
            assert directory is True
            assert entry.name == "epoch"
            return self.epoch_handle

        def close(self, _handle: object) -> None:
            return None

    api = DirectoryApi()
    monkeypatch.setattr(module, "_load_windows_backend", lambda: api)
    epoch_identity, targets = module._observe_windows(
        _private_windows_projection(module)
    )

    assert epoch_identity == _shared_windows_snapshot(module, file_id=2).identity_json
    assert len(targets) == 6
    assert api.require_stream_values and all(api.require_stream_values)


def test_windows_file_and_parent_drift_return_no_evidence() -> None:
    module = _load_module()
    entry = module.WindowsDirectoryEntry(
        "memory.db",
        0,
        "ntfs_file_index_64",
        7,
    )
    initial_membership = module._windows_membership((entry,))

    class DriftApi:
        def __init__(self, *, state_drift: bool, membership_drift: bool) -> None:
            self.states = iter(
                (
                    _shared_windows_snapshot(
                        module,
                        file_id=7,
                        kind="regular_file",
                        size=4,
                    ),
                    _shared_windows_snapshot(
                        module,
                        file_id=7,
                        kind="regular_file",
                        size=5 if state_drift else 4,
                    ),
                )
            )
            self.membership_drift = membership_drift
            self.file_handle = object()

        def open_by_id(self, *_args, **_kwargs) -> object:
            return self.file_handle

        def snapshot(self, *_args, **_kwargs):
            return next(self.states)

        def hash_file(self, handle: object):
            assert handle is self.file_handle
            return hashlib.sha256(b"data").hexdigest(), 4

        def enumerate_directory(self, *_args):
            if self.membership_drift:
                return (
                    module.WindowsDirectoryEntry(
                        "renamed.db",
                        0,
                        "ntfs_file_index_64",
                        7,
                    ),
                )
            return (entry,)

        def close(self, handle: object) -> None:
            assert handle is self.file_handle
            return None

    for state_drift, membership_drift in ((True, False), (False, True)):
        with pytest.raises(module.FilesystemObservationError) as exc_info:
            module._windows_observe_file(
                DriftApi(
                    state_drift=state_drift,
                    membership_drift=membership_drift,
                ),
                volume_handle=object(),
                parent_handle=object(),
                parent_initial=initial_membership,
                filesystem="NTFS",
                volume_serial=1,
                entry=entry,
                role="memory_database",
                relative_path="memory.db",
            )
        assert exc_info.value.code == "observation_raced"


def test_windows_file_close_failure_preserves_primary_observer_error() -> None:
    module = _load_module()
    entry = module.WindowsDirectoryEntry(
        "memory.db",
        0,
        "ntfs_file_index_64",
        7,
    )
    primary = module.FilesystemObservationError("observation_raced")
    native_close_error = OSError("close failed")
    file_handle = object()

    class FailingCloseApi:
        def open_by_id(self, *_args, **_kwargs) -> object:
            return file_handle

        def snapshot(self, *_args, **_kwargs):
            raise primary

        def close(self, handle: object) -> None:
            assert handle is file_handle
            raise module.WindowsHeldHandleError("observation_failed") from native_close_error

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._windows_observe_file(
            FailingCloseApi(),
            volume_handle=object(),
            parent_handle=object(),
            parent_initial=module._windows_membership((entry,)),
            filesystem="NTFS",
            volume_serial=1,
            entry=entry,
            role="memory_database",
            relative_path="memory.db",
        )

    assert exc_info.value is primary
    assert isinstance(primary.__cause__, module.FilesystemObservationError)
    assert primary.__cause__.code == "observation_failed"
    assert primary.__cause__.__cause__ is native_close_error


def test_windows_context_close_failure_is_translated_inside_primary_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    root_handle = object()

    class ExitFailingApi(_ContextManagedBackendDouble):
        def __exit__(self, _exc_type, exc, traceback) -> bool:
            assert isinstance(exc, module.FilesystemObservationError)
            close_error = module.WindowsHeldHandleError("observation_failed")
            exc.__cause__ = close_error
            exc.__suppress_context__ = True
            raise exc.with_traceback(traceback)

        def open_root(self, _root: str) -> object:
            return root_handle

        def volume_filesystem(self, handle: object) -> str:
            assert handle is root_handle
            return "NTFS"

        def snapshot(self, handle: object, *_args, **_kwargs):
            assert handle is root_handle
            return _shared_windows_snapshot(module, file_id=1)

        def enumerate_directory(self, handle: object, _filesystem: str):
            assert handle is root_handle
            return ()

    monkeypatch.setattr(module, "_load_windows_backend", ExitFailingApi)

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))

    assert exc_info.value.code == "required_root_missing"
    assert isinstance(exc_info.value.__cause__, module.FilesystemObservationError)
    assert exc_info.value.__cause__.code == "observation_failed"


def test_windows_backend_primary_translates_context_close_failure_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()

    class BackendPrimaryExitFailingApi(_ContextManagedBackendDouble):
        def __exit__(self, _exc_type, exc, traceback) -> bool:
            assert isinstance(exc, module.WindowsHeldHandleError)
            assert exc.code == "sharing_conflict"
            close_error = module.WindowsHeldHandleError("observation_failed")
            exc.__cause__ = close_error
            exc.__suppress_context__ = True
            raise exc.with_traceback(traceback)

        def open_root(self, _root: str) -> object:
            raise module.WindowsHeldHandleError("sharing_conflict")

    monkeypatch.setattr(
        module,
        "_load_windows_backend",
        BackendPrimaryExitFailingApi,
    )

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))

    assert exc_info.value.code == "sharing_conflict"
    assert isinstance(exc_info.value.__cause__, module.FilesystemObservationError)
    assert exc_info.value.__cause__.code == "observation_failed"


def test_windows_backend_primary_preserves_native_cause_and_translates_close_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    native_primary = OSError("primary native failure")

    class ExistingCauseExitFailingApi(_ContextManagedBackendDouble):
        def __exit__(self, _exc_type, exc, traceback) -> bool:
            assert isinstance(exc, module.WindowsHeldHandleError)
            assert exc.__cause__ is native_primary
            close_error = module.WindowsHeldHandleError("observation_failed")
            exc.__context__ = close_error
            raise exc.with_traceback(traceback)

        def open_root(self, _root: str) -> object:
            raise module.WindowsHeldHandleError("sharing_conflict") from native_primary

    monkeypatch.setattr(
        module,
        "_load_windows_backend",
        ExistingCauseExitFailingApi,
    )

    with pytest.raises(module.FilesystemObservationError) as exc_info:
        module._observe_windows(_private_windows_projection(module))

    assert exc_info.value.code == "sharing_conflict"
    assert exc_info.value.__cause__ is native_primary
    assert isinstance(exc_info.value.__context__, module.FilesystemObservationError)
    assert exc_info.value.__context__.code == "observation_failed"


def test_deep_windows_faiss_tree_is_iterative_not_recursion_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    deepest_directory = 1050
    leaf_id = 5000

    class DeepApi(_ContextManagedBackendDouble):
        def __init__(self) -> None:
            self.handles_by_file_id = {
                file_id: object()
                for file_id in (*range(1, deepest_directory + 1), leaf_id)
            }
            self.file_ids_by_handle = {
                handle: file_id
                for file_id, handle in self.handles_by_file_id.items()
            }

        def open_root(self, _root: str) -> object:
            return self.handles_by_file_id[1]

        def volume_filesystem(self, handle: object) -> str:
            assert handle is self.handles_by_file_id[1]
            return "NTFS"

        def snapshot(self, handle: object, *_args, **kwargs):
            kind = kwargs["object_kind"]
            return _shared_windows_snapshot(
                module,
                file_id=self.file_ids_by_handle[handle],
                kind=kind,
                size=0,
            )

        def enumerate_directory(self, handle: object, _filesystem: str):
            file_id = self.file_ids_by_handle[handle]
            if file_id == 1:
                return (
                    module.WindowsDirectoryEntry(
                        "epoch", 0x10, "ntfs_file_index_64", 2
                    ),
                )
            if file_id == 2:
                return (
                    module.WindowsDirectoryEntry(
                        "faiss", 0x10, "ntfs_file_index_64", 3
                    ),
                )
            if 3 <= file_id < deepest_directory:
                return (
                    module.WindowsDirectoryEntry(
                        f"d{file_id}",
                        0x10,
                        "ntfs_file_index_64",
                        file_id + 1,
                    ),
                )
            if file_id == deepest_directory:
                return (
                    module.WindowsDirectoryEntry(
                        "leaf.index",
                        0,
                        "ntfs_file_index_64",
                        leaf_id,
                    ),
                )
            raise AssertionError(f"unexpected directory file id {file_id}")

        def open_by_id(self, volume: object, entry, *, directory: bool) -> object:
            assert volume is self.handles_by_file_id[1]
            assert directory is entry.is_directory
            return self.handles_by_file_id[int(entry.file_id)]

        def hash_file(self, handle: object):
            assert handle is self.handles_by_file_id[leaf_id]
            return hashlib.sha256(b"").hexdigest(), 0

        def close(self, handle: object) -> None:
            assert handle in self.file_ids_by_handle
            return None

    monkeypatch.setattr(module, "_load_windows_backend", DeepApi)
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
    native = module.WindowsHeldHandleBackend()

    class TraceApi:
        def __init__(self) -> None:
            self.root_paths: list[str] = []
            self.opened_ids: list[int | bytes] = []
            self.enum_cache: dict[object, tuple] = {}

        def __enter__(self):
            native.__enter__()
            return self

        def __exit__(self, *args) -> bool:
            return native.__exit__(*args)

        def open_root(self, root: str) -> object:
            self.root_paths.append(root)
            return native.open_root(root)

        def open_by_id(self, volume_handle, entry, *, directory: bool):
            self.opened_ids.append(entry.file_id)
            return native.open_by_id(volume_handle, entry, directory=directory)

        def enumerate_directory(self, handle: object, filesystem: str):
            if handle not in self.enum_cache:
                self.enum_cache[handle] = native.enumerate_directory(handle, filesystem)
            return self.enum_cache[handle]

        def __getattr__(self, name: str):
            return getattr(native, name)

    trace = TraceApi()
    monkeypatch.setattr(module, "_load_windows_backend", lambda: trace)
    result = module.observe_filesystem(_projection(outer))

    assert result.filesystem_targets[0].exists is True
    assert trace.root_paths == [f"{Path(outer).drive}\\"]
    assert trace.opened_ids
    assert all(
        isinstance(file_id, int) or isinstance(file_id, bytes)
        for file_id in trace.opened_ids
    )


@pytest.mark.parametrize(
    ("file_id_kind", "file_id", "expected_identity_json"),
    (
        (
            "ntfs_file_index_64",
            0xFEDCBA9876543210,
            '{"file_id":"fedcba9876543210","file_id_kind":"ntfs_file_index_64",'
            '"object_kind":"regular_file","schema":"goodq.windows-file-identity.v1",'
            '"volume_serial":"123456789abcdef0"}',
        ),
        (
            "refs_file_id_128",
            bytes(range(16)),
            '{"file_id":"000102030405060708090a0b0c0d0e0f",'
            '"file_id_kind":"refs_file_id_128","object_kind":"regular_file",'
            '"schema":"goodq.windows-file-identity.v1",'
            '"volume_serial":"123456789abcdef0"}',
        ),
    ),
)
def test_windows_outward_evidence_preserves_shared_identity_json(
    file_id_kind: str,
    file_id: int | bytes,
    expected_identity_json: str,
) -> None:
    module = _load_module()
    entry = module.WindowsDirectoryEntry(
        "memory.db",
        0,
        file_id_kind,
        file_id,
    )
    snapshot = module.WindowsObjectSnapshot(
        volume_serial=0x123456789ABCDEF0,
        file_id_kind=file_id_kind,
        file_id=file_id,
        object_kind="regular_file",
        size_bytes=4,
        mtime_ns=500,
        allocation_size=4096,
        link_count=1,
        attributes=0,
        reparse_tag=0,
        last_write_ticks=116444736000000005,
        change_ticks=116444736000000006,
        streams=(("::$DATA", 4, 4096),),
    )

    class EvidenceBackend:
        def open_by_id(self, *_args, **_kwargs) -> object:
            return object()

        def snapshot(self, *_args, **_kwargs):
            return snapshot

        def hash_file(self, _handle: object):
            return hashlib.sha256(b"data").hexdigest(), 4

        def enumerate_directory(self, *_args):
            return (entry,)

        def close(self, _handle: object) -> None:
            return None

    target = module._windows_observe_file(
        EvidenceBackend(),
        volume_handle=object(),
        parent_handle=object(),
        parent_initial=module._windows_membership((entry,)),
        filesystem="NTFS" if file_id_kind == "ntfs_file_index_64" else "ReFS",
        volume_serial=0x123456789ABCDEF0,
        entry=entry,
        role="memory_database",
        relative_path="memory.db",
    )

    assert target.file_identity_json == expected_identity_json
    assert target.file_identity_json == snapshot.identity_json




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
