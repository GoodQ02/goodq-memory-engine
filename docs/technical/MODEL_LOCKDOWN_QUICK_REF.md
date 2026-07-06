<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Model Lockdown Quick Reference

## Commands

### Verify Lockdown (Daily)
```bash
scripts\VERIFY_MODEL_LOCKDOWN.bat
# or
conda activate goodq_core
python scripts/verify_model_lockdown.py
```

**Expected Output**: "✓ Lockdown verification PASSED - All models properly pinned!"

### Update Version Pins (When adding new models)
```bash
scripts\PIN_MODEL_VERSIONS.bat
# or
conda activate goodq_core
python scripts/pin_model_versions.py
```

**What it does**:
- Fetches latest commit SHAs from HuggingFace
- Updates model_registry.yaml
- Creates backup (.yaml.bak)
- Computes file hashes for external assets

### Bootstrap Models (Download)
```bash
conda activate goodq_core
python scripts/bootstrap_models.py
```

**What it does**:
- Reads pinned versions from registry
- Downloads at exact commit SHAs
- Skips cached models
- Reports versions used

## Key Files

| File | Purpose |
|------|---------|
| `configs/model_registry.yaml` | Central registry with all version pins |
| `archive/docs/status-reports/LOCKDOWN_STATUS.md` | Historical verification snapshot |
| `configs/model_registry.yaml.bak` | Automatic backup |
| `logs/model_pin_report.json` | Pin operation report |

## Adding a New Model

1. **Add to registry** (`configs/model_registry.yaml`):
   ```yaml
   huggingface_models:
     my_new_model:
       repo_id: "org/model-name"
       revision: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # Placeholder
       model_type: "text-classification"
       required: true
   ```

2. **Fetch real SHA**:
   ```bash
   python scripts/pin_model_versions.py
   ```

3. **Verify**:
   ```bash
   python scripts/verify_model_lockdown.py
   ```

4. **Download**:
   ```bash
   python scripts/bootstrap_models.py
   ```

5. **Commit**:
   ```bash
   git add configs/model_registry.yaml
   git commit -m "Add new model: org/model-name"
   ```

## Updating a Model

1. **Research**: Check changelog, breaking changes, test in isolation
2. **Update registry**: Edit `model_registry.yaml` with new revision SHA
3. **Verify**: Run `verify_model_lockdown.py`
4. **Test**: Process test files with new version
5. **Rollback if needed**: Restore from `.yaml.bak`
6. **Commit**: Document change in git

## Troubleshooting

### "Placeholder revision detected"
Run `pin_model_versions.py` to fetch real SHAs.

### "SHA256 hash mismatch"
File corrupted. Delete and re-download:
```bash
rm <GOODQ_DATA_ROOT>/models/path/to/file
python scripts/bootstrap_models.py
```

### "Authentication failed"
Set tokens in `.env.local`:
```bash
HF_TOKEN=hf_your_token_here
PYANNOTE_TOKEN=hf_your_token_here
```

### "Model not found in cache"
Download it:
```bash
python scripts/bootstrap_models.py
```

## Security Checklist

- [ ] `auto_update: false` in registry
- [ ] `manual_approval_required: true`
- [ ] All models have commit SHA or tag
- [ ] External assets have SHA256 hashes
- [ ] Gated models use secure token env vars
- [ ] Verification passes with 0 errors

## Status Indicators

| Symbol | Meaning |
|--------|---------|
| ✓ OK | Model properly pinned and verified |
| ⚠ Warning | Minor issue (e.g., tagged release instead of SHA) |
| ✗ Error | Critical issue (e.g., missing required file, hash mismatch) |

## Registry Structure

### HuggingFace Model Entry
```yaml
model_key:
  repo_id: "org/model-name"
  revision: "abc123...def789"  # 40-char commit SHA
  model_type: "vision-to-text"
  required: true
  requires_auth: false
```

### External Asset Entry
```yaml
asset_key:
  name: "Asset Name"
  source_url: "https://..."
  version: "1.0.0"
  sha256: "abc123...def789"
  local_path: "subdir/file.ext"
  file_size_bytes: 12345678
  required: true
```

## Best Practices

1. ✅ Always use commit SHAs, not branch names
2. ✅ Verify after every registry change
3. ✅ Backup before updates (automatic)
4. ✅ Test in staging before production
5. ✅ Document updates in git commits
6. ✅ Run verification in CI/CD
7. ✅ Review security advisories monthly

## Integration with Environment Isolation

Lockdown works with environment isolation:

```bash
# Environment isolation flags
PYTHONNOUSERSITE=1
PIP_NO_CACHE_DIR=1
pip install --no-user --no-cache-dir --isolated

# + Model lockdown
configs/model_registry.yaml (pinned versions)
```

Result: **Fully reproducible pipeline** across all environments and time.

## Quick Status Check

```bash
# One command to check everything
python scripts/verify_model_lockdown.py

# Look for:
# - "✓ Lockdown verification PASSED"
# - "✓ OK: 20" (all green)
# - "✗ Error: 0"
# - "Auto-update: False"
# - "Manual approval: True"
```

## Emergency Rollback

```bash
# 1. Restore registry backup
copy configs\model_registry.yaml.bak configs\model_registry.yaml

# 2. Re-download old versions
python scripts\bootstrap_models.py

# 3. Verify restoration
python scripts\verify_model_lockdown.py
```

## Daily Workflow

1. **Morning**: Run verification
   ```bash
   python scripts/verify_model_lockdown.py
   ```

2. **Work**: Make changes, add models as needed

3. **Before commit**: Verify again
   ```bash
   python scripts/verify_model_lockdown.py
   git add configs/model_registry.yaml
   git commit -m "..."
   ```

4. **CI/CD**: Automated verification runs

## Related Documentation

- [Full Guide](MODEL_LOCKDOWN.md) - Complete documentation
- [Historical Status Report](../../archive/docs/status-reports/LOCKDOWN_STATUS.md) - Archived verification snapshot
- [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md) - How it fits together

---

**Remember**: The lockdown system protects you from version drift. Keep it verified!
