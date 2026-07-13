from __future__ import annotations

import json
import multiprocessing
import os
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import pytest
import sqlite3
from lib.knowledge_graph import KnowledgeGraph
from lib import summary_aggregator
from api.routes import summary as summary_route
from api.utils.loaders import DataLoader
from api.utils.response_models import (
    SummaryDashboardResponse,
    EntityProfileResponse,
    SaveCollectionRequest
)

def create_test_db_for_summary(db_path: Path):
    """Set up a temporary knowledge graph with raw unstitched entities for summary testing."""
    with KnowledgeGraph(str(db_path)) as kg:
        # Add people
        kg.add_node(node_type="person", name="Joe", properties={"source": "operator_manual_override"}, timestamp=10.0)
        kg.add_node(node_type="person", name="Maria", properties={"source": "operator_manual_override"}, timestamp=20.0)
        
        # Add location
        kg.add_node(node_type="location", name="Living Room", properties={"source": "extractor"}, timestamp=10.0)
        kg.add_node(node_type="location", name="Kitchen", properties={"source": "extractor"}, timestamp=20.0)
        
        # Add temporal context
        kg.add_node(node_type="temporal_context", name="Explicit_dates_1988-05-18", properties={"source": "extractor", "confidence": 0.95})
        kg.add_node(node_type="temporal_context", name="Christmas Dinner", properties={"source": "extractor", "confidence": 0.85}) # matches holiday
        
        # Add concept
        kg.add_node(node_type="concept", name="Speech", properties={"source": "extractor"})
        
        # Add scene nodes
        scene1_id = kg.add_node(node_type="scene", name="scene_001")
        scene2_id = kg.add_node(node_type="scene", name="scene_002")
        
        # Add media nodes
        m1 = kg.add_media_node(media_type="video_scene", media_path="vid1.mp4", scene_id="scene_001", timestamp_start=0.0, timestamp_end=10.0)
        m2 = kg.add_media_node(media_type="video_scene", media_path="vid1.mp4", scene_id="scene_002", timestamp_start=10.0, timestamp_end=20.0)
        
        # Link nodes to media to simulate occurrences and co-occurrences
        kg.link_node_to_media(node_id=kg.add_node(node_type="person", name="Joe"), media_id=m1)
        kg.link_node_to_media(node_id=kg.add_node(node_type="location", name="Living Room"), media_id=m1)
        kg.link_node_to_media(node_id=kg.add_node(node_type="person", name="Maria"), media_id=m1)
        
        kg.link_node_to_media(node_id=kg.add_node(node_type="person", name="Joe"), media_id=m2)
        kg.link_node_to_media(node_id=kg.add_node(node_type="location", name="Kitchen"), media_id=m2)


class MockDataLoader:
    """Mock DataLoader for summary testing."""
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.data_root = temp_dir
        self.processing_dir = temp_dir / "processing"
        self.completed_dir = temp_dir / "completed"
        
    def list_processed_videos(self) -> list[str]:
        return ["vid1"]
        
    def load_temporal_index(self, video_id: str) -> dict | None:
        idx_path = self.processing_dir / video_id / "temporal_index.json"
        if not idx_path.exists():
            return None
        with idx_path.open("r", encoding="utf-8") as f:
            return json.load(f)


def _historical_v1_collection() -> dict:
    """Representative collection persisted by the original v1 writer."""
    return {
        "collection_id": "col_20260524_192200_0001",
        "name": "Historical playlist",
        "description": None,
        "status": "active",
        "collection_type": "manual_playlist",
        "query_params": {"person": "Joe"},
        "scene_refs": [{"video_id": "vid1", "scene_id": "scene_001"}],
        "source_epoch": "epoch_historical_v1",
        "created_at_utc": "2026-05-24T19:22:00Z",
        "created_by": "operator",
        "updated_at_utc": "2026-05-24T19:22:00Z",
        "deleted_at_utc": None,
        "history": [
            {
                "action": "create",
                "timestamp_utc": "2026-05-24T19:22:00Z",
                "operator_note": None,
            }
        ],
    }


def _spawn_collection_worker(
    db_path: str,
    action: str,
    value: str,
    start_event,
    result_queue,
) -> None:
    """Spawn-safe worker for real cross-process collection mutations."""
    if not start_event.wait(timeout=15):
        raise RuntimeError("collection worker start gate timed out")
    if action == "create":
        result = summary_aggregator.add_collection(
            Path(db_path),
            {"name": value},
        )
    elif action == "delete":
        result = summary_aggregator.soft_delete_collection(Path(db_path), value)
    else:
        raise ValueError(f"unsupported test action: {action}")
    result_queue.put((action, result))


def _run_spawn_collection_workers(
    db_path: Path,
    operations: list[tuple[str, str]],
) -> list[tuple[str, object]]:
    try:
        context = multiprocessing.get_context("spawn")
    except ValueError as exc:  # pragma: no cover - only on runtimes without spawn
        pytest.skip(f"multiprocessing spawn is unavailable: {exc}")

    start_event = context.Event()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_spawn_collection_worker,
            args=(str(db_path), action, value, start_event, result_queue),
        )
        for action, value in operations
    ]
    try:
        for process in processes:
            process.start()
        start_event.set()
        for process in processes:
            process.join(timeout=30)
            assert not process.is_alive(), "spawned collection worker timed out"
            assert process.exitcode == 0
        return [result_queue.get(timeout=5) for _ in processes]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        result_queue.close()
        result_queue.join_thread()


def test_dashboard_and_profile_schemas(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db_for_summary(db_path)
    
    # Create mock temporal_index
    vid_dir = tmp_path / "processing" / "vid1"
    vid_dir.mkdir(parents=True, exist_ok=True)
    temporal_index_data = {
        "version": 1,
        "video_path": "L:\\_DATA\\GoodQ_Data\\import_inbox\\vid1.mp4",
        "segments": [
            {
                "scene_id": "scene_001",
                "start": 0.0,
                "end": 10.0,
                "sentiment_label": "positive",
                "audio_emotion": "approval",
                "speaker_count": 2,
                "speaker_ids": ["SPEAKER_00", "SPEAKER_01"],
                "visible_people": [{"name": "Joe"}, {"name": "Maria"}]
            },
            {
                "scene_id": "scene_002",
                "start": 10.0,
                "end": 20.0,
                "sentiment_label": "negative",
                "audio_emotion": "anger",
                "speaker_count": 1,
                "speaker_ids": ["SPEAKER_00"]
            }
        ]
    }
    with (vid_dir / "temporal_index.json").open("w", encoding="utf-8") as f:
        json.dump(temporal_index_data, f)
        
    loader = MockDataLoader(tmp_path)
    
    # 1. Test stable entity_id behavior
    assert summary_aggregator._get_stable_entity_id("person", "Joe") == "person:Joe"
    t, n = summary_aggregator._parse_stable_entity_id("person:Joe")
    assert t == "person"
    assert n == "Joe"
    
    # 2. Compile dashboard and validate against Pydantic schema
    dash_data = summary_aggregator.get_summary_dashboard(db_path, loader)
    # Check scope metadata fields
    assert dash_data["scope_metadata"]["epoch"] == tmp_path.name
    assert dash_data["scope_metadata"]["db_path"] == "knowledge_graph.db"
    assert dash_data["scope_metadata"]["video_count"] == 1
    assert dash_data["scope_metadata"]["scene_count"] == 2
    
    # Validate Occasions Rename
    assert len(dash_data["occasions"]) == 1
    assert dash_data["occasions"][0]["name"] == "Christmas Dinner"
    assert dash_data["occasions"][0]["occasion_type"] == "holiday"
    assert dash_data["occasions"][0]["confidence"] == 0.85
    
    # Validate Pydantic parse
    parsed_dash = SummaryDashboardResponse(**dash_data)
    assert len(parsed_dash.people) == 2
    assert parsed_dash.people[0].name == "Joe"
    assert parsed_dash.people[0].entity_id == "person:Joe"
    
    # 3. Test entity profile schema
    profile_data = summary_aggregator.get_entity_profile(db_path, loader, "person:Joe")
    parsed_profile = EntityProfileResponse(**profile_data)
    assert parsed_profile.name == "Joe"
    assert parsed_profile.node_type == "person"
    assert parsed_profile.occurrence_count == 3
    assert len(parsed_profile.co_occurrences) == 3 # Maria, Living Room, Kitchen
    assert len(parsed_profile.scenes) == 2


def test_collections_crud_and_atomic_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db_for_summary(db_path)
    
    # 1. Test load empty collections file
    col_data = summary_aggregator.load_collections(db_path)
    assert col_data["schema_version"] == 1
    assert col_data["collections"] == []
    
    # 2. Test create collection (atomic write)
    req = {
        "name": "My Custom Highlight",
        "description": "Custom operator scene playlist",
        "collection_type": "manual_playlist",
        "query_params": {"person": "Joe"},
        "scene_refs": [{"video_id": "vid1", "scene_id": "scene_001"}]
    }
    new_col = summary_aggregator.add_collection(db_path, req, created_by="operator")
    assert new_col["collection_id"].startswith("col_")
    assert new_col["name"] == "My Custom Highlight"
    assert new_col["status"] == "active"
    assert len(new_col["history"]) == 1
    assert new_col["history"][0]["action"] == "create"
    
    # Verify file was atomically written
    col_file = db_path.parent / "saved_collections.json"
    assert col_file.is_file()
    
    # 3. Test list collections (active only)
    loaded = summary_aggregator.load_collections(db_path)
    assert len(loaded["collections"]) == 1
    assert loaded["collections"][0]["collection_id"] == new_col["collection_id"]
    
    # 4. Test soft-delete collection
    success = summary_aggregator.soft_delete_collection(db_path, new_col["collection_id"])
    assert success is True
    
    # Verify soft-deleted details in JSON
    with col_file.open("r", encoding="utf-8") as f:
        stored = json.load(f)
        col = stored["collections"][0]
        assert col["status"] == "deleted"
        assert col["deleted_at_utc"] is not None
        assert len(col["history"]) == 2
        assert col["history"][-1]["action"] == "delete"
        
    # Check that deleted collection is not returned by soft-delete list check
    data_list = summary_aggregator.load_collections(db_path)
    active_cols = [c for c in data_list.get("collections", []) if c.get("status") == "active"]
    assert len(active_cols) == 0


@pytest.mark.parametrize("omitted_optional_field", [None, "description", "deleted_at_utc"])
def test_load_accepts_historical_v1_collection_and_optional_nullable_fields(
    tmp_path: Path,
    omitted_optional_field: str | None,
) -> None:
    collection = _historical_v1_collection()
    if omitted_optional_field is not None:
        collection.pop(omitted_optional_field)
    payload = {"schema_version": 1, "collections": [collection]}
    collections_file = tmp_path / "saved_collections.json"
    collections_file.write_text(json.dumps(payload), encoding="utf-8")

    assert summary_aggregator.load_collections(tmp_path / "knowledge_graph.db") == payload


@pytest.mark.parametrize(
    "missing_field",
    [
        "collection_id",
        "name",
        "status",
        "collection_type",
        "query_params",
        "scene_refs",
        "source_epoch",
        "created_at_utc",
        "created_by",
        "updated_at_utc",
        "history",
    ],
)
def test_load_fails_closed_when_required_v1_collection_field_is_missing(
    tmp_path: Path,
    missing_field: str,
) -> None:
    collection = _historical_v1_collection()
    collection.pop(missing_field)
    payload = {"schema_version": 1, "collections": [collection]}
    collections_file = tmp_path / "saved_collections.json"
    persisted = json.dumps(payload).encode("utf-8")
    collections_file.write_bytes(persisted)

    with pytest.raises(RuntimeError, match="saved collections store"):
        summary_aggregator.load_collections(tmp_path / "knowledge_graph.db")
    assert collections_file.read_bytes() == persisted


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("collection_id", ""),
        ("name", ""),
        ("description", 7),
        ("status", "unknown"),
        ("collection_type", ""),
        ("query_params", []),
        ("scene_refs", {}),
        ("scene_refs", ["not-a-reference"]),
        ("source_epoch", ""),
        ("created_at_utc", ""),
        ("created_by", ""),
        ("updated_at_utc", ""),
        ("deleted_at_utc", 7),
        ("history", {}),
    ],
)
def test_load_fails_closed_on_malformed_v1_collection_field(
    tmp_path: Path,
    field: str,
    invalid_value: object,
) -> None:
    collection = _historical_v1_collection()
    collection[field] = invalid_value
    payload = {"schema_version": 1, "collections": [collection]}
    collections_file = tmp_path / "saved_collections.json"
    persisted = json.dumps(payload).encode("utf-8")
    collections_file.write_bytes(persisted)

    with pytest.raises(RuntimeError, match="saved collections store"):
        summary_aggregator.load_collections(tmp_path / "knowledge_graph.db")
    assert collections_file.read_bytes() == persisted


@pytest.mark.parametrize(
    "invalid_history_entry",
    [
        "not-an-entry",
        {},
        {"timestamp_utc": "2026-05-24T19:22:00Z"},
        {"action": "create"},
        {"action": "", "timestamp_utc": "2026-05-24T19:22:00Z"},
        {"action": "create", "timestamp_utc": ""},
        {
            "action": "create",
            "timestamp_utc": "2026-05-24T19:22:00Z",
            "operator_note": 7,
        },
    ],
)
def test_load_fails_closed_on_malformed_v1_history_entry(
    tmp_path: Path,
    invalid_history_entry: object,
) -> None:
    collection = deepcopy(_historical_v1_collection())
    collection["history"] = [invalid_history_entry]
    payload = {"schema_version": 1, "collections": [collection]}
    collections_file = tmp_path / "saved_collections.json"
    persisted = json.dumps(payload).encode("utf-8")
    collections_file.write_bytes(persisted)

    with pytest.raises(RuntimeError, match="saved collections store"):
        summary_aggregator.load_collections(tmp_path / "knowledge_graph.db")
    assert collections_file.read_bytes() == persisted


@pytest.mark.parametrize(
    "invalid_payload",
    [
        b"{not-json",
        json.dumps({"schema_version": 2, "collections": []}).encode("utf-8"),
        json.dumps({"schema_version": 1, "collections": {}}).encode("utf-8"),
        json.dumps(
            {
                "schema_version": 1,
                "collections": [
                    {"collection_id": "", "status": "active", "history": []}
                ],
            }
        ).encode("utf-8"),
    ],
)
def test_collection_mutations_fail_closed_on_invalid_existing_store(
    tmp_path: Path,
    invalid_payload: bytes,
) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    collections_file = tmp_path / "saved_collections.json"
    collections_file.write_bytes(invalid_payload)

    with pytest.raises(RuntimeError, match="saved collections store"):
        summary_aggregator.add_collection(db_path, {"name": "must not persist"})
    assert collections_file.read_bytes() == invalid_payload

    with pytest.raises(RuntimeError, match="saved collections store"):
        summary_aggregator.soft_delete_collection(db_path, "col_existing")
    assert collections_file.read_bytes() == invalid_payload


def test_load_absent_collection_store_creates_no_artifact(tmp_path: Path) -> None:
    epoch_dir = tmp_path / "absent-epoch"
    db_path = epoch_dir / "knowledge_graph.db"

    assert summary_aggregator.load_collections(db_path) == {
        "schema_version": 1,
        "collections": [],
    }
    assert not epoch_dir.exists()


def test_load_existing_collection_store_creates_no_artifact(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    collections_file = tmp_path / "saved_collections.json"
    collections_file.write_text(
        json.dumps({"schema_version": 1, "collections": []}),
        encoding="utf-8",
    )
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    assert summary_aggregator.load_collections(db_path) == {
        "schema_version": 1,
        "collections": [],
    }
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_directory_close_failure_is_reported_as_unsupported_not_raised(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    class FailingCloseOS:
        name = "posix"
        O_RDONLY = os.O_RDONLY
        O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)

        @staticmethod
        def open(_path, _flags):
            return 41

        @staticmethod
        def fsync(_descriptor):
            return None

        @staticmethod
        def close(_descriptor):
            raise OSError("simulated directory descriptor close failure")

    monkeypatch.setattr(summary_aggregator, "os", FailingCloseOS)

    assert summary_aggregator._fsync_directory_if_supported(tmp_path) is False
    assert "directory descriptor" in caplog.text.lower()


class _FlushFailingFile:
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __enter__(self):
        self._wrapped.__enter__()
        return self

    def __exit__(self, *args):
        return self._wrapped.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    def flush(self):
        raise OSError("simulated temp flush failure")


@pytest.mark.parametrize("failure_stage", ["write", "flush", "fsync", "replace"])
def test_collection_save_failure_preserves_authoritative_bytes_and_cleans_temp(
    tmp_path: Path,
    monkeypatch,
    failure_stage: str,
) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    summary_aggregator.add_collection(db_path, {"name": "authoritative"})
    collections_file = tmp_path / "saved_collections.json"
    authoritative_bytes = collections_file.read_bytes()
    foreign_temp = tmp_path / "saved_collections.json.tmp-foreign-owner"
    foreign_temp_bytes = b"foreign writer artifact"
    foreign_temp.write_bytes(foreign_temp_bytes)

    if failure_stage == "write":
        def fail_dump(_data, handle, **_kwargs):
            handle.write("{")
            raise OSError("simulated temp write failure")

        monkeypatch.setattr(summary_aggregator.json, "dump", fail_dump)
    elif failure_stage == "flush":
        real_open = Path.open

        def fail_temp_flush(path, *args, **kwargs):
            opened = real_open(path, *args, **kwargs)
            mode = str(args[0] if args else kwargs.get("mode", "r"))
            if ".tmp-" in path.name and "w" in mode:
                return _FlushFailingFile(opened)
            return opened

        monkeypatch.setattr(Path, "open", fail_temp_flush)
    elif failure_stage == "fsync":
        monkeypatch.setattr(
            os,
            "fsync",
            lambda _fd: (_ for _ in ()).throw(
                OSError("simulated temp fsync failure")
            ),
        )
    else:
        monkeypatch.setattr(
            os,
            "replace",
            lambda *_args: (_ for _ in ()).throw(OSError("simulated replace failure")),
        )

    with pytest.raises(RuntimeError, match="Failed to save collections"):
        summary_aggregator.add_collection(db_path, {"name": "must not persist"})

    assert collections_file.read_bytes() == authoritative_bytes
    assert foreign_temp.read_bytes() == foreign_temp_bytes
    assert list(tmp_path.glob("saved_collections.json.tmp-*")) == [foreign_temp]


def test_concurrent_collection_creates_lose_no_updates_and_use_unique_ids(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    worker_count = 16
    barrier = threading.Barrier(worker_count)

    def create(index: int) -> dict:
        barrier.wait(timeout=10)
        return summary_aggregator.add_collection(
            db_path,
            {"name": f"concurrent-{index}"},
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        created = list(executor.map(create, range(worker_count)))

    loaded = summary_aggregator.load_collections(db_path)["collections"]
    assert {item["name"] for item in loaded} == {
        f"concurrent-{index}" for index in range(worker_count)
    }
    assert len({item["collection_id"] for item in created}) == worker_count
    assert len({item["collection_id"] for item in loaded}) == worker_count


def test_concurrent_collection_create_and_delete_lose_no_update(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    target = summary_aggregator.add_collection(db_path, {"name": "delete-target"})
    create_count = 12
    barrier = threading.Barrier(create_count + 1)

    def create(index: int) -> dict:
        barrier.wait(timeout=10)
        return summary_aggregator.add_collection(
            db_path,
            {"name": f"survivor-{index}"},
        )

    def delete() -> bool:
        barrier.wait(timeout=10)
        return summary_aggregator.soft_delete_collection(
            db_path,
            target["collection_id"],
        )

    with ThreadPoolExecutor(max_workers=create_count + 1) as executor:
        create_futures = [
            executor.submit(create, index) for index in range(create_count)
        ]
        delete_future = executor.submit(delete)
        created = [future.result(timeout=15) for future in create_futures]
        deleted = delete_future.result(timeout=15)

    loaded = summary_aggregator.load_collections(db_path)["collections"]
    by_id = {item["collection_id"]: item for item in loaded}
    assert deleted is True
    assert by_id[target["collection_id"]]["status"] == "deleted"
    assert {item["name"] for item in loaded if item["status"] == "active"} == {
        f"survivor-{index}" for index in range(create_count)
    }
    assert len({item["collection_id"] for item in created}) == create_count


def test_spawned_collection_creates_lose_no_updates(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    operations = [("create", f"spawn-create-{index}") for index in range(6)]

    results = _run_spawn_collection_workers(db_path, operations)

    loaded = summary_aggregator.load_collections(db_path)["collections"]
    assert {item["name"] for item in loaded} == {
        f"spawn-create-{index}" for index in range(6)
    }
    created = [result for action, result in results if action == "create"]
    assert len(created) == 6
    assert len({item["collection_id"] for item in created}) == 6


def test_spawned_collection_create_and_delete_lose_no_update(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    target = summary_aggregator.add_collection(db_path, {"name": "spawn-delete-target"})
    operations = [
        *(('create', f"spawn-survivor-{index}") for index in range(5)),
        ("delete", target["collection_id"]),
    ]

    results = _run_spawn_collection_workers(db_path, operations)

    loaded = summary_aggregator.load_collections(db_path)["collections"]
    by_id = {item["collection_id"]: item for item in loaded}
    assert any(action == "delete" and result is True for action, result in results)
    assert by_id[target["collection_id"]]["status"] == "deleted"
    assert {item["name"] for item in loaded if item["status"] == "active"} == {
        f"spawn-survivor-{index}" for index in range(5)
    }


def test_no_mutation_invariants(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db_for_summary(db_path)
    
    # Copy or create target files
    manifest_path = tmp_path / "processing" / "vid1" / "video" / "scene_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"scenes": []}))
    manifest_hash_before = hash(manifest_path.read_text())
    
    # Record SQLite row counts before
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    nodes_count_before = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    edges_count_before = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    conn.close()
    
    # Run dashboard, profiles, and collection operations
    loader = MockDataLoader(tmp_path)
    
    # 1. Read operations
    summary_aggregator.get_summary_dashboard(db_path, loader)
    try:
        summary_aggregator.get_entity_profile(db_path, loader, "person:Joe")
    except Exception:
        pass
        
    # 2. Write collections operations
    req = {
        "name": "No Mutation Test Collection",
        "scene_refs": [{"video_id": "vid1", "scene_id": "scene_001"}]
    }
    col = summary_aggregator.add_collection(db_path, req)
    summary_aggregator.soft_delete_collection(db_path, col["collection_id"])
    
    # Verify SQLite counts are identical (no mutation of SQLite core tables)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    nodes_count_after = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    edges_count_after = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    conn.close()
    
    assert nodes_count_before == nodes_count_after
    assert edges_count_before == edges_count_after
    
    # Verify scene_manifest is unchanged
    manifest_hash_after = hash(manifest_path.read_text())
    assert manifest_hash_before == manifest_hash_after


def test_graceful_missing_temporal_index(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db_for_summary(db_path)
    
    # Keep vid1 directory empty (no temporal_index.json)
    loader = MockDataLoader(tmp_path)
    
    # Dashboard and profile should run gracefully and not fail
    dash_data = summary_aggregator.get_summary_dashboard(db_path, loader)
    assert dash_data["scope_metadata"]["scene_count"] == 0
    assert len(dash_data["built_in_highlights"]["positive_moments"]) == 0
    
    profile_data = summary_aggregator.get_entity_profile(db_path, loader, "person:Joe")
    assert profile_data["name"] == "Joe"
    assert len(profile_data["scenes"]) == 0
