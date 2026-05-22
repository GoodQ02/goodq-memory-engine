<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: PUBLIC_RELEASE_STATUS -->
<!-- DOC_LAST_VERIFIED: 2026-05-22 -->

# GoodQ4All Agent Status

This public status surface is scoped to GoodQ4All 0.1.1 - Epistemic Memory
Preview. It replaces private restart-state detail with a release-safe operator
summary.

## Current Release Posture

- Release identity: GoodQ4All 0.1.1 - Epistemic Memory Preview.
- Supported posture: early local-first, scene-centric memory preview.
- Canonical runtime owner: `cli/run_ingestion.py`.
- Automation surface: Watchdog plus the configured import inbox.
- Truth surfaces: scene manifests, temporal indexes, persisted run artifacts,
  SQLite state, knowledge graph state, and Qdrant vectors when configured.
- API posture: local read/inspection surface on loopback, not a hosted public
  service.
- UI posture: read-only Operator Console v1 plus the Justification Channel,
  both served locally under `/ui/*`; no UI execution authority. Operator
  Console v1 opens with a Current Scope strip for API base, latest run, run
  source, temporal scope, strict audio proof, browsing target, selected scene,
  and read-only mode.

## Current Public Mirror Checkpoint

- 2026-05-22 public-safe mirror status: local Ollama fallback and configured
  WSL audio readiness are now represented more truthfully in runtime status and
  agent-facing workflows. The public release still treats these as local
  operator-managed services, not cloud dependencies.
- API runtime status now checks the configured WSL audio worker before
  reporting `faster_whisper` readiness, avoiding false negatives from plain WSL
  Python environments.
- A fresh scene-first validation pattern confirmed strict current-run audio
  proof, sentiment, text-emotion rankings, audio-emotion rankings, channelized
  entity evidence, Qdrant vectors, and explicit-ID FAISS indexes on a clean
  validation epoch.
- A reusable evidence-first runtime repair workflow was added to the source
  agent office so future operators can repair one capability seam at a time
  before broad reruns.
- 2026-05-21 public-safe mirror status: the local read-only API and Operator
  Console now surface transcript, sentiment, text-emotion ranking, audio-emotion
  ranking, and strict current-run audio-vector proof when those artifacts are
  present in the active run.
- Latest evidence read models now expose channelized entity evidence instead
  of collapsing KG state to a boolean. Dialogue-mentioned entities,
  candidate-visible people, speaker-aligned mentions, and strict scene-present
  identity remain separate.
- Retrieval read models preserve that same entity channel split through
  `POST /api/search/multimodal` when timeline scene evidence is available.
- Recent clean probe validation used a short operator-owned clip, a fresh epoch,
  reset Qdrant collections, and fresh explicit-ID FAISS indexes before checking
  the evidence route and UI read models.
- Audio emotion rankings are review evidence until they meet the configured
  promotion threshold; the UI should show ranked signal without over-claiming a
  hard label.
- Before any broad personal-memory run, reset disposable vector/index state or
  start a fresh epoch, then validate one scene first.

## Operator Boundaries

- ControlAgent and healing are not part of the public preview release surface.
- Optional enrichments may fail, but failures should be visible in artifacts or
  logs rather than silently converted into success.
- Runtime config is raw for runtime consumers, but display/logging/operator
  surfaces must sanitize config-like payloads before output.
- Public release docs must not claim healthcare readiness, autonomous control,
  polished consumer UI maturity, full offline-installer maturity, or post-1.0
  API stability.

## Public First-Run Bias

The first public success loop should prove:

- local bootstrap can prepare the runtime
- one operator-owned input can become scene-level memory
- persisted scene artifacts are inspectable
- local API/CLI surfaces and the read-only Operator Console can inspect that
  state
- uncertainty and limits remain explicit

Use `docs/guides/FIRST_RUN.md` as the first-run entrypoint.

Start with the guided demo in `docs/guides/DEMO.md` when a visual walkthrough is
more useful than reading the command list first.

## Release Watch Items

- Keep optional dataset, eval, reference-bank, and synthetic fixture assets out
  of the base installer unless a selected manifest explicitly clears them.
- Keep private media, fresh witness outputs, runtime databases, logs, local
  machine snapshots, and Seinfeld/test-run memory out of the base release.
- Keep public docs framed as an epistemic memory preview, not as a finished app.
