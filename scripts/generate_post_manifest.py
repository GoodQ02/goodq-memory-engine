import os
import sys
import socket
import datetime
import subprocess
import json
import urllib.request
import urllib.parse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path.cwd()))
try:
    from steps.common.config_loader import load_configs
except ModuleNotFoundError:
    from goodq4all.steps.common.config_loader import load_configs

config = load_configs({})
paths = config.get('paths', {})

db_path = Path(paths.get('db_path')) if paths.get('db_path') else None
kg_path = Path(paths.get('knowledge_graph_db')) if paths.get('knowledge_graph_db') else None
faiss_dir = Path(paths.get('faiss_dir')) if paths.get('faiss_dir') else None

# 1. Gather files status
memory_db_status = "absent"
if db_path and db_path.exists():
    try:
        memory_db_status = "present (empty)" if db_path.stat().st_size == 0 else f"present ({db_path.stat().st_size} bytes)"
    except Exception as e:
        memory_db_status = f"error checking: {e}"

kg_db_status = "absent"
if kg_path and kg_path.exists():
    try:
        kg_db_status = "present (empty)" if kg_path.stat().st_size == 0 else f"present ({kg_path.stat().st_size} bytes)"
    except Exception as e:
        kg_db_status = f"error checking: {e}"

# 2. Gather FAISS status
faiss_index_count = 0
faiss_id_map_count = 0
if faiss_dir and faiss_dir.exists():
    for root, _, files in os.walk(faiss_dir):
        for f in files:
            if f.endswith('.index'):
                faiss_index_count += 1
            elif f.endswith('.sqlite') or f.endswith('.db'):
                faiss_id_map_count += 1

# 3. Gather Git & Host info
try:
    git_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=str(Path.cwd())).decode().strip()
except Exception as e:
    git_commit = f"unknown: {e}"

hostname = socket.gethostname()
timestamp = datetime.datetime.utcnow().isoformat() + 'Z'

# 4. Gather Qdrant info
base = 'http://127.0.0.1:6333'
collections_report = []
try:
    collections_data = json.load(urllib.request.urlopen(base + '/collections', timeout=5))
    collections = collections_data['result']['collections']
    for col in sorted(collections, key=lambda c: c['name']):
        name = col['name']
        if not name.startswith('goodq_'):
            continue
        info = json.load(urllib.request.urlopen(base + '/collections/' + urllib.parse.quote(name, safe=''), timeout=5))['result']
        
        # Get vector dimensions
        vector_config = info.get('config', {}).get('params', {}).get('vectors', {})
        dim = vector_config.get('size') if isinstance(vector_config, dict) else None
        
        collections_report.append({
            'name': name,
            'vector_dimension': dim,
            'points_count': info.get('points_count'),
            'status': info.get('status')
        })
except Exception as e:
    print(f"Error querying Qdrant: {e}")

# 5. Build final payload
payload = {
    'kind': 'qdrant_post_cleanup_manifest',
    'timestamp': timestamp,
    'machine_hostname': hostname,
    'git_commit': git_commit,
    'active_epoch': config.get('paths', {}).get('db_dir'),
    'database_states': {
        'memory_db': memory_db_status,
        'knowledge_graph_db': kg_db_status
    },
    'faiss_states': {
        'faiss_index_count': faiss_index_count,
        'faiss_id_map_count': faiss_id_map_count
    },
    'qdrant_collections': collections_report
}

today_str = datetime.date.today().isoformat()
out_dir = Path(f'reports/local_housekeeping/{today_str}-memory-clean-start')
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / 'qdrant_post_cleanup_manifest.json'
out_file.write_text(json.dumps(payload, indent=2), encoding='utf-8')

print("\n=== POST-CLEANUP MANIFEST COMPILED ===")
print(json.dumps(payload, indent=2))
