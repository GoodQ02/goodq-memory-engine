#!/usr/bin/env python3
"""
[TARGET] Configuration Values Test
Validates that settings are being loaded correctly
"""
import sys
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from steps.common.config_loader import load_configs


def test_config_clap_model_matches_registry_authority():
    result = load_configs({})
    registry_path = Path(__file__).resolve().parents[2] / "configs" / "model_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry_model = (
        registry.get("huggingface_models", {})
        .get("clap_audio", {})
        .get("repo_id")
    )

    assert registry_model == "laion/clap-htsat-unfused"
    assert result.get("segmentation", {}).get("phase4", {}).get("clap_model") == registry_model


def test_config_loads_segmentation_activation_as_string():
    result = load_configs()
    segmentation = result.get('segmentation', {})
    assert isinstance(segmentation.get('activation'), str)
    assert segmentation.get('activation') == 'off'


def test_validated_config_preserves_llm_runtime_contract():
    scripts_path = str(Path(__file__).resolve().parents[2] / "scripts")
    inserted = False
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
        inserted = True
    try:
        result = load_configs({
            "llm": {
                "vllm_url": "http://localhost:38005/v1",
                "ollama_url": "http://localhost:31434/v1",
                "vllm_model": "meta-llama/Llama-3.2-1B-Instruct",
                "features": {
                    "scene_context_analysis": True
                }
            }
        })
    finally:
        if inserted:
            sys.path.remove(scripts_path)

    llm = result.get("llm", {})
    assert llm.get("vllm_url") == "http://localhost:38005/v1"
    assert llm.get("ollama_url") == "http://localhost:31434/v1"
    assert llm.get("vllm_model") == "meta-llama/Llama-3.2-1B-Instruct"
    assert llm.get("features", {}).get("scene_context_analysis") is True


def test_config_derives_modality_faiss_paths_from_faiss_dir(tmp_path):
    epoch_dir = tmp_path / "epoch_under_test"
    faiss_dir = epoch_dir / "faiss"

    result = load_configs({
        "paths": {
            "db_dir": str(epoch_dir),
            "faiss_dir": str(faiss_dir),
        }
    })

    paths = result.get("paths", {})
    expected_suffixes = {
        "faiss_index_path": "/faiss/text/faiss_text.index",
        "faiss_clip_path": "/faiss/clip/faiss_clip.index",
        "faiss_dino_path": "/faiss/dino/faiss_dino.index",
        "clip_id_map_db": "/faiss/clip/clip_id_map.sqlite",
        "dino_id_map_db": "/faiss/dino/dino_id_map.sqlite",
        "clap_id_map_db": "/faiss/audio/clap_id_map.sqlite",
    }

    for key, suffix in expected_suffixes.items():
        value = paths.get(key)
        assert isinstance(value, str), f"{key} should be derived from paths.faiss_dir"
        assert value.replace("\\", "/").endswith(suffix)


def test_config_values():
    """Test that all critical settings have correct values"""
    print("=" * 70)
    print("[SEARCH] GoodQ Configuration Values Test")
    print("=" * 70)
    print()
    
    result = load_configs()
    # Canonical loader returns top-level config; keep legacy nested fallback for old snapshots.
    cfg = result if isinstance(result.get('video'), dict) else result.get('config', {})
    paths = result.get('paths', {})
    
    # Test Video Settings
    print("[VIDEO] VIDEO SETTINGS:")
    scene_detect = cfg.get('video', {}).get('scene_detect', {})
    threshold = scene_detect.get('threshold', 'NOT SET')
    min_scene = scene_detect.get('min_scene_len_sec', 'NOT SET')
    max_scenes = scene_detect.get('max_scenes', 'NOT SET')

    print(f"   Scene Threshold: {threshold}")
    print(f"   Min Scene Length: {min_scene}s")
    max_scenes_display = max_scenes if isinstance(max_scenes, (int, float)) and max_scenes > 0 else "unlimited"
    print(f"   Max Scenes: {max_scenes_display}")
    print("   Entity Refinement: retired")
    
    # Validate
    if threshold == 15.0:
        print("   [OK] Scene threshold is CORRECT (15.0 for home movies)")
    else:
        print(f"   [FAIL] Scene threshold is WRONG (expected 15.0, got {threshold})")
    print()
    
    # Test Audio Settings
    print("[AUDIO] AUDIO SETTINGS:")
    audio = cfg.get('audio', {})
    transcribe = audio.get('transcribe', {})
    chunk_seconds = transcribe.get('chunk_seconds', 'NOT SET')
    model = transcribe.get('model', 'NOT SET')
    language = transcribe.get('language', 'NOT SET')
    
    print(f"   Transcribe Model: {model}")
    print(f"   Chunk Seconds: {chunk_seconds}")
    print(f"   Language: {language}")
    
    if chunk_seconds == 30:
        print("   [OK] Chunk seconds is CORRECT (30 for efficiency)")
    else:
        print(f"   [WARN]  Chunk seconds could be optimized (expected 30, got {chunk_seconds})")
    print()
    
    # Test New Settings
    print("[SYMBOL]️  NEW CONFIGURATION SECTIONS:")
    
    faiss = cfg.get('faiss', {})
    if faiss:
        print(f"   FAISS Index Type: {faiss.get('index_type', 'NOT SET')}")
        print(f"   FAISS Metric: {faiss.get('metric', 'NOT SET')}")
        print("   [OK] FAISS configuration found")
    else:
        print("   [WARN]  FAISS configuration missing")
    print()
    
    memory = cfg.get('memory', {})
    if memory:
        print(f"   Max Summaries/Video: {memory.get('max_summaries_per_video', 'NOT SET')}")
        print(f"   Retention Days: {memory.get('retention_days', 'NOT SET')}")
        print("   [OK] Memory management configuration found")
    else:
        print("   [WARN]  Memory management configuration missing")
    print()
    
    processing = cfg.get('processing', {})
    if processing:
        print(f"   Image Batch Size: {processing.get('batch_size_images', 'NOT SET')}")
        print(f"   Max Workers: {processing.get('max_workers', 'NOT SET')}")
        print("   [OK] Processing optimization configuration found")
    else:
        print("   [WARN]  Processing optimization configuration missing")
    print()
    
    kg = cfg.get('knowledge_graph', {})
    if kg:
        print(f"   KG Enabled: {kg.get('enabled', 'NOT SET')}")
        print(f"   Min Confidence: {kg.get('min_confidence', 'NOT SET')}")
        print("   [OK] Knowledge graph configuration found")
    else:
        print("   [WARN]  Knowledge graph configuration missing")
    print()
    
    print("=" * 70)
    print("[TARGET] Configuration Test Complete")
    print("=" * 70)


def test_build_llm_models_profile_injection(monkeypatch):
    from steps.common.llm_model_factory import build_llm_models
    
    # 1. Default case (no profile)
    monkeypatch.delenv("GOODQ_HOST_PROFILE", raising=False)
    cfg = load_configs({
        "llm": {
            "vllm_url": "http://localhost:38005/v1",
            "ollama_url": "http://localhost:31434/v1",
            "vllm_model": "meta-llama/Llama-3.2-1B-Instruct",
            "ollama_model": "phi4"
        }
    })
    models = build_llm_models(cfg)
    assert len(models) == 2
    assert models[0].name == "Llama-1B-Speed"
    assert models[1].name == "Llama3.2-Ollama"
    
    # 2. Ingest quality profile case
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_16GB_INGEST_QUALITY")
    cfg = load_configs({
        "llm": {
            "vllm_url": "http://localhost:38005/v1",
            "ollama_url": "http://localhost:31434/v1",
            "vllm_model": "meta-llama/Llama-3.2-1B-Instruct",
            "ollama_model": "phi4"
        }
    })
    models = build_llm_models(cfg)
    assert len(models) == 3
    assert models[0].name == "DeepSeek-R1-Distill-Qwen-14B"
    assert models[0].backend == "ollama"
    assert models[0].vram_gb == 9.5
    assert models[0].priority == 200


def test_load_configs_runtime_config_merge(monkeypatch, tmp_path):
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    runtime_config_file = tmp_path / "runtime_config.json"
    import json
    runtime_config_file.write_text(json.dumps({
        "qdrant_port": 6399,
        "qdrant_host": "192.168.1.100"
    }), encoding="utf-8")

    result = load_configs({})
    assert result.get("qdrant", {}).get("port") == 6399
    assert result.get("qdrant", {}).get("host") == "192.168.1.100"


if __name__ == "__main__":
    test_config_values()
