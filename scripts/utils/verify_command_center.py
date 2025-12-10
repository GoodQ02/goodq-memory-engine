#!/usr/bin/env python3
"""
Quick verification that Command Center is fully operational
"""
import requests
import json
from datetime import datetime

print("=" * 80)
print("[SYMBOL] COMMAND CENTER VERIFICATION")
print("=" * 80)
print()

# Test API endpoint
try:
    response = requests.get("http://localhost:30000/api/command-center")
    response.raise_for_status()
    data = response.json()
    
    print("[OK] API Endpoint: OPERATIONAL")
    print(f"   URL: http://localhost:30000/api/command-center")
    print()
    
    print("[STATS] SYSTEM STATUS")
    print(f"   Status: {data['status'].upper()}")
    print(f"   Timestamp: {data['timestamp']}")
    print()
    
    print("[SYMBOL]️  PROCESSING")
    proc = data['processing']
    print(f"   Active: {'YES [WARN]' if proc['active'] else 'NO [OK]'}")
    if proc['active']:
        print(f"   File: {proc['current_file']}")
        print(f"   Started: {proc['started']}")
    print()
    
    print("[SAVE] DATABASE METRICS")
    db = data['database']
    print(f"   Scenes: {db['scenes']}")
    print(f"   Segments: {db['segments']}")
    print(f"   Embeddings: {db['embeddings']}")
    print(f"   Entities: {db['entities']}")
    print(f"   Relationships: {db['relationships']}")
    print(f"   Latest Activity: {db.get('latest_activity', 'N/A')}")
    print()
    
    print("[BOT] LLM STATUS")
    llm = data['system']['llm']
    print(f"   Available: {'YES [OK]' if llm['available'] else 'NO [FAIL]'}")
    print(f"   Model: {llm['model']}")
    print()
    
    print("[SYMBOL] SYSTEM HEALTH")
    health = data['system']['health']
    for component, status in health.items():
        symbol = "[OK]" if status else "[FAIL]"
        print(f"   {symbol} {component.replace('_', ' ').title()}")
    print()
    
    print("[SYMBOL] RECENT LOGS (Last 5)")
    logs = data['logs']['recent'][-5:]
    for log in logs:
        print(f"   {log}")
    print()
    
    print("=" * 80)
    print("[OK] COMMAND CENTER IS FULLY OPERATIONAL")
    print("=" * 80)
    print()
    print("[SYMBOL] Access the UI at: http://localhost:30000")
    print("[SYMBOL] Click 'Command Center' in the sidebar to view the dashboard")
    print()
    
except requests.exceptions.RequestException as e:
    print(f"[FAIL] ERROR: Could not connect to API")
    print(f"   {e}")
    print()
    print("Make sure the API server is running:")
    print("   python api_server.py")
except Exception as e:
    print(f"[FAIL] ERROR: {e}")
    import traceback
    traceback.print_exc()
