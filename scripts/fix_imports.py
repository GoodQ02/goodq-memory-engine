import re
import os
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]

files_to_fix = [
    repo_root / "pipelines" / "direct_ingestion.py",
    repo_root / "cli" / "test_ingestion.py",
    repo_root / "tests" / "test_ingestion.py",
    repo_root / "api" / "main.py",
    repo_root / "cli" / "run_ingestion.py",
    repo_root / "api" / "routes" / "search.py",
    repo_root / "api" / "routes" / "scenes.py",
    repo_root / "api" / "routes" / "timeline.py",
    repo_root / "api" / "routes" / "media.py",
    repo_root / "api" / "routes" / "system.py",
    repo_root / "retrieval" / "multimodal_search.py",
    repo_root / "steps" / "video" / "scene_visual_embeddings.py",
    repo_root / "steps" / "video" / "cross_modal_harmonizer.py",
]

# Pattern to replace
pattern = re.compile(r'^from goodq4all\.', re.MULTILINE)
replacement = 'from '

fixed_count = 0
for filepath in files_to_fix:
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"SKIP (not found): {filepath}")
        continue
    
    with filepath.open('r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = pattern.sub(replacement, content)
    
    if new_content != content:
        with filepath.open('w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"FIXED: {filepath}")
        fixed_count += 1
    else:
        print(f"OK (no changes needed): {filepath}")

print(f"\nTotal files fixed: {fixed_count}")
