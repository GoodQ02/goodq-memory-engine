# Model Lockdown System

## Overview

The GoodQ Model Lockdown System prevents version drift by pinning all external dependencies (models, datasets, and assets) to exact versions using commit SHAs, file hashes, and explicit version tags.

## Why Model Pinning?

Without version pinning:
- Models can auto-update to incompatible versions
- Results become non-reproducible across environments
- Breaking changes can silently break your pipeline
- Security vulnerabilities can be introduced without notice

With proper lockdown:
- ✓ Exact reproducibility across all environments
- ✓ No unexpected breaking changes
- ✓ Explicit control over updates
- ✓ Security through verification
- ✓ Audit trail of all model versions

## Architecture

### Model Registry (`configs/model_registry.yaml`)

Central registry containing:

1. **HuggingFace Models** - Pinned to exact commit SHAs
2. **External Models** - Verified with SHA256 hashes
3. **Lexicons & Datasets** - Version tracked
4. **System Tools** - Binary path and version info
5. **Update Policy** - Controls how updates are handled

### Key Scripts

| Script | Purpose |
|--------|---------|
| `pin_model_versions.py` | Fetch latest commit SHAs and update registry |
| `verify_model_lockdown.py` | Verify all models are properly pinned |
| `bootstrap_models.py` | Download models respecting registry pins |

## Usage

### Initial Setup

1. **Run the model version pinning script** (one-time or when adding models):
   ```bash
   conda activate goodq_zenml
   python scripts/pin_model_versions.py
   ```
   
   Or use the batch file:
   ```bash
   scripts\PIN_MODEL_VERSIONS.bat
   ```

   This will:
   - Connect to HuggingFace Hub
   - Fetch the latest commit SHA for each model
   - Update `model_registry.yaml` with real SHAs
   - Create a backup of the old registry
   - Compute file hashes for local assets

2. **Review the updated registry**:
   ```bash
   code configs\model_registry.yaml
   ```
   
   Check that placeholder revisions have been replaced with actual 40-character commit SHAs.

3. **Verify the lockdown**:
   ```bash
   python scripts/verify_model_lockdown.py
   ```
   
   Or use:
   ```bash
   scripts\VERIFY_MODEL_LOCKDOWN.bat
   ```

   This verifies:
   - All models have proper version pins
   - External assets match expected hashes
   - System tools are available
   - Update policy is secure

### Bootstrap Models with Lockdown

The bootstrap script automatically respects the registry:

```bash
conda activate goodq_zenml
python scripts/bootstrap_models.py
```

It will:
- Read pinned versions from `model_registry.yaml`
- Download models at exact commit SHAs
- Skip models that are already cached
- Report which versions were used

## Model Registry Structure

### HuggingFace Models

```yaml
huggingface_models:
  model_key:
    repo_id: "org/model-name"
    revision: "abc123...def789"  # 40-char commit SHA
    model_type: "vision-to-text"
    required: true
    requires_auth: false  # Set true for gated models
    auth_token_env: "HF_TOKEN"  # Environment variable for token
```

### External Models

```yaml
external_models:
  model_key:
    name: "Model Name"
    source_url: "https://..."
    version: "1.0.0"
    sha256: "abc123...def789"  # File integrity hash
    local_path: "subdir/model.pt"
    file_size_bytes: 12345678
    required: true
    model_type: "object-detection"
```

### Update Policy

```yaml
update_policy:
  auto_update: false  # NEVER auto-update
  security_updates_only: false
  manual_approval_required: true  # Explicit approval needed
  check_for_updates: false  # Don't check for newer versions
```

## Workflow

### Adding a New Model

1. Add entry to `model_registry.yaml`:
   ```yaml
   my_new_model:
     repo_id: "org/new-model"
     revision: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # Placeholder
     model_type: "text-classification"
     required: true
   ```

2. Run pin script to fetch real SHA:
   ```bash
   python scripts/pin_model_versions.py
   ```

3. Verify the pin:
   ```bash
   python scripts/verify_model_lockdown.py
   ```

4. Bootstrap to download:
   ```bash
   python scripts/bootstrap_models.py
   ```

### Updating a Model

1. **MANUAL PROCESS - Never automatic**
   
2. Research the new version:
   - Review changelog
   - Check for breaking changes
   - Test in isolated environment

3. Update `model_registry.yaml` with new revision SHA

4. Run verification:
   ```bash
   python scripts/verify_model_lockdown.py
   ```

5. Test thoroughly before committing

6. Document the change in git commit

### Emergency Rollback

If a model update causes issues:

1. Restore from backup:
   ```bash
   copy configs\model_registry.yaml.bak configs\model_registry.yaml
   ```

2. Re-download old version:
   ```bash
   python scripts/bootstrap_models.py
   ```

3. Verify restoration:
   ```bash
   python scripts/verify_model_lockdown.py
   ```

## Security Considerations

### SHA256 Verification

External models are verified using SHA256 hashes:
- Prevents file corruption
- Detects tampering
- Ensures download integrity

### Gated Models

For models requiring authentication:

```yaml
model_key:
  repo_id: "pyannote/speaker-diarization"
  revision: "..."
  requires_auth: true
  auth_token_env: "PYANNOTE_TOKEN"
```

Set token in `.env.local`:
```bash
PYANNOTE_TOKEN=hf_your_token_here
```

### Offline Mode

For air-gapped environments:

```yaml
verification:
  offline_mode: true  # Never download, only use cache
  allow_cache: true
```

## Best Practices

1. **Always use commit SHAs**, not branch names or tags
   - ✓ Good: `revision: "abc123def456..."`
   - ✗ Bad: `revision: "main"` (can change)
   - ⚠ Acceptable: `revision: "v1.0.0"` (tagged release)

2. **Verify after every change**
   - Run `verify_model_lockdown.py` after updates
   - Check CI/CD pipelines pass verification

3. **Document all changes**
   - Git commit messages should explain version changes
   - Note why a model was updated

4. **Test before production**
   - Use staging environment
   - Run full pipeline tests
   - Compare outputs against baseline

5. **Backup before updates**
   - `pin_model_versions.py` auto-creates backups
   - Keep multiple backup versions

6. **Monitor for security advisories**
   - Subscribe to model repo security alerts
   - Manually review and apply security updates

## Troubleshooting

### "Placeholder revision detected"

The registry has a placeholder SHA (all same character). Run:
```bash
python scripts/pin_model_versions.py
```

### "SHA256 hash mismatch"

File was corrupted or modified. Delete and re-download:
```bash
rm L:/models/path/to/model.pt
python scripts/bootstrap_models.py
```

### "Model not found in cache"

Run bootstrap to download:
```bash
python scripts/bootstrap_models.py
```

### Authentication failures

For gated models, ensure token is set:
```bash
set HF_TOKEN=hf_your_token_here
set PYANNOTE_TOKEN=hf_your_token_here
python scripts/bootstrap_models.py
```

## Integration with Environment Isolation

Model lockdown complements the environment isolation system:

```bash
# Install with isolation flags
PYTHONNOUSERSITE=1 \
PIP_NO_CACHE_DIR=1 \
pip install --no-user --no-cache-dir --isolated \
    --upgrade-strategy only-if-needed \
    -r requirements.txt
```

Combined benefits:
- Environment isolation prevents dependency bleed
- Model lockdown prevents version drift
- Together: fully reproducible pipeline

## Maintenance Schedule

| Task | Frequency | Command |
|------|-----------|---------|
| Verify lockdown | Daily (CI/CD) | `verify_model_lockdown.py` |
| Check for updates | Monthly | Manual review of model repos |
| Update models | Quarterly | Pin → Test → Deploy |
| Backup registry | Before updates | Auto (by pin script) |
| Security audit | Monthly | Review CVEs and advisories |

## Related Documentation

- [Environment Setup](../guides/install/INSTALL.md)
- [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md)
- Development Guide

## Support

For issues with model lockdown:
1. Check verification output for specific errors
2. Review this documentation
3. Check logs in `logs/model_pin_report.json`
4. See troubleshooting section above
