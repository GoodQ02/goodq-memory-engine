import sys
import os
import glob
sys.path.insert(0, "L:/goodq4all")

from steps.common.config_loader import load_configs
from steps.image_embed_clip.step import image_embed_clip
import faiss

cfg = load_configs({})

# Find test images
image_dir = r"L:\_DATA\GoodQ_Data\completed\1987_1988_run1\1987_1988\frames"
images = glob.glob(os.path.join(image_dir, "scene_*.jpg"))[:5]  # Test first 5

print(f"Testing CLIP with {len(images)} images...")
print("="*60)

success_count = 0
for img_path in images:
    test_item = {"source_path": img_path, "modality": "image"}
    result = image_embed_clip(test_item, cfg)
    clip_meta = result.get("clip_meta", {})
    status = clip_meta.get("status")
    
    if status == "ok":
        success_count += 1
        print(f"✓ {os.path.basename(img_path)} -> FAISS ID: {clip_meta.get('faiss_id')}")
    else:
        print(f"✗ {os.path.basename(img_path)} -> Error: {clip_meta.get('error')}")

print("="*60)
print(f"\nResults: {success_count}/{len(images)} successful")

# Check final index
index_path = cfg.get("paths", {}).get("faiss_clip_path")
if os.path.exists(index_path):
    idx = faiss.read_index(index_path)
    print(f"✓ CLIP index created successfully")
    print(f"  Path: {index_path}")
    print(f"  Vectors: {idx.ntotal}")
    print(f"  Dimension: {idx.d}")
    print(f"  Size: {os.path.getsize(index_path)/1024:.2f} KB")
else:
    print(f"✗ Index not created")

# Check ID map
map_db = cfg.get("paths", {}).get("clip_id_map_db")
if os.path.exists(map_db):
    import sqlite3
    conn = sqlite3.connect(map_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM clip_id_map")
    count = cur.fetchone()[0]
    print(f"✓ ID map database created")
    print(f"  Path: {map_db}")
    print(f"  Entries: {count}")
    conn.close()
else:
    print(f"✗ ID map not created")
