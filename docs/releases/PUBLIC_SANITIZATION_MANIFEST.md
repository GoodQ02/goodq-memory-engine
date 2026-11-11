<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_MANIFEST -->
<!-- DOC_LAST_VERIFIED: 2026-11-11 -->

# Public release sanitization manifest

## Source and authority

- Private development source: `5c9709b3bd2952a89adcd04e68851efcfa8a22cf` (`dev`).
- Public parent: `50df353e87279f487d51e4522c7aca716383b35c` (`main`).
- Public destination: `GoodQ02/goodq-memory-engine`, branch `main`.
- The public commit is a sanitized snapshot, not a merge of private history.
- Workstation deployment continues to use the private checkout. This mirror is
  independently checked source, not a second local service instance.

## Exclusions and transformations

Private reports, archives, witness receipts, model/corpus data, onboarding media,
host-specific maintenance scripts, and local plans are omitted. Signed model
manifests and product code retain their upstream source bytes. Public-only
changes are documentation, fixture/config anonymization, four epoch examples in
docstrings, public-scope test expectations, and the declared exclusions; no
runtime feature is developed exclusively in this mirror.

The current-state files are generated from a public **unconfigured template**.
Their zero counts and `not_probed` states do not assert an empty or healthy
installation. Operator preferences and the runtime evidence manifest use
anonymous sample identity; they cannot qualify any real corpus.

## Validation boundary

Required gates are source parity, privacy and portability inspection,
documentation drift/authority/dependency checks, installer semantic contract
checks, and focused unit tests covering the changed source. Record terminal
results in the commit and local release receipt before publication.

This release updates source only. It does not replace published installer
assets, certify arbitrary hardware, or claim a restored backup. Existing public
history is retained; the snapshot prevents new private history from being pushed.

## Local verification

- Documentation drift, authority, dependency and banned-token gates pass.
- Installer semantic compatibility passes all 15 checks.
- The initial changed-source suite passed 554 tests and found two defects.
  Retiring obsolete candidate-only scripts cleared the catalog gate (51 tests).
  Cross-process fallback locking passed 43 targeted audit/privacy tests.
- Unconfigured-template truth and projection checks passed 65 tests.
- Product code and signed model-manifest bytes match the pinned private source,
  apart from the declared comment examples and privacy exclusions.
- Known source warnings: Pydantic class-based configuration is deprecated.

For the 2026-09-23 supervised dev-mode update, the eight changed source/test
files match the pinned private commit byte for byte. The four focused test
modules pass 56 tests with two existing Pydantic deprecation warnings.
Documentation drift, authority, dependency, banned-token, and installer
semantic checks pass. A CI-profile bootstrap check passes with the same
Baseline/GPU settings as hosted CI when this checkout's ignored workstation
`.env.local` is excluded from the check. Hosted results must still be matched
to the public commit after publication.

## Existing-store startup follow-up

The supervisor queries Qdrant before requesting service-start permission.
The regression fixture rejects a redundant start while still proving that a
stopped store is started and failed API startup blocks Watchdog. The five
native Windows startup checks pass on the private source.

## Supervised dev-mode follow-up

The portable supervisor, Dev On/Off scripts, dashboard labels, and focused tests
are copied from the pinned private source. Dev On reuses one verified existing
supervisor; Dev Off requests its receipt-bound drain before stopping the
configured GoodQ WSL compute extension. Ambient Ollama models and unrelated
workstation services are outside these scripts' scope. Public documentation
describes the portable behavior without GOOD-CUBE shortcut, panel, or distro
paths. The live sign-in shortcut and native panel remain private workstation
integration, not public installer content.

The initial publication was blocked by GitHub billing before job steps ran.
That block is cleared. Check the run matching the source commit in
[GitHub Actions](https://github.com/GoodQ02/goodq-memory-engine/actions)
for hosted results; local validation and hosted validation are separate evidence.

## Watchdog stale-owner follow-up

A stale lock could refer to a process ID recycled by Windows. The owner check
now requires the process to predate the lock and preserves an owner whose
identity cannot be read. Native lock, safety and real runtime lifecycle tests
pass (11 tests); the unrelated process is never terminated.

## Fresh-checkout hosted follow-up

Fresh-checkout verification caught two links to excluded internal archives in
the changelog. Those links now describe the public scope instead of implying
that private archives are available here.

The full hosted suite then passed 4,340 tests and found two public-scope fixture
mismatches. The retrieval-context matrix covers every published caller; the
private corpus-report case is replaced by an assertion that its excluded script
stays absent. The runtime-evidence listing test expects the explicitly unqualified
anonymous epoch from this snapshot. Both adaptations preserve the private
repository's original tests and change no product code or runtime behavior.

## Scoped operator documentation update (2026-09-26)

The concise agent guidance and operator skill are copied from the pinned private
source. The clean-memory workflow has the same current safety procedure, with a
public-checkout wording adjustment and a public reference boundary replacing its
private archive link. The private historical cleanup archive, workstation baseline,
runtime repair receipts, temporary-file backups, and worktree evidence are excluded.
Previously sanitized operator-lane and release-roadmap text is preserved.

This update changes documentation and instructions only. Product code, dependencies,
installer payloads, and runtime configuration are unchanged. It does not warrant
rebuilding an installer or restarting a user's services. Older local and hosted
verification results above belong to their named releases, not this commit.

Local gates for this documentation update passed: documentation drift and authority,
dependency drift, banned-token inspection, all 15 installer semantic checks, and
36 focused documentation-authority tests. The guidance and skill match the pinned
private source; only the declared workflow reference/checkout wording is adapted.
Hosted checks are verified separately against the resulting public commit.

## Context7 library rename correction - 2026-09-26

The root context7.json URL and README Context7 link now target
`https://context7.com/goodq02/goodq-memory-engine`. The public verification key
is unchanged; the JSON matches private dev. Only public URL metadata and this
release manifest changed. Documentation drift/authority, dependency drift,
banned-token, and all 15 installer semantic checks pass. Upstream claim status
and index completion are separate service-side checks, not release guarantees.
## CI and startup-test cleanup - 2026-09-26

The three changed CI/test files match private dev byte for byte. Control callers
have bounded failure cleanup; the CheckRunning test budget includes shell startup
in addition to its HTTP timeout. Obsolete fixture root/port rewriting is removed.
Pull-request CI covers all changes and uses read-only permissions, a 45-minute
job limit, cancellation of superseded runs, and runtime/test-duration diagnostics.
Production launcher behavior and the locked dependency baseline are unchanged.
Private validation passed 37 startup tests, 21 CI/installer contract tests, all
15 installer semantic checks, and documentation/dependency/banned-token gates.
Hosted full-suite results must be matched to these new commits separately.
The hosted private first-pass suite passed 4,346 tests. Public CI exposed two
additional test races: snapshot disappearance between enumeration and reading,
and control checks racing a transient backoff window. The follow-up retries
only transient missing snapshots within the existing deadline, holds the fixture
backoff until both checks finish, and applies consistent cold-shell time budgets.
All 38 startup tests and 21 CI/installer tests pass locally. The two changed test
files match private fa31aca9 byte for byte; production runtime logic is unchanged.
The next hosted runs exposed an existing worker-receipt race: a restarted owner
could be monitoring before its replacement transaction overwrote the old receipt.
The recovery test now waits for a new live PID-plus-creation-time identity and
allows legitimate PID reuse. Real-entrypoint fixtures get a separate 30-second
startup budget; early exits include fixture diagnostics. All 39 startup tests
and 21 CI/installer checks pass locally. Test sources match private df3f9831.
Production lifecycle behavior is unchanged; hosted final results remain separate.
A subsequent hosted run passed worker recovery but exposed a fixed-sleep heartbeat
assertion and two native-process stalls. Native lifecycle tests now run in a
separate mandatory CI step before the remaining unit suite; a coverage/order
regression test prevents silently omitting them. Heartbeat validation observes
actual progress within a deadline and releases the lock even on failure. Native
control logs identify compilation and listener-query phases. All four changed
source files match private 2c13cec6. Local focused checks passed (31 affected
checks, then 27 final workflow/lock checks including the new coverage guard).
No production runtime or dependency changes are included.

## UI modernization, multi-recording curation, and quality-of-life release - 2026-11-09

Mirrors pinned private commit `e33c4109` onto `GoodQ02/goodq-memory-engine` `main` (parent `fbb89c10`):
- **UI & Quality-of-Life Upgrades**: Deepened Obsidian Night Mode and Daylight Studio theme synchronization across Memory Explorer, Identity Curation Workbench, Speaker Stitching Workbench, Summary Console, Justification UI, and Operator Console; combined multi-recording library federation with unavailable-source disclosure; `People -> Scenes -> Watch` navigation; cross-movie face/voice match review with `Correct / Incorrect / Unsure` decisions, `"Who is this instead?"` rejected-pairing reassignment, and alias-tolerant frozen-comparison guards; producer and API `<ref>`/`<box>` grounding-markup stripping; config-driven `EntityExtractor` person terms; corpus-neutral search/grounding repairs; lossless audio phrase grouping and LF-pinned worker digests; and Pydantic `ConfigDict` migration (resolving the previously noted class-based configuration warning) plus unused `steps/tts/` retirement.
- **Public Showcase Media**: Four UI screenshots (`samples/assets/ui_*.png` and `retro_console_preview.png`) were generated from an isolated synthetic public-domain NASA Apollo 11 harness and re-encoded without metadata chunks. No personal media, family names, corpus databases, or workstation receipts are included.
- **Parity & Privacy Gates**: Product code in `api/`, `cli/`, `common/`, `configs/`, `envs/`, `lib/`, `pipelines/`, `retrieval/`, `steps/`, `ui/`, and `wsl2_audio/` matches `e33c4109` byte for byte. Documentation drift, authority, dependency drift, banned-token, installer semantic contract, deep personal-term/path privacy scan, and focused unit/UI suites pass prior to publication.

### Hosted Windows startup-test follow-up

Hosted runs on `9d87e440` passed `doc-drift-lint` and `codeql` and 53/54 Windows
startup checks, exposing two hosted-runner timing/sharing races: `held.replace(receipt)`
colliding with concurrent `supervisor.json` handles or overwriting a freshly
republished heartbeat receipt during discovery fault injection, and a two-second
`Invoke-WebRequest` readiness probe budget under cold `powershell.exe` `Add-Type`
compilation jitter. `start_goodq_dev.ps1` and `tests/unit/test_dev_startup.py`
now match private `915c79f8` byte for byte; all 68 local startup/caller checks
and hosted startup tests on both `dev` (`42761838665`) and `main` (`42762401537`)
passed on the first attempt.

Full-suite collection on `23608419` then surfaced `tests/unit/test_verify_entity_quality_metrics.py`
importing the excluded `scripts/internal/verify_entity_quality.py` helper.
Matching `test_retrieval_context_authority.py`, the public test now verifies
that `scripts/internal/verify_entity_quality.py` remains excluded while private
`dev` retains direct unit tests. The complete CI-profile unit suite in the
isolated public checkout passed 7,102 tests plus seven subtests with zero
failures before publication.

## Audio consensus, UCF stereo preservation, and cross-film identity curation - 2026-11-11

Mirrors pinned private commit `5c9709b3` onto `GoodQ02/goodq-memory-engine` `main` (parent `50df353e`):
- **Audio Engine & Transcription Sanitization**: Defaults `audio.transcribe.vocabulary_mode` to `"off"` so configured person-name hints never seed Whisper decoder prompt-echo hallucinations on non-speech hums; adds bridge-level prompt-echo, decoder-loop, and stock-boilerplate filtering (`bridge_prompt_echo_filter_v1`); preserves stereo channel layout in UCF scene audio extraction (`-ac 2`) while downmixing mono exclusively at Whisper's 16 kHz staging boundary; and fixes Qdrant point-ID deterministic UUIDv5 collision safety for multi-chunk transcripts plus occurrence-aware `context_frames` schema migration (`scripts/ucf/ucf_ledger.py`).
- **Semantic Entity & Tag Hygiene**: Splits fused roster names in NER output, excludes person names from topic/concept tags, strips noisy single-token false `PERSON` tags, and wires video-epoch `EntityExtractor` directly to `scene_ingest_results.json`.
- **Cross-Film Identity Curation Workbench**: Adds visual DBSCAN face clustering (`Layout: Visual clusters`) on Match Review (`lib/identity_matching.py`, `ui/identity_workbench/`), sticky `Who is this instead?` reassignment with inline `+ New person...` roster creation (`POST /api/identity/roster`), retrospective cross-film face scanning (`POST /api/identity/roster/{id}/scan-films`) across configured sibling witnesses, and `<1s` prior-film match refresh (`POST /api/identity/matches/refresh` / `Refresh from prior films`) so downstream epochs pick up newly confirmed prior-film faces without re-ingestion.
- **Parity & Privacy Gates**: Product code in `agents/`, `api/`, `cli/`, `common/`, `configs/`, `envs/`, `lib/`, `pipelines/`, `retrieval/`, `steps/`, `ui/`, and `wsl2_audio/` matches `5c9709b3` byte for byte (apart from the declared anonymous operator preference template — whose `path_meta` `source` values now use valid `"developer_seed"` enum entries so fresh-checkout `MiniAgentClient` policy validation passes — and `epoch_public_example` docstring). Documentation drift, authority, dependency drift, banned-token, all 15 installer semantic checks, personal-term/path privacy scan, and 531 focused unit/agent checks pass before publication.
