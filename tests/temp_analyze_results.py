import json

data = json.load(open('logs/test_debug.json'))
print('=== RESULTS STRUCTURE ===')
print(f'Keys: {list(data.keys())}')
print(f'Videos count: {len(data)}')
print(f'First video: {list(data.keys())[0]}')
vdata = data[list(data.keys())[0]]
print(f'Video keys: {list(vdata.keys())}')
print(f'Scenes: {len(vdata.get("scenes", []))}')
if vdata.get('scenes'):
    scene = vdata['scenes'][0]
    print(f'\nScene 0 keys: {list(scene.keys())}')
    if 'keyframe' in scene:
        print(f'Keyframe keys: {list(scene["keyframe"].keys())}')
    if 'audio' in scene:
        audio = scene['audio']
        print(f'Audio keys: {list(audio.keys())}')
        if 'transcript' in audio:
            trans = audio['transcript']
            print(f'\nTranscript ({len(trans)} chars): {trans[:300]}...')
        if 'sentiment_label' in audio:
            print(f'Sentiment: {audio["sentiment_label"]} ({audio.get("sentiment_score", "N/A")})')
        if 'tags' in audio:
            print(f'Tags: {audio["tags"][:10]}')
        if 'entities' in audio:
            print(f'Entities: {audio["entities"][:5]}')
