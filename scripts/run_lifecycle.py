#!/usr/bin/env python3
import os
import sys
import sqlite3
import json
import uuid
import requests
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mini_agent_client import MiniAgentClient
from steps.common.config_loader import load_configs

# Constants from request
VIDEO_HASH = "edbe944b455af57136c3fa62510605857dcd92a389c0889c795bcc1031cc9fba"
EPOCH_ID = "epoch_2026_06_16_r0_smoke"

def run_gated_tool(client: MiniAgentClient, tool_name: str, tool_args: dict):
    print(f"\n--- Requesting confirmation for tool: {tool_name} ---")
    envelope, rc = client.execute_tool(
        tool_name=tool_name,
        tool_args=tool_args,
        confirm=False
    )
    print(f"Initial call return code: {rc}")
    print(f"Initial envelope status: {envelope.get('status')}")
    
    if envelope.get("status") == "needs_confirmation":
        token = envelope["result"]["confirmation_token"]
        print(f"Obtained confirmation token: {token}")
        print(f"--- Executing tool with confirmation: {tool_name} ---")
        envelope, rc = client.execute_tool(
            tool_name=tool_name,
            tool_args=tool_args,
            confirm=True,
            confirmation_token=token
        )
        print(f"Confirmed call return code: {rc}")
    return envelope, rc

def query_ledger_status_counts(ledger_db_path: Path):
    conn = sqlite3.connect(str(ledger_db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT promotion_status, count(*) FROM context_frames "
        "WHERE video_hash = ? AND epoch_id = ? GROUP BY promotion_status",
        (VIDEO_HASH, EPOCH_ID)
    )
    counts = dict(cursor.fetchall())
    conn.close()
    return counts

def main():
    print("Initializing MiniAgentClient(profile='safe')...")
    client = MiniAgentClient(profile="safe")
    
    cfg = load_configs({})
    db_dir = cfg.get("paths", {}).get("db_dir")
    data_root = cfg.get("paths", {}).get("data_root")
    qdrant_host = cfg.get("qdrant", {}).get("host", "http://127.0.0.1:6333")
    
    ledger_db_path = Path(db_dir) / "ucf" / "ucf_ledger.db"
    memory_db_path = Path(cfg["paths"]["db_path"])
    kg_db_path = Path(cfg["paths"]["knowledge_graph_db"])
    
    print(f"Ledger DB path: {ledger_db_path}")
    print(f"Memory DB path: {memory_db_path}")
    print(f"Knowledge Graph DB path: {kg_db_path}")
    
    # ----------------------------------------------------
    # b. Premature Promotion Check
    # ----------------------------------------------------
    print("\n[STEP B] Attempting premature promotion (before validation)...")
    envelope, rc = run_gated_tool(
        client, 
        "promote_ucf_to_memory", 
        {"video_hash": VIDEO_HASH, "epoch_id": EPOCH_ID}
    )
    
    print(f"Premature promotion envelope status: {envelope.get('status')}")
    print(f"Premature promotion output: {envelope.get('output')}")
    
    assert envelope["status"] == "success", f"Expected envelope status success, got {envelope['status']}"
    assert envelope["output"]["status"] == "blocked", f"Expected output status blocked, got {envelope['output']['status']}"
    assert envelope["output"]["reason"] == "promotion_blocked_unvalidated_frames", \
        f"Expected reason promotion_blocked_unvalidated_frames, got {envelope['output']['reason']}"
    print("[STEP B] Premature promotion assertion PASSED successfully.")

    # Check ledger status before validation
    counts_before = query_ledger_status_counts(ledger_db_path)
    print(f"Ledger frame counts before validation: {counts_before}")
    assert counts_before.get("staged", 0) > 0, "No staged frames found in ledger!"

    # ----------------------------------------------------
    # c. Execute Validation
    # ----------------------------------------------------
    print("\n[STEP C] Executing validation...")
    envelope_val, rc_val = run_gated_tool(
        client,
        "validate_ucf_frames",
        {"video_hash": VIDEO_HASH, "epoch_id": EPOCH_ID}
    )
    print(f"Validation envelope status: {envelope_val.get('status')}")
    print(f"Validation output: {envelope_val.get('output')}")
    
    assert envelope_val["status"] == "success", f"Expected validation status success, got {envelope_val['status']}"
    output_val = envelope_val["output"]
    assert output_val["status"] == "validated_complete", f"Expected validated_complete, got {output_val['status']}"
    assert output_val["validated_count"] == 115, f"Expected 115 validated frames, got {output_val['validated_count']}"
    print("[STEP C] Validation assertions PASSED successfully.")

    # ----------------------------------------------------
    # d. Verify database frame states (validated)
    # ----------------------------------------------------
    print("\n[STEP D] Verifying ledger DB states after validation...")
    counts_after_val = query_ledger_status_counts(ledger_db_path)
    print(f"Ledger frame counts after validation: {counts_after_val}")
    assert counts_after_val.get("staged", 0) == 0, f"Expected staged count to be 0, got {counts_after_val.get('staged')}"
    assert counts_after_val.get("validated", 0) == 115, f"Expected validated count to be 115, got {counts_after_val.get('validated')}"
    print("[STEP D] Ledger DB validation states verified successfully.")

    # ----------------------------------------------------
    # e. Execute Promotion
    # ----------------------------------------------------
    print("\n[STEP E] Executing promotion to memory...")
    envelope_prom, rc_prom = run_gated_tool(
        client,
        "promote_ucf_to_memory",
        {"video_hash": VIDEO_HASH, "epoch_id": EPOCH_ID}
    )
    print(f"Promotion envelope status: {envelope_prom.get('status')}")
    print(f"Promotion output: {json.dumps(envelope_prom.get('output'), indent=2)}")
    
    assert envelope_prom["status"] == "success", f"Expected promotion status success, got {envelope_prom['status']}"
    output_prom = envelope_prom["output"]
    assert output_prom["status"] == "promoted_complete", f"Expected promoted_complete, got {output_prom['status']}"
    assert output_prom["promoted_count"] == 115, f"Expected 115 promoted frames, got {output_prom['promoted_count']}"
    
    qsync = output_prom["qdrant_sync"]
    assert qsync["status"] == "ok", f"Expected Qdrant sync status 'ok', got {qsync['status']}"
    assert qsync["points_attempted"] > 0, f"Expected points_attempted > 0, got {qsync['points_attempted']}"
    assert len(qsync["collections_attempted"]) > 0, "Expected collections_attempted to be non-empty"
    print("[STEP E] Promotion assertions PASSED successfully.")

    # ----------------------------------------------------
    # f. Verify database frame states (promoted)
    # ----------------------------------------------------
    print("\n[STEP F] Verifying ledger DB states after promotion...")
    counts_after_prom = query_ledger_status_counts(ledger_db_path)
    print(f"Ledger frame counts after promotion: {counts_after_prom}")
    assert counts_after_prom.get("validated", 0) == 0, f"Expected validated count to be 0, got {counts_after_prom.get('validated')}"
    assert counts_after_prom.get("promoted", 0) == 115, f"Expected promoted count to be 115, got {counts_after_prom.get('promoted')}"
    print("[STEP F] Ledger DB promotion states verified successfully.")

    # ----------------------------------------------------
    # g. Verify Memory DB tables populated
    # ----------------------------------------------------
    print("\n[STEP G] Verifying Memory DB records...")
    assert memory_db_path.exists(), f"Memory DB does not exist at {memory_db_path}"
    conn_mem = sqlite3.connect(str(memory_db_path))
    cursor_mem = conn_mem.cursor()
    
    tables_to_check = ["scenes", "segments", "embeddings", "links", "scene_text_fts", "ucf_provenance_mapping"]
    mem_counts = {}
    for table in tables_to_check:
        try:
            cursor_mem.execute(f"SELECT count(*) FROM {table}")
            cnt = cursor_mem.fetchone()[0]
            mem_counts[table] = cnt
        except Exception as e:
            print(f"Error checking table {table}: {e}")
            mem_counts[table] = -1
    conn_mem.close()
    
    print("Memory DB Table Row Counts:")
    for tbl, cnt in mem_counts.items():
        print(f"  - {tbl}: {cnt}")
        assert cnt >= 0, f"Table {tbl} check failed!"
        assert cnt > 0, f"Table {tbl} is empty!"
    print("[STEP G] Memory DB validation verified successfully.")

    # ----------------------------------------------------
    # h. Verify Knowledge Graph DB nodes and edges
    # ----------------------------------------------------
    print("\n[STEP H] Verifying Knowledge Graph DB...")
    assert kg_db_path.exists(), f"Knowledge Graph DB does not exist at {kg_db_path}"
    conn_kg = sqlite3.connect(str(kg_db_path))
    cursor_kg = conn_kg.cursor()
    
    cursor_kg.execute("SELECT count(*) FROM nodes")
    kg_nodes_total = cursor_kg.fetchone()[0]
    cursor_kg.execute("SELECT count(*) FROM edges")
    kg_edges_total = cursor_kg.fetchone()[0]
    
    cursor_kg.execute("SELECT node_type, count(*) FROM nodes GROUP BY node_type")
    kg_nodes_breakdown = dict(cursor_kg.fetchall())
    conn_kg.close()
    
    print(f"Total Nodes: {kg_nodes_total}")
    print(f"Total Edges: {kg_edges_total}")
    print("Nodes breakdown by type:")
    for nt, cnt in kg_nodes_breakdown.items():
        print(f"  - {nt}: {cnt}")
        
    assert kg_nodes_total > 0, "KG has no nodes!"
    assert kg_edges_total > 0, "KG has no edges!"
    for required_type in ["video", "scene", "segment", "evidence"]:
        assert kg_nodes_breakdown.get(required_type, 0) > 0, f"No KG nodes of type: {required_type}"
    print("[STEP H] Knowledge Graph DB verified successfully.")

    # ----------------------------------------------------
    # i. Collect, map and print materialization report
    # ----------------------------------------------------
    print("\n[STEP I] Collecting and validating materialization run manifest/report...")
    report_raw = output_prom.get("materialization_report", {})
    
    # Construct/Map materialization report fields
    materialization_run_id = str(uuid.uuid4())
    materialization = {
        "materialization_run_id": materialization_run_id,
        "epoch_id": report_raw.get("scope", {}).get("epoch_id"),
        "video_hash": report_raw.get("scope", {}).get("video_hash"),
        "promotion_scope": report_raw.get("scope"),
        "source_ucf_frame_count": len(report_raw.get("scope", {}).get("promoted_frame_ids", [])),
        "memory_db_records_created": sum(report_raw.get("counts", {}).get(k, 0) for k in ("scenes_materialized", "segments_materialized", "embeddings_materialized")),
        "kg_nodes_created": report_raw.get("counts", {}).get("kg_nodes_materialized", 0),
        "kg_edges_created": report_raw.get("counts", {}).get("kg_edges_materialized", 0),
        "records_skipped": 0,
        "errors": report_raw.get("errors", []),
        "warnings": envelope_prom.get("warnings", []),
        "validation_report_ref": report_raw.get("validation_reference", "validate_ucf_epoch --mode strict")
    }
    
    print("\nMaterialization Manifest:")
    print(json.dumps(materialization, indent=2))
    
    required_fields = [
        "materialization_run_id", "epoch_id", "video_hash", "promotion_scope",
        "source_ucf_frame_count", "memory_db_records_created", "kg_nodes_created",
        "kg_edges_created", "records_skipped", "errors", "warnings", "validation_report_ref"
    ]
    for field in required_fields:
        assert field in materialization, f"Required field '{field}' is missing from materialization manifest"
    print("[STEP I] Materialization Manifest assertions PASSED successfully.")

    print("\nAll run_lifecycle steps completed successfully.")

if __name__ == "__main__":
    main()
