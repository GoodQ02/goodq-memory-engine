<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: DRAFT -->
<!-- DOC_LAST_VERIFIED: 2026-05-14 -->

# GoodQ4All 0.1.1 Public Preview Draft

## Purpose

This draft prepares the public-facing release note, release checklist, and short
announcement copy for GoodQ4All `0.1.1` while final bootstrap evidence is still
being collected.

Do not publish this as a GitHub Release until the final first-run bootstrap gate
has passed and the operator has approved release publication.

## Draft GitHub Release Notes

Title:

`GoodQ4All 0.1.1 - Epistemic Memory Preview`

Summary:

GoodQ4All `0.1.1` is an early public preview of a local-first multimodal memory
system for scene-level video, audio, and text intelligence.

This release is intentionally narrow. It is meant to show the project identity,
the epistemic read model, the first memory loop, and the supported local runtime
surface. It is not a finished consumer product, a healthcare or compliance
system, a polished UI release, or an autonomous control-agent release.

What this preview proves:

- Windows-first local bootstrap and validation path.
- API, CLI, Watchdog, and persisted artifacts as the supported operator
  surfaces.
- Scene manifests and temporal indexes as durable memory truth surfaces.
- Phase 6 harmonization as the final step that turns per-scene outputs into
  coherent temporal and vector memory.
- CPU-safe baseline behavior with optional GPU and WSL acceleration.
- Visible optional-enrichment failures instead of silent success masking.
- Sanitized operator config display and public-safe release evidence.

What is not included:

- No production end-user UI.
- No Docker or Docker Compose support yet.
- No healthcare, clinical, compliance, or regulatory claims.
- No autonomous mutation, healing, or ControlAgent activation by default.
- No optional corpus, evaluation, witness, private, or copyrighted media
  payloads in the base installer.
- No post-1.0 API stability guarantee.

Start here:

- First run: `docs/guides/FIRST_RUN.md`
- Release checkpoint: `docs/releases/RELEASE_0.1.1.md`
- Shipping profile: `docs/releases/SHIP_PROFILE.md`
- Roadmap: `docs/ROADMAP.md`

Host-tools note:

The source repo remains the source, docs, configs, manifests, and small-example
surface. Host tools and large payloads belong in release assets with manifests,
checksums, source evidence, license evidence, restore locations, and validation
commands. The sealed host-tools asset evidence applies only to the exact asset
name and checksum recorded in `docs/releases/VENDOR_PAYLOAD_EXIT_PLAN.md`.

## Pre-Publish Checklist

- [ ] Public repository visibility confirmed.
- [ ] Default branch confirmed as `main`.
- [ ] `main` protected by active ruleset.
- [ ] Latest CI passes on the release commit.
- [ ] Latest CodeQL passes on the release commit.
- [ ] Secret scanning alerts checked or owner-verified.
- [ ] Dependabot alerts checked or owner-verified.
- [ ] Code scanning alerts checked or owner-verified.
- [ ] No open release-blocking PRs or issues.
- [ ] Final bootstrap first-run evidence captured.
- [ ] `docs/guides/FIRST_RUN.md` still matches the observed first-run path.
- [ ] Host-tools asset, if attached, matches the documented SHA256.
- [ ] No generated archives, model caches, runtime databases, logs, raw media,
  private memory, witness outputs, or optional corpus/eval packs are committed.
- [ ] Release notes preserve the public-preview boundary.

Stop publication if any of these are true:

- Bootstrap cannot complete the supported first-run path.
- Operator config or logs expose secrets or raw local config.
- Optional corpus, witness, private, or copyrighted media appears in release
  assets or tracked files.
- Release text implies a finished product, medical product, autonomous agent,
  sealed offline installer, polished UI, or post-1.0 stable API.

## Short Public Announcement Draft

GoodQ4All `0.1.1` is now available as an Epistemic Memory Preview.

It is a Windows-first, local-first memory system that ingests media into
scene-level artifacts, keeps the proof path visible, and exposes API, CLI,
Watchdog, and persisted memory surfaces for inspection.

This is not a finished app. It is a public checkpoint for the core idea:
machine memory should earn every claim it makes.

Start with one file:

`docs/guides/FIRST_RUN.md`

## Landing Polish Notes

Current landing posture is sufficient for public preview:

- `README.md` routes new users to the first success loop near the top.
- `docs/README.md` lists `FIRST_RUN.md` under Start Here.
- `docs/ROADMAP.md` is public-preview scoped and avoids product, clinical,
  Docker, offline-installer, and autonomous-control overclaims.
- Repository topics and the short GitHub description should be kept concise and
  searchable.

Suggested repository description:

`Local-first multimodal epistemic memory for scene-level video, audio, and text intelligence.`

Suggested topics:

`local-first`, `multimodal`, `memory-system`, `epistemic-ai`,
`computer-vision`, `audio-processing`, `knowledge-graph`, `qdrant`, `windows`,
`offline-first`
