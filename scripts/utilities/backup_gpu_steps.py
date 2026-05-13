import os
import re

# Steps that need refactoring
STEPS_TO_REFACTOR = [
    "audio_diarize",
    "audio_embed_clap",
    "audio_emotion",
    "audio_transcribe",
    "emotion_classify",
    "face_embed",
    "image_caption",
    "image_embed_clip",
    "image_embed_dino",
    "object_detect",
    "sentiment",
    "text_embed"
]

# Backup and refactor each step
for step_name in STEPS_TO_REFACTOR:
    step_file = f"steps/{step_name}/step.py"
    backup_file = f"steps/{step_name}/step.py.backup_pre_gpu_refactor"
    
    print(f"\n{'='*80}")
    print(f"Processing: {step_name}")
    print(f"{'='*80}")
    
    if not os.path.exists(step_file):
        print(f"[FAIL] File not found: {step_file}")
        continue
    
    # Create backup
    with open(step_file, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(original_content)
    print(f"[OK] Backup created: {backup_file}")

print(f"\n{'='*80}")
print("[OK] All backups created successfully!")
print("Ready for manual refactoring")
print(f"{'='*80}")
