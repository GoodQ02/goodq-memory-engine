#!/usr/bin/env python3
"""
Check that all step functions actually call models, not just return mock data
"""
import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Set

REPO_ROOT = Path(__file__).resolve().parents[1]

def check_function_calls_models(filepath: Path, function_name: str) -> Dict[str, Any]:
    """Check if a function actually loads and uses models"""
    issues = []
    has_model_loading = False
    has_model_inference = False
    
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content, filename=str(filepath))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                # Check for model loading patterns
                code = ast.unparse(node) if hasattr(ast, 'unparse') else ''
                
                # Model loading indicators
                if any(pattern in code for pattern in [
                    'from_pretrained',
                    'WhisperModel',
                    'BlipProcessor',
                    'pipeline(',
                    'YOLO(',
                    'load_model',
                    '.load(',
                ]):
                    has_model_loading = True
                
                # Inference indicators
                if any(pattern in code for pattern in [
                    '.generate(',
                    '.predict(',
                    '.transcribe(',
                    '.encode(',
                    '.forward(',
                    '.process(',
                ]):
                    has_model_inference = True
                
                # Check for trivial returns
                if 'return {}' in code or 'return None' in code:
                    # Only flag if it's the ONLY return
                    returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
                    if len(returns) == 1:
                        issues.append('Single trivial return statement')
                
    except Exception as e:
        issues.append(f'Parse error: {e}')
    
    return {
        'file': str(filepath.relative_to(REPO_ROOT)),
        'function': function_name,
        'has_model_loading': has_model_loading,
        'has_model_inference': has_model_inference,
        'issues': issues
    }

def main():
    print("=" * 80)
    print("CHECKING STEP IMPLEMENTATIONS FOR ACTUAL MODEL USAGE")
    print("=" * 80)
    
    # Key step functions to check
    steps_to_check = [
        ('steps/audio_transcribe/step.py', 'audio_transcribe'),
        ('steps/image_caption/step.py', 'image_caption'),
        ('steps/image_ocr/step.py', 'image_ocr'),
        ('steps/object_detect/step.py', 'object_detect'),
        ('steps/face_embed/step.py', 'face_embed'),
        ('steps/text_embed/step.py', 'text_embed'),
        ('steps/sentiment/step.py', 'sentiment'),
        ('steps/emotion_classify/step.py', 'emotion_classify'),
        ('steps/audio_diarize/step.py', 'audio_diarize'),
        ('steps/audio_emotion/step.py', 'audio_emotion'),
        ('steps/tagger/step.py', 'tagger'),
    ]
    
    results = []
    concerns = []
    
    for step_path, func_name in steps_to_check:
        filepath = REPO_ROOT / step_path
        if not filepath.exists():
            concerns.append(f"{step_path}: FILE NOT FOUND")
            continue
        
        result = check_function_calls_models(filepath, func_name)
        results.append(result)
        
        # Flag potential issues
        if not result['has_model_loading'] and not result['has_model_inference']:
            concerns.append(f"{step_path}::{func_name}: No model loading or inference detected")
        elif result['has_model_loading'] and not result['has_model_inference']:
            concerns.append(f"{step_path}::{func_name}: Model loaded but no inference detected")
    
    # Report
    print("\n" + "=" * 80)
    print(f"CHECKED {len(results)} STEP FUNCTIONS")
    print("=" * 80)
    
    if concerns:
        print(f"\n⚠️  FOUND {len(concerns)} POTENTIAL ISSUES:\n")
        for concern in concerns:
            print(f"  • {concern}")
    else:
        print("\n✓ All checked steps appear to have proper model implementations!")
    
    # Detailed report
    print("\n" + "=" * 80)
    print("DETAILED REPORT")
    print("=" * 80)
    
    for result in results:
        status = "✓" if result['has_model_loading'] and result['has_model_inference'] else "⚠"
        print(f"\n{status} {result['function']}")
        print(f"  File: {result['file']}")
        print(f"  Model loading: {'Yes' if result['has_model_loading'] else 'No'}")
        print(f"  Model inference: {'Yes' if result['has_model_inference'] else 'No'}")
        if result['issues']:
            print(f"  Issues: {', '.join(result['issues'])}")

if __name__ == '__main__':
    main()
