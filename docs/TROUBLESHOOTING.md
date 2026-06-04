<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-20 -->

# Troubleshooting Guide

This is the current operator-facing troubleshooting guide for GoodQ4All.

Use this page for live issues in the supported runtime. Historical setup notes
and superseded failure modes belong in archived material, not here.

## Start Here

Run these first before changing anything:

```powershell
conda run -n goodq_core python scripts/system_readiness_check.py
conda run -n goodq_core python scripts/cache_readiness_check.py
Invoke-WebRequest http://127.0.0.1:6333/collections
```

If the issue involves accelerated audio, also verify the WSL truth surface:

```powershell
conda run -n goodq_core python scripts/wsl_audio_preflight.py
```

## What Counts As Healthy

A healthy current run can still include:

- occasional native vision-step crashes such as `image_caption`,
  `object_detect`, or `image_embed_dino`
- fallback or retry behavior on optional enrichments
- `speaker_voice_signature_meta.status = skipped` on scenes without enough
  diverse voiced speech

Those are not necessarily run failures if:

- the episode still finishes cleanly
- `phase6_complete = true`
- `qdrant_ok = true`
- the failing step is surfaced truthfully in artifacts

## System Will Not Start

Symptoms:

- launcher exits immediately
- health summary does not come up
- API docs are unavailable

Check:

```powershell
conda run -n goodq_core python scripts/system_readiness_check.py
Invoke-WebRequest http://127.0.0.1:6333/collections
```

Most common current causes:

- Qdrant is not reachable on `127.0.0.1:6333`
- `goodq_core` is unavailable or corrupted
- config or local cache surfaces are missing

## WSL Audio Not Ready

Symptoms:

- host-side preflight reports WSL audio degraded
- scenes show no speaker continuity on voiced material
- diarization is missing across an episode

Check:

```powershell
conda run -n goodq_core python scripts/wsl_audio_preflight.py
```

What matters now:

- `diarization_ready` means the sourced WSL runtime can load the configured
  diarization chain offline
- import success and token presence alone are not enough

If `diarization_ready = false`, inspect:

- `GOODQ_WSL_WORKSPACE`
- the active cache root selected by the sourced runtime
- whether the exact pyannote diarization repos exist in that active cache
- the WSL venv package pair:
  - `pyannote.audio==3.3.2`
  - `huggingface-hub==0.35.3`

If the error mentions `Pipeline.from_pretrained()` or `hf_hub_download()` with
unexpected `token` / `use_auth_token` arguments, treat it as WSL dependency
drift. Pull the latest repo and rerun the bootstrap/setup path so
`wsl2_audio/requirements-bootstrap-constraints.txt` is restaged into the WSL
workspace. Do not fix this with broad package upgrades.

Reference:

- `docs/reference/WSL_AUDIO_RUNTIME.md`

## Qdrant Not Reachable

Symptoms:

- `qdrant_ok = false`
- vector persistence fails
- collection check on port `6333` fails

Check:

```powershell
Invoke-WebRequest http://127.0.0.1:6333/collections
```

If Qdrant is down, restore the local service before treating ingestion as the
problem.

## A Run Looks Stuck

Symptoms:

- no scene progress for several minutes
- one episode appears frozen

Check the live episode log first, not old historical paths:

```text
reports/fresh_ingest_runs/<run_root>/<episode>_scene_context_llm/ingest.stdout.log
reports/fresh_ingest_runs/<run_root>/<episode>_scene_context_llm/ingest.stderr.log
```

Then inspect the canonical epoch artifacts:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<episode>/
```

Good questions to answer:

- is scene count still advancing?
- is WSL audio succeeding or downgrading?
- is the run retrying a native scene step but continuing?
- did the episode eventually write `scene_manifest.json` and `temporal_index.json`?

## Speaker Continuity Is Missing

If `speaker_count` is zero or absent across a voiced episode, inspect the
persisted scene truth before assuming the runtime failed.

Check:

- `scene_ingest_results.json`
- `scene_manifest.json`
- `temporal_index.json`

Look for:

- `speaker_count`
- `speaker_voice_signature_meta`
- `diarization_status`
- `diarization_error`
- `dominant_speaker_id`

Interpretation:

- if `diarization_status` is present and `speaker_count > 0`, the repaired
  speaker layer is active
- if `diarization_status = success` but signatures are skipped, that usually
  means insufficient voiced material, not a broken pipeline
- if these fields are missing entirely, treat that as a projection or
  persistence seam, not just a scene-quality issue

## Output Looks Too Literal Or Awkward

This is now usually a quality issue, not a wiring issue.

Examples from older witnesses included transcript-fragment style tags such as
awkward phrase lifts. Those are interpretation-normalization seams, not proof
that the pipeline failed.

If the run is otherwise healthy, inspect:

- `narrative_summary`
- `primary_tags`
- `dialogue_topics`
- transcript excerpts

Use that to separate:

- bad runtime truth
- conservative but correct truth
- low-quality phrase promotion

## Useful Current Artifact Paths

Run ledger:

```text
reports/fresh_ingest_runs/<run_root>/experiment_log.json
```

Episode output summary:

```text
reports/fresh_ingest_runs/<run_root>/<episode>_scene_context_llm/output/scene_ingest_results.json
```

Canonical persisted scene bundle:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<episode>/video/scene_manifest.json
```

Canonical temporal rollup:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<episode>/temporal_index.json
```

Knowledge graph:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
```

## Before Escalating

Verify:

- `phase6_complete = true`
- `qdrant_ok = true`
- `generic_context_detected = false`
- `speaker_count` and `diarization_status` on persisted outputs
- whether the issue is isolated to one scene, one episode, or the full run

That distinction matters. A single-scene optional failure and a broken witness
are not the same problem.

## Ingestion Watchdog Troubleshooting

### Stale Lock File Check
If the Ingestion Watchdog exits immediately or fails to start, a stale lock file might be present from a dead process. 

To clear this:
1. Verify if a python process running `cli.watchdog` is actually running.
2. If no process is running, locate the lock file:
   `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/logs/watchdog.lock`
3. Delete the `watchdog.lock` file or run `.\start_goodq_dev.ps1` (which automatically checks and removes stale locks on startup).

### Retry Behavior for Failed Ingestions
Files that failed ingestion (e.g. due to VRAM limits or transient errors) write a `failed` record to the watchdog state registry. The watchdog and API duplicate check are configured so that only `success` statuses skip ingestion. If a previous run failed, the watchdog will automatically re-queue and retry the file when re-scanned.

### Restarting the Dev Environment Background Services
If the Watchdog or API Server processes need to be restarted to enact changes, run the following in a local PowerShell console:

```powershell
# Navigate to the project root
cd <ProjectRoot>

# Terminate any orphaned/stale service sessions
Get-CimInstance Win32_Process -Filter "name = 'powershell.exe'" | Where-Object { $_.CommandLine -like "*api.server*" -or $_.CommandLine -like "*cli.watchdog*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Where-Object { $_.CommandLine -like "*api.server*" -or $_.CommandLine -like "*cli.watchdog*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Start the services persistently using the auto-start script
.\start_goodq_dev.ps1
```

## Related Docs

- `README.md`
- `docs/README.md`
- `docs/TESTING_GUIDE.md`
- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`

