#!/usr/bin/env python3
# ==============================================================================
# CANONICAL INGESTION PROMOTION ENGINE
# ==============================================================================
# File: scripts/ucf/validate_and_promote_epoch.py
# Description: Permanent workflow runner to execute validation checks on the UCF 
#              ledger for active epochs and promote staged data to relational 
#              memory.db and semantic graph layers.
# Safety Notes:
# - Run only after offline validation queries have passed.
# - Leverages MiniAgentClient to execute transaction-safe promotions.
# ==============================================================================
import sys
import sqlite3
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mini_agent_client import MiniAgentClient

EPOCH_ID = "epoch_2026_07_05_home_memory_clean_01"

def run_gated_tool(client: MiniAgentClient, tool_name: str, tool_args: dict):
    print(f"\n--- Requesting confirmation for tool: {tool_name} with args {tool_args} ---")
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

def main():
    print(f"Initializing MiniAgentClient(profile='safe') to promote epoch: {EPOCH_ID}...")
    client = MiniAgentClient(profile="safe")
    
    # Let's find all video hashes for this epoch from the database
    db_path = Path("L:/_DATA/GoodQ_Data/epochs/epoch_2026_07_05_home_memory_clean_01/ucf/ucf_ledger.db")
    if not db_path.exists():
        print("Database not found!")
        return
        
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT video_hash FROM context_frames WHERE epoch_id = ?", (EPOCH_ID,))
    video_hashes = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    
    print(f"Found {len(video_hashes)} videos in epoch {EPOCH_ID} to promote:")
    for vh in video_hashes:
        print(f"  {vh}")
        
    # Promote each video hash
    for i, vh in enumerate(video_hashes):
        print(f"\n==================================================")
        print(f"Promoting video {i+1}/{len(video_hashes)}: {vh}")
        print(f"==================================================")
        
        envelope_prom, rc_prom = run_gated_tool(
            client,
            "promote_ucf_to_memory",
            {"video_hash": vh, "epoch_id": EPOCH_ID}
        )
        print(f"Promotion envelope status: {envelope_prom.get('status')}")
        print(f"Promotion output status: {envelope_prom.get('output', {}).get('status')}")
        print(f"Promoted count: {envelope_prom.get('output', {}).get('promoted_count')}")

if __name__ == "__main__":
    main()
