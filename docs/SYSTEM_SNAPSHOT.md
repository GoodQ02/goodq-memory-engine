<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-04-08 -->

# System Snapshot

_Generated: 2026-04-08T07:35:00_

## Host & OS
- Hostname: GOOD-CUBE
- OS: Windows 10 Pro (10.0.26200)
- Architecture: AMD64
- Timezone: Central Standard Time

## CPU / Memory
- CPU: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel
- RAM: 68465905664

## GPU
- GPU(s): NVIDIA GeForce RTX 4070 Ti SUPER
- CUDA: 595.79

## Storage (Top-Level)
- System volume: total=3352GB free=2074GB
- Workspace volume: total=3353GB free=3249GB

## Toolchain
- Python: Python 3.13.11
- Conda: conda 25.11.1
- Git: git version 2.53.0.windows.1
- Node: v24.14.0
- Codex CLI: unavailable

## Installed Host Tools
- FFmpeg: present
- Tesseract: present
- Poppler / `pdftotext`: present
- Piper: present
- Qdrant / NSSM payloads: present

## WSL
- WSL enabled: Default Distribution: Ubuntu-22.04 | Default Version: 2 | WSL1 is not supported with your current machine configuration. | Please enable the "Windows Subsystem for Linux" optional component to use WSL1.
- Distros: NAME            STATE           VERSION | * Ubuntu-22.04    Stopped         2

## Local Services (Presence Check)
- Qdrant (6333): reachable
- Ollama (unknown): unavailable
- LM Studio (1234): not reachable

## Offline Packaging State
- Workspace-adjacent machine-audit pack: present
- Workspace-adjacent offline bundle root: present
- Repo payload staged into offline bundle: present
- Transport reconciliation final gap report: `HIGH` confidence
- Phase 1 self-extracting installer: present
- Closure state:
  - Linux wheels: complete
  - Windows wheels: complete
  - Host payloads: complete
- Current large local asset work:
  - required model cache: present locally
  - NRC lexicon: present locally
  - dataset prefetch: active / large cache already materialized

## Benchmark State
- Monitored 2-episode baseline rerun: successful
- Current monitored benchmark root: `../scratch/debug_runs/two_episode_baseline_verify_monitored_20260408/`
- Fresh canonical outputs confirmed perception wiring for:
  - visible person-object counts
  - audio emotion
  - music event rollups
  - time-hint rollups
  - speaker voice-signature coverage
- Completed full-season benchmark witness: `reports/fresh_ingest_runs/20260408_070502_season1_main_benchmark_witness/`
- Benchmark commit: `31fd533`
- Benchmark memo: `docs/testing/SEASON1_MAIN_BENCHMARK_MEMO_2026-04-08.md`
