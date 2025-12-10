#!/usr/bin/env python3
"""
Fix Validation Issues Script
Automatically resolves issues found in step validation
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

FIXES = {
    "face_recognition_missing": {
        "description": "Install face_recognition in goodq_face_embed environment",
        "env": "goodq_face_embed",
        "commands": [
            "conda install -n goodq_face_embed -c conda-forge dlib -y",
            "conda run -n goodq_face_embed pip install face_recognition --no-cache-dir"
        ]
    },
    "pytesseract_missing": {
        "description": "Install pytesseract in goodq_ocr environment",
        "env": "goodq_ocr",
        "commands": [
            "conda run -n goodq_ocr pip install pytesseract pillow --no-cache-dir"
        ]
    },
    "audio_embed_cuda": {
        "description": "Reinstall PyTorch with CUDA in goodq_audio_embed",
        "env": "goodq_audio_embed",
        "commands": [
            "conda run -n goodq_audio_embed pip uninstall torch torchvision torchaudio -y",
            "conda run -n goodq_audio_embed pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir"
        ]
    },
    "audio_diarize_pyannote": {
        "description": "Install pyannote.audio in goodq_audio_diarize",
        "env": "goodq_audio_diarize",
        "commands": [
            "conda run -n goodq_audio_diarize pip install pyannote.audio --no-cache-dir"
        ]
    },
    "audio_transcribe_missing": {
        "description": "Ensure soundfile/librosa in goodq_audio_transcribe",
        "env": "goodq_audio_transcribe",
        "commands": [
            "conda run -n goodq_audio_transcribe pip install soundfile librosa --no-cache-dir"
        ]
    }
}

def run_fix(fix_name: str, fix_config: dict) -> bool:
    """Execute a fix"""
    print(f"\n{'='*80}")
    print(f"Applying Fix: {fix_name}")
    print(f"Description: {fix_config['description']}")
    print(f"Environment: {fix_config['env']}")
    print(f"{'='*80}")
    
    for i, cmd in enumerate(fix_config['commands'], 1):
        print(f"\n[{i}/{len(fix_config['commands'])}] Running: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                print(f"  [OK] Success")
            else:
                print(f"  [WARN] Warning: exit code {result.returncode}")
                if result.stderr:
                    print(f"  Error output: {result.stderr[:500]}")
        except Exception as e:
            print(f"  [FAIL] Failed: {e}")
            return False
    
    return True

def main():
    print("\n" + "="*80)
    print("GOODQ4ALL VALIDATION ISSUE FIX SCRIPT")
    print("="*80)
    print(f"\nTotal Fixes Available: {len(FIXES)}")
    
    print("\n\nSelect fixes to apply:")
    print("  [1] face_recognition_missing - Install face_recognition")
    print("  [2] pytesseract_missing - Install pytesseract")
    print("  [3] audio_embed_cuda - Fix CUDA in audio_embed")
    print("  [4] audio_diarize_pyannote - Install pyannote.audio")
    print("  [5] audio_transcribe_missing - Install audio libraries")
    print("  [A] Apply all fixes")
    print("  [Q] Quit")
    
    choice = input("\nEnter selection: ").strip().upper()
    
    if choice == 'Q':
        print("Exiting...")
        return
    
    if choice == 'A':
        for fix_name, fix_config in FIXES.items():
            run_fix(fix_name, fix_config)
    else:
        fix_map = {
            '1': 'face_recognition_missing',
            '2': 'pytesseract_missing',
            '3': 'audio_embed_cuda',
            '4': 'audio_diarize_pyannote',
            '5': 'audio_transcribe_missing'
        }
        if choice in fix_map:
            fix_name = fix_map[choice]
            run_fix(fix_name, FIXES[fix_name])
        else:
            print(f"Invalid choice: {choice}")
    
    print("\n" + "="*80)
    print("Fix application complete!")
    print("Run 'python scripts/validate_all_steps.py' to re-validate")
    print("="*80)

if __name__ == "__main__":
    main()
