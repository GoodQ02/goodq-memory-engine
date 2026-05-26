<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/releases/SHIP_PROFILE.md -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Release Checkpoint - 2026-02-10

## Scope
- Stabilize test execution path and remove collection crashes.
- Fix watchdog registry deadlock.
- Fix diarization CUDA import/fallback behavior and add regression coverage.
- Remove tracked secrets and enforce env-driven resolution paths.
- Align AGENTS protocol location to repository root.
- Update local `origin` remote URL to canonical repository location.

## Landed Commits (Ordered)
1. `ca90278` - fix (wsl2_audio): correct dataclass field ordering for AudioJob
2. `8711533` - test: stabilize pytest discovery for runnable unit suite
3. `880c06c` - watchdog: remove ProcessedRegistry lock re-entry deadlock
4. `a97f734` - audio_diarize: fix CUDA torch import scope and error handling
5. `f7a7f96` - security: remove tracked credentials and use env references
6. `4ddbd41` - security: remove remaining implicit token fallback in readiness check
7. `1606753` - test: align config values test with canonical loader contract
8. `fbaf8f2` - docs: relocate AGENTS protocol to repository root

## Validation Commands and Results
```powershell
python -m pytest -q
```
- Result: `23 passed`

```powershell
python -m pytest -q tests/unit/test_watchdog_registry_deadlock.py tests/unit/test_audio_diarize_cuda_path.py
```
- Result: `5 passed`

```powershell
rg -n "hf_[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}" --glob '!archive/**' --glob '!vendor/**' .
```
- Result: no matches for live secret-like token patterns in tracked files.

```powershell
git remote -v
```
- Result: `origin` points to `https://github.com/JoesDomingo/Goodq4all.git` for fetch/push.

## Rollback Points
- Revert latest checkpoint doc move:
  - `git revert fbaf8f2`
- Revert config/test/security sequence incrementally (newest to oldest):
  - `git revert 1606753`
  - `git revert 4ddbd41`
  - `git revert f7a7f96`
  - `git revert a97f734`
  - `git revert 880c06c`
  - `git revert 8711533`
  - `git revert ca90278`

## Notes
- Local uncommitted runtime change exists in `wsl2_audio/bridge_config.json` and was intentionally excluded from release commits.
