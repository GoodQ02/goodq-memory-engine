import re
import os
from pathlib import Path

files_to_fix = [
    r"L:\goodq4all\pipelines\direct_ingestion.py",
    r"L:\goodq4all\test_ingestion.py",
    r"L:\goodq4all\api\main.py",
    r"L:\goodq4all\cli\run_ingestion.py",
    r"L:\goodq4all\api\routes\search.py",
    r"L:\goodq4all\api\routes\scenes.py",
    r"L:\goodq4all\api\routes\timeline.py",
    r"L:\goodq4all\api\routes\media.py",
    r"L:\goodq4all\api\routes\system.py",
    r"L:\goodq4all\retrieval\multimodal_search.py",
    r"L:\goodq4all\steps\video\scene_visual_embeddings.py",
    r"L:\goodq4all\steps\video\cross_modal_harmonizer.py"
]

# Pattern to replace
pattern = re.compile(r'^from goodq4all\.', re.MULTILINE)
replacement = 'from '

fixed_count = 0
for filepath in files_to_fix:
    if not os.path.exists(filepath):
        print(f"SKIP (not found): {filepath}")
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = pattern.sub(replacement, content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"FIXED: {filepath}")
        fixed_count += 1
    else:
        print(f"OK (no changes needed): {filepath}")

print(f"\nTotal files fixed: {fixed_count}")
