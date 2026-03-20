# Changelog

This changelog tracks public-facing GoodQ4All milestones and release-readiness
checkpoints.

It is intentionally lightweight. Historical phase-by-phase notes, internal
audits, and archived release artifacts remain under [`docs/archive/`](docs/archive/)
and related canonical docs.

## [Unreleased]

- Ongoing doc cleanup and archive alignment around the remaining historical
  surfaces.

## [0.1.0] - 2026-03-20

Reference checkpoint:
[`docs/releases/RELEASE_0.1.0.md`](docs/releases/RELEASE_0.1.0.md)

### Release Highlights

- Fresh-machine Windows bootstrap is now a supported path through
  `python scripts/bootstrap_install.py`.
- The active release surface is aligned around the canonical local API, CLI,
  watchdog, bootstrap, and persisted runtime artifacts.
- `BASELINE` remains CPU-safe by default while GPU/WSL acceleration stays
  additive and optional.
- The API contract is aligned around loopback host `127.0.0.1` and port
  `30000`.
- Qdrant is handled consistently as a Windows service-first dependency.
- Forward-facing docs, quick references, and support indexes were rewritten to
  reflect the real launcher/API/watchdog contract.
- Large legacy clusters were retired or archived from the active support
  surface, including obsolete UI scaffolding, legacy orchestration surfaces,
  process-manager residue, and raw vLLM direct-start helpers.
- Second-wave historical docs were quarantined out of the active support
  surface, with current GPU/LLM/WSL/Watchdog indexes and technical refs
  retargeted to canonical docs or explicit archive paths.
- Documentation governance now guards against active drive-root drift,
  corrupted characters, and generated snapshots that overclaim authority.

### Validation

- Local CI-equivalent baseline passed with `python -m pytest -q`.
- Active documentation governance lint passed with
  `python scripts/docs/doc_drift_lint.py`.
- Fresh laptop bootstrap succeeded after bootstrap hardening.
- Forced-ingest runtime sanity validation succeeded after the Windows audio
  fallback repair.

## [2026-03-10] Public Readiness Checkpoint

Tag: `public-readiness-2026-03-10`

### Added

- Portable bootstrap installer entrypoint via
  [`scripts/bootstrap_install.py`](scripts/bootstrap_install.py)
- Public install environment definition in
  [`environment.yml`](environment.yml)
- Baseline GitHub Actions CI and CodeQL workflows under
  [`.github/workflows/`](.github/workflows/)
- Root public changelog for release-facing milestones

### Changed

- Sanitized public configuration surface with example/local override patterns
- Public docs aligned to the canonical runtime surface and bootstrap path
- API/package/public-doc version reporting unified around a single shared
  version constant
- Launcher isolation defaults aligned to `PYTHONNOUSERSITE=1`
- API CORS defaults tightened to config-gated localhost-only behavior
- Qdrant vendor config now binds to `127.0.0.1` by default

### Removed From Public Surface

- Private runtime snapshots and machine-local report artifacts
- Copyright-sensitive Seinfeld-derived text artifacts
- Tracked env-style local files in favor of example/template variants

## [2026-03-09] Season 1 Witness Baseline

Tag: `season1-witness-run-2026-03-09`

### Added

- Formal witness-run publication bundle for the five-episode control set
- Clean-release experiment summary in
  [`docs/experiments/SEINFELD_EXPERIMENT_SUMMARY.md`](docs/experiments/SEINFELD_EXPERIMENT_SUMMARY.md)

### Validated

- `185` scenes processed across Season 1 control media
- `182/185` transcript-bearing scenes
- `0` processing-error scenes
- WSL audio effective across all witness scenes
- Typed KG and vector persistence preserved under clean reruns

## Historical Notes

- Older internal milestones and phase reports remain archived under
  [`docs/archive/`](docs/archive/).
- Legacy runtime tags remain in Git history for internal traceability, but this
  changelog focuses on current public-facing release checkpoints.
