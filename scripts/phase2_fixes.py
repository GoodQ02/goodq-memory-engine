"""
Phase 2 Comprehensive Fixes: Embedding & Knowledge Graph Integration

This script fixes all the embedding and knowledge graph issues identified:
1. Fix scene_id parameter propagation in all embedding steps
2. Fix knowledge graph builder to extract all entity types
3. Ensure proper linking between embeddings and knowledge graph
4. Fix FAISS index paths configuration
"""
import sys
from pathlib import Path

print("="*80)
print("PHASE 2: FIXING EMBEDDING & KNOWLEDGE GRAPH INTEGRATION")
print("="*80)

# Issue 1: Fix scene_id propagation in embedding steps
print("\n[1/6] Fixing scene_id propagation in text_embed step...")

text_embed_file = Path("L:/goodq4all/steps/text_embed/step.py")
content = text_embed_file.read_text()

# The text_embed step needs to extract scene_id from item and pass it to upsert_embedding
old_code = '''        # persist mapping for recall/linking
        try:
            upsert_embedding(cfg, _content_fingerprint(item), (ids or [None])[0], item.get("source_path", ""), item.get("modality", ""))
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 120: {str(e)}')
            pass'''

new_code = '''        # persist mapping for recall/linking
        try:
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, _content_fingerprint(item), (ids or [None])[0], item.get("source_path", ""), item.get("modality", ""), scene_id=scene_id)
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 120: {str(e)}')
            pass'''

if old_code in content:
    content = content.replace(old_code, new_code)
    text_embed_file.write_text(content)
    print("  [SYMBOL] Fixed text_embed step")
else:
    print("  [SYMBOL] text_embed already updated or pattern not found")

# Issue 2: Fix scene_id in image_embed_clip
print("\n[2/6] Fixing scene_id propagation in image_embed_clip step...")

clip_file = Path("L:/goodq4all/steps/image_embed_clip/step.py")
content = clip_file.read_text()

old_code = '''        try:
            from goodq4all.steps.common.memory import upsert_embedding
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "image") or "image")
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 96: {str(e)}')
            pass'''

new_code = '''        try:
            from goodq4all.steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "image") or "image", scene_id=scene_id)
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 96: {str(e)}')
            pass'''

if old_code in content:
    content = content.replace(old_code, new_code)
    clip_file.write_text(content)
    print("  [SYMBOL] Fixed image_embed_clip step")
else:
    print("  [SYMBOL] image_embed_clip already updated or pattern not found")

# Issue 3: Fix scene_id in audio_embed_clap
print("\n[3/6] Fixing scene_id propagation in audio_embed_clap step...")

clap_file = Path("L:/goodq4all/steps/audio_embed_clap/step.py")
content = clap_file.read_text()

old_code = '''        try:
            from goodq4all.steps.common.memory import upsert_embedding
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "audio") or "audio")
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 124: {str(e)}')
            pass'''

new_code = '''        try:
            from goodq4all.steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "audio") or "audio", scene_id=scene_id)
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 124: {str(e)}')
            pass'''

if old_code in content:
    content = content.replace(old_code, new_code)
    clap_file.write_text(content)
    print("  [SYMBOL] Fixed audio_embed_clap step")
else:
    print("  [SYMBOL] audio_embed_clap already updated or pattern not found")

# Issue 4: Check/fix image_embed_dino as well
print("\n[4/6] Checking image_embed_dino step...")

dino_file = Path("L:/goodq4all/steps/image_embed_dino/step.py")
if dino_file.exists():
    content = dino_file.read_text()
    
    # Check if it has upsert_embedding call
    if 'upsert_embedding' in content and 'scene_id' not in content:
        print("  [SYMBOL] DINO step needs scene_id fix - attempting to fix...")
        
        # Find and fix the upsert_embedding call
        import re
        pattern = r'upsert_embedding\(cfg,\s*h,\s*faiss_id,\s*path,\s*item\.get\("modality",\s*"[^"]+"\)[^)]*\)'
        
        def replacer(match):
            original = match.group(0)
            # Add scene_id parameter before the closing paren
            if 'scene_id' not in original:
                # Insert scene_id extraction before the call
                return original.replace(
                    'upsert_embedding(cfg, h, faiss_id, path,',
                    '''scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path,'''
                ).replace('or "image")', 'or "image", scene_id=scene_id)')
            return original
        
        new_content = re.sub(pattern, replacer, content)
        if new_content != content:
            dino_file.write_text(new_content)
            print("  [SYMBOL] Fixed image_embed_dino step")
        else:
            print("  [SYMBOL] Could not auto-fix DINO - manual review needed")
    elif 'scene_id' in content:
        print("  [SYMBOL] DINO step already has scene_id support")
    else:
        print("  ℹ DINO step doesn't use upsert_embedding")
else:
    print("  ℹ image_embed_dino step not found")

# Issue 5: Fix knowledge graph builder to extract more entity types
print("\n[5/6] Enhancing knowledge graph builder...")

kg_builder = Path("L:/goodq4all/steps/graph_builder/graph_builder.py")
content = kg_builder.read_text()

# Check if _process_objects handles all detection types
if 'detections = scene.get(\'detections\'' in content:
    # It exists, let's check if it handles 'objects' field too
    if 'objects = scene.get(\'objects\'' not in content:
        print("  Adding support for 'objects' field in graph builder...")
        
        # Find the _process_objects function and enhance it
        old_func = '''def _process_objects(kg, scene: Dict, media_id: int, timestamp: float):
    """Extract and add object entities"""
    detections = scene.get('detections', [])'''

        new_func = '''def _process_objects(kg, scene: Dict, media_id: int, timestamp: float):
    """Extract and add object entities"""
    # Handle both 'detections' and 'objects' fields
    detections = scene.get('detections', []) or scene.get('objects', [])'''
        
        if old_func in content:
            content = content.replace(old_func, new_func)
            kg_builder.write_text(content)
            print("  [SYMBOL] Enhanced graph builder to handle 'objects' field")
        else:
            print("  [SYMBOL] Could not find exact pattern - manual review needed")
    else:
        print("  [SYMBOL] Graph builder already handles 'objects' field")
else:
    print("  [SYMBOL] Graph builder structure different than expected")

# Issue 6: Verify FAISS index configuration in config.yaml
print("\n[6/6] Verifying FAISS index paths in configuration...")

config_file = Path("L:/goodq4all/config.yaml")
if config_file.exists():
    import yaml
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    # Check if paths section exists
    if 'paths' not in config:
        config['paths'] = {}
    
    paths_updated = False
    expected_paths = {
        'db_path': 'L:/_DATA/GoodQ_Data/memory.db',
        'faiss_index_path': 'L:/_DATA/GoodQ_Data/faiss_indices/text/faiss_text_index.bin',
        'faiss_clip_path': 'L:/_DATA/GoodQ_Data/faiss_indices/clip/faiss_clip_index.bin',
        'faiss_dino_path': 'L:/_DATA/GoodQ_Data/faiss_indices/dino/faiss_dino_index.bin',
        'faiss_audio_path': 'L:/_DATA/GoodQ_Data/faiss_indices/audio/faiss_audio_index.bin',
        'clip_id_map_db': 'L:/_DATA/GoodQ_Data/databases/clip_id_map.sqlite',
        'dino_id_map_db': 'L:/_DATA/GoodQ_Data/databases/dino_id_map.sqlite',
        'clap_id_map_db': 'L:/_DATA/GoodQ_Data/databases/clap_id_map.sqlite',
    }
    
    for key, expected_path in expected_paths.items():
        if key not in config['paths'] or config['paths'][key] != expected_path:
            config['paths'][key] = expected_path
            paths_updated = True
            print(f"  Updated: {key}")
    
    if paths_updated:
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print("  [SYMBOL] Configuration updated")
    else:
        print("  [SYMBOL] Configuration already correct")
else:
    print("  [SYMBOL] config.yaml not found")

print("\n" + "="*80)
print("PHASE 2 FIXES COMPLETE!")
print("="*80)
print("\nNext steps:")
print("1. Re-run sample.mp4 ingestion to generate embeddings with scene_id")
print("2. Knowledge graph will auto-populate with proper entity extraction")
print("3. Verify embeddings are linked to scenes in memory.db")
print("4. Check knowledge graph has all entity types (person, object, etc.)")
