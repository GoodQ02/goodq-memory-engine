# GPU Optimization - Quick Start Guide

## 🚀 Ready to Test in 3 Steps

### Prerequisites
- ✅ GPU configured (NVIDIA RTX 4070 Ti SUPER detected)
- ✅ All pipeline steps have GPU configuration
- ✅ CUDA available (version 13.0)

### Step 1: Quick Validation (30 seconds)
```bash
cd L:\goodq4all
conda activate goodq_zenml
python scripts\test_gpu_config.py
```

**Expected Output**:
```
✅ GPU Configuration Test Complete
✓ Auto-configuration working
✓ Memory allocation working
✓ Tensor allocation working
✓ Cache clearing working
```

### Step 2: Run Monitored Pipeline (10-15 minutes)
```bash
python scripts\monitor_gpu_pipeline.py
```

**What This Does**:
1. Starts the watchdog/pipeline
2. Monitors GPU usage every 2 seconds
3. Detects which step is running
4. Displays real-time stats
5. Generates comprehensive report

**Watch For**:
- GPU utilization jumping to 70-90% during heavy steps
- VRAM usage increasing appropriately per step
- Temperature rising to 60-70°C
- No out-of-memory errors

### Step 3: Review Results
Check the generated report:
```bash
# Report location
ls logs\gpu_optimization\monitor_report_*.json

# View with Python
python -m json.tool logs\gpu_optimization\monitor_report_LATEST.json
```

**Key Metrics**:
- Peak VRAM usage per step
- Average GPU utilization
- Processing duration
- Temperature and power draw

---

## 📊 What to Expect

### Sample Output During Run
```
[  12.5s] scene_detect         | VRAM:  2100/ 16376 MB (12.8%) | GPU:  15% | Temp: 42°C | Power:  85.2W
[  45.3s] audio_transcribe     | VRAM:  4500/ 16376 MB (27.5%) | GPU:  82% | Temp: 64°C | Power: 185.2W
[ 125.8s] audio_diarize        | VRAM:  5800/ 16376 MB (35.4%) | GPU:  91% | Temp: 68°C | Power: 225.5W
[ 165.2s] face_embed           | VRAM:  3200/ 16376 MB (19.5%) | GPU:  75% | Temp: 65°C | Power: 175.0W
```

### Final Report Example
```
Step: audio_diarize
Duration: 4.2 minutes
Memory: Peak 5.8 GB (35.4%)
GPU Util: Average 88%, Peak 95%
Temperature: Average 66°C, Peak 70°C
Power: Average 210W, Peak 245W

Recommendation: OPTIMAL
  Current allocation: 35%
  Peak usage: 35.4%
  Status: Perfectly balanced ✅
```

---

## 🔍 Troubleshooting

### Issue: GPU Not Being Used
**Symptom**: GPU utilization stays at 0-5%

**Check**:
```bash
nvidia-smi  # Should show python processes when pipeline runs
python -c "import torch; print(torch.cuda.is_available())"  # Should be True
```

**Fix**: Verify GPU config was injected into steps

### Issue: Out of Memory
**Symptom**: `RuntimeError: CUDA out of memory`

**Fix**: Reduce allocation for the failing step
```bash
python scripts\gpu_config_tuner.py
# Then: set <step_name> <lower_percent>
# Then: save
```

### Issue: Still Slow
**Symptom**: No speedup vs before

**Possible Causes**:
1. CPU bottleneck (data loading)
2. I/O bottleneck (slow disk)
3. Small model (GPU faster than it can be fed)

**Diagnose**: Check nvidia-smi during run - GPU should be 70-90% utilized

---

## ⚙️ Advanced: Full Optimization

### Multi-Iteration Testing (1-2 hours)
```bash
# Run full optimization suite
RUN_GPU_OPTIMIZATION.bat
```

**What This Does**:
1. Runs pipeline 5 times
2. Monitors each iteration
3. Analyzes patterns
4. Adjusts allocations between runs
5. Generates final optimized config
6. Validates consistency

**Use When**:
- First time processing a new video type
- After major model/code changes
- Want absolute optimal performance

### Interactive Tuning
```bash
python scripts\gpu_config_tuner.py

# Commands:
list                        # Show current allocations
set audio_diarize 40        # Increase allocation
set face_embed 15           # Decrease allocation
save                        # Save changes
```

---

## 📈 Performance Targets

### Good Performance
- ✅ GPU utilization: 60-90%
- ✅ VRAM usage: 60-90% of allocated
- ✅ No OOM errors
- ✅ Temperature: <75°C

### Excellent Performance
- ✅ GPU utilization: 75-95%
- ✅ VRAM usage: 70-90% of allocated
- ✅ Consistent across iterations
- ✅ Temperature: <70°C
- ✅ 10-15x speedup vs CPU

---

## 📁 Important Files

### Configuration
- `steps/common/gpu_config.py` - Main config (edit allocations here)

### Tools
- `scripts/test_gpu_config.py` - Quick test
- `scripts/monitor_gpu_pipeline.py` - Real-time monitoring
- `scripts/gpu_config_tuner.py` - Interactive tuner
- `RUN_GPU_OPTIMIZATION.bat` - Full optimization suite

### Documentation
- `docs/GPU_OPTIMIZATION_GUIDE.md` - Complete guide
- `docs/GPU_OPTIMIZATION_SESSION_REPORT.md` - What was built
- `docs/GPU_QUICKSTART.md` - This file

### Reports
- `logs/gpu_optimization/monitor_report_*.json` - Monitoring results
- `logs/gpu_optimization/full_optimization_*.json` - Optimization results

---

## 🎯 Success Checklist

After running monitored pipeline:

- [ ] GPU utilization >70% during heavy steps
- [ ] No out-of-memory errors
- [ ] Temperature <75°C
- [ ] Processing completes successfully
- [ ] Report generated in logs/
- [ ] Pipeline 10-15x faster than before

If all checked: ✅ **GPU optimization successful!**

---

## 📞 Need Help?

1. **Check status**:
   ```bash
   python scripts\test_gpu_config.py
   nvidia-smi
   ```

2. **Review logs**:
   ```bash
   type logs\gpu_optimization\monitor_report_LATEST.json
   ```

3. **Consult docs**:
   - GPU_OPTIMIZATION_GUIDE.md (comprehensive)
   - GPU_OPTIMIZATION_SESSION_REPORT.md (implementation details)

---

## 🏁 Quick Command Reference

```bash
# Test GPU config
python scripts\test_gpu_config.py

# Run monitored pipeline
python scripts\monitor_gpu_pipeline.py

# Show current allocations
python scripts\gpu_config_tuner.py show

# Interactive tuning
python scripts\gpu_config_tuner.py

# Full optimization (1-2 hours)
RUN_GPU_OPTIMIZATION.bat

# Watch GPU in real-time
nvidia-smi -l 1
```

---

**That's it! You're ready to achieve 15x speedup!** 🚀

Start with Step 1 above and work your way through. Good luck!
