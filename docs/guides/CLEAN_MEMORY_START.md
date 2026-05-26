# Clean Memory Start Guide

Use this guide when you want to start a fresh memory run (e.g. after a testing phase) by clearing historical Qdrant vector database collections and resetting local relational database memory, without completely reinstalling the system.

## 1. Delete Historical Qdrant Collections

To delete all Qdrant vector collections that begin with `goodq_`, run this script from the repository root:

```powershell
python -c "
import json, urllib.request, urllib.parse
base='http://127.0.0.1:6333'
try:
    collections=json.load(urllib.request.urlopen(base + '/collections', timeout=5))['result']['collections']
    deleted=[]
    for col in collections:
        name=col['name']
        if name.startswith('goodq_'):
            req=urllib.request.Request(base + '/collections/' + urllib.parse.quote(name, safe=''), method='DELETE')
            with urllib.request.urlopen(req, timeout=15) as resp:
                deleted.append(name)
    print(f'Deleted collections: {deleted}')
except Exception as e:
    print(f'Qdrant cleanup skipped or failed: {e}')
"
```

## 2. Initialize Fresh Empty Collections

Recreate the empty collections required by the pipeline:

```powershell
conda run --no-capture-output -n goodq_core python scripts/init_qdrant_collections.py
```

## 3. Reset Relational Memory Databases

Delete the SQLite and Knowledge Graph database files from your data root (default is `%USERPROFILE%\GoodQ_Data\db\`). They will be recreated empty when the pipeline starts next:

```powershell
Remove-Item -Path \"$env:USERPROFILE\GoodQ_Data\db\*.db\" -Force -ErrorAction SilentlyContinue
```
*(If you have configured a custom `GOODQ_DATA_ROOT` in `.env.local`, delete the databases under `<GOODQ_DATA_ROOT>\db\` instead).*
