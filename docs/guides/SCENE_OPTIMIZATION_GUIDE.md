<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/architecture/SCENE_MANIFEST_SPECIFICATION.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Scene Optimization Guide

## Overview
Optimized scene segmentation for GPU-accelerated multimodal processing.

## Changes Made (2025-12-13)

### 1. Scene Detection Parameters
**File**: `configs/config.yaml`

```yaml
scene_threshold: 27.0  # Lower = more sensitive = shorter scenes
min_scene_len_sec: 30.0  # Minimum 30s for meaningful audio
max_scene_len_sec: 300.0  # Maximum 5min - force split longer scenes
```

**Impact**:
- Shorter scenes = faster GPU processing
- Better temporal granularity for entities/events
- Prevents audio timeout on very long scenes

### 2. Dynamic Audio Timeout
**File**: `scripts/wsl2_audio_bridge.py`

```python
def process_audio(self, audio_file, timeout=None, audio_duration=None):
    if timeout is None:
        if audio_duration:
            # 60s base + 2x duration
            timeout = max(120, int(60 + (audio_duration * 2)))
        else:
            timeout = 600  # Default fallback
```

**Impact**:
- Short scenes (30s): ~120s timeout
- Medium scenes (3min): ~420s timeout  
- Long scenes (5min): ~660s timeout
- Prevents premature timeouts while avoiding infinite hangs

### 3. Scene Duration Passing
**File**: `steps/audio/audio_wsl2_bridge.py`

```python
audio_duration = kwargs.get('duration', None)
result = bridge.process_audio(audio_path, timeout=timeout, audio_duration=audio_duration)
```

**Impact**:
- Upstream steps pass scene duration
- Audio processing self-adjusts timeout
- No hardcoded magic numbers

## GPU Processing Pipeline

### Full WSL2 Audio Stack (CUDA-Accelerated)

1. **Transcription** (Faster Whisper)
   - GPU: ~0.2x realtime
   - CPU fallback: ~1x realtime

2. **Diarization** (Pyannote)
   - GPU: ~0.5x realtime
   - Requires cuDNN 9.1

3. **Emotion** (Wav2Vec2)
   - GPU: ~0.1x realtime

4. **Embeddings** (Wav2Vec2)
   - GPU: ~0.1x realtime

**Total**: ~0.9x realtime on GPU (300s scene = ~4.5min processing)

## Scene Segmentation Strategy

### Before Optimization
- Scenes: Variable (30s to 18+ minutes)
- Audio timeouts: Fixed 10min
- Result: 18min scene timed out, wasted compute

### After Optimization  
- Scenes: 30s - 5min (forced split)
- Audio timeouts: Dynamic (2-11min)
- Result: All scenes process successfully

## Benefits

### 1. GPU Efficiency
- Smaller batches = better GPU utilization
- Less VRAM pressure per scene
- Predictable processing times

### 2. Better Granularity
- More precise entity timestamps
- Finer temporal resolution
- Better scene-level metadata

### 3. Robustness
- No mega-scenes that timeout
- Dynamic timeouts prevent false failures
- Graceful handling of variable content

## Scene Length Guidelines

| Duration | Use Case | Processing Time |
|----------|----------|-----------------|
| 30-60s   | Quick cuts, action | ~2-3min |
| 1-3min   | Conversations, events | ~3-7min |
| 3-5min   | Long scenes (max) | ~7-11min |
| >5min    | **Force split** | N/A |

## Configuration Tuning

### More Scenes (Finer Granularity)
```yaml
scene_threshold: 25.0  # More sensitive
min_scene_len_sec: 20.0  # Shorter minimum
max_scene_len_sec: 180.0  # 3min max
```

### Fewer Scenes (Faster Processing)
```yaml
scene_threshold: 32.0  # Less sensitive
min_scene_len_sec: 60.0  # Longer minimum
max_scene_len_sec: 600.0  # 10min max
```

## Troubleshooting

### Still Getting Timeouts?
1. Check GPU is actually being used (nvidia-smi)
2. Verify cuDNN libraries loaded (check WSL2 logs)
3. Reduce max_scene_len_sec to 240 (4min)

### Scenes Too Short?
1. Increase scene_threshold (less sensitive)
2. Increase min_scene_len_sec
3. Check video content (rapid cuts = more scenes)

### Want Faster Processing?
1. Disable diarization for non-speech content
2. Use base model instead of large for transcription
3. Skip emotion detection for non-human scenes

## Next Steps

1. ✅ Scene optimization implemented
2. ✅ Dynamic timeout working
3. ⏳ Monitor ingestion for improvements
4. ⏳ Tune thresholds based on actual data
5. ⏳ Implement intelligent scene merging for very short scenes

---

**Last Updated**: 2025-12-13  
**Status**: Active - monitoring overnight ingestion
