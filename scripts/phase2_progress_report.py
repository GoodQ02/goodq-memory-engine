"""
Phase 2 Progress Report
Shows current state of embedding and knowledge graph integration
"""
import sqlite3
from datetime import datetime
from pathlib import Path

print("="*80)
print(f"PHASE 2 PROGRESS REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Memory DB Analysis
print("\n📊 MEMORY.DB STATUS")
print("-" * 80)

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
cur = conn.cursor()

# Total counts
cur.execute("SELECT COUNT(*) FROM embeddings")
total_emb = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM embeddings WHERE scene_id IS NOT NULL")
with_scene_id = cur.fetchone()[0]

cur.execute("SELECT COUNT(DISTINCT scene_id) FROM embeddings WHERE scene_id IS NOT NULL")
unique_scenes = cur.fetchone()[0]

print(f"✓ Total Embeddings: {total_emb}")
print(f"✓ With scene_id: {with_scene_id} ({with_scene_id/total_emb*100:.1f}%)")
print(f"✓ Unique Scenes Linked: {unique_scenes}")

# By modality
print("\nEmbeddings by Modality:")
cur.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
for row in cur.fetchall():
    print(f"  {row[0]:15s}: {row[1]:3d}")

# Scenes
cur.execute("SELECT COUNT(*) FROM scenes")
scene_count = cur.fetchone()[0]
print(f"\n✓ Total Scenes: {scene_count}")

# Links
cur.execute("SELECT COUNT(*) FROM links")
link_count = cur.fetchone()[0]
print(f"✓ Total Links: {link_count}")

cur.execute("SELECT relation, COUNT(*) FROM links GROUP BY relation")
print("\nLinks by Relation:")
for row in cur.fetchall():
    print(f"  {row[0]:20s}: {row[1]:3d}")

# Segments
cur.execute("SELECT COUNT(*) FROM segments")
segment_count = cur.fetchone()[0]
print(f"\n✓ Total Segments: {segment_count}")

conn.close()

# Knowledge Graph Analysis
print("\n" + "="*80)
print("🔗 KNOWLEDGE GRAPH STATUS")
print("-" * 80)

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/knowledge_graph.db')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM nodes")
node_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM edges")
edge_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM media_nodes")
media_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM node_media")
nm_count = cur.fetchone()[0]

print(f"Total Nodes: {node_count}")
print(f"Total Edges: {edge_count}")
print(f"Total Media Nodes: {media_count}")
print(f"Total Node-Media Links: {nm_count}")

if node_count > 0:
    print("\nNodes by Type:")
    cur.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
    for row in cur.fetchall():
        print(f"  {row[0]:15s}: {row[1]:3d}")

if edge_count > 0:
    print("\nEdges by Type:")
    cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
    for row in cur.fetchall():
        print(f"  {row[0]:20s}: {row[1]:3d}")

conn.close()

# FAISS Index Status
print("\n" + "="*80)
print("💾 FAISS INDEX STATUS")
print("-" * 80)

faiss_dir = Path("L:/_DATA/GoodQ_Data/faiss_indices")
indices = ['text', 'clip', 'dino', 'audio']

for idx_name in indices:
    idx_file = faiss_dir / idx_name / f"faiss_{idx_name}_index.bin"
    if idx_file.exists():
        size_mb = idx_file.stat().st_size / 1024 / 1024
        print(f"✓ {idx_name:10s}: {size_mb:6.2f} MB - {idx_file}")
    else:
        print(f"✗ {idx_name:10s}: MISSING")

# Overall Assessment
print("\n" + "="*80)
print("📈 PHASE 2 ASSESSMENT")
print("="*80)

fixes_working = []
issues_remaining = []

# Check 1: Scene ID linkage
if with_scene_id > 0:
    fixes_working.append(f"✓ Scene ID linkage working ({with_scene_id}/{total_emb} embeddings)")
else:
    issues_remaining.append("✗ Scene ID linkage not working")

# Check 2: Multiple modalities
modalities_found = set()
conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
cur = conn.cursor()
cur.execute("SELECT DISTINCT modality FROM embeddings")
for row in cur.fetchall():
    if row[0]:
        modalities_found.add(row[0])
conn.close()

if len(modalities_found) >= 3:
    fixes_working.append(f"✓ Multi-modal embeddings ({len(modalities_found)} modalities)")
else:
    issues_remaining.append(f"⚠ Limited modalities ({len(modalities_found)} found)")

# Check 3: Knowledge graph
if node_count > 0:
    fixes_working.append(f"✓ Knowledge graph populated ({node_count} nodes, {edge_count} edges)")
else:
    issues_remaining.append("⚠ Knowledge graph empty (may still be processing)")

# Check 4: FAISS indices
faiss_count = sum(1 for idx in indices if (faiss_dir / idx / f"faiss_{idx}_index.bin").exists())
if faiss_count >= 3:
    fixes_working.append(f"✓ FAISS indices created ({faiss_count}/{len(indices)})")
else:
    issues_remaining.append(f"⚠ Some FAISS indices missing ({faiss_count}/{len(indices)})")

print("\n✅ WORKING:")
for item in fixes_working:
    print(f"   {item}")

if issues_remaining:
    print("\n⚠️  REMAINING ISSUES:")
    for item in issues_remaining:
        print(f"   {item}")

print("\n" + "="*80)
expected_scenes = 16  # sample.mp4 has 16 scenes
if scene_count >= expected_scenes:
    print(f"✅ PROCESSING COMPLETE: {scene_count}/{expected_scenes} scenes processed")
else:
    print(f"⏳ PROCESSING IN PROGRESS: {scene_count}/{expected_scenes} scenes processed")
    print(f"   Estimated {(expected_scenes - scene_count) * 90} seconds remaining")
print("="*80)
