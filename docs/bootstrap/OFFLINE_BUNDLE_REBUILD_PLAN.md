<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_EXECPLAN -->
<!-- DOC_LAST_VERIFIED: 2026-05-11 -->

# Offline Bundle Rebuild ExecPlan

Status: ACTIVE
Branch: `main`
Public-safe: yes, for plan text only. Scratch artifacts, machine-audit payloads,
private reports, token-like files, and generated installers are not public-safe.

This ExecPlan is subordinate to `AGENTS.md`,
`docs/architecture/GOODQ_EXECPLAN_PROTOCOL.md`, and the canonical GoodQ runtime
contracts. It must be updated as the offline bundle is rebuilt.

## Purpose / Operator Outcome

Rebuild the GoodQ offline bundle from current source and current bootstrap
doctrine so laptop/bootstrap trials cannot accidentally consume stale installer
payloads.

After this plan is sealed, an operator should be able to identify:

- the exact source commit used for the staged offline repo
- the exact bootstrap and WSL audio lane doctrine included in the payload
- which wheelhouses, model caches, host tools, and manifests were accepted
- whether the bundle is transport-ready, partially staged, or blocked
- why older offline bundle artifacts are no longer in circulation

This is packaging truth maintenance. It does not alter ingestion behavior,
runtime configuration, model versions, package lanes, Qdrant contents, or
ControlAgent state.

## Scope Lock

Allowed in this planning pass:

- `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md`
- bounded status updates that prevent future operators from treating retired
  bundle artifacts as current truth
- validation of documentation hygiene and branch state

Allowed in a future rebuild pass after this plan is committed:

- audit the preserved workspace-adjacent machine-audit pack as input
- write a repo-tracked staging helper only after its contract is reviewed
- create a new temporary staged payload under the operator-selected scratch root
- generate a bundle manifest from current source and accepted offline assets
- package archive or self-extracting artifacts only after the staged payload
  passes validation

Forbidden:

- ingestion or witness runs
- package upgrades or model version changes
- bootstrap target changes
- source, config, lockfile, or package-manifest mutation without a separate
  audit
- ControlAgent activation
- healing or config mutation
- Qdrant backfill or mutation of existing vectors
- staging `reports/control_recurrence/*`, fresh-ingest reports, scratch payloads,
  installers, archives, caches, or token-like files
- wildcard deletion as a documented safe path
- reusing retired bundle payloads as active packaging truth

## Current Evidence

- The previous workspace-adjacent offline bundle generation was audited and
  retired from circulation.
- The removed obsolete artifacts were the staged offline repo, extracted
  installer payload, archive, and self-extracting installer. The remaining
  offline-bundle scratch directory contains only small historical scripts,
  readmes, and logs.
- The previous machine-audit pack has been removed from the active scratch
  surface and must not be treated as current rebuild input.
- The old staged repo had no git metadata and could not prove its exact source
  commit.
- The old staged/offline repo was missing
  `wsl2_audio/requirements-bootstrap-constraints.txt`.
- The old staged/offline WSL setup surfaces predated the current WSL bootstrap
  readiness doctrine.
- The old Linux wheel evidence included `torch`, `torchvision`, and
  `torchaudio` on the observed cu128 drift lane. That lane is not the bootstrap
  target and must not be substituted for the canonical WSL audio target.
- Current doctrine remains:
  - `torch==2.5.1+cu121`
  - `torchvision==0.20.1+cu121`
  - `torchaudio==2.5.1+cu121`
- The observed sourced WSL worker lane remains classified only as
  `WSL_AUDIO_LANE_OBSERVED_FUNCTIONAL_DRIFT_CU128`; it is functional evidence,
  not package approval, not a bootstrap target, and not an offline bundle target.
- No local Linux wheelhouse proving the canonical WSL audio torch family was
  identified during the first bundle audit.
- A token-named file was observed in scratch legacy-reference material; legacy
  scratch material must not be circulated into the new bundle without explicit
  sanitization.
- The standalone legacy root-level model cache was audited after the bundle
  contract pass. Its nonzero material model payload files matched the
  canonical model cache by hash; only non-runtime cache logs were unmatched.
  It is drift evidence, not packaging authority.

## Progress

- [x] 2026-05-05 - Audited the old offline bundle root and identified stale
  packaging surfaces.
- [x] 2026-05-05 - Removed the obsolete staged payload, extracted installer
  payload, archive, and self-extracting installer from circulation after
  containment review.
- [x] 2026-05-05 - Preserved the machine-audit pack as temporary rebuild input.
- [x] 2026-05-05 - Added the GoodQ ExecPlan protocol.
- [x] 2026-05-05 - Drafted this offline bundle rebuild ExecPlan.
- [x] 2026-05-11 - Removed the old machine-audit pack from the active scratch
  surface; it is no longer available as rebuild authority.
- [x] 2026-05-11 - Built a source-evidence manifest from current source and
  accepted local assets. Current summary: 16 computed artifacts, 2 partial
  computed artifacts, 2 optional deferred artifacts, zero pending hashes.
- [x] 2026-05-11 - Resolved the canonical Linux WSL audio wheelhouse evidence
  with the cu121 lane; do not substitute observed cu128 drift wheels.
- [x] 2026-05-11 - Staged and hash-computed Windows Conda package tarballs from
  current GoodQ envs: 209 tarballs, zero missing Conda tarballs.
- [x] 2026-05-11 - Staged and hash-computed current WSL apt archive evidence:
  181 `.deb` files.
- [x] 2026-05-11 - Classified host-tool hashes as source evidence only until
  copied into the final host tools pack and hash-manifested there.
- [x] 2026-05-11 - Copied and hash-sealed the host tools pack, including
  FFmpeg, Tesseract, Poppler, Piper, Qdrant, and NSSM; staged pack size is
  741,766,692 bytes across 541 files.
- [x] 2026-05-11 - Sealed the Windows pip wheelhouse: 155 exact PyPI
  requirements verified from the Python 3.10 wheelhouse, plus one source-owned
  package covered by the source pack.
- [x] 2026-05-11 - Created and hash-sealed a private WSL audio distro export as
  the preferred near-term offline restore payload; export size is
  48,162,938,880 bytes.
- [ ] Restore-rehearse the sealed Windows env payload, host tools pack, and WSL
  distro export on a disposable target before creating a final installer.
- [ ] Treat the WSL apt archive cache as supplemental partial evidence only.
  Direct setup package archives are still missing for `python3-pip`,
  `python3-venv`, `sox`, and `git`.
- [ ] Keep standalone legacy root-level model cache copies out of the base
  bundle unless a future manifest proves they are required.
- [ ] Validate the staged payload before creating archive or installer
  artifacts.
- [ ] Package a new offline archive or self-extracting installer only after the
  staged payload passes validation.
- [ ] Decide whether a public-safe mirror note is required after private
  artifact details are excluded.

## Surprises & Discoveries

- Observation: The old bundle generation contained multiple heavy copies of
  the same stale payload generation.
  Evidence: the bundle audit found a staged repo, extracted installer payload,
  archive, and self-extracting installer occupying redundant scratch space.

- Observation: The old staging script is historical intel, not a production
  rebuild contract.
  Evidence: it points at local scratch and machine-audit paths and should not
  be treated as a portable tracked staging surface without redesign.

- Observation: The old Linux wheel lane can recreate the exact WSL drift we are
  trying to stop.
  Evidence: stale wheel evidence used the observed cu128 drift lane while
  current bootstrap doctrine remains the cu121 target listed above.

- Observation: Retaining "legacy" bundle copies as active references would
  increase operator confusion.
  Evidence: the bundle had already been replaced by source-side doctrine and
  recent bootstrap fixes; old artifacts were removed from circulation rather
  than preserved as active package truth.

- Observation: The legacy root-level model cache does not add current runtime
  model coverage.
  Evidence: the cache drift audit matched all nonzero material model payloads
  by hash in the canonical model cache; unmatched files were non-runtime cache
  logs only.

- Observation: Installed host tools are not the same as a portable offline
  host tools pack.
  Evidence: FFmpeg, Tesseract, Poppler, Piper, Qdrant, and NSSM are discovered
  or present locally, but source-evidence hashes alone were not enough to seal
  the portable pack.

- Observation: The host tools gap is now closed at the staged-payload level.
  Evidence: the staged host tools pack contains FFmpeg, Tesseract, Poppler,
  Piper, Qdrant, and NSSM with a deterministic pack hash, and staged-tool
  version/TTS smoke checks passed.

- Observation: The Windows pip gap was a real restore gap but needed exact
  interpreter handling.
  Evidence: an initial default-Python attempt used the wrong ABI, so the
  wheelhouse was rebuilt with the canonical `goodq_core` Python 3.10
  interpreter and then verified with local no-index downloads for all exact
  PyPI requirements.

## Decision Log

- Decision: Retire the previous offline bundle generation instead of labeling
  it as active legacy.
  Rationale: It carried stale WSL bootstrap surfaces and stale cu128 wheel
  evidence that could mislead laptop/bootstrap testing.
  Date/Author: 2026-05-05 / Codex

- Decision: Preserve the machine-audit pack temporarily as rebuild input.
  Rationale: It may contain useful host-tool, wheel, manifest, and cache
  evidence, but it does not prove current bundle readiness by itself.
  Date/Author: 2026-05-05 / Codex

- Decision: Do not package observed cu128 WSL torch wheels as the canonical
  Linux WSL audio wheel lane.
  Rationale: The observed lane is classified as functional drift only. Future
  promotion requires an explicit lane-promotion audit.
  Date/Author: 2026-05-05 / Codex

- Decision: Prefer a WSL audio distro export for the near-term offline restore
  strategy.
  Rationale: The wheelhouse is strong, but reconstructing WSL from apt package
  archives still has direct package gaps. A validated `wsl --export` tar gives
  the installer a reproducible offline runtime target without depending on apt
  resolver behavior during install.
  Date/Author: 2026-05-11 / Codex

- Decision: Create a rebuild plan before authoring or running a new packager.
  Rationale: Offline packaging is restart-sensitive and can reintroduce old
  runtime doctrine if the source, wheelhouse, and manifest contract are not
  explicit.
  Date/Author: 2026-05-05 / Codex

## Plan Of Work

Milestone 1: Freeze source doctrine.

- What changes: commit this plan and the status corrections that mark old
  bundle artifacts retired.
- Why it is safe: documentation-only; no runtime or package mutation.
- Files touched: this plan plus bounded operator-status docs.
- Proof: `git diff --check`, docs-only diff, doctrine string scans, clean staged
  diff.
- Stop if: any source/config/lock/package file changes appear.

Milestone 2: Build a staged payload manifest.

- What changes: create a future tracked staging helper or dry-run inventory
  that copies current source into a temporary stage and writes a manifest.
- Why it is safe: stage is generated outside tracked source and can be deleted
  without touching runtime state.
- Files/systems touched: future staging helper, operator-selected scratch root,
  and generated temp stage only.
- Proof: manifest records source commit, included docs, wheelhouse inventory,
  model-cache inventory, excluded files, and local-path hygiene.
- Stop if: the helper needs hardcoded local drive roots, secrets, or old bundle
  payloads as authority.

Milestone 3: Resolve offline WSL audio wheel doctrine.

- What changes: inventory accepted Linux wheels for the canonical WSL audio
  torch family or mark WSL offline restore incomplete.
- Why it is safe: inventory first; no package promotion or mutation.
- Files/systems touched: wheelhouse inventory and generated manifest only.
- Proof: manifest either lists the canonical cu121 Linux wheels or records a
  blocking wheelhouse gap.
- Stop if: observed cu128 drift wheels are the only available Linux torch
  family and someone attempts to treat them as the canonical target.

Milestone 4: Validate staged payload before packaging.

- What changes: run tracked validation against the staged payload without
  creating a final archive or installer.
- Why it is safe: validation reads generated stage content and source docs.
- Proof: bootstrap verify in CI profile, WSL bootstrap path tests, local-path
  scans, token-pattern scans, and manifest completeness checks pass.
- Stop if: constraints file is missing, stale cu128 approval wording appears,
  token-like files are included, or source commit cannot be proven.

Milestone 5: Package only after validation.

- What changes: create a new archive or self-extracting installer from the
  validated stage.
- Why it is safe: packaging consumes a validated stage and writes new generated
  artifacts outside tracked source.
- Proof: archive manifest matches staged manifest; extraction smoke confirms
  expected top-level files; no retired payload files are included.
- Stop if: generated package contents differ from the validated stage.

## Concrete Commands

Working directory for source-side validation:

```powershell
<repo-root>
```

Current docs-only validation:

```powershell
git diff --check
git status --short
git diff --stat
git diff --name-only
```

Doctrine scans for this pass:

```powershell
git diff -- docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md docs/SYSTEM_SNAPSHOT.md docs/goodq4all_agent_status.md docs/bootstrap/INSTALL_BOOTSTRAP.md
```

Run the local-path hygiene scan and the forbidden cu128-approval wording scan
from the operator shell. Do not store those forbidden strings in this plan,
because the validation artifact should not create its own false positives.

Future staged-payload validation candidates:

```powershell
python scripts/bootstrap_verify.py --json --profile ci
python -m pytest tests/unit/test_bootstrap_install_wsl.py
python -m pytest tests/unit/test_wsl_audio_preflight.py
python -m pytest tests/unit/test_bootstrap_verify.py
```

Future packaging work must add exact staging and packaging commands here before
it runs them. Do not rely on remembered chat history.

## Validation And Acceptance

This planning pass is accepted when:

- this ExecPlan exists and is committed on `main`
- stale status docs no longer claim the retired offline bundle or installer is
  current
- changed files are documentation-only
- no generated reports, scratch artifacts, caches, archives, installers, or
  local config files are staged
- changed docs contain no local drive-root paths
- changed docs contain no language approving the observed cu128 drift lane
- `reports/control_recurrence/*` local artifacts remain unstaged

The future rebuild is accepted only when:

- staged payload manifest records the exact source commit
- WSL audio constraints file is present in the staged repo
- wheelhouse contents match current doctrine or missing pieces are explicitly
  marked incomplete
- model cache excludes incomplete downloads unless intentionally retained with
  a reason
- standalone legacy model-cache roots are excluded unless explicitly justified
  by the staged manifest
- token-like files are excluded
- generated installer artifacts are created only after staged payload validation
- extraction smoke confirms the packaged contents match the validated stage

## Idempotence And Recovery

The previous bundle generation has been removed from circulation. A future
rebuild should create a new stage from current source rather than modifying old
payloads in place.

If a rebuild is interrupted:

- keep the machine-audit pack until a replacement bundle is validated
- delete only exact temporary stage paths after containment review
- regenerate the staged payload from source instead of repairing stale copies
- never promote generated artifacts without a manifest and validation record

## Public / Private Handling

This plan is public-safe because it describes doctrine and process, not private
artifact contents. Public branch updates should include only docs that do not
reference private reports, local scratch contents, token-like files, or
machine-specific paths.

Generated bundle manifests, scratch inventories, and packaging logs must be
reviewed before any public exposure.

## Commit And Push Plan

Stage exact files only:

- `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md`
- `docs/bootstrap/INSTALL_BOOTSTRAP.md`
- `docs/SYSTEM_SNAPSHOT.md`
- `docs/goodq4all_agent_status.md`

Validation before commit:

- `git diff --check`
- changed-doc local-path scan
- changed-doc cu128 approval scan
- docs-only diff review

Commit message:

```text
docs: plan offline bundle rebuild
```

Branch to push:

- `main`

Public branch:

- defer unless this plan is intentionally mirrored after private artifact
  references are reviewed for public safety.

## Outcomes & Retrospective

Pending. Fill this section when the rebuild is sealed, deferred, or replaced by
a newer packaging plan.
