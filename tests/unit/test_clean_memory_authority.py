from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from steps.common import clean_memory
from steps.common.clean_memory import (
    CandidatePlanStore,
    CleanMemoryPlanConflict,
    CleanMemoryPlanIntegrityError,
    CleanMemoryPlanPersistenceError,
    CleanMemoryPlanRecoveryError,
    FilesystemTargetEvidence,
    ProtectedBoundaryEvidence,
    QdrantCollectionEvidence,
    ResolvedCleanupScope,
    build_candidate_plan,
)


EPOCH_ID = "epoch_2026_07_family"
CONFIG_SCOPE_SHA256 = "a" * 64
FILE_SHA256 = "b" * 64
POINT_STATE_SHA256 = "c" * 64
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


def _canonical_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _identity(value: str) -> str:
    return _canonical_text(
        {
            "schema": "goodq.test-platform-identity.v1",
            "value": value,
        }
    )


def _present_file(role: str, relative_path: str, marker: str) -> FilesystemTargetEvidence:
    return FilesystemTargetEvidence(
        role=role,
        target_type="regular_file",
        relative_path=relative_path,
        exists=True,
        size_bytes=100 + len(marker),
        mtime_ns=1_720_000_000_000_000_000 + len(marker),
        file_identity_json=_identity(f"file-{marker}"),
        sha256=hashlib.sha256(marker.encode("utf-8")).hexdigest(),
    )


def _absent_file(role: str, relative_path: str) -> FilesystemTargetEvidence:
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


def _collection(role: str, *, fingerprint_kind: str = "point_state_sha256") -> QdrantCollectionEvidence:
    if fingerprint_kind == "generation_token":
        fingerprint_value = f"generation-{role}-1"
    else:
        fingerprint_value = hashlib.sha256(role.encode("utf-8")).hexdigest()
    return QdrantCollectionEvidence(
        role=role,
        collection_name=f"goodq_{role}_{EPOCH_ID}",
        exists=True,
        configuration_json=_canonical_text(
            {
                "distance": "Cosine",
                "vector_size": 768 if role != "audio" else 512,
            }
        ),
        point_count=17,
        fingerprint_kind=fingerprint_kind,
        fingerprint_value=fingerprint_value,
    )


def _scope(**overrides: object) -> ResolvedCleanupScope:
    values: dict[str, object] = {
        "epoch_id": EPOCH_ID,
        "config_scope_sha256": CONFIG_SCOPE_SHA256,
        "epoch_root_identity_json": _identity("epoch-root"),
        "filesystem_targets": (
            _present_file("memory_database", "memory/memory.db", "memory"),
            _absent_file("memory_database_wal", "memory/memory.db-wal"),
            _absent_file("memory_database_shm", "memory/memory.db-shm"),
            _present_file(
                "knowledge_graph_database",
                "knowledge_graph/knowledge_graph.db",
                "knowledge-graph",
            ),
            _absent_file(
                "knowledge_graph_database_wal",
                "knowledge_graph/knowledge_graph.db-wal",
            ),
            _absent_file(
                "knowledge_graph_database_shm",
                "knowledge_graph/knowledge_graph.db-shm",
            ),
            _present_file("faiss_file", "faiss/text.index", "faiss-text"),
        ),
        "qdrant_endpoint": "http://127.0.0.1:6333",
        "qdrant_collections": (
            _collection("text", fingerprint_kind="generation_token"),
            _collection("clip"),
            _collection("dino"),
            _collection("audio"),
        ),
        "protected_boundaries": tuple(
            ProtectedBoundaryEvidence(
                role=role,
                logical_id=f"protected:{role.replace('_', '-')}",
                identity_json=_identity(f"{role}-identity"),
            )
            for role in PROTECTED_BOUNDARY_ROLES
        ),
    }
    values.update(overrides)
    return ResolvedCleanupScope(**values)


def _plan(
    scope: ResolvedCleanupScope | None = None,
    *,
    observed_at_utc: str = "2026-07-13T20:00:00+00:00",
):
    return build_candidate_plan(
        scope or _scope(),
        observed_at_utc=observed_at_utc,
    )


def _tree_state(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
    if not root.exists():
        return ()
    state: list[tuple[str, str, bytes | None]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state.append((relative, "symlink", os.readlink(path).encode("utf-8")))
        elif path.is_dir():
            state.append((relative, "directory", None))
        else:
            state.append((relative, "file", path.read_bytes()))
    return tuple(state)


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def test_clean_memory_module_import_is_pure(tmp_path: Path) -> None:
    script = """
import importlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
before_env = dict(os.environ)
before_path = list(sys.path)
before_modules = set(sys.modules)
importlib.import_module('steps.common.clean_memory')
new_modules = set(sys.modules) - before_modules
forbidden = {
    'steps.common.config_loader',
    'api.utils.action_jobs',
    'agents.mini_agent_client',
    'steps.common.qdrant_client',
    'requests',
    'socket',
    'subprocess',
}
print(json.dumps({
    'environment_unchanged': dict(os.environ) == before_env,
    'sys_path_unchanged': list(sys.path) == before_path,
    'forbidden_imports': sorted(new_modules & forbidden),
    'tree': sorted(path.relative_to(root).as_posix() for path in root.rglob('*')),
}))
"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result == {
        "environment_unchanged": True,
        "sys_path_unchanged": True,
        "forbidden_imports": [],
        "tree": [],
    }


def test_candidate_plan_uses_only_injected_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    canary = tmp_path / "outside-canary.bin"
    canary.write_bytes(b"outside-stays-unchanged")
    before = _tree_state(tmp_path)

    plan = _plan()

    assert plan.plan_id == f"plan_{plan.plan_sha256}"
    assert _tree_state(tmp_path) == before


def test_authority_digest_matches_exact_canonical_json_contract() -> None:
    plan = _plan()
    authority = plan.authority
    expected_bytes = json.dumps(
        authority,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert authority["schema"] == "goodq.clean-memory-plan.v1"
    assert authority["operation"] == "clean_memory.apply"
    assert plan.plan_sha256 == hashlib.sha256(expected_bytes).hexdigest()
    assert plan.plan_id == f"plan_{plan.plan_sha256}"


def test_candidate_identity_ignores_observation_and_input_order() -> None:
    original = _scope()
    permuted = replace(
        original,
        filesystem_targets=tuple(reversed(original.filesystem_targets)),
        qdrant_collections=tuple(reversed(original.qdrant_collections)),
        protected_boundaries=tuple(reversed(original.protected_boundaries)),
    )

    first = _plan(original, observed_at_utc="2026-07-13T20:00:00+00:00")
    second = _plan(permuted, observed_at_utc="2026-07-13T20:01:00+00:00")

    assert first.authority == second.authority
    assert first.plan_sha256 == second.plan_sha256
    assert first.plan_id == second.plan_id
    assert first.observed_at_utc != second.observed_at_utc


def test_candidate_authority_is_detached_and_unapproved() -> None:
    plan = _plan()
    detached = plan.authority
    detached["epoch"]["epoch_id"] = "changed"
    keys = {key.lower() for key in _walk_keys(plan.authority)}

    assert plan.authority["epoch"]["epoch_id"] == EPOCH_ID
    assert keys.isdisjoint(
        {
            "job_id",
            "token",
            "authorization",
            "approval",
            "disposition",
            "rollback",
            "created_at_utc",
            "observed_at_utc",
            "nonce",
        }
    )
    assert plan.to_record()["observation"] == {
        "observed_at_utc": plan.observed_at_utc,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda scope: replace(scope, config_scope_sha256="A" * 64),
        lambda scope: replace(scope, epoch_root_identity_json='{"value":NaN}'),
        lambda scope: replace(
            scope,
            qdrant_collections=(
                replace(scope.qdrant_collections[0], configuration_json='{"size":NaN}'),
                *scope.qdrant_collections[1:],
            ),
        ),
        lambda scope: replace(
            scope,
            filesystem_targets=(
                replace(scope.filesystem_targets[0], size_bytes=True),
                *scope.filesystem_targets[1:],
            ),
        ),
    ],
)
def test_candidate_rejects_noncanonical_evidence_before_persistence(
    tmp_path: Path,
    mutate,
) -> None:
    store = CandidatePlanStore(tmp_path / "evidence")

    with pytest.raises(ValueError):
        store.persist(_plan(mutate(_scope())))

    assert not (tmp_path / "evidence").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"size_bytes": None},
        {"mtime_ns": None},
        {"file_identity_json": None},
        {"sha256": None},
        {"sha256": "B" * 64},
    ],
)
def test_present_files_require_complete_exact_prestate(changes: dict[str, object]) -> None:
    scope = _scope()
    targets = (
        replace(scope.filesystem_targets[0], **changes),
        *scope.filesystem_targets[1:],
    )

    with pytest.raises(ValueError):
        _plan(replace(scope, filesystem_targets=targets))


def test_present_files_reject_duplicate_platform_identity() -> None:
    scope = _scope()
    first_present = scope.filesystem_targets[0]
    targets = tuple(
        replace(target, file_identity_json=first_present.file_identity_json)
        if target.role == "faiss_file"
        else target
        for target in scope.filesystem_targets
    )

    with pytest.raises(ValueError, match="identity.*duplicated"):
        _plan(replace(scope, filesystem_targets=targets))


def test_absent_file_rejects_stale_prestate_and_duplicate_or_root_target() -> None:
    scope = _scope()
    absent_with_state = replace(
        scope.filesystem_targets[1],
        size_bytes=1,
        mtime_ns=1,
        file_identity_json=_identity("stale"),
        sha256=FILE_SHA256,
    )
    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                filesystem_targets=(
                    scope.filesystem_targets[0],
                    absent_with_state,
                    *scope.filesystem_targets[2:],
                ),
            )
        )

    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                filesystem_targets=(
                    replace(scope.filesystem_targets[0], target_type="directory"),
                    *scope.filesystem_targets[1:],
                ),
            )
        )


@pytest.mark.parametrize(
    "relative_path",
    [
        "faiss/file:stream",
        "faiss/file.",
        "faiss/file ",
        "faiss/CON.index",
    ],
)
def test_windows_alias_and_ads_paths_are_rejected(relative_path: str) -> None:
    scope = _scope()
    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                filesystem_targets=(
                    *scope.filesystem_targets[:-1],
                    replace(scope.filesystem_targets[-1], relative_path=relative_path),
                ),
            )
        )


def test_windows_case_equivalent_target_aliases_are_rejected() -> None:
    scope = _scope()
    alias = replace(
        scope.filesystem_targets[-1],
        relative_path=scope.filesystem_targets[-1].relative_path.upper(),
    )
    with pytest.raises(ValueError):
        _plan(replace(scope, filesystem_targets=(*scope.filesystem_targets, alias)))

    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                filesystem_targets=(
                    *scope.filesystem_targets,
                    replace(scope.filesystem_targets[-1]),
                ),
            )
        )

    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                filesystem_targets=(
                    replace(scope.filesystem_targets[0], relative_path="."),
                    *scope.filesystem_targets[1:],
                ),
            )
        )


@pytest.mark.parametrize("missing_role", ["text", "clip", "dino", "audio"])
def test_qdrant_prestate_requires_exact_four_roles(missing_role: str) -> None:
    scope = _scope()
    collections = tuple(
        item for item in scope.qdrant_collections if item.role != missing_role
    )

    with pytest.raises(ValueError):
        _plan(replace(scope, qdrant_collections=collections))


def test_qdrant_prestate_rejects_duplicate_name_extra_role_and_missing_fingerprint() -> None:
    scope = _scope()
    duplicate_name = replace(
        scope.qdrant_collections[1],
        collection_name=scope.qdrant_collections[0].collection_name,
    )
    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                qdrant_collections=(
                    scope.qdrant_collections[0],
                    duplicate_name,
                    *scope.qdrant_collections[2:],
                ),
            )
        )

    whitespace_token = replace(
        scope.qdrant_collections[0],
        fingerprint_kind="generation_token",
        fingerprint_value="\n",
    )
    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                qdrant_collections=(
                    whitespace_token,
                    *scope.qdrant_collections[1:],
                ),
            )
        )


@pytest.mark.parametrize(
    "endpoint",
    [
        "HTTP://127.0.0.1:6333",
        "http://127.0.0.1:06333",
        "http://127.0.0.1:6333?",
        "http://127.0.0.1:6333#",
    ],
)
def test_qdrant_endpoint_requires_one_canonical_spelling(endpoint: str) -> None:
    with pytest.raises(ValueError):
        _plan(replace(_scope(), qdrant_endpoint=endpoint))


def test_protected_boundary_set_is_exact_and_identities_are_nonempty() -> None:
    scope = _scope()
    assert {item.role for item in scope.protected_boundaries} == set(
        PROTECTED_BOUNDARY_ROLES
    )

    with pytest.raises(ValueError):
        _plan(replace(scope, protected_boundaries=scope.protected_boundaries[:-1]))

    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                protected_boundaries=(
                    replace(scope.protected_boundaries[0], identity_json="{}"),
                    *scope.protected_boundaries[1:],
                ),
            )
        )

    with pytest.raises(ValueError):
        _plan(replace(scope, epoch_root_identity_json="{}"))

    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                filesystem_targets=(
                    replace(scope.filesystem_targets[0], file_identity_json="{}"),
                    *scope.filesystem_targets[1:],
                ),
            )
        )

    extra = replace(scope.qdrant_collections[0], role="extra")
    with pytest.raises(ValueError):
        _plan(replace(scope, qdrant_collections=(*scope.qdrant_collections, extra)))

    missing_fingerprint = replace(
        scope.qdrant_collections[0],
        fingerprint_kind=None,
        fingerprint_value=None,
    )
    with pytest.raises(ValueError):
        _plan(
            replace(
                scope,
                qdrant_collections=(
                    missing_fingerprint,
                    *scope.qdrant_collections[1:],
                ),
            )
        )


def test_protected_boundaries_reject_duplicate_canonical_identity_envelopes() -> None:
    scope = _scope()
    duplicated_boundary = replace(
        scope.protected_boundaries[1],
        identity_json=scope.protected_boundaries[0].identity_json,
    )

    with pytest.raises(ValueError, match="Protected-boundary identity is duplicated"):
        _plan(
            replace(
                scope,
                protected_boundaries=(
                    scope.protected_boundaries[0],
                    duplicated_boundary,
                    *scope.protected_boundaries[2:],
                ),
            )
        )


def test_execution_order_is_canonical_not_input_enumeration_order() -> None:
    scope = _scope()
    expected = _plan(scope).authority["execution_order"]
    permuted = replace(
        scope,
        filesystem_targets=tuple(reversed(scope.filesystem_targets)),
        qdrant_collections=tuple(reversed(scope.qdrant_collections)),
    )

    assert _plan(permuted).authority["execution_order"] == expected


@pytest.mark.parametrize(
    "mutate",
    [
        lambda scope: replace(scope, epoch_id="epoch_2026_07_other"),
        lambda scope: replace(scope, config_scope_sha256="d" * 64),
        lambda scope: replace(scope, epoch_root_identity_json=_identity("other-root")),
        lambda scope: replace(
            scope,
            filesystem_targets=(
                replace(scope.filesystem_targets[0], size_bytes=999),
                *scope.filesystem_targets[1:],
            ),
        ),
        lambda scope: replace(scope, qdrant_endpoint="http://127.0.0.1:6334"),
        lambda scope: replace(
            scope,
            qdrant_collections=(
                replace(scope.qdrant_collections[0], point_count=18),
                *scope.qdrant_collections[1:],
            ),
        ),
        lambda scope: replace(
            scope,
            protected_boundaries=(
                replace(scope.protected_boundaries[0], identity_json=_identity("other")),
                *scope.protected_boundaries[1:],
            ),
        ),
    ],
)
def test_every_bound_prestate_change_changes_digest(mutate) -> None:
    baseline = _plan(_scope())
    changed = _plan(mutate(_scope()))

    assert changed.plan_sha256 != baseline.plan_sha256


def test_first_writer_persists_digest_named_plan_atomically(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    store = CandidatePlanStore(root)
    plan = _plan()

    persisted = store.persist(plan)
    target = store.record_path(plan.plan_sha256)

    assert target == root / f"plan_{plan.plan_sha256}.json"
    assert target.is_file()
    assert not target.is_symlink()
    assert target.read_bytes() == persisted.record_bytes()
    assert store.load(plan.plan_sha256) == persisted
    assert list(root.glob("plan_*.json")) == [target]
    assert list(root.glob("*.tmp-*")) == []


def test_repeated_and_concurrent_writers_preserve_first_record(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    first = CandidatePlanStore(root).persist(
        _plan(observed_at_utc="2026-07-13T20:00:00+00:00")
    )
    first_bytes = CandidatePlanStore(root).record_path(first.plan_sha256).read_bytes()

    def persist(index: int):
        return CandidatePlanStore(root).persist(
            _plan(observed_at_utc=f"2026-07-13T20:{index + 1:02d}:00+00:00")
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(executor.map(persist, range(16)))

    assert all(item == first for item in records)
    assert CandidatePlanStore(root).record_path(first.plan_sha256).read_bytes() == first_bytes
    assert len(list(root.glob("plan_*.json"))) == 1


def test_separate_process_writers_converge_on_first_record(tmp_path: Path) -> None:
    root = tmp_path / "process-evidence"
    script = """
from pathlib import Path
import hashlib
import json
import sys
from steps.common.clean_memory import CandidatePlanStore
from tests.unit.test_clean_memory_authority import _plan

store = CandidatePlanStore(Path(sys.argv[1]))
persisted = store.persist(_plan(observed_at_utc=sys.argv[2]))
print(json.dumps({
    "observed_at_utc": persisted.observed_at_utc,
    "record_sha256": hashlib.sha256(persisted.record_bytes()).hexdigest(),
}, sort_keys=True))
"""

    def persist(index: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(root),
                f"2026-07-13T21:{index:02d}:00+00:00",
            ],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(persist, range(8)))

    assert all(result.stderr == "" for result in results)
    receipts = [json.loads(result.stdout) for result in results]
    assert len({json.dumps(receipt, sort_keys=True) for receipt in receipts}) == 1
    plan_files = list(root.glob("plan_*.json"))
    assert len(plan_files) == 1
    persisted = CandidatePlanStore(root).load(plan_files[0].stem.removeprefix("plan_"))
    assert persisted is not None
    assert persisted.plan_sha256 == _plan().plan_sha256
    assert persisted.observed_at_utc == receipts[0]["observed_at_utc"]
    assert hashlib.sha256(plan_files[0].read_bytes()).hexdigest() == receipts[0][
        "record_sha256"
    ]


def test_same_digest_conflict_preserves_first_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(clean_memory, "_authority_sha256", lambda _authority: "f" * 64)
    store = CandidatePlanStore(tmp_path / "evidence")
    first = store.persist(_plan())
    target = store.record_path(first.plan_sha256)
    first_bytes = target.read_bytes()
    changed_scope = replace(_scope(), epoch_id="epoch_2026_07_other")

    with pytest.raises(CleanMemoryPlanConflict, match="collision|immutable"):
        store.persist(_plan(changed_scope))

    assert target.read_bytes() == first_bytes


@pytest.mark.parametrize(
    "payload",
    [
        b"{",
        json.dumps({"unknown": True}).encode("utf-8"),
    ],
)
def test_corrupt_existing_plan_fails_closed_and_preserves_bytes(
    tmp_path: Path,
    payload: bytes,
) -> None:
    store = CandidatePlanStore(tmp_path / "evidence")
    plan = _plan()
    target = store.record_path(plan.plan_sha256)
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)

    with pytest.raises(CleanMemoryPlanIntegrityError):
        store.persist(plan)

    assert target.read_bytes() == payload


def test_publish_failure_leaves_no_record_or_owned_temp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "evidence"
    store = CandidatePlanStore(root)
    plan = _plan()
    canary = tmp_path / "outside-canary.bin"
    canary.write_bytes(b"unchanged")
    monkeypatch.setattr(
        clean_memory,
        "_publish_no_replace",
        lambda *_args: (_ for _ in ()).throw(OSError("simulated publish failure")),
    )

    with pytest.raises(CleanMemoryPlanPersistenceError, match="persist"):
        store.persist(plan)

    assert not store.record_path(plan.plan_sha256).exists()
    assert list(root.glob("*.tmp-*")) == []
    assert canary.read_bytes() == b"unchanged"


def test_noncooperating_first_writer_is_never_overwritten(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = CandidatePlanStore(tmp_path / "evidence")
    plan = _plan()
    target = store.record_path(plan.plan_sha256)
    foreign_bytes = b'{"foreign":"first-writer"}\n'
    real_open = Path.open
    injected = False

    def open_with_racing_writer(path, *args, **kwargs):
        nonlocal injected
        handle = real_open(path, *args, **kwargs)
        if ".tmp-" in Path(path).name and not injected:
            injected = True
            target.write_bytes(foreign_bytes)
        return handle

    monkeypatch.setattr(Path, "open", open_with_racing_writer)

    with pytest.raises(CleanMemoryPlanIntegrityError):
        store.persist(plan)

    assert target.read_bytes() == foreign_bytes
    assert list(store.root.glob("*.tmp-*")) == []


def test_post_publish_verification_failure_preserves_evidence_for_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = CandidatePlanStore(tmp_path / "evidence")
    plan = _plan()
    target = store.record_path(plan.plan_sha256)
    real_read_bytes = Path.read_bytes
    foreign_bytes = b'{"foreign":"post-publish"}\n'
    substituted = False

    def substitute_before_verification(path):
        nonlocal substituted
        if Path(path) == target and target.exists() and not substituted:
            substituted = True
            target.write_bytes(foreign_bytes)
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", substitute_before_verification)

    with pytest.raises(CleanMemoryPlanRecoveryError, match="manual recovery"):
        store.persist(plan)

    assert target.read_bytes() == foreign_bytes


@pytest.mark.skipif(os.name != "nt", reason="Windows move vacates the source pathname")
def test_successful_windows_publish_never_deletes_foreign_temp_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = CandidatePlanStore(tmp_path / "evidence")
    plan = _plan()
    real_publish = clean_memory._publish_no_replace
    replacement: dict[str, Path] = {}
    foreign_bytes = b"foreign-temp-replacement"

    def publish_then_replace(source: Path, destination: Path) -> None:
        real_publish(source, destination)
        assert not source.exists()
        source.write_bytes(foreign_bytes)
        replacement["path"] = source

    monkeypatch.setattr(clean_memory, "_publish_no_replace", publish_then_replace)

    assert store.persist(plan).plan_sha256 == plan.plan_sha256
    assert replacement["path"].read_bytes() == foreign_bytes


def test_reparse_evidence_root_is_rejected_without_outside_change(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    canary = outside / "canary.bin"
    canary.write_bytes(b"outside-unchanged")
    redirected = tmp_path / "redirected-evidence"
    try:
        redirected.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")

    store = CandidatePlanStore(redirected)
    with pytest.raises(CleanMemoryPlanIntegrityError, match="reparse|redirect"):
        store.persist(_plan())

    assert canary.read_bytes() == b"outside-unchanged"
    assert list(outside.glob("plan_*.json")) == []


def test_missing_plan_read_is_passive(tmp_path: Path) -> None:
    root = tmp_path / "absent" / "evidence"
    store = CandidatePlanStore(root)

    assert store.load("a" * 64) is None
    assert not root.exists()


def test_existing_non_directory_evidence_root_is_not_reported_absent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "evidence"
    root.write_bytes(b"not-a-directory")
    store = CandidatePlanStore(root)

    with pytest.raises(CleanMemoryPlanIntegrityError, match="regular directory"):
        store.load("a" * 64)

    assert root.read_bytes() == b"not-a-directory"


def test_existing_non_directory_evidence_ancestor_is_not_reported_absent(
    tmp_path: Path,
) -> None:
    blocked_parent = tmp_path / "blocked-parent"
    blocked_parent.write_bytes(b"not-a-directory")
    store = CandidatePlanStore(blocked_parent / "evidence")

    with pytest.raises(CleanMemoryPlanIntegrityError, match="regular directory"):
        store.load("a" * 64)

    assert blocked_parent.read_bytes() == b"not-a-directory"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_dangling_windows_junction_ancestor_is_rejected(tmp_path: Path) -> None:
    junction_target = tmp_path / "junction-target"
    junction_target.mkdir()
    junction = tmp_path / "dangling-junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(junction_target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"junction unavailable: {result.stderr.strip()}")
    junction_target.rmdir()
    try:
        store = CandidatePlanStore(junction / "evidence")
        with pytest.raises(CleanMemoryPlanIntegrityError, match="reparse|redirect"):
            store.load("a" * 64)
    finally:
        junction.rmdir()
