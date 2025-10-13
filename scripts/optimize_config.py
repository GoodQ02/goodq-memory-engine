#!/usr/bin/env python3
"""
GoodQ Configuration Optimizer
Audits and optimizes configuration for long-form video processing
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List

CONFIG_PATH = Path("L:/goodq4all/config.yaml")

# Optimal settings for long home movies (30-120 minutes)
OPTIMAL_SETTINGS = {
    "video": {
        "scene_detection": {
            "threshold": 27.0,  # Balanced - catches most scene changes
            "min_scene_len": 1.0,  # Allow 1-second scenes
            "adaptive": True
        },
        "frame_extraction": {
            "method": "scene_middle",  # More representative frame
            "max_frames_per_scene": 1,
            "quality": 95
        }
    },
    "audio": {
        "transcribe": {
            "model": "medium",  # Good balance of quality/speed
            "chunk_seconds": 30.0,  # Longer chunks = better context
            "language": None,  # Auto-detect
            "enable_vad": True,
            "vad_threshold": 0.4,  # Lower = catch quiet speech
            "min_speech_duration": 0.25,  # 250ms minimum
            "max_speech_duration": 300.0,  # 5 minutes max per segment
            "beam_size": 5,
            "best_of": 5,
            "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        },
        "diarization": {
            "enabled": True,
            "min_speakers": 1,
            "max_speakers": 10,  # Good for family videos
            "embedding_model": "speechbrain/spkrec-ecapa-voxceleb"
        },
        "emotion": {
            "enabled": True,
            "model": "speechbrain/emotion-recognition-wav2vec2-IEMOCAP"
        }
    },
    "image": {
        "caption": {
            "model": "Salesforce/blip-image-captioning-large",
            "max_length": 50,
            "num_beams": 4
        },
        "object_detection": {
            "model": "facebook/detr-resnet-50",
            "confidence_threshold": 0.7,  # Lower = more detections
            "max_detections": 100
        },
        "face_detection": {
            "enabled": True,
            "min_face_size": 20,
            "confidence_threshold": 0.9
        },
        "ocr": {
            "enabled": True,
            "languages": ["eng"],
            "tesseract_config": "--psm 11"
        }
    },
    "embeddings": {
        "text": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "batch_size": 32
        },
        "image_clip": {
            "model": "openai/clip-vit-base-patch16",
            "batch_size": 8
        },
        "image_dino": {
            "model": "facebook/dinov2-base",
            "batch_size": 8
        },
        "audio_clap": {
            "model": "laion/clap-htsat-unfused",
            "batch_size": 4
        }
    },
    "processing": {
        "batch_size": 10,  # Process 10 scenes at a time
        "memory_management": {
            "max_cache_size_gb": 8.0,
            "clear_gpu_cache": True,
            "gc_frequency": 50  # Run GC every 50 scenes
        },
        "timeout": {
            "per_scene_seconds": 180,  # 3 minutes per scene max
            "per_video_hours": 24  # 24 hours total per video
        }
    },
    "knowledge_graph": {
        "enabled": True,
        "entity_extraction": {
            "enabled": True,
            "min_confidence": 0.5
        },
        "relationship_extraction": {
            "enabled": True,
            "temporal_linking": True,
            "spatial_linking": True,
            "semantic_linking": True
        }
    }
}

def audit_config() -> Dict[str, Any]:
    """Audit current configuration and identify issues"""
    issues = []
    recommendations = []
    
    if not CONFIG_PATH.exists():
        issues.append("config.yaml not found")
        return {"issues": issues, "recommendations": ["Create config.yaml with optimal settings"]}
    
    with open(CONFIG_PATH) as f:
        current_config = yaml.safe_load(f) or {}
    
    # Check critical settings
    audio_transcribe = current_config.get("audio", {}).get("transcribe", {})
    chunk_seconds = audio_transcribe.get("chunk_seconds")
    
    if chunk_seconds and chunk_seconds < 20:
        issues.append(f"Chunk size too small: {chunk_seconds}s (optimal: 30s+)")
        recommendations.append("Increase audio.transcribe.chunk_seconds to 30 for better context")
    
    scene_threshold = current_config.get("video", {}).get("scene_detection", {}).get("threshold")
    if scene_threshold and scene_threshold > 30:
        issues.append(f"Scene threshold too high: {scene_threshold} (may miss scene changes)")
        recommendations.append("Lower video.scene_detection.threshold to ~27 for home videos")
    
    # Check VAD settings
    if not audio_transcribe.get("enable_vad"):
        recommendations.append("Enable VAD (Voice Activity Detection) for better transcription")
    
    # Check diarization
    diarization = current_config.get("audio", {}).get("diarization", {})
    if not diarization.get("enabled"):
        recommendations.append("Enable speaker diarization to track who's speaking")
    
    # Check knowledge graph
    kg = current_config.get("knowledge_graph", {})
    if not kg.get("enabled"):
        recommendations.append("Enable knowledge_graph for relationship extraction")
    
    return {
        "issues": issues,
        "recommendations": recommendations,
        "current_config": current_config
    }

def apply_optimal_settings() -> None:
    """Apply optimal settings to config.yaml"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            current_config = yaml.safe_load(f) or {}
    else:
        current_config = {}
    
    # Deep merge optimal settings
    def deep_merge(base: Dict, update: Dict) -> Dict:
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    optimized = deep_merge(current_config, OPTIMAL_SETTINGS)
    
    # Backup original
    if CONFIG_PATH.exists():
        backup_path = CONFIG_PATH.with_suffix('.yaml.backup')
        import shutil
        shutil.copy2(CONFIG_PATH, backup_path)
        print(f"[INFO] Backed up original config to: {backup_path}")
    
    # Write optimized config
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(optimized, f, default_flow_style=False, sort_keys=False, indent=2)
    
    print(f"[SUCCESS] Optimized configuration written to: {CONFIG_PATH}")
    print("\n[INFO] Key optimizations applied:")
    print("  • Whisper: 30s chunks with enhanced VAD settings")
    print("  • Scene Detection: Threshold=27, adaptive=True")
    print("  • Diarization: Enabled with 1-10 speakers")
    print("  • Knowledge Graph: Enabled with relationship extraction")
    print("  • Memory: 8GB cache, auto-GC every 50 scenes")
    print("  • Timeouts: 3min/scene, 24h/video")

def main():
    print("=" * 60)
    print("GoodQ Configuration Optimizer")
    print("=" * 60)
    print()
    
    # Audit current settings
    print("[1/2] Auditing current configuration...")
    audit = audit_config()
    
    if audit["issues"]:
        print("\n[ISSUES FOUND]")
        for issue in audit["issues"]:
            print(f"  ⚠ {issue}")
    
    if audit["recommendations"]:
        print("\n[RECOMMENDATIONS]")
        for rec in audit["recommendations"]:
            print(f"  → {rec}")
    
    print()
    print("[2/2] Applying optimal settings...")
    apply_optimal_settings()
    
    print()
    print("=" * 60)
    print("[COMPLETE] Configuration optimized for long-form video processing")
    print("=" * 60)

if __name__ == "__main__":
    main()
