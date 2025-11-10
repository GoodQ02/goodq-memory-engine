import json
import sqlite3

conn = sqlite3.connect('data/memory.db')

# Get scene metadata from database
scene = conn.execute('SELECT id, meta FROM scenes WHERE id LIKE "4070c%"').fetchone()
if scene:
    scene_id, meta_json = scene
    meta = json.loads(meta_json)
    
    print(f'Scene ID: {scene_id}')
    print(f'\nMetadata keys: {list(meta.keys())}')
    print(f'\n{"="*70}')
    
    # Check key fields
    if 'transcript' in meta:
        print(f'Transcript in DB: "{meta["transcript"][:100]}"...')
    
    if 'sentiment_label' in meta:
        print(f'Sentiment: {meta["sentiment_label"]} ({meta.get("sentiment_score", "N/A")})')
    
    if 'speakers' in meta:
        print(f'Speakers: {meta["speakers"]}')
    
    if 'objects' in meta:
        print(f'Objects: {len(meta["objects"])} objects')
        for obj in meta["objects"][:3]:
            print(f'  - {obj.get("label", "?")} ({obj.get("score", 0):.2f})')
    
    if 'faces' in meta:
        print(f'Faces: {meta["faces"]}')
    
    if 'tags' in meta:
        print(f'Tags: {meta["tags"][:10]}')
    
    if 'entities' in meta:
        print(f'Entities: {meta["entities"][:5]}')

# Check segments
print(f'\n{"="*70}')
print('SEGMENTS:')
segments = conn.execute('SELECT id, speaker, meta FROM segments').fetchall()
for seg_id, speaker, meta_json in segments:
    meta = json.loads(meta_json) if meta_json else {}
    print(f'  {seg_id[:16]}... | Speaker: {speaker}')

conn.close()
