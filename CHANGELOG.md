# Changelog

This changelog tracks public-facing GoodQ4All milestones and release-readiness
checkpoints.

It is intentionally lightweight. Historical phase-by-phase notes, internal
audits, and archived release artifacts remain under [`docs/archive/`](docs/archive/)
and related canonical docs.

## [Unreleased]

- Ongoing public-surface cleanup and release hardening on the `public` branch.
- Reliability: `sentiment` now uses the existing one-shot native-crash retry path, recovering from intermittent Windows first-load subprocess crashes without breaking scene validity.
- Runtime hardening: stale `GOODQ_WSL_WORKSPACE` overrides now fall back to the
  canonical `~/goodq_audio` workspace when the explicit path is missing, rather
  than disabling WSL audio for the run.
- Reliability: the WSL audio bridge now retries `result.json` freshness checks
  once before failing and records richer probe details when verification still
  cannot be completed.

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
