#!/usr/bin/env python3
"""
Integration test suite acting as governance regression guards for Phase 7 & 8.
Covers:
1. Pipeline step coverage (inventoried, governed destinations).
2. Model loader registry lockdown (no unregistered repo IDs).
3. UCF/vector parity (14/14 strict gates).
4. Materialization provenance & orphan edge detection.
5. Search lifecycle promoted-only restrictions.
6. Encoding, path, and token hygiene.
7. Agent security profile controls (safe, offline, unrestricted).
"""

import os
import re
import sys
import json
import sqlite3
import pytest
import yaml
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agents.mini_agent_client import MiniAgentClient
from retrieval.multimodal_search import MultimodalSearchEngine
from steps.common.model_provisioner import _FALLBACK_REGISTRY

# Define governed output destination mapping for all 17 core steps
GOVERNED_DESTINATIONS = {
    "video_scene_detect": {"ucf_context_frame", "scene_manifest"},
    "image_caption": {"ucf_context_frame"},
    "image_ocr": {"ucf_context_frame"},
    "object_detect": {"ucf_context_frame"},
    "face_embed": {"ucf_context_frame"},
    "image_embed_clip": {"ucf_context_frame", "vector_store"},
    "image_embed_dino": {"ucf_context_frame", "vector_store"},
    "audio_metadata": {"ucf_context_frame"},
    "audio_diarize": {"ucf_context_frame"},
    "audio_transcribe": {"ucf_context_frame", "raw_ref"},
    "audio_emotion": {"ucf_context_frame"},
    "audio_embed_clap": {"ucf_context_frame", "vector_store"},
    "text_embed": {"ucf_context_frame", "vector_store"},
    "sentiment": {"ucf_context_frame"},
    "emotion_classify": {"ucf_context_frame"},
    "tagger": {"ucf_context_frame"},
    "overview": {"ucf_context_frame", "scene_manifest"}
}

def test_pipeline_step_coverage():
    """Phase 7.1: Pipeline step coverage validator.
    Fails if a registered pipeline step has no governed output destination,
    or if a step silently disappears from the inventory.
    """
    from tests.legacy.utilities.validate_all_steps import STEP_DEFINITIONS
    
    # 1. Check that no step from the expected 17 core steps silently disappeared
    expected_steps = set(GOVERNED_DESTINATIONS.keys())
    for step in expected_steps:
        assert step in STEP_DEFINITIONS, f"Step '{step}' silently disappeared from the inventory!"
        
    # 2. Check that every step in the inventory has at least one governed output destination
    for step in STEP_DEFINITIONS:
        dest = GOVERNED_DESTINATIONS.get(step)
        assert dest is not None and len(dest) > 0, f"Step '{step}' has no governed output destination configured!"

def test_model_loader_validator():
    """Phase 7.2: Model loader validator.
    Fails if raw unregistered model loads remain, or if a repo ID is used outside the central registry.
    """
    # Load registered IDs from central configs/model_registry.yaml
    registry_path = REPO_ROOT / "configs" / "model_registry.yaml"
    assert registry_path.is_file(), "Model registry configuration file not found!"
    
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = yaml.safe_load(f) or {}
        
    registered_ids = set()
    # Add HF models keys, repo_ids, and short names
    hf_models = registry.get("huggingface_models", {}) or {}
    for key, info in hf_models.items():
        registered_ids.add(key)
        repo_id = info.get("repo_id")
        if repo_id:
            registered_ids.add(repo_id)
            if "/" in repo_id:
                registered_ids.add(repo_id.split("/")[-1])
                
    # Add external models keys, names, and local paths
    ext_models = registry.get("external_models", {}) or {}
    for key, info in ext_models.items():
        registered_ids.add(key)
        name = info.get("name")
        if name:
            registered_ids.add(name)
        lpath = info.get("local_path")
        if lpath:
            registered_ids.add(lpath)
            registered_ids.add(Path(lpath).name)
            
    # Add fallbacks
    for fb_id, fb_info in _FALLBACK_REGISTRY.items():
        registered_ids.add(fb_id)
        if "/" in fb_id:
            registered_ids.add(fb_id.split("/")[-1])
        registered_ids.add(fb_info["key"])
        if "local_path" in fb_info:
            registered_ids.add(fb_info["local_path"])
            registered_ids.add(Path(fb_info["local_path"]).name)
            
    # Production directories to scan
    scan_dirs = ["agents", "api", "cli", "common", "lib", "pipelines", "retrieval", "steps", "wsl2_audio"]
    
    # regexes for model loadings
    patterns = [
        re.compile(r"from_pretrained\s*\(\s*['\"]([^'\"]+)['\"]"),
        re.compile(r"SentenceTransformer\s*\(\s*['\"]([^'\"]+)['\"]"),
        re.compile(r"YOLO\s*\(\s*['\"]([^'\"]+)['\"]"),
        re.compile(r"WhisperModel\s*\(\s*['\"]([^'\"]+)['\"]"),
    ]
    
    unregistered_loads = []
    
    for sdir in scan_dirs:
        dir_path = REPO_ROOT / sdir
        if not dir_path.is_dir():
            continue
        for pfile in dir_path.glob("**/*.py"):
            # Exclude tests/ or other non-production content in sdirs
            if "test" in pfile.name.lower() or "archive" in pfile.parts or "deprecated" in pfile.name.lower():
                continue
            try:
                content = pfile.read_text(encoding="utf-8")
                for pat in patterns:
                    for match in pat.finditer(content):
                        model_id = match.group(1)
                        # Skip environment variable variables or function arguments
                        if model_id.startswith(("$", "{", "self.", "cfg")):
                            continue
                        if model_id not in registered_ids:
                            unregistered_loads.append((str(pfile.relative_to(REPO_ROOT)), model_id))
            except Exception as e:
                pass
                
    assert len(unregistered_loads) == 0, f"Unregistered model loads found: {unregistered_loads}"

def test_ucf_vector_parity_gates():
    """Phase 7.3: UCF/vector parity validator.
    Ensure strict mode remains 14/14 or expands, never weakens.
    """
    validator_script_path = REPO_ROOT / "scripts" / "ucf" / "validate_ucf_epoch.py"
    assert validator_script_path.is_file(), "UCF validation script not found!"
    
    import ast
    with open(validator_script_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
        
    report_keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "report":
                    if isinstance(node.value, ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant):
                                report_keys.append(k.value)
                            elif isinstance(k, ast.Str):
                                report_keys.append(k.s)
                                
    # Exclude non-gate report properties
    non_gates = {"epoch_id", "timestamp", "summary", "transcript_coverage", "per_scene_coverage"}
    gates = [k for k in report_keys if k not in non_gates]
    
    # Assert that all 14 gates are present
    expected_gates = {
        "path_hygiene", "schema_version", "promotion_status", "temporal_bounds",
        "payload_hash", "flatness", "spatial_region", "manifest_reconciliation",
        "raw_ref_gate", "scene_overlap_gate", "raw_reconciliation",
        "absolute_timestamps", "media_sources_gate", "vector_integrity"
    }
    
    for gate in expected_gates:
        assert gate in gates, f"Gate '{gate}' is missing from the UCF validator!"
        
    assert len(gates) >= 14, f"Validator strict mode weakened! Expected >= 14 gates, got {len(gates)}."

def test_materialization_validator(tmp_path):
    """Phase 7.4: Materialization validator.
    Verify active memory/KG records have UCF provenance, no orphan graph edges,
    no active rows for staged/validated/terminal evidence.
    """
    # Create temporary mock SQLite databases
    ucf_path = tmp_path / "ucf_ledger.db"
    mem_path = tmp_path / "memory.db"
    kg_path = tmp_path / "knowledge_graph.db"
    
    # 1. Setup ucf_ledger with various states
    conn_ucf = sqlite3.connect(ucf_path)
    conn_ucf.execute("CREATE TABLE context_frames (frame_id INTEGER PRIMARY KEY, promotion_status TEXT)")
    conn_ucf.execute("INSERT INTO context_frames VALUES (1, 'promoted')")
    conn_ucf.execute("INSERT INTO context_frames VALUES (2, 'staged')")
    conn_ucf.execute("INSERT INTO context_frames VALUES (3, 'validated')")
    conn_ucf.execute("INSERT INTO context_frames VALUES (4, 'rejected')")
    conn_ucf.execute("INSERT INTO context_frames VALUES (5, 'superseded')")
    conn_ucf.commit()
    conn_ucf.close()
    
    # 2. Setup memory.db
    conn_mem = sqlite3.connect(mem_path)
    conn_mem.execute("CREATE TABLE scenes (id TEXT, ucf_provenance TEXT)")
    conn_mem.execute("CREATE TABLE segments (id TEXT, ucf_provenance TEXT)")
    conn_mem.execute("CREATE TABLE ucf_provenance_mapping (record_type TEXT, record_id TEXT, ucf_frame_id INTEGER)")
    
    # Insert a valid scene (maps to frame 1 - promoted)
    conn_mem.execute("INSERT INTO scenes VALUES ('scene_1', '[1]')")
    conn_mem.execute("INSERT INTO ucf_provenance_mapping VALUES ('scene', 'scene_1', 1)")
    
    # Insert an invalid segment (maps to frame 2 - staged, which is non-promoted!)
    conn_mem.execute("INSERT INTO segments VALUES ('seg_1', '[2]')")
    conn_mem.execute("INSERT INTO ucf_provenance_mapping VALUES ('segment', 'seg_1', 2)")
    conn_mem.commit()
    
    # 3. Setup knowledge_graph.db
    conn_kg = sqlite3.connect(kg_path)
    conn_kg.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY, type TEXT, properties TEXT)")
    conn_kg.execute("CREATE TABLE edges (source TEXT, target TEXT, type TEXT, properties TEXT)")
    
    # Node 1: promoted provenance
    conn_kg.execute("INSERT INTO nodes VALUES ('n1', 'scene', '{\"ucf_provenance\": [1]}')")
    # Node 2: staged provenance
    conn_kg.execute("INSERT INTO nodes VALUES ('n2', 'segment', '{\"ucf_provenance\": [2]}')")
    # Node 3: no provenance at all (orphan/anonymous!)
    conn_kg.execute("INSERT INTO nodes VALUES ('n3', 'entity', '{}')")
    
    # Edge 1: valid node connection
    conn_kg.execute("INSERT INTO edges VALUES ('n1', 'n2', 'scene_has_segment', '{\"ucf_provenance\": [1]}')")
    # Edge 2: orphan edge (target 'n99' does not exist!)
    conn_kg.execute("INSERT INTO edges VALUES ('n1', 'n99', 'invalid_edge', '{\"ucf_provenance\": [1]}')")
    conn_kg.commit()
    conn_kg.close()
    
    # Run Validator logic
    # Step A: Load non-promoted frame IDs
    conn_ucf = sqlite3.connect(ucf_path)
    cur = conn_ucf.execute("SELECT frame_id FROM context_frames WHERE promotion_status != 'promoted'")
    non_promoted_fids = {r[0] for r in cur.fetchall()}
    conn_ucf.close()
    
    assert non_promoted_fids == {2, 3, 4, 5}
    
    # Step B: Validate memory.db
    errors = []
    
    # Check scenes ucf_provenance
    cur = conn_mem.execute("SELECT id, ucf_provenance FROM scenes")
    for r_id, prov in cur.fetchall():
        if not prov:
            errors.append(f"Scene '{r_id}' has no UCF provenance!")
            continue
        try:
            fids = json.loads(prov)
            if not fids:
                errors.append(f"Scene '{r_id}' has empty UCF provenance!")
            for fid in fids:
                if fid in non_promoted_fids:
                    errors.append(f"Scene '{r_id}' contains non-promoted UCF frame {fid}!")
        except Exception as e:
            errors.append(f"Scene '{r_id}' has invalid provenance JSON: {e}")
            
    # Check segments ucf_provenance (should find seg_1 mapped to frame 2)
    cur = conn_mem.execute("SELECT id, ucf_provenance FROM segments")
    for r_id, prov in cur.fetchall():
        if not prov:
            errors.append(f"Segment '{r_id}' has no UCF provenance!")
            continue
        try:
            fids = json.loads(prov)
            for fid in fids:
                if fid in non_promoted_fids:
                    errors.append(f"Segment '{r_id}' contains non-promoted UCF frame {fid}!")
        except Exception:
            pass
            
    # Check ucf_provenance_mapping for staged/terminal frames
    cur = conn_mem.execute("SELECT record_type, record_id, ucf_frame_id FROM ucf_provenance_mapping")
    for r_type, r_id, fid in cur.fetchall():
        if fid in non_promoted_fids:
            errors.append(f"Provenance mapping '{r_type}:{r_id}' is active but points to non-promoted frame {fid}!")
            
    # Verify we caught the errors in memory.db
    assert any("Segment 'seg_1' contains non-promoted" in e for e in errors)
    assert any("Provenance mapping 'segment:seg_1' is active but points to non-promoted" in e for e in errors)
    
    # Step C: Validate knowledge_graph.db
    kg_errors = []
    conn_kg = sqlite3.connect(kg_path)
    
    # Get all node IDs
    cur_n = conn_kg.execute("SELECT id, properties FROM nodes")
    nodes = {r[0]: json.loads(r[1]) for r in cur_n.fetchall()}
    
    for nid, props in nodes.items():
        prov = props.get("ucf_provenance")
        if not prov:
            kg_errors.append(f"KG Node '{nid}' has no UCF provenance!")
        else:
            for fid in prov:
                if fid in non_promoted_fids:
                    kg_errors.append(f"KG Node '{nid}' contains non-promoted UCF frame {fid}!")
                    
    # Validate edges
    cur_e = conn_kg.execute("SELECT source, target, type, properties FROM edges")
    for src, tgt, etype, props in cur_e.fetchall():
        if src not in nodes:
            kg_errors.append(f"Orphan edge: source '{src}' does not exist!")
        if tgt not in nodes:
            kg_errors.append(f"Orphan edge: target '{tgt}' does not exist!")
        try:
            p_dict = json.loads(props)
            prov = p_dict.get("ucf_provenance")
            if not prov:
                kg_errors.append(f"Edge '{src}->{tgt}' has no UCF provenance!")
            else:
                for fid in prov:
                    if fid in non_promoted_fids:
                        kg_errors.append(f"Edge '{src}->{tgt}' contains non-promoted UCF frame {fid}!")
        except Exception:
            pass
            
    conn_kg.close()
    conn_mem.close()
    
    # Verify we caught graph violations
    assert any("KG Node 'n3' has no UCF provenance!" in e for e in kg_errors)
    assert any("KG Node 'n2' contains non-promoted" in e for e in kg_errors)
    assert any("Orphan edge: target 'n99' does not exist!" in e for e in kg_errors)

def test_search_lifecycle_promoted_only():
    """Phase 7.5: Search lifecycle validator.
    Ensure active search is promoted-only by default.
    """
    from steps.common.config_loader import load_configs
    search = MultimodalSearchEngine(config=load_configs({}))
    
    # 1. Default filter check: must include ucf_promotion_status = promoted
    default_filter = search._build_ucf_filter(payload_filter=None, ucf_include_terminal=False)
    assert default_filter == {"must": [{"key": "ucf_promotion_status", "match": {"value": "promoted"}}]}
    
    # 2. Debug/audit mode (ucf_include_terminal=True): should bypass promoted-only filter
    debug_filter = search._build_ucf_filter(payload_filter=None, ucf_include_terminal=True)
    assert debug_filter == {}

def test_hygiene_and_sanitization():
    """Phase 7.6: Encoding, path, and token hygiene.
    Explicit UTF-8 for JSON/text, no absolute local drive roots in public docs/envelopes.
    """
    client = MiniAgentClient(profile="safe")
    
    # Verify sanitization of absolute paths
    windows_path = "C:\\Users\\jdben\\My Drive\\_AGENT\\file.txt"
    sanitized_win = client.sanitize_envelope(windows_path)
    assert "C:\\" not in sanitized_win
    assert "relative/file.txt" in sanitized_win
    
    unc_path = "\\\\GOODCUBE\\shared\\data.json"
    sanitized_unc = client.sanitize_envelope(unc_path)
    assert "\\\\" not in sanitized_unc
    assert "relative/data.json" in sanitized_unc
    
    wsl_path = "/mnt/l/GOODCUBE/projects/goodq4all/scripts/test.py"
    sanitized_wsl = client.sanitize_envelope(wsl_path)
    assert "/mnt/" not in sanitized_wsl
    assert "relative/test.py" in sanitized_wsl
    
    linux_path = "/home/jdben/config.yaml"
    sanitized_lin = client.sanitize_envelope(linux_path)
    assert "/home/" not in sanitized_lin
    assert "relative/config.yaml" in sanitized_lin

def test_security_profiles_and_agent_controls():
    """Phase 8: Verify policy and agent controls hold.
    Audit safe/offline/unrestricted profile behavior.
    """
    # 1. Verify default profile is 'safe' (never unrestricted)
    default_client = MiniAgentClient()
    assert default_client.profile == "safe"
    
    # 2. Offline profile checks: blocks ingestion, mutation, external side effects, and destruction
    offline_client = MiniAgentClient(profile="offline")
    
    # Mutating tools must be blocked immediately (allowed = False)
    blocked_tools = ["run_ingestion", "promote_ucf_to_memory", "reject_ucf_frames", "supersede_ucf_frames", "file_delete"]
    for tool in blocked_tools:
        envelope, rc = offline_client.validate_action(
            prompt="Execute mutation",
            mode="ops",
            tool_name=tool,
            tool_args={}
        )
        assert rc == 1, f"Tool '{tool}' was not blocked in offline profile!"
        assert envelope["status"] == "error"
        assert envelope["errors"][0]["code"] == "offline_blocked"
        
    # Read-only tools must be allowed (allowed = True)
    allowed_tools = ["qdrant_query", "memory_search", "status_read"]
    for tool in allowed_tools:
        envelope, rc = offline_client.validate_action(
            prompt="Read status",
            mode="research",
            tool_name=tool,
            tool_args={}
        )
        if not offline_client.agent_available:
            assert rc == 0
            assert envelope["result"]["offline_fallback_active"] is True
            
    # 3. Safe profile checks: requires HITL (confirmation token) for canonical mutation
    safe_client = MiniAgentClient(profile="safe")
    
    # Mutating tool without confirmation must return status="needs_confirmation" and rc=3
    envelope, rc = safe_client.validate_action(
        prompt="Promote ucf frames",
        mode="ops",
        tool_name="promote_ucf_to_memory",
        tool_args={"epoch_id": "test_epoch"}
    )
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    assert "confirmation_token" in envelope["result"]
    assert envelope["errors"][0]["code"] == "mutability_requires_confirmation"
    
    token = envelope["result"]["confirmation_token"]
    assert token.startswith("token-promote-ucf-to-memory-")
    
    # 4. Unrestricted profile checks: allows execution without confirmation
    unrestricted_client = MiniAgentClient(profile="unrestricted")
    unrestricted_client.agent_available = True
    
    envelope, rc = unrestricted_client.validate_action(
        prompt="Promote ucf frames",
        mode="ops",
        tool_name="promote_ucf_to_memory",
        tool_args={"epoch_id": "test_epoch"}
    )
    # Direct bypass should return success / status="ok" (allowed to proceed without token)
    assert rc == 0
    assert envelope["status"] == "ok"
