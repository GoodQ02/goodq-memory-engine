import json

d = json.load(open('logs/test_debug.json'))
print(f'Total videos: {len(d)}')
print(f'Total scenes: {len(d[0]["scenes"])}')

for i, scene in enumerate(d[0]['scenes']):
    print(f'\n{"="*70}')
    print(f'SCENE {i}: {scene["start"]}-{scene["end"]}s')
    print(f'{"="*70}')
    
    # Keyframe data
    if 'keyframe' in scene:
        kf = scene['keyframe']
        print(f'\nKEYFRAME:')
        print(f'  Caption: {kf.get("caption", "N/A")}')
        print(f'  OCR: {kf.get("ocr_text", "N/A")}')
        print(f'  Objects: {kf.get("object_count", 0)} detected')
        print(f'  Faces: {kf.get("face_count", 0)} detected')
        print(f'  Tags: {kf.get("tags", [])[:5]}')
    
    # Audio data
    if 'audio' in scene:
        audio = scene['audio']
        print(f'\nAUDIO:')
        trans = audio.get('transcript', 'N/A')
        print(f'  Transcript ({len(trans) if trans != "N/A" else 0} chars):')
        print(f'    "{trans[:200]}"...')
        print(f'  Speakers: {audio.get("speakers", "N/A")}')
        print(f'  Sentiment: {audio.get("sentiment_label", "N/A")} ({audio.get("sentiment_score", "N/A")})')
        
        tags = audio.get('tags', [])
        if tags:
            print(f'  Tags ({len(tags)}): {tags[:10]}')
        
        entities = audio.get('entities', [])
        if entities:
            print(f'  Entities ({len(entities)}): {entities[:5]}')
