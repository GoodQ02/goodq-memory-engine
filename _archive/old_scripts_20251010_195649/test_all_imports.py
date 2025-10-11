#!/usr/bin/env python3
"""
Test all Python modules can be imported without errors
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

def test_imports():
    """Test critical imports"""
    errors = []
    
    print("=" * 80)
    print("TESTING ALL MODULE IMPORTS")
    print("=" * 80)
    
    # Core modules
    tests = [
        # Pipelines
        ("Pipeline: ingest_multimodal_conda", "pipelines.ingest_multimodal_conda"),
        
        # Library modules
        ("Library: knowledge_graph", "lib.knowledge_graph"),
        ("Library: graph_query", "lib.graph_query"),
        ("Library: memory_management", "lib.memory_management"),
        
        # CLI tools
        ("CLI: run_ingestion", "cli.run_ingestion"),
        ("CLI: memory", "cli.memory"),
        ("CLI: retrieve", "cli.retrieve"),
        
        # Common utilities
        ("Common: config_loader", "goodq4all.steps.common.config_loader"),
        ("Common: memory", "goodq4all.steps.common.memory"),
        ("Common: conda_runner", "goodq4all.steps.common.conda_runner"),
        
        # Key steps (just import the modules, not run them)
        ("Step: video_scene_detect", "goodq4all.steps.video_scene_detect.step"),
        ("Step: image_caption", "goodq4all.steps.image_caption.step"),
        ("Step: audio_transcribe", "goodq4all.steps.audio_transcribe.step"),
        ("Step: text_embed", "goodq4all.steps.text_embed.step"),
        ("Step: graph_builder", "goodq4all.steps.graph_builder.graph_builder"),
    ]
    
    passed = 0
    for name, module_path in tests:
        try:
            __import__(module_path)
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            errors.append((name, str(e)))
    
    print("=" * 80)
    print(f"RESULTS: {passed}/{len(tests)} imports successful")
    print("=" * 80)
    
    if errors:
        print("\nFailed imports:")
        for name, error in errors:
            print(f"  {name}: {error}")
        return 1
    else:
        print("\n✅ All critical modules import successfully!")
        return 0

if __name__ == '__main__':
    sys.exit(test_imports())
