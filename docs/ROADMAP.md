<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-14 -->

# GoodQ4All Public Preview Roadmap

## Purpose

This roadmap describes the narrow public-preview path for GoodQ4All after the
`0.1.1` Epistemic Memory Preview checkpoint.

It is not a product guarantee, installer seal, clinical or regulatory plan,
or autonomous-agent activation plan. It is a conservative map of the work most
likely to help a new operator clone the repo, bootstrap it, process one local
file, and inspect the first memory without weakening the local-first runtime
contract.

## Current Supported Surface

The supported public-preview surface is:

- local Windows-first bootstrap and validation
- API + CLI + Watchdog + persisted runtime artifacts
- scene manifests, temporal indexes, SQLite memory, knowledge graph state, and
  Qdrant vectors as local truth surfaces
- CPU-safe baseline behavior with optional GPU and WSL acceleration
- visible failure states for optional enrichments
- source, docs, configs, manifests, and small examples in Git
- versioned host-tool and offline payload evidence through release asset
  manifests, not expanded payloads in Git

## Current Non-Goals

GoodQ4All public preview does not currently ship:

- a production end-user UI
- Docker or Docker Compose support
- healthcare, clinical, compliance, or regulatory claims
- autonomous mutation, healing, or ControlAgent activation by default
- optional corpus, evaluation, witness, private, or copyrighted media payloads
  in the base installer
- cloud-required execution
- a post-1.0 stable public API guarantee

## Roadmap Tracks

### P0: Keep The Preview Honest And Runnable

Status: active release-readiness work.

- Keep `docs/guides/FIRST_RUN.md` as the shortest honest success loop.
- Keep `docs/reference/API.md` aligned with routes actually mounted in code.
- Keep `cli.print_config` and other operator surfaces sanitized by default.
- Keep public release packaging evidence separate from generated release
  assets.
- Keep README, release docs, and docs indexes aligned with the supported
  surface: API, CLI, Watchdog, and persisted artifacts.
- Add GitHub repository topics and concise discovery metadata outside the code
  tree.

### P1: Make First Success Easier

Status: recommended next polish after the public-preview checkpoint.

- Add an owned or permissively licensed synthetic demo fixture plus expected
  artifacts.
- Record a short demo GIF or video only after the synthetic fixture is
  selected and its rights are clear.
- Add a read-only status surface over existing health, Watchdog, and artifact
  data. It must not trigger ingestion, mutate memory, heal configs, or activate
  ControlAgent.
- Publish careful performance notes based on existing timing surfaces such as
  `step_runs.jsonl`, release evidence, and WSL audio timing probes.
- Improve model-cache operator messaging where it helps first-run clarity,
  while preserving the existing bootstrap and registry contract.

### P2: Packaging And Portability

Status: design and evidence work only unless separately approved.

- Continue moving large host tools and offline payloads toward GitHub Release
  assets with manifests, checksums, source URLs, license evidence, restore
  locations, and validation commands.
- Keep required runtime model caches separate from optional dataset, corpus,
  reference-pack, witness, and private-memory payloads.
- Explore Linux support only after the Windows-first path remains stable and
  observable.
- Treat macOS as a future portability target, not a current promise.
- Treat Docker or Docker Compose as an experimental future lane, not a
  supported public-preview install path.

### P3: Contributor Growth

Status: later public-facing polish.

- Add issue templates and contributor labels once the first public feedback
  loop is real.
- Expand docs around safe fixture creation, release asset validation, and
  read-only UI contribution boundaries.
- Add public examples only when the media, source evidence, and expected
  artifacts are owned, synthetic, or clearly redistributable.
- Keep all claims evidence-backed and avoid turning historical reports into
  active release promises.

## Decision Gates

Before any item moves from roadmap to supported surface:

- The change must preserve the canonical ingest path: Watchdog and
  `cli.run_ingestion` remain the automation and processing owners.
- Runtime truth must remain scene-centric and artifact-backed.
- Optional enrichments must fail visibly rather than silently.
- New public fixtures must have explicit source and license evidence.
- New dashboards must be read-only unless a separate control-surface design is
  approved.
- New performance claims must cite current evidence and avoid universal
  hardware promises.
- New packaging work must keep generated archives, model caches, corpus packs,
  witness outputs, and private material out of tracked Git history.

## Related Docs

- First run: [`docs/guides/FIRST_RUN.md`](guides/FIRST_RUN.md)
- Release checkpoint: [`docs/releases/RELEASE_0.1.1.md`](releases/RELEASE_0.1.1.md)
- Shipping profile: [`docs/releases/SHIP_PROFILE.md`](releases/SHIP_PROFILE.md)
- API reference: [`docs/reference/API.md`](reference/API.md)
- Vendor payload exit plan: [`docs/releases/VENDOR_PAYLOAD_EXIT_PLAN.md`](releases/VENDOR_PAYLOAD_EXIT_PLAN.md)
- Offline release asset model: [`docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md`](bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md)
