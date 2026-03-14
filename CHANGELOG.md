# Changelog

This changelog tracks public-facing GoodQ4All milestones and release-readiness
checkpoints.

It is intentionally lightweight. Historical phase-by-phase notes, internal
audits, and archived release artifacts remain under [`docs/archive/`](docs/archive/)
and related canonical docs.

## [Unreleased]

- Ongoing public-surface cleanup and release hardening on the `public` branch.
- Retired the legacy `scripts/api_server.py` monolith from the tracked surface and repointed direct support-facing references to the canonical `api.server` wrapper.
- Retired the legacy `scripts/refresh_vllm_portproxy.bat` helper from the tracked surface; Windows↔WSL vLLM access is no longer documented through manual portproxy mutation.
- Retired stale WSL/vLLM report-style docs from the tracked support surface and repointed live indexes to the current operator docs.
- Retired the stale `docs/guides/llm/WSL_AGENT_BRIEFING.md` coordination brief and repointed live docs to current WSL/vLLM operator references.
- Sanitized `docs/guides/llm/VLLM_SYSTEMD_SETUP.md` into a portable advanced-operator reference and removed workstation-specific path and user assumptions.
- Reclassified `scripts/wsl/install_vllm_service.sh` as a current WSL/vLLM runtime utility and aligned its default model path with the safer WSL-home fallback.
- Hardened `scripts/start_vllm_servers.bat` to fail visibly when the `vllm-llama1b` systemd service is inactive instead of falling back to stale direct-launch scripts with drifted port assumptions.
- Demoted legacy agent-system docs so they no longer present the old real-time orchestration stack as the current runtime contract.
- Retired the legacy `agents/watchdog_agent_integration.py` watcher and made the obsolete startup menu fail visibly toward the canonical `cli.watchdog` path.
- Retired the legacy `agents/pipeline_integration.py` and `agents/orchestrator.py` core, removed the obsolete quick agent test, and made the remaining startup menu options fail visibly toward canonical CLI surfaces.
- Sanitized `docs/architecture/AGENT_SYSTEM.md` so its retired watcher/pipeline sections no longer document deleted imports and entrypoints as live behavior.
- Retired the legacy `scripts/utilities/process_manager.py` cluster and `tests/TEST_PROCESS_MANAGER.bat`, then collapsed the old process-management guides into short historical notes that redirect to canonical launcher/watchdog surfaces.
- Reliability: `sentiment` now uses the existing one-shot native-crash retry path, recovering from intermittent Windows first-load subprocess crashes without breaking scene validity.
- Runtime hardening: stale `GOODQ_WSL_WORKSPACE` overrides now fall back to the
  canonical `~/goodq_audio` workspace when the explicit path is missing, rather
  than disabling WSL audio for the run.
- Reliability: the WSL audio bridge now retries `result.json` freshness checks
  once before failing and records richer probe details when verification still
  cannot be completed.
- Security hardening: the legacy API server launcher now defaults to
  `127.0.0.1`, with LAN exposure remaining explicit via `GOODQ_API_HOST`.
- Security hardening: environment preparation now seeds `GOODQ_API_HOST` with a
  loopback default rather than a broad network bind.
- Portability hardening: `setup_agents.ps1` now defaults agent setup data and
  model roots to the portable `C:/GoodQ_Data` / `<GOODQ_DATA_ROOT>/models`
  pattern instead of desktop-specific `L:/` paths.

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
