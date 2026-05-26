<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: VERIFIED_CHECKLIST -->
<!-- DOC_LAST_VERIFIED: 2026-04-02 -->

# Repo-Grounded Cleanup Checklist

This checklist is based on direct repo verification, not external research alone.
Use it as the working list for duplicate-launcher, legacy-WSL, and environment-sprawl cleanup.

## Scope

- Focus on active operator confusion, dead automation, and duplicated execution doctrines.
- Do not use this checklist to justify broad refactors.
- Treat canonical runtime and architecture docs as already aligned unless this checklist says otherwise.

## Status Buckets

- **Verified True**: confirmed in the current repo and still actionable.
- **Already Fixed**: historically true, but no longer an active issue in current canonical docs or runtime.
- **Defer / Archive**: real drift exists, but it is historical, diagnostic, or low priority compared with runtime/operator confusion.

## Verified True

No active verified-true cleanup items remain in the current operator/runtime
surface. Historical and archive material may still mention removed doctrines, but
the live repo surface is now aligned.

## Already Fixed

| Area | Verified files | Current truth |
| --- | --- | --- |
| Canonical front door clarity | [README.md](../../README.md), [AGENTS.md](../../AGENTS.md), [CLI-REFERENCE.md](../CLI-REFERENCE.md) | Canonical entrypoints are now clearly described through bootstrap, launcher, and `cli.run_ingestion`. |
| Dead WSL toggle automation | [QUICK_START.md](../../wsl2_audio/QUICK_START.md), [README.md](../../wsl2_audio/README.md), [SCRIPT_REGISTRY.md](../../archive/docs/bootstrap/SCRIPT_REGISTRY.md) | The deleted toggle script is no longer part of the active repo surface, and operator docs now point to the canonical runtime selection model instead of pipeline-file edits. |
| Stale WSL setup references | [INSTALL_WSL2_AUDIO.bat](../../scripts/INSTALL_WSL2_AUDIO.bat), [QUICK_START.md](../../wsl2_audio/QUICK_START.md), [QUICK_REFERENCE_WSL2.md](../guides/wsl2/QUICK_REFERENCE_WSL2.md) | Active WSL setup/operator docs now point to the current setup guide, runtime reference, and canonical launcher names. |
| Parallel WSL doctrine | [audio_bridge.py](../../wsl2_audio/audio_bridge.py), [step_wsl2.py](../../steps/audio_transcribe/step_wsl2.py), [step_wsl2.py](../../steps/audio_diarize/step_wsl2.py), [step_wsl2.py](../../steps/audio_ingest_unified/step_wsl2.py) | Legacy helper surfaces now adapter-wrap to the canonical unified bridge instead of maintaining a second execution doctrine. |
| Active runtime/doc path drift | [SCENE_MANIFEST_SPECIFICATION.md](../SCENE_MANIFEST_SPECIFICATION.md), [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md), [ARCHITECTURE_REFERENCE.md](../architecture/ARCHITECTURE_REFERENCE.md), [MEMORY_STORAGE.md](../architecture/MEMORY_STORAGE.md), [PHASE6_MULTIMODAL_FUSION.md](../PHASE6_MULTIMODAL_FUSION.md) | Canonical docs now describe epoch-scoped storage, direct unified WSL audio, operational Phase 6, and Qdrant as canonical. |
| Identity layer documentation | [IDENTITY_STITCHING_CONTRACT.md](../architecture/IDENTITY_STITCHING_CONTRACT.md), [goodq4all_agent_status.md](../goodq4all_agent_status.md) | The stitching ladder is now documented as a core truth layer, not buried in side notes. |
| Legacy launcher clutter | [LAUNCH_GOODQ.ps1](../../LAUNCH_GOODQ.ps1), [LAUNCH_GOODQ.bat](../../LAUNCH_GOODQ.bat) | The only supported launch surfaces are now the repo-root canonical launcher and wrapper. The older legacy launchers were removed from the active repo surface. |
| Step-env sprawl by default | [prepare_step_envs.ps1](../../scripts/prepare_step_envs.ps1), [README.md](../../envs/locks/README.md) | The manual repair surface now provisions the supported step-env pack by default and supports explicit `-Steps` for narrower repairs. |
| Tracked step backup siblings | [steps/](../../steps), [.gitignore](../../.gitignore) | The `17` tracked `steps/*/step.py.backup_*` siblings were removed from the active source tree after reference audit proved no active runtime/test consumers; future `*.backup*` files are ignored. |
| Root scene-detection config relic | [CONFIG_LOADING_CONTRACT.md](../architecture/CONFIG_LOADING_CONTRACT.md), [config_loader.py](../../steps/common/config_loader.py), [step.py](../../steps/video_scene_detect/step.py) | The retired root `config.json` override and obsolete fixer/monitor helper scripts were removed; canonical runtime config remains `configs/config.yaml` through `steps.common.config_loader`. |
| Historical artifact-path docs | [ARTIFACT_LOCATION_CONTRACT.md](../technical/ARTIFACT_LOCATION_CONTRACT.md), [PIPELINE_RESTORATION_BACKLOG.md](../technical/PIPELINE_RESTORATION_BACKLOG.md) | These docs are now explicitly marked historical/reference-only instead of reading like current operator truth. |
| Historical pipeline references | [PHASE5_FINAL_ACTIVATION_SUMMARY.md](../technical/PHASE5_FINAL_ACTIVATION_SUMMARY.md), [PIPELINES.md](../architecture/PIPELINES.md) | These docs now explicitly mark legacy orchestration references as historical/reference-only rather than active runtime doctrine. |

## Defer / Archive

| Area | Verified files | Why it should not interrupt current work |
| --- | --- | --- |
| Bootstrap/doc inventory surfaces | [doc_authority_map.md](./doc_authority_map.md), [runtime_path_authority_audit.py](../../scripts/docs/runtime_path_authority_audit.py) | These are inventory and audit tools, not runtime/operator guidance. Keep them honest later, but do not let them drive cleanup before active confusion is removed. |

## Recommended Execution Order

1. Keep future cleanup limited to historical/archive surfaces unless a new active operator contradiction is discovered.

## Non-Action Rules

- Do not use this checklist to justify rewriting the canonical launcher or ingestion runtime.
- Do not delete historical material without preserving an archive path or a clear note.
- Do not combine launcher cleanup, WSL doctrine cleanup, and env-pack narrowing into one commit.
- Validate each item independently before moving to the next.
