#!/usr/bin/env python3
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mini_agent_client import MiniAgentClient

VIDEO_HASH = "da735e12e1dba6fcfc511d5c3d8a6428ad85845a8d4cef61a03f821e00c90a62"
EPOCH_ID = "epoch_2026_06_21_family_clean_01"

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

def main():
    print("Initializing MiniAgentClient(profile='safe')...")
    client = MiniAgentClient(profile="safe")
    
    # 1. Execute Validation
    print("\n[STEP 1] Executing validation via MiniAgentClient...")
    envelope_val, rc_val = run_gated_tool(
        client,
        "validate_ucf_frames",
        {"video_hash": VIDEO_HASH, "epoch_id": EPOCH_ID}
    )
    print(f"Validation envelope status: {envelope_val.get('status')}")
    print(f"Validation output: {envelope_val.get('output')}")
    
    # 2. Execute Promotion
    print("\n[STEP 2] Executing promotion to memory...")
    envelope_prom, rc_prom = run_gated_tool(
        client,
        "promote_ucf_to_memory",
        {"video_hash": VIDEO_HASH, "epoch_id": EPOCH_ID}
    )
    print(f"Promotion envelope status: {envelope_prom.get('status')}")
    print(f"Promotion output status: {envelope_prom.get('output', {}).get('status')}")
    print(f"Promoted count: {envelope_prom.get('output', {}).get('promoted_count')}")

if __name__ == "__main__":
    main()
