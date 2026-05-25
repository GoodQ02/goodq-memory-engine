from __future__ import annotations

import json
from pathlib import Path
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
