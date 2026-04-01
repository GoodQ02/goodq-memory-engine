# Scene Manifest Specification

**Status:** ✅ **STABLE AND OPERATIONAL**  
**Last Verified:** April 1, 2026  
**Evidence:** stitching-era witness runs produced epoch-scoped manifests with active WSL audio, Phase 6 completion, and persisted speaker voice signatures

---

## Overview

The **scene_manifest.json** is the canonical index file created during video ingestion that catalogs all detected scenes with their associated metadata, keyframes, audio chunks, and processing results.

### Location

```
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_manifest.json
```

**Example:**
```
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/epoch_2025_12_22/processing/01x01 - Good News, Bad News/video/scene_manifest.json
```

### Creation

- **Module:** `cli/run_ingestion.py`
- **Lines:** 1377-1382
- **Timing:** Created during scene ingestion and finalized before Phase 6b completes
- **Purpose:** Provides Phase 6 and downstream retrieval/memory systems with the canonical scene bundle

---

## Structure

### Top Level

```json
{
  "video_id": "7215a98e...",           // SHA256 hash of video file
  "video_path": "<GOODQ_DATA_ROOT>/import_inbox/...",  // Original video path
  "phase6_status": "complete",         // Phase 6 truth surface
  "phase6_complete": true,
  "scenes": [...]                      // Array of scene objects
}
```

### Scene Object

Each scene contains:

```json
{
  "scene_id": "7fde117a...",           // Unique SHA256 hash
  "index": 0,                          // Sequential scene number
  "start": 0.0,                        // Start timestamp (seconds)
  "end": 4.171,                        // End timestamp (seconds)
  "duration": 4.171,                   // Duration (seconds)
  "confidence": 1.0,                   // Scene detection confidence
  "clip_id": "clip_scene_...",         // Phase 6a CLIP vector id
  "dino_id": "dino_scene_...",         // Phase 6a DINO vector id
  "qdrant_ok": true,                   // Scene vectors committed to Qdrant
  "speaker_ids": ["SPEAKER_00"],
  "speaker_count": 1,
  "keyframe": {...},                   // Visual analysis results
  "audio": {...}                       // Audio analysis results
}
```

---

## Keyframe Object

Visual processing results from the scene's representative frame:

```json
"keyframe": {
  "path": "<project_root>\\logs\\scene_ingest\\...\\frames\\scene_0000.jpg",
  "timestamp": 2.0855,               // Midpoint of scene
  "scene": {
    "start": 0.0,
    "end": 4.171,
    "duration": 4.171
  },
  
  // Vision Processing Results
  "ocr_text": "Text detected in frame",
  "caption": "a blurry photo of a street scene with a light",
  "caption_meta": {
    "status": "ok",
    "engine": "vit-gpt2"
  },
  
  "objects": [],                     // YOLO detected objects
  "detect_meta": {
    "status": "unavailable",
    "engine": "yolo"
  },
  
  "faces": [],                       // Face embeddings
  "faces_meta": {
    "status": "error",
    "error": "No module named 'facenet_pytorch'"
  },
  
  "dino_meta": {"status": "unavailable"},
  "clip_meta": {"status": "unavailable"},
  
  "tags": [],                        // Image tags
  "usefulness": 0.03,                // Quality score
  "entities": [],                    // Extracted entities
  "frame_text": "Combined text description"
}
```

---

## Audio Object

Audio processing results from the scene's audio chunk:

```json
"audio": {
  "path": "${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video>/audio/scene_0000.wav",
  "start": 0.0,
  "end": 4.171,
  "duration": 4.171,

  // Backend contract
  "audio_backend_selected": "wsl",
  "audio_backend_effective": "wsl",
  "audio_backend_downgraded": false,
  
  // Transcription (WSL2 Unified)
  "transcript": "look at it it's too high it's in no man's land",
  "transcript_meta": {
    "status": "success",
    "engine": "wsl_unified",
    "device": "cuda",
    "segment_count": 7
  },
  
  // Speaker Diarization
  "diarization": [
    {
      "speaker": "SPEAKER_00",
      "start": 0.483,
      "end": 2.788,
      "text": "You"
    }
  ],
  "diarization_meta": {
    "status": "ok",
    "engine": "pyannote-3.1",
    "num_speakers": 1
  },

  // Speaker-owned transcript alignment
  "speaker_transcript": [
    {
      "speaker": "SPEAKER_00",
      "text": "look at it it's too high it's in no man's land",
      "start": 0.0,
      "end": 3.9
    }
  ],

  // Per-speaker voice signatures
  "speaker_voice_signatures": [
    {
      "speaker": "SPEAKER_00",
      "embedding": [0.119, -0.306, ...],
      "embedding_dim": 768,
      "voiced_seconds": 5.72,
      "segment_count": 3
    }
  ],
  "speaker_voice_signature_meta": {
    "status": "ok",
    "emitted": 1,
    "attempted_speakers": 1,
    "min_voiced_seconds": 4.0,
    "min_segment_count": 2
  },
  
  // Emotion Analysis
  "emotions": [
    {
      "start": 0.0,
      "end": 4.171,
      "emotion": "neutral",
      "confidence": 0.85
    }
  ],
  "emotion_meta": {
    "status": "ok",
    "engine": "wav2vec2-emotion"
  },
  
  // Audio Embeddings
  "embeddings": [0.119, -0.306, ...],  // 768-dim scene-level vector
  "embedding_dim": 768,
  "wsl2_unified": true,
  "gpu_used": true,
  "gpu_name": "NVIDIA GeForce RTX 4070 Ti SUPER",

  "music_events": "",
  "music_events_meta": {"status": "none"},
  "time_hints": {
    "explicit_dates": [],
    "times": [],
    "weekdays": [],
    "months": [],
    "relative_phrases": []
  },
  "time_hints_meta": {"status": "none"},
  
  // Analysis
  "sentiment": {
    "label": "POSITIVE",
    "score": 0.678
  },
  "sentiment_meta": {"engine": "hf"},
  
  "tags": "You",
  "usefulness": 0.0,
  "entities": "You",
  "vocabulary": "you",
  
  "clap_meta": {"status": "no_index_path"}
}
```

---

## Consumers

### Phase 6 Modules (Operational)

1. **Scene Visual Embeddings** (`steps/video/scene_visual_embeddings.py`)
   - Reads: `scene_manifest.json`
   - Purpose: Pool CLIP/DINO embeddings across scenes
   - Status: Wired and operational

2. **Cross-Modal Harmonizer** (`steps/video/cross_modal_harmonizer.py`)
   - Reads: `scene_manifest.json`
   - Purpose: Align audio/visual timelines, resolve entities
   - Status: Wired and operational

3. **Embedding Pooler** (`steps/video/embedding_pooler.py`)
   - Reads: Scene embeddings
   - Purpose: Aggregate scene-level vectors
   - Status: Used by Phase 6a

### API/Query Systems

4. **API Loaders** (`api/utils/loaders.py`)
   - Reads: `scene_manifest.json` from the epoch processing tree
   - Purpose: Serve scene data to UI/API
   - Status: Deployment-dependent consumer

5. **Multimodal Search** (`retrieval/multimodal_search.py`)
   - Potential consumer of aggregated scene data
   - Status: Runtime consumer when retrieval is enabled

---

## Statistics (Production Data)

**Dataset:** 13 videos processed (Dec 12-14, 2025)

| Video Name | Scenes | Size | Date |
|------------|--------|------|------|
| 03. 1989 - 1990 | ~100+ | 6.55 MB | 12/14/25 07:31 |
| 02. 1988 - 1989 | ~90+ | 5.32 MB | 12/14/25 04:54 |
| 01. 1987 - 1988 | ~80+ | 4.60 MB | 12/14/25 02:48 |
| 05. 1992 - 1994 | ~60+ | 3.53 MB | 12/14/25 10:42 |
| 07. 1996 - 1999 | ~60+ | 3.45 MB | 12/14/25 13:59 |
| 04. 1990 - 1992 | ~50+ | 3.03 MB | 12/14/25 09:00 |
| 08. 1999 - 2002 | ~45+ | 2.71 MB | 12/14/25 15:47 |
| 06. 1995 - 1996 | ~30+ | 1.66 MB | 12/14/25 11:57 |
| 10. 2003-2005 | 13 | 0.83 MB | 12/14/25 19:01 |
| 09. 2002 - 2003 | ~10+ | 0.66 MB | 12/14/25 16:15 |

**Total:** ~600+ scenes across all videos

---

## Validation

### Structure Checks

✅ **Required Fields Present:**
- `video_id`, `video_path`, `scenes` array
- Per scene: `scene_id`, `index`, `start`, `end`, `duration`, `confidence`
- `keyframe` object with `path` and processing results
- `audio` object with `path`, `transcript`, `diarization`

✅ **Data Integrity:**
- All manifests JSON-parseable
- All referenced paths exist on disk
- SHA256 hashes unique per scene
- Timestamps sequential and non-overlapping

✅ **Completeness:**
- 100% of ingested videos have manifests
- No empty or truncated manifests found
- All scenes have both keyframe and audio data

### Size Distribution

Average manifest size correlates with:
- Number of scenes detected
- Length of transcripts (verbose speech → larger files)
- Number of entities extracted
- Embedding data (768-dim float arrays)

**Rule of thumb:** ~50-70 KB per scene

---

## Known Issues

### 1. Partial Scene Errors Remain Possible

Some scenes may still carry partial keyframe or optional-audio failures while the manifest remains canonical.

**Current behavior:** the scene stays persisted, `content_state` and step-level error fields remain truthful, and Phase 6 continues when allowed.

### 2. Backend Markers Must Be Read From Audio Fields

Use:
```json
"audio_backend_selected"
"audio_backend_effective"
"audio_backend_downgraded"
```

These fields are authoritative for whether WSL audio succeeded, downgraded, or was never selected.

### 3. Identity Formation Starts Here, Not In The KG Alone

`speaker_voice_signatures`, `speaker_voice_signature_meta`, and `speaker_transcript` are now part of the manifest contract. They are the input surface for the identity ladder defined in `docs/architecture/IDENTITY_STITCHING_CONTRACT.md`.

---

## Usage Examples

### Python: Load Manifest

```python
import os
import json
from pathlib import Path

processing_root = Path(os.environ["GOODQ_DATA_ROOT"]) / "GoodQ_Data" / "epochs" / epoch / "processing"
manifest_path = Path(processing_root) / video_name / "video" / "scene_manifest.json"
with open(manifest_path) as f:
    data = json.load(f)

print(f"Video: {data['video_id']}")
print(f"Total scenes: {len(data['scenes'])}")

for scene in data['scenes']:
    print(f"Scene {scene['index']}: {scene['start']:.2f}s - {scene['end']:.2f}s")
    print(f"  Transcript: {scene['audio'].get('transcript', 'N/A')}")
    print(f"  Caption: {scene['keyframe'].get('caption', 'N/A')}")
```

### PowerShell: Validate All Manifests

```powershell
Get-ChildItem -Path "$env:GOODQ_DATA_ROOT\\GoodQ_Data\\epochs" -Recurse -Filter "scene_manifest.json" | ForEach-Object {
    $json = Get-Content $_.FullName | ConvertFrom-Json
    Write-Output "$($_.Directory.Parent.Name): $($json.scenes.Count) scenes"
}
```

### Query: Find Scenes with Specific Speaker

```python
def find_speaker_scenes(manifest_path, speaker_id="SPEAKER_00"):
    with open(manifest_path) as f:
        data = json.load(f)
    
    results = []
    for scene in data['scenes']:
        diarization = scene['audio'].get('diarization', [])
        if any(seg['speaker'] == speaker_id for seg in diarization):
            results.append({
                'scene_id': scene['scene_id'],
                'start': scene['start'],
                'transcript': scene['audio'].get('transcript')
            })
    return results
```

---

## Future Enhancements

### Phase 6 Activation

When Phase 6 modules are wired:

1. **Scene-level embeddings** will be added:
   ```json
   "scene_embedding": {
     "clip": [...],      // 512-dim
     "dino": [...],      // 384-dim
     "pooled": [...]     // Combined vector
   }
   ```

2. **Cross-modal confidence scores:**
   ```json
   "harmonization": {
     "audio_visual_alignment": 0.92,
     "entity_consistency": 0.87
   }
   ```

3. **Resolved entities:**
   ```json
   "entities": [
     {
       "text": "John",
       "type": "PERSON",
       "sources": ["audio_transcript", "visual_ocr"],
       "confidence": 0.95
     }
   ]
   ```

---

## Related Documentation

- **Pipeline Overview:** `docs/INGESTION_PIPELINE.md`
- **Entity Extraction:** `docs/integrations/ENTITY_EXTRACTION.md`
- **WSL2 Audio:** `docs/WSL2_AUDIO_PROCESSING.md`
- **Phase 6 Modules:** `docs/PHASE6_CAPABILITIES.md` (if activated)
- **Forensic Audit:** `docs/FORENSIC_AUDIT_DEC14.md`

---

## Summary

✅ **Scene manifests are STABLE and PRODUCTION-READY**  
✅ **13 manifests generated across real videos**  
✅ **Structure validated, all fields present**  
✅ **Consumed by Phase 6 modules (when activated)**  
✅ **Format supports future enhancements without breaking changes**

**Last Generated:** December 14, 2025 19:01:52  
**Largest Manifest:** 6.55 MB (03. 1989 - 1990)  
**Total Scenes Tracked:** ~600+ across all videos
