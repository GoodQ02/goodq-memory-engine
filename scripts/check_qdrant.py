#!/usr/bin/env python3
import sqlite3
import json
import uuid
import requests
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def main():
    db_path = Path("L:/_DATA/GoodQ_Data/epochs/epoch_2026_06_16_r0_smoke/ucf/ucf_ledger.db")
    if not db_path.exists():
        print(f"Error: UCF ledger database not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT vector_key, vector_collection, modality, worker_name "
        "FROM context_frames "
        "WHERE vector_backend = 'qdrant' AND promotion_status = 'promoted' AND vector_key IS NOT NULL "
        "LIMIT 5"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No promoted Qdrant frames found in ledger!")
        return

    print("Found promoted frames with vector keys:")
    for row in rows:
        print(f"  - Key: {row[0]}, Collection: {row[1]}, Modality: {row[2]}, Worker: {row[3]}")

    # Query Qdrant for the first point
    vector_key, vector_collection, modality, worker = rows[0]
    
    # Normalize ID matching mini_agent_client
    GOODQ_POINT_ID_NAMESPACE = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")
    s = vector_key.strip()
    hex_candidate = s.replace("-", "")
    if len(hex_candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in hex_candidate):
        qdrant_id = str(uuid.UUID(hex_candidate))
    elif s.isdigit():
        qdrant_id = s
    else:
        qdrant_id = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))

    qdrant_host = "http://127.0.0.1:6333"
    url = f"{qdrant_host}/collections/{vector_collection}/points/{qdrant_id}"
    print(f"\nQuerying Qdrant REST API: GET {url}")
    
    try:
        resp = requests.get(url, timeout=5)
        print(f"HTTP Status: {resp.status_code}")
        if resp.status_code == 200:
            result = resp.json().get("result", {})
            payload = result.get("payload", {})
            print("Point Payload:")
            print(json.dumps(payload, indent=2))
            assert payload.get("ucf_promotion_status") == "promoted", \
                f"Expected ucf_promotion_status to be 'promoted', got: {payload.get('ucf_promotion_status')}"
            print("\nVerification SUCCESS: ucf_promotion_status is 'promoted'.")
        else:
            print(f"Error payload: {resp.text}")
    except Exception as e:
        print(f"Failed to query Qdrant: {e}")

if __name__ == "__main__":
    main()
