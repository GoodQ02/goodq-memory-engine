# Environment Lock Files

**Generated:** October 6, 2025  
**Purpose:** Reproducible environment builds with exact package versions

---

## 📦 What Are Lock Files?

Lock files contain the **exact versions** of all packages (including transitive dependencies) installed in each environment. This ensures:

- **Reproducibility:** Rebuild environments with identical package versions
- **Stability:** Prevent accidental upgrades breaking functionality
- **Security:** Know exactly what's installed (audit trail)
- **Debugging:** Pin to known-good versions when troubleshooting

---

## 🔒 Lock File Format

Each `.lock.txt` file is generated with `pip freeze` and contains lines like:
```
torch==2.3.1+cu121
transformers==4.43.3
numpy==1.26.4
...
```

**Format:** `package==version` with optional version specifiers (+cu121 for CUDA builds, etc.)

---

## 🔄 Using Lock Files

### Recreate Environment from Lock

```powershell
# Create fresh environment
conda create -n goodq_<step> python=3.10 -y

# Install from lock file
conda run -n goodq_<step> pip install -r locks/<step>.lock.txt --no-cache-dir
```

### Update Lock After Changes

```powershell
# After modifying requirements.txt and installing:
conda run -n goodq_<step> pip freeze > envs/locks/<step>.lock.txt
```

### Compare Environments

```powershell
# Check differences between lock files
Compare-Object `
    (Get-Content envs/locks/audio_emotion.lock.txt) `
    (Get-Content envs/locks/audio_transcribe.lock.txt)
```

---

## 📋 Lock File Inventory

| Environment | Packages | Lock File |
|-------------|----------|-----------|
| audio_diarize | 203 | audio_diarize.lock.txt |
| audio_embed | 166 | audio_embed.lock.txt |
| audio_emotion | 165 | audio_emotion.lock.txt |
| audio_metadata | 161 | audio_metadata.lock.txt |
| audio_transcribe | 157 | audio_transcribe.lock.txt |
| emotion_classify | 153 | emotion_classify.lock.txt |
| face_embed | 66 | face_embed.lock.txt |
| home_assistant_status | 145 | home_assistant_status.lock.txt |
| image_caption | 156 | image_caption.lock.txt |
| llm_chat | 145 | llm_chat.lock.txt |
| object_detect | 162 | object_detect.lock.txt |
| object_track | 146 | object_track.lock.txt |
| object_track_yolo | 152 | object_track_yolo.lock.txt |
| ocr | 147 | ocr.lock.txt |
| pdf_text | 145 | pdf_text.lock.txt |
| sentiment | 152 | sentiment.lock.txt |
| system_metrics | 148 | system_metrics.lock.txt |
| tagger | 152 | tagger.lock.txt |
| text_embed | 162 | text_embed.lock.txt |
| tts | 145 | tts.lock.txt |
| video_scene_detect | 147 | video_scene_detect.lock.txt |
| zenml | 171 | zenml.lock.txt |

**Total:** 22 environments, 3,340 packages locked

---

## ⚠️ Important Notes

### When to Update Locks

**DO update** locks when:
- ✅ You intentionally upgrade a package
- ✅ You add a new dependency
- ✅ Security patches are applied
- ✅ Validated changes work correctly

**DON'T update** locks when:
- ❌ Random `pip install --upgrade` runs
- ❌ Unverified package changes
- ❌ Before testing changes
- ❌ During troubleshooting (use locks to restore!)

### Version Conflicts

If you see errors like `ERROR: pip's dependency resolver does not currently take into account all the packages...`:

1. **Check requirements.txt** - Ensure no conflicting pins
2. **Use lock file** - Install from working lock, don't resolve fresh
3. **Test incrementally** - Update one package at a time
4. **Document reasons** - Why each version matters

### CUDA-Specific Builds

Many packages have `+cu121` suffix (CUDA 12.1):
```
torch==2.3.1+cu121
torchvision==0.18.1+cu121
torchaudio==2.3.1+cu121
```

**Important:** When installing from locks, use PyTorch's index:
```powershell
pip install -r locks/<step>.lock.txt `
    --extra-index-url https://download.pytorch.org/whl/cu121
```

---

## 🔧 Maintenance

### Regenerate All Locks

```powershell
# Use provided script
pwsh scripts/lock_envs.ps1
```

### Validate Lock Files

```powershell
# Verify each environment matches its lock
foreach ($env in (conda env list | Select-String "goodq_")) {
    $envName = ($env -split '\s+')[0]
    $step = $envName -replace '^goodq_', ''
    $lockFile = "envs/locks/$step.lock.txt"
    
    Write-Host "Validating $envName..." -ForegroundColor Cyan
    $current = conda run -n $envName pip freeze | Sort-Object
    $locked = Get-Content $lockFile | Sort-Object
    
    $diff = Compare-Object $current $locked
    if ($diff) {
        Write-Host "  Differences found!" -ForegroundColor Yellow
        $diff | Format-Table
    } else {
        Write-Host "  ✓ Matches lock file" -ForegroundColor Green
    }
}
```

---

## 📚 Best Practices

### 1. Git Tracking

Lock files **SHOULD** be committed to git:
```powershell
git add envs/locks/*.lock.txt
git commit -m "Lock environment dependencies"
```

### 2. Documentation

When updating locks, document WHY:
```
commit message:
Update audio_emotion lock: PyTorch 2.3.1 → 2.4.0 for CUDA 12.2 support
```

### 3. Testing After Lock Changes

Always test after updating locks:
```powershell
# Run smoke test
pwsh scripts/ingest_videos_lite.ps1 -MaxVideos 1 -MaxScenes 1

# Check for errors
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 100 | `
    Select-String '"status":"error"'
```

### 4. Rollback Strategy

Keep old locks in git history:
```powershell
# Revert to previous lock
git checkout HEAD~1 envs/locks/audio_emotion.lock.txt

# Reinstall
conda run -n goodq_audio_emotion pip install -r envs/locks/audio_emotion.lock.txt --force-reinstall
```

---

## 🚀 CI/CD Integration

For automated builds:

```yaml
# Example GitHub Actions
- name: Create Environment
  run: conda create -n test_env python=3.10 -y

- name: Install from Lock
  run: |
    conda run -n test_env pip install -r envs/locks/<step>.lock.txt \
      --no-cache-dir \
      --no-user \
      --isolated

- name: Verify Installation
  run: conda run -n test_env python -c "import torch; print(torch.__version__)"
```

---

## 🎯 Quick Reference

| Action | Command |
|--------|---------|
| Generate lock | `conda run -n <env> pip freeze > envs/locks/<step>.lock.txt` |
| Install from lock | `conda run -n <env> pip install -r envs/locks/<step>.lock.txt` |
| Compare locks | `Compare-Object (Get-Content lock1.txt) (Get-Content lock2.txt)` |
| Validate match | `conda run -n <env> pip freeze | Compare-Object - (Get-Content lock.txt)` |
| Regenerate all | `pwsh scripts/lock_envs.ps1` |

---

*Lock files last generated: October 6, 2025*

**Remember:** Lock files are your safety net. When in doubt, restore from locks rather than trying to resolve dependencies manually!
