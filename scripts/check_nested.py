#!/usr/bin/env python3
import sqlite3, json

conn = sqlite3.connect('data/memory.db')
conn.row_factory = sqlite3.Row

# Get a scene with faces
scene = dict(conn.execute("SELECT * FROM scenes LIMIT 5").fetchall()[1])
meta = json.loads(scene.get('meta', '{}'))

print("CHECKING NESTED STRUCTURE:")
print(f"\nkeyframe field exists: {'keyframe' in meta}")
print(f"audio field exists: {'audio' in meta}")

if 'keyframe' in meta:
    kf = meta['keyframe']
    print(f"\nkeyframe type: {type(kf)}")
    if isinstance(kf, dict):
        print(f"keyframe keys: {list(kf.keys())}")
        print(f"  has faces: {'faces' in kf}")
        print(f"  has objects: {'objects' in kf}")
        print(f"  has caption: {'caption' in kf}")

if 'audio' in meta:
    audio = meta['audio']
    print(f"\naudio type: {type(audio)}")
    if isinstance(audio, dict):
        print(f"audio keys: {list(audio.keys())}")
        print(f"  has sentiment: {'sentiment' in audio}")
        print(f"  has emotions: {'emotions' in audio}")
        print(f"  has speaker_transcript: {'speaker_transcript' in audio}")
        if 'sentiment' in audio:
            print(f"  sentiment value: {audio['sentiment']}")

print(f"\nTop-level has faces: {'faces' in meta}")
print(f"Top-level has face_count: {'face_count' in meta}")
if 'faces' in meta:
    print(f"  faces value: {meta['faces']}")
if 'face_count' in meta:
    print(f"  face_count: {meta['face_count']}")

print(f"\nTop-level has speaker_transcript: {'speaker_transcript' in meta}")
if 'speaker_transcript' in meta:
    st = meta['speaker_transcript']
    print(f"  speaker_transcript count: {len(st)}")
    if st:
        print(f"  first segment: {st[0]}")

conn.close()
