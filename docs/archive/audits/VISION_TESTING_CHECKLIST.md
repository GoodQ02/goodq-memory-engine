<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/components/VISION_PIPELINE.md -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Vision Stack GPU Optimization - Testing Checklist

## ✅ Completed (by AI Assistant)

- [x] Audited all vision step code
- [x] Integrated centralized GPU configuration
- [x] Updated gpu_config.py with vision memory limits
- [x] Added GPU acceleration to face_embed
- [x] Added GPU acceleration to emotion_classify
- [x] Added GPU acceleration to object_detect
- [x] Added GPU acceleration to image_embed_clip
- [x] Added GPU acceleration to image_embed_dino
- [x] Added GPU acceleration to image_caption
- [x] Created optimization script (optimize_vision_gpu.py)
- [x] Created audit script (audit_vision_pipeline.py)
- [x] Created test frame extractor (extract_test_frame.py)
- [x] Created batch launchers (.bat files)
- [x] Created comprehensive documentation (VISION_GPU_OPTIMIZATION.md)
- [x] Verified all 5 vision environments exist
- [x] Confirmed CUDA is available in all environments

## ⏳ Your Turn - Testing Phase

### Step 1: Run Optimization (15-20 minutes)
- [ ] Open command prompt
- [ ] Navigate to: `cd L:\goodq4all`
- [ ] Run: `run_vision_optimization.bat`
- [ ] Wait for completion (downloads models, installs packages)
- [ ] Verify: All environments show "✅ optimization complete"
- [ ] Note: First run downloads ~2-3 GB of models to L:/models

### Step 2: Extract Test Frame (< 1 minute)
- [ ] Run: `extract_test_frame.bat`
- [ ] OR manually:
  - [ ] Open any video from L:/_DATA/FAMILY_FEAST
  - [ ] Pause at any frame (suggest 10-30 seconds in)
  - [ ] Screenshot and save as: `L:\goodq4all\test_data\sample_frame.jpg`
- [ ] Verify: File exists and is a valid image

### Step 3: Run Vision Audit (5-10 minutes)
- [ ] Run: `run_vision_audit.bat`
- [ ] Wait for all tests to complete
- [ ] Review console output for any failures
- [ ] Check: `L:\goodq4all\output\vision_audit_report.txt`
- [ ] Target: 7/7 tests passing (100%)

**Expected Results:**
```
✅ GPU Utilization: PASS
✅ Face Detection: PASS
✅ Emotion Classification: PASS
✅ Object Detection: PASS
✅ Image Embeddings: PASS
✅ Image Captioning: PASS
✅ Model Caching: PASS
```

### Step 4: Quick Integration Test (1-2 hours)
- [ ] Find a short video (30-60 seconds) from your collection
- [ ] Copy to: `L:\goodq4all\import_inbox\test_short.mp4`
- [ ] Launch watchdog: `Launch_GoodQ.bat`
- [ ] Open second terminal and run: `nvidia-smi -l 1`
  - [ ] Verify GPU memory usage increases during processing
  - [ ] Check GPU utilization reaches 60-90%
- [ ] Monitor UI (http://localhost:30000)
  - [ ] Wait for processing to complete
  - [ ] Check "Scenes" tab for detected faces
  - [ ] Check "Analytics" for emotions and objects
  - [ ] Verify knowledge graph shows visual entities
- [ ] Check database:
  - [ ] Open: `L:\goodq4all\output\goodq.db`
  - [ ] Query: `SELECT * FROM scenes LIMIT 10;`
  - [ ] Verify: Emotion data populated
  - [ ] Verify: Face data populated
  - [ ] Verify: Object data populated

### Step 5: Full Production Test (full movie)
- [ ] Choose complete home movie from L:/_DATA/FAMILY_FEAST
- [ ] Copy to import_inbox
- [ ] Launch watchdog
- [ ] Monitor progress:
  - [ ] GPU utilization (nvidia-smi)
  - [ ] Command center logs (UI)
  - [ ] Processing time per scene
- [ ] Performance verification:
  - [ ] Face detection: Target ~80ms/frame
  - [ ] Emotion classify: Target ~40ms/text
  - [ ] Object detect: Target ~120ms/frame
  - [ ] Overall: Should be ~10x faster than previous CPU runs
- [ ] Data verification:
  - [ ] Faces detected and tracked across scenes
  - [ ] Emotions classified for all scenes with speech/captions
  - [ ] Objects detected and labeled
  - [ ] CLIP/DINO embeddings in FAISS indices
  - [ ] Image captions generated for key frames
- [ ] UI verification:
  - [ ] All vision data displays correctly
  - [ ] Knowledge graph shows people, objects, emotions
  - [ ] Search works for visual queries
  - [ ] Timeline shows visual events

## 🐛 Troubleshooting Checklist

If optimization fails:
- [ ] Check CUDA installation: `nvidia-smi`
- [ ] Verify PyTorch CUDA: `conda run -n goodq_face_embed python -c "import torch; print(torch.cuda.is_available())"`
- [ ] Reinstall PyTorch: See VISION_GPU_OPTIMIZATION.md troubleshooting section

If audit fails:
- [ ] Check test image exists: `L:\goodq4all\test_data\sample_frame.jpg`
- [ ] Verify it's a valid image (open in image viewer)
- [ ] Re-run individual tests (see audit_vision_pipeline.py)
- [ ] Check console for specific error messages

If integration test fails:
- [ ] Check command center logs for errors
- [ ] Verify watchdog is running (not frozen)
- [ ] Check GPU memory hasn't filled up (nvidia-smi)
- [ ] Look for Python errors in terminal
- [ ] Verify all environments can import models

If out of GPU memory:
- [ ] Reduce memory fractions in gpu_config.py
- [ ] Process smaller batches
- [ ] Restart system to clear GPU memory
- [ ] Close other GPU applications (games, browsers with hardware accel, etc.)

## 📊 Success Criteria

### Optimization Phase
- ✅ All 5 environments install PyTorch with CUDA successfully
- ✅ GPU detection returns True in all environments
- ✅ All vision models load on GPU without errors

### Audit Phase
- ✅ 7/7 tests pass (100%)
- ✅ No CUDA errors
- ✅ Models cached in L:/models
- ✅ GPU memory usage stays under 12 GB

### Integration Phase
- ✅ Short video processes without errors
- ✅ Vision data appears in database
- ✅ UI displays faces, emotions, objects
- ✅ GPU utilization 60-90% during vision steps
- ✅ Processing faster than CPU baseline

### Production Phase
- ✅ Full movie processes end-to-end
- ✅ No crashes or memory errors
- ✅ ~10x speedup vs CPU (or better)
- ✅ All vision features work in UI
- ✅ Knowledge graph rich with visual data
- ✅ Search and timeline functional

## 📝 Notes & Observations

### Optimization Notes:
```
Date:
Duration:
Any errors?
Model download size:
```

### Audit Notes:
```
Date:
Tests passed:
Any warnings?
GPU memory peak:
```

### Integration Notes:
```
Date:
Video length:
Processing time:
GPU utilization:
Issues encountered:
```

### Production Notes:
```
Date:
Video length:
Processing time:
Speedup vs CPU:
Total faces detected:
Total objects detected:
Unique emotions:
Any issues:
```

## 🎉 Completion

When all checkboxes are complete and success criteria met:

- [ ] Vision stack is fully GPU-accelerated
- [ ] All components tested and working
- [ ] Production-ready for large-scale ingestion
- [ ] Performance gains validated
- [ ] Ready to process entire home movie collection

**Congratulations!** Your vision pipeline is now optimized for maximum performance! 🚀

---

**Questions or issues?** Refer to:
- `L:\goodq4all\docs\VISION_GPU_OPTIMIZATION.md` (implementation guide)
- Step code in `L:\goodq4all\steps\*` (technical details)
- `gpu_config.py` (configuration reference)
