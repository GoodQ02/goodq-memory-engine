<!-- DOC_BADGE: EXPERIMENTAL -->
<!-- DOC_STATUS: DRAFT_REVIEW -->
<!-- DOC_LAST_VERIFIED: 2026-08-08 -->

# Ingestion Capability Contract Design

## Goal

Make every ingestion run publish one canonical capability receipt that states
what ran, what degraded, what was blocked, why, and where the durable evidence
lives. Reconcile model provisioning, runtime step behavior, fallbacks, tests,
and installer packs so a declared capability cannot silently change meaning
between those surfaces.

## Governing Invariants

- CPU Baseline is the survival floor: it installs every distributable
  CPU-capable pack and produces the minimum truthful ingestion outcome on a
  machine with no usable GPU.
- GPU Enhanced is additive: it contains the complete CPU Baseline plus
  compatible distributable GPU packs. A GPU failure may downgrade to an
  equivalent CPU path when available; it may not silently remove capability.
- A run may halt only when the core ingestion contract cannot produce truthful
  durable output. Performance loss, unavailable optional enrichment, or an
  unsupported accelerator is not by itself a core-ingestion failure.
- Every skip, fallback, retry, blocked capability, and profile mismatch is
  durable, attributable, and visible in the final receipt.
- Public installers contain only sealed distributable packs. Personal installers
  may additionally consume sealed personal or agreement-gated packs from the
  private vault, but those packs have no public publication path.

## Existing Authorities Reused

| Authority | Role in this design |
|---|---|
| `cli/run_ingestion.py` | Sole runtime writer of the per-run capability receipt. |
| `steps/common/step_logger.py` | Durable per-step `step_runs.jsonl` truth. |
| Scene manifests and `scene_ingest_results.json` | Per-scene outcome and artifact truth. |
| `lib/control_recurrence_report.py` | Read-only aggregation, recurrence classification, and operator reporting. |
| `configs/model_registry.yaml` | Model intent: profile scope, gating, classification, and provision behavior. |
| `configs/offline_asset_catalog.yaml` | Installer eligibility, vault disposition, and capability-pack membership. |
| Personal asset vault contract | Source immutability, terms, and pack derivation boundary. |

No daemon, dashboard service, second evidence store, or parallel profile
registry is introduced.

## Capability Receipt

`cli.run_ingestion` writes `capability_receipt.json` beside its existing run
artifacts, on both successful and failed terminal paths. It is derived only
from existing structured evidence produced in that run.

The receipt contains:

- run identity, selected profile, terminal outcome, and schema version;
- core-ingestion outcome: `complete`, `degraded`, `blocked`, `failed`, or
  `not_applicable` with a reason;
- one row per capability with requested implementation, effective
  implementation, status, fallback/retry chain, affected scenes, limitation,
  and evidence references;
- a summary of required-core failures, optional skips, recovered fallbacks,
  and unresolved degraded capabilities;
- exact evidence paths for `step_runs.jsonl`, run warnings, scene results,
  scene manifest, and Phase 6/recurrence evidence when applicable.

The terminal prints a compact version of the same receipt. It must never claim
full capability when optional work was skipped, nor claim failure solely because
an optional capability is unavailable.

## Reconciliation Matrix

A deterministic, testable matrix is generated from the current repository. For
each capability, it joins:

1. model or tool registry metadata;
2. installer asset catalog disposition and pack scope;
3. runtime step owner and call-site continuation semantics;
4. fallback candidates and their hardware/profile conditions;
5. durable status field and receipt evidence source;
6. contract-test coverage.

The matrix has exactly one effective classification for each active capability:

- `core_required` — absence prevents a truthful core ingestion result;
- `enhancement_optional` — the scene may survive, but degradation is reported;
- `profile_optional` — available only to a selected CPU/GPU profile and reported
  as `not_applicable` outside it;
- `gated_personal` — valid only from an accepted personal sealed pack;
- `excluded` — unavailable to every installer and cannot be selected at runtime.

The matrix rejects contradictions, including an active required asset whose sole
runtime path is an unreported optional skip, a public pack referencing a
personal-only asset, and an installer-selected capability without a durable
runtime status surface.

## Profile and Pack Contract

### Public CPU Baseline

- Selects every sealed distributable CPU-capable pack.
- Excludes personal, agreement-gated, restricted, and hardware-incompatible
  packs.
- Uses CPU implementations or no-op `not_applicable` outcomes where a feature
  has no lawful CPU implementation.

### Public GPU Enhanced

- Selects all Public CPU Baseline packs plus every sealed compatible GPU pack.
- Uses GPU implementations preferentially and records every CPU fallback.
- Never treats GPU performance or availability alone as core failure.

### Personal Air-Gap

- Uses the same capability matrix and pack manifests.
- May include sealed personal and agreement-gated packs only after local
  acceptance/provenance validation.
- Performs no download, substitution, or partial installation during the
  offline installation or witness run.

## Error Handling

- Required-core failure: terminal receipt is `failed` or `blocked`, identifies
  the missing/failed capability, and exits nonzero.
- Optional failure: terminal receipt is `degraded`, identifies the capability
  and limitation, preserves the scene when its core contract survives, and
  exits according to the existing run outcome policy.
- Successful fallback: terminal receipt is `degraded` unless the declared
  capability contract defines the fallback as equivalent; original error and
  effective path remain visible.
- Intentional profile exclusion: terminal receipt is `not_applicable`, never
  `skipped` or silently absent.

## Validation

1. Unit tests create required failure, optional skip, CPU fallback, profile
   exclusion, and normal-success fixtures and assert receipt/console parity.
2. Matrix tests reject representative registry/runtime/catalog contradictions.
3. Installer contract tests prove CPU is a subset of GPU, public packs exclude
   personal assets, and personal builds cannot proceed without sealed acceptance
   evidence.
4. A clean isolated scene run produces a receipt whose evidence references
   resolve and whose capability rows agree with `step_runs.jsonl` and the scene
   manifest.
5. The existing control-recurrence report reads the receipt evidence without
   changing its read-only boundary and exposes the aggregate capability outcome.

## Scope and Rollback

This design changes ingestion observability, reconciliation validation, and
installer selection contracts. It does not alter model inference algorithms,
promotion semantics, personal corpus data, public-release publishing, or live
service topology.

Rollback is one coherent reversion of the receipt writer, matrix generator,
installer contract wiring, and their tests. Existing per-step logs and scene
artifacts remain authoritative throughout.
