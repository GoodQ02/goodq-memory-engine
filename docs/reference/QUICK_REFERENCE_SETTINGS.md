# 🎯 GoodQ Settings Quick Reference

## Test Settings
```batch
TEST_CONFIG_VALUES.bat
```

## Key Settings for Home Videos

### Scene Detection
```yaml
threshold: 15.0              # Lower = more scenes (home movies need 15-20)
min_scene_len_sec: 1.5       # Minimum scene duration
max_scenes: 0                # No limit
```

### Audio Transcription
```yaml
model: "medium"              # Best balance (large-v3 for better accuracy but slower)
chunk_seconds: 30            # Larger = more efficient
language: "en"               # Explicit language
beam_size: 5                 # Higher = more accurate
```

### Entity Tracking
```yaml
entity_max_samples: 300      # Track across hours
entity_sample_rate: 0.5      # Every other frame
```

### Processing
```yaml
batch_size_images: 8         # GPU batch size
batch_size_audio: 4          # Audio batch size
max_workers: 1               # Parallel workers
```

## Expected Performance (2-Hour Video)

| Step | Time |
|------|------|
| Scene Detection | 10-15 min |
| Frame Extraction | 5-10 min |
| Image Analysis | 30-45 min |
| Audio Diarization | 30-60 min |
| Transcription | 45-90 min |
| Embeddings | 10-20 min |
| Knowledge Graph | 5-10 min |
| **TOTAL** | **2.5-4 hours** |

## What Should Happen

✅ **100-200+ scenes** detected for 2-hour video  
✅ **Actual dialogue** transcribed with speaker labels  
✅ **People/objects** tracked throughout  
✅ **Embeddings** created for all modalities  
✅ **Knowledge graph** populated with entities  
✅ **No silent failures** (all errors logged)

## Troubleshooting

| Problem | Check |
|---------|-------|
| Few scenes | `TEST_CONFIG_VALUES.bat` - verify threshold is 15.0 |
| Slow transcription | Verify chunk_seconds is 30, GPU is used |
| Missing data | Check step_log.jsonl for errors |
| High memory | Verify auto_vacuum enabled |

## Files to Monitor

- `L:\goodq4all\logs\[workspace]\step_log.jsonl` - Step execution
- `L:\goodq4all\logs\watchdog.log` - Watchdog activity
- `L:\goodq4all\data\memory.db` - Main database
- `L:\goodq4all\data\graph\goodq_graph.json` - Knowledge graph

---

**Last Updated**: 2025-10-12  
**Status**: Optimized for long-form home video processing
