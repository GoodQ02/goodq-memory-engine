#!/usr/bin/env python3
"""
[TARGET] Configuration Values Test
Validates that settings are being loaded correctly
"""
import sys
import re
from pathlib import Path

import yaml
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from steps.common import config_loader
from steps.common.config_loader import load_configs


_GENERIC_USER_DEFAULTS = {
    "name": "Local User",
    "nickname": "Local Operator",
    "pronouns": "unspecified",
    "personality_traits": "Configured in configs/config.local.yaml",
    "values": "Configured in configs/config.local.yaml",
    "background": "Private local profile belongs in configs/config.local.yaml",
    "music_style": "Configured in configs/config.local.yaml",
    "role_nursing": "Configured in configs/config.local.yaml",
    "nursing_philosophy": "Configured in configs/config.local.yaml",
    "role_personal": "Configured in configs/config.local.yaml",
}

_GENERIC_MODEL_LOCAL_DEFAULTS = {
    "zone_1": "local",
    "zone_1_desc": "Configured in configs/config.local.yaml",
    "zone_2": "optional",
    "zone_2_desc": "Configured in configs/config.local.yaml",
    "zone_3": "optional",
    "zone_3_desc": "Configured in configs/config.local.yaml",
    "main_hardware": "auto",
    "main_hardware_codename": "local",
    "mission_name": "GoodQ4All",
    "assigned_zone": "local",
    "workplace": "Configured in configs/config.local.yaml",
}

_GENERIC_TTS_DEFAULTS = {
    "elevenlabs_voice_id": "${ELEVENLABS_VOICE_ID:-example_voice_id}",
    "piper_voice": "${GOODQ_PIPER_VOICE:-default}",
    "last_used_voice": "${GOODQ_TTS_LAST_USED_VOICE:-default}",
}


def _config_scalar_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _config_scalar_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _config_scalar_values(child)
    else:
        yield value


def test_tracked_config_is_generic_and_portable():
    config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
    tracked = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    if tracked["user"] != _GENERIC_USER_DEFAULTS:
        pytest.fail("tracked user defaults are not generic", pytrace=False)
    if set(tracked["system"].values()) != {"auto"}:
        pytest.fail("tracked system defaults are not portable", pytrace=False)
    model_local_defaults = {
        key: tracked["model"][key]
        for key in _GENERIC_MODEL_LOCAL_DEFAULTS
    }
    if model_local_defaults != _GENERIC_MODEL_LOCAL_DEFAULTS:
        pytest.fail("tracked model topology is not generic", pytrace=False)
    if tracked["tts"] != _GENERIC_TTS_DEFAULTS:
        pytest.fail("tracked voice preferences are not generic", pytrace=False)
    assert tracked["home_assistant"]["url"] == (
        "${GOODQ_HOME_ASSISTANT_URL:-http://127.0.0.1:8123}"
    )

    strings = [value for value in _config_scalar_values(tracked) if isinstance(value, str)]
    assert not any(re.search(r"epoch[_-]?20\d{2}", value, re.IGNORECASE) for value in strings)
    assert not any(re.match(r"^[A-Za-z]:[\\/]", value) for value in strings)
    assert not any(value.startswith("\\\\") for value in strings)
    assert not any(re.match(r"^/home/[^/]+", value) for value in strings)
    assert not any(
        re.search(r"(?:^|[^0-9])(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.", value)
        for value in strings
    )


def test_local_override_template_covers_private_authority_fields():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "configs"
        / "config.local.example.yaml"
    )
    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))

    assert set(_GENERIC_MODEL_LOCAL_DEFAULTS).issubset(template["model"])
    assert set(_GENERIC_TTS_DEFAULTS).issubset(template["tts"])
    assert template["home_assistant"]["url"].startswith(
        "${GOODQ_HOME_ASSISTANT_URL:-"
    )


def test_tracked_configuration_surface_has_no_literal_drive_roots():
    config_dir = Path(__file__).resolve().parents[2] / "configs"
    violations = []
    for path in config_dir.rglob("*"):
        if path.name == "config.local.yaml" or path.suffix.lower() not in {".py", ".yaml", ".json"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", line):
                violations.append(f"{path.relative_to(config_dir)}:{line_no}")

    assert violations == []


def test_conda_fallback_uses_programdata_environment(monkeypatch, tmp_path):
    from configs import python_paths

    program_data = tmp_path / "program-data"
    conda_root = program_data / "miniconda3"
    conda_exe = conda_root / "Scripts" / "conda.exe"
    conda_exe.parent.mkdir(parents=True)
    conda_exe.touch()

    monkeypatch.delenv("CONDA_EXE", raising=False)
    monkeypatch.setenv("PROGRAMDATA", str(program_data))
    monkeypatch.setattr(python_paths.platform, "system", lambda: "Windows")
    monkeypatch.setattr(python_paths.shutil, "which", lambda _name: None)
    monkeypatch.setattr(python_paths.Path, "home", staticmethod(lambda: tmp_path / "home"))

    assert python_paths.PythonPathConfig()._find_conda_base() == conda_root


def test_no_local_overlay_loads_portable_baseline(monkeypatch, tmp_path):
    real_isfile = config_loader.os.path.isfile

    def without_local_files(path_value):
        normalized = str(path_value).replace("\\", "/")
        if normalized.endswith("/.env.local"):
            return False
        if normalized.endswith("/configs/config.local.yaml"):
            return False
        return real_isfile(path_value)

    monkeypatch.setattr(config_loader.os.path, "isfile", without_local_files)
    monkeypatch.delenv("GOODQ_DATA_ROOT", raising=False)
    monkeypatch.delenv("GOODQ_EPOCH_ID", raising=False)
    monkeypatch.setenv("GOODQ_WSL_USER", "portable-user")
    monkeypatch.setattr(
        config_loader.PlatformHelper,
        "get_data_root",
        staticmethod(lambda: tmp_path / "portable-data"),
    )

    cfg = load_configs()

    if cfg["user"] != _GENERIC_USER_DEFAULTS:
        pytest.fail("no-overlay user defaults are not generic", pytrace=False)
    if set(cfg["system"].values()) != {"auto"}:
        pytest.fail("no-overlay system defaults are not portable", pytrace=False)
    assert cfg["qdrant"]["collections"] == {
        "clip": "goodq_clip_default",
        "dino": "goodq_dino_default",
        "text": "goodq_text_default",
        "audio": "goodq_audio_default",
    }
    assert cfg["phase6"]["clip_collection"] == "goodq_clip_default"
    assert cfg["phase6"]["dino_collection"] == "goodq_dino_default"
    assert not any(
        "${" in value
        for value in _config_scalar_values(
            {
                key: cfg[key]
                for key in ("host", "paths", "qdrant", "phase6")
            }
        )
        if isinstance(value, str)
    )


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


def test_default_config_loads_11434_ollama_url():
    result = load_configs()
    llm = result.get("llm", {})
    assert llm.get("ollama_url") == "http://127.0.0.1:11434/v1"


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
