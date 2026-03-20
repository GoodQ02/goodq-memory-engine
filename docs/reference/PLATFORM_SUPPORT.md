<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Dual-Host Compatibility Contract (Desktop + Laptop)

## Purpose
Define a stable runtime contract that supports:
- **Desktop:** GPU-maximal execution.
- **Laptop:** GPU-optional execution with functional CPU-safe behavior.

This contract assumes **desktop is canonical** and laptop is follower.

---

## Host Roles (Non-Negotiable)

| Role | Contract |
|---|---|
| High-power desktop | Source of truth for data epochs, ingestion, and alignment state. |
| Portable laptop | Follower host; must align from desktop, not overwrite canonical state. |

Evidence: `AGENTS.md:17`, `AGENTS.md:18`, `AGENTS.md:38`.

---

## Mandatory Baseline Assumptions (Common to Both Hosts)

| Baseline assumption | Why mandatory | Evidence |
|---|---|---|
| Windows + Conda-run execution model | Current launch/orchestration assumes Windows shells and `conda run` bindings. | `AGENTS.md:17`, `AGENTS.md:47`, `LAUNCH_GOODQ.bat:6`, `scripts/_lib/interpreter_bindings.ps1:12` |
| Config loaded through `config_loader` with env expansion | Baseline portability depends on env-driven config resolution and `.env.local` loading. | `AGENTS.md:43`, `steps/common/config_loader.py:31`, `steps/common/config_loader.py:61`, `steps/common/config_loader.py:80` |
| Persistent local memory stores present | SQLite + Qdrant are treated as authoritative persistence layer in current contract. | `AGENTS.md:11`, `AGENTS.md:21`, `AGENTS.md:22`, `configs/config.yaml:46`, `configs/config.yaml:47`, `configs/config.yaml:139` |
| CPU-safe operation must be preserved | GPU setup is optional at runtime in multiple critical paths; CPU fallback is expected. | `steps/common/gpu_config.py:117`, `steps/common/gpu_config.py:120`, `steps/audio_diarize/step.py:73`, `steps/video_scene_detect/step.py:114`, `docs/guides/gpu/GPU_SETUP.md:293` |
| WSL binding is deterministic when enabled | Cross-host behavior should use distro-scoped invocation and a single distro variable. | `AGENTS.md:48`, `scripts/_lib/interpreter_bindings.ps1:4`, `scripts/_lib/interpreter_bindings.bat:7` |

---

## Performance-Tier Enhancements

### Profile: `BASELINE` (portable/default-safe)
- Goal: Full functional pipeline on CPU-safe paths (slower but operational).
- Intended host: Laptop or any host with uncertain GPU/WSL readiness.
- Behavior:
  - Disable automatic GPU activation.
  - Prefer CPU-safe scene/audio routes.
  - Treat WSL audio acceleration as optional.

Existing runtime hooks:
- `GOODQ_NO_AUTO_GPU=1` disables auto GPU config (`steps/common/gpu_config.py:178`, `steps/common/gpu_config.py:182`).
- Scene detection has CPU fallback (`steps/video_scene_detect/step.py:114`, `steps/video_scene_detect/step.py:119`).
- Audio transcription falls back to Windows/CPU if WSL or GPU path is unavailable (`steps/audio_transcribe/step.py:397`, `steps/audio_transcribe/step.py:432`, `steps/audio_transcribe/step.py:441`, `steps/audio_transcribe/step.py:481`).

### Profile: `GPU_ENHANCED` (desktop-maximal)
- Goal: Max throughput via CUDA + WSL2 accelerated audio.
- Intended host: Desktop with validated CUDA/WSL stack.
- Behavior:
  - Enable GPU memory tuning and mixed-precision inference.
  - Prefer WSL2 audio processing and CUDA-backed vision/audio inference.

Evidence:
- GPU profile defaults and CUDA pinning in config (`configs/config.yaml:112`, `configs/config.yaml:114`, `configs/config.yaml:115`).
- WSL2 bridge and CUDA env wiring (`scripts/wsl2_audio_bridge.py:18`, `scripts/wsl2_audio_bridge.py:73`, `wsl2_audio/setup_cuda_env.sh:12`).
- Phase 5 GPU scene flag (`configs/config.yaml:227`, `scripts/config_schema.py:211`).

---

## Proposed Environment Flags / Profiles

## Already present (usable now)
- `GOODQ_NO_AUTO_GPU` (`steps/common/gpu_config.py:178`).
- `GOODQ_WSL_DISTRO` (`AGENTS.md:48`, `scripts/_lib/interpreter_bindings.ps1:5`).

## Proposed contract flags (recommended)
- `GOODQ_HOST_PROFILE=BASELINE|GPU_ENHANCED`
- `GOODQ_ENABLE_GPU=0|1`
- `GOODQ_ENABLE_WSL_AUDIO=0|1`
- `GOODQ_REQUIRE_GPU=0|1` (if `1`, fail-fast instead of fallback)
- `GOODQ_REQUIRE_WSL_AUDIO=0|1` (if `1`, fail-fast when WSL audio unavailable)
- `GOODQ_QDRANT_REQUIRED=0|1`

## Proposed profile mapping
- `BASELINE`:
  - `GOODQ_NO_AUTO_GPU=1`
  - `GOODQ_ENABLE_GPU=0`
  - `GOODQ_ENABLE_WSL_AUDIO=0`
  - `GOODQ_REQUIRE_GPU=0`
  - `GOODQ_REQUIRE_WSL_AUDIO=0`
- `GPU_ENHANCED`:
  - `GOODQ_NO_AUTO_GPU=0`
  - `GOODQ_ENABLE_GPU=1`
  - `GOODQ_ENABLE_WSL_AUDIO=1`
  - `GOODQ_REQUIRE_GPU=1` (desktop only)
  - `GOODQ_REQUIRE_WSL_AUDIO=1` (desktop only)

---

## Hard Blockers For Portability

| Blocker | Impact | Evidence |
|---|---|---|
| Hardcoded Windows drive paths in canonical config/launch | Non-`L:` machines require manual edits/overrides before basic runtime works. | `configs/config.yaml:43`, `configs/config.yaml:53`, `LAUNCH_GOODQ.bat:5` |
| Hardcoded WSL user/workspace in bridge | Breaks on hosts where WSL user/path is not `joesdomingo` or layout differs. | `scripts/wsl2_audio_bridge.py:16`, `scripts/wsl2_audio_bridge.py:17` |
| WSL audio config defaults are CUDA-first | CPU-only WSL hosts may fail model init due to `device=cuda`/`float16` defaults. | `wsl2_audio/config.json:8`, `wsl2_audio/config.json:10`, `wsl2_audio/audio_service.py:174`, `wsl2_audio/audio_service.py:180` |
| Runtime contract drift: `goodq_zenml` vs `goodq_core` | Ambiguous baseline env breaks reproducibility between docs and launcher paths. | `docs/releases/SHIP_PROFILE.md:11`, `docs/releases/SHIP_PROFILE.md:80`, `LAUNCH_GOODQ.ps1:37`, `README.md:374` |
| Policy/docs still over-emphasize NVIDIA/CUDA | Can conflict with the desired GPU-optional portability target unless profile semantics stay explicit. | `AGENTS.md:19`, `AGENTS.md:45`, `docs/releases/SHIP_PROFILE.md:10`, `docs/guides/general/INSTALL.md:13` |

---

## Minimal Common Denominator Install (Both Hosts)

This is the smallest target that should keep system behavior functional without requiring GPU acceleration:

1. Windows host + repository checkout.
2. Python 3.10 + Conda available via `conda run` bindings.
3. One baseline orchestration env (recommend standardizing to one name and aliasing the other until drift is resolved).
4. Config loader stack (`pyyaml`, `python-dotenv`) and core Python runtime dependencies used by orchestration.
5. Local persistence services:
   - SQLite files for memory + KG.
   - Qdrant service on `6333` (canonical contract target).
6. FFmpeg on PATH (or configured tool path) for media slicing/extraction.
7. CPU-safe profile defaults (`BASELINE`) active.
8. `.env.local` present for secrets and host-specific overrides.

Evidence anchors:
- `setup.py:10`, `AGENTS.md:47`, `steps/common/config_loader.py:61`, `AGENTS.md:11`, `AGENTS.md:21`, `steps/common/qdrant_client.py:290`, `steps/common/tool_paths.py:33`.

---

## Compatibility Decision Rule

- If a host satisfies **Mandatory Baseline**, it is contract-compliant as `BASELINE` even without GPU.
- `GPU_ENHANCED` is an additive tier and must not be required for correctness.
- Desktop remains canonical for synchronization and epoch authority; laptop remains follower-only.
