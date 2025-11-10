import sqlite3
import json
from pathlib import Path

# Connect to database
conn = sqlite3.connect('data/memory.db')
cursor = conn.cursor()

print("=" * 80)
print("DATABASE STRUCTURE")
print("=" * 80)

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print(f"\nTables found: {len(tables)}")
for table in tables:
    print(f"  - {table}")

print("\n" + "=" * 80)
print("SAMPLE.MP4 PROCESSING ANALYSIS")
print("=" * 80)

# Check for sample.mp4 in various tables
sample_file = 'sample.mp4'

# Check files table
print("\n--- FILES TABLE ---")
cursor.execute("SELECT * FROM files WHERE filename LIKE '%sample%' ORDER BY created_at DESC LIMIT 5")
files = cursor.fetchall()
if files:
    cursor.execute("PRAGMA table_info(files)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Columns: {columns}")
    for file in files:
        print(f"\nFile record:")
        for i, col in enumerate(columns):
            value = file[i]
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"  {col}: {value}")
else:
    print("No sample files found in files table")

# Check scenes
print("\n--- SCENES TABLE ---")
cursor.execute("""
    SELECT COUNT(*) as scene_count 
    FROM scenes s
    JOIN files f ON s.file_id = f.id
    WHERE f.filename LIKE '%sample%'
""")
result = cursor.fetchone()
print(f"Scenes detected for sample.mp4: {result[0] if result else 0}")

if result and result[0] > 0:
    cursor.execute("""
        SELECT s.scene_id, s.start_time, s.end_time, s.description
        FROM scenes s
        JOIN files f ON s.file_id = f.id
        WHERE f.filename LIKE '%sample%'
        ORDER BY s.start_time
        LIMIT 5
    """)
    scenes = cursor.fetchall()
    print(f"\nFirst 5 scenes:")
    for scene in scenes:
        print(f"  Scene {scene[0]}: {scene[1]:.2f}s - {scene[2]:.2f}s | {scene[3]}")

# Check frames
print("\n--- FRAMES TABLE ---")
cursor.execute("""
    SELECT COUNT(*) as frame_count 
    FROM frames fr
    JOIN files f ON fr.file_id = f.id
    WHERE f.filename LIKE '%sample%'
""")
result = cursor.fetchone()
print(f"Frames extracted for sample.mp4: {result[0] if result else 0}")

if result and result[0] > 0:
    cursor.execute("""
        SELECT fr.frame_number, fr.timestamp, fr.caption, fr.objects_detected
        FROM frames fr
        JOIN files f ON fr.file_id = f.id
        WHERE f.filename LIKE '%sample%'
        ORDER BY fr.frame_number
        LIMIT 5
    """)
    frames = cursor.fetchall()
    print(f"\nFirst 5 frames:")
    for frame in frames:
        caption = frame[2][:80] + "..." if frame[2] and len(frame[2]) > 80 else frame[2]
        print(f"  Frame {frame[0]} @ {frame[1]:.2f}s")
        print(f"    Caption: {caption}")
        print(f"    Objects: {frame[3]}")

# Check transcripts
print("\n--- TRANSCRIPTS TABLE ---")
cursor.execute("""
    SELECT COUNT(*) as segment_count, SUM(LENGTH(text)) as total_text_length
    FROM transcripts t
    JOIN files f ON t.file_id = f.id
    WHERE f.filename LIKE '%sample%'
""")
result = cursor.fetchone()
print(f"Transcript segments for sample.mp4: {result[0] if result else 0}")
print(f"Total text length: {result[1] if result and result[1] else 0} characters")

if result and result[0] > 0:
    cursor.execute("""
        SELECT t.start_time, t.end_time, t.speaker, t.text
        FROM transcripts t
        JOIN files f ON t.file_id = f.id
        WHERE f.filename LIKE '%sample%'
        ORDER BY t.start_time
        LIMIT 10
    """)
    transcripts = cursor.fetchall()
    print(f"\nFirst 10 transcript segments:")
    for trans in transcripts:
        text = trans[3][:100] + "..." if len(trans[3]) > 100 else trans[3]
        speaker = trans[2] if trans[2] else "Unknown"
        print(f"  [{trans[0]:.2f}s - {trans[1]:.2f}s] {speaker}: {text}")

# Check faces
print("\n--- FACES TABLE ---")
cursor.execute("""
    SELECT COUNT(DISTINCT person_id) as unique_people, COUNT(*) as total_detections
    FROM faces fc
    JOIN frames fr ON fc.frame_id = fr.id
    JOIN files f ON fr.file_id = f.id
    WHERE f.filename LIKE '%sample%'
""")
result = cursor.fetchone()
print(f"Unique people detected: {result[0] if result else 0}")
print(f"Total face detections: {result[1] if result else 0}")

if result and result[0] > 0:
    cursor.execute("""
        SELECT fc.person_id, COUNT(*) as appearances, fc.confidence
        FROM faces fc
        JOIN frames fr ON fc.frame_id = fr.id
        JOIN files f ON fr.file_id = f.id
        WHERE f.filename LIKE '%sample%'
        GROUP BY fc.person_id
        ORDER BY appearances DESC
    """)
    faces = cursor.fetchall()
    print(f"\nPeople appearances:")
    for face in faces:
        print(f"  Person {face[0]}: {face[1]} appearances (confidence: {face[2]:.2f})")

# Check embeddings
print("\n--- EMBEDDINGS TABLE ---")
cursor.execute("""
    SELECT embedding_type, COUNT(*) as count
    FROM embeddings e
    JOIN files f ON e.file_id = f.id
    WHERE f.filename LIKE '%sample%'
    GROUP BY embedding_type
""")
embeddings = cursor.fetchall()
if embeddings:
    print("Embeddings generated:")
    for emb in embeddings:
        print(f"  {emb[0]}: {emb[1]} embeddings")
else:
    print("No embeddings found")

# Check entities
print("\n--- ENTITIES TABLE ---")
cursor.execute("""
    SELECT entity_type, COUNT(*) as count
    FROM entities ent
    JOIN files f ON ent.file_id = f.id
    WHERE f.filename LIKE '%sample%'
    GROUP BY entity_type
""")
entities = cursor.fetchall()
if entities:
    print("Entities extracted:")
    for ent in entities:
        print(f"  {ent[0]}: {ent[1]} entities")
else:
    print("No entities found")

# Check knowledge graph
print("\n--- KNOWLEDGE GRAPH TABLE ---")
cursor.execute("""
    SELECT COUNT(*) as triplet_count
    FROM knowledge_graph kg
    JOIN files f ON kg.file_id = f.id
    WHERE f.filename LIKE '%sample%'
""")
result = cursor.fetchone()
print(f"Knowledge graph triplets: {result[0] if result else 0}")

if result and result[0] > 0:
    cursor.execute("""
        SELECT kg.subject, kg.predicate, kg.object, kg.confidence
        FROM knowledge_graph kg
        JOIN files f ON kg.file_id = f.id
        WHERE f.filename LIKE '%sample%'
        ORDER BY kg.confidence DESC
        LIMIT 10
    """)
    triplets = cursor.fetchall()
    print(f"\nTop 10 knowledge triplets:")
    for triplet in triplets:
        print(f"  {triplet[0]} --[{triplet[1]}]--> {triplet[2]} (conf: {triplet[3]:.2f})")

# Check emotions
print("\n--- EMOTIONS TABLE ---")
cursor.execute("""
    SELECT emotion, AVG(confidence) as avg_conf, COUNT(*) as count
    FROM emotions em
    JOIN frames fr ON em.frame_id = fr.id
    JOIN files f ON fr.file_id = f.id
    WHERE f.filename LIKE '%sample%'
    GROUP BY emotion
    ORDER BY count DESC
""")
emotions = cursor.fetchall()
if emotions:
    print("Emotions detected:")
    for emotion in emotions:
        print(f"  {emotion[0]}: {emotion[2]} occurrences (avg confidence: {emotion[1]:.2f})")
else:
    print("No emotions detected")

# Check metadata
print("\n--- METADATA TABLE ---")
cursor.execute("""
    SELECT meta_key, meta_value
    FROM metadata m
    JOIN files f ON m.file_id = f.id
    WHERE f.filename LIKE '%sample%'
""")
metadata = cursor.fetchall()
if metadata:
    print("Metadata extracted:")
    for meta in metadata:
        value = meta[1][:100] + "..." if len(str(meta[1])) > 100 else meta[1]
        print(f"  {meta[0]}: {value}")
else:
    print("No metadata found")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

# Get file status
cursor.execute("""
    SELECT id, filename, status, error_message, processing_time, created_at, updated_at
    FROM files 
    WHERE filename LIKE '%sample%'
    ORDER BY created_at DESC
    LIMIT 1
""")
file_info = cursor.fetchone()
if file_info:
    print(f"\nFile ID: {file_info[0]}")
    print(f"Filename: {file_info[1]}")
    print(f"Status: {file_info[2]}")
    print(f"Error: {file_info[3] if file_info[3] else 'None'}")
    print(f"Processing time: {file_info[4]:.2f}s" if file_info[4] else "N/A")
    print(f"Created: {file_info[5]}")
    print(f"Updated: {file_info[6]}")
else:
    print("\nNo file record found for sample.mp4")

conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
