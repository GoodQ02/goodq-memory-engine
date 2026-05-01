<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-01 -->

<p align="center">
  <img src="samples/assets/q-git-square.png" alt="GoodQ4All mark" width="140" />
</p>

# GoodQ4All

GoodQ4All is a local-first multimodal memory system for long-running video, audio, and text intelligence.

It ingests media into scene-level memory, persists what it learns locally, and keeps the proof path visible. The system is built around deterministic Windows-first execution, with CPU-safe baseline behavior and optional GPU / WSL2 acceleration when you want more throughput.

GoodQ4All's thesis is simple: machine memory should earn every claim it makes.

## What This Actually Is

GoodQ4All is not just an ingest runner or a benchmark harness. It is a full local memory stack with five major layers:

- **Perception engine**
  Detects scenes, extracts keyframes, runs OCR and captions, tags objects and faces, transcribes audio, tracks speakers, and generates embeddings across modalities.

- **Interpretation engine**
  Turns raw perception into scene meaning through `scene_context_llm`, epistemic evidence surfaces, arbitration, and Phase 6 multimodal harmonization.

- **Memory engine**
  Persists scene manifests, temporal indexes, SQLite memory state, knowledge graph state, and Qdrant vectors as durable local memory rather than disposable run logs.

- **Retrieval engine**
  Supports vector search, KG-backed querying, natural-language lookup, and scene-level analysis against persisted memory.

- **Operations layer**
  Exposes bootstrap, validation, watchdog, health, monitoring, and release-evidence surfaces so the system can be run and audited like infrastructure, not just a script.

## Why This Project Exists

Most media-intelligence stacks are either:

- cloud-dependent
- opaque when they fail
- or impressive in demos but weak under long-running, real-world ingestion

GoodQ4All is trying to be the opposite:

- local-first
- scene-centric
- auditable
- resilient under partial failure

The design goal is simple: a working memory system is more valuable than a clever one.

## What Is Proven Today

Release `0.1.1` is the current supported checkpoint.

What is actually proven, not just intended:

- The canonical runtime is Windows-first and local-first.
- The supported surface is API + CLI + watchdog + persisted runtime artifacts.
- Scene-context interpretation quality is witness-proven, not just anecdotal.
- Phase 6 harmonization is operating cleanly on the proving run.
- Episode-quality scoring now has a local offline eval lane using curated IMDb-backed anchors for audit only.

Post-release operator validation on the current `main` / `public` line additionally proves:

- WSL audio readiness now means real offline diarization loadability, not import-only checks.
- Successful unified audio preserves diarization and emotion sub-step truth instead of hiding partial failures behind a coarse success result.
- Speaker continuity now persists through `scene_ingest_results.json`, `scene_manifest.json`, and `temporal_index.json`.
- Episode-to-episode continuity is proven on fresh Season 5 material, not just on the release-era comparison witness.
- API scene read models now expose persisted speaker-truth and continuity fields instead of thinner legacy projections.
- Similar-scene retrieval is now a real multimodal feature and can fuse text, visual, and audio memory instead of falling back to an empty path.
- Read-only control recurrence reporting can compare witnesses, index durable artifacts, draft deterministic inspection plans, and derive conservative trends from existing JSON reports without healing or mutation.

Current proving run and release proof path:

- [`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)
- [`docs/releases/SHIP_PROFILE.md`](docs/releases/SHIP_PROFILE.md)
- [`reports/README.md`](reports/README.md)

Current eval result on the proving witness:

- `6/6` core beats covered
- `9.0/9.0` salience weight hit

That result comes from the local episode-reference eval lane and is summarized in the release checkpoint and evidence map above.

## Verify It Yourself

### Fast Verification

If you want the shortest honest path to “does this work on this machine?”:

1. Clone the repo and enter the project root.
2. Run the bootstrap installer.
3. Run the bootstrap validator.
4. Start the API.
5. Check the local health endpoint.

```powershell
git clone <repo_url>
cd goodq4all
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
python -m api.server
```

Then open:

- `http://127.0.0.1:30000/api/health/summary`
- `http://127.0.0.1:30000/docs`

Reference:

- [`docs/bootstrap/INSTALL_BOOTSTRAP.md`](docs/bootstrap/INSTALL_BOOTSTRAP.md)
- [`docs/reference/API.md`](docs/reference/API.md)

### Full Proof Path

If you want to verify the stronger claims, use the proving witness and release evidence directly:

- [`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)
- [`reports/README.md`](reports/README.md)
- [`docs/diagnostics/README.md`](docs/diagnostics/README.md)

## Supported Surface Today

GoodQ4All currently supports:

- local install and bootstrap on Windows
- local API runtime
- CLI ingestion
- watchdog-driven long-running ingestion
- SQLite + knowledge graph + Qdrant-backed persisted memory
- CPU-safe baseline execution with optional GPU / WSL acceleration

GoodQ4All does **not** currently ship a polished end-user UI. That is a future layer, not a current product claim.

UI status:

- [`docs/guides/ui/JUSTIFICATION_UI.md`](docs/guides/ui/JUSTIFICATION_UI.md)

## What Makes It Different

- **Scene-centric memory**
  Every major interpretation surface is built around scenes as the atomic unit.

- **Full perception-to-memory pipeline**
  The system does not stop at captions or transcripts. It carries perception forward into harmonized scene truth, temporal rollups, graph relationships, and retrieval surfaces.

- **Knowledge graph with conservative identity logic**
  People, concepts, objects, places, speaker patterns, and identity evidence are persisted locally, with promotion rules designed to avoid hallucinated merges.

- **Audit-first quality**
  The system is tuned with witnesses, diagnostics, and reference evals instead of vibes.

- **Local truth boundary**
  Public episode anchors can inform audit and scoring, but they do not overwrite runtime scene evidence.

- **Controlled acceleration**
  GPU and WSL are additive performance layers, not hidden requirements.

- **Failure visibility**
  Optional enrichments may fail without collapsing the whole run, and the failure path is meant to remain visible.

## Architecture at a Glance

- **Host:** Windows 11 is the canonical runtime host
- **Profiles:** `UNSET`, `BASELINE`, `GPU_ENHANCED`
- **Perception:** scene detection, captions, OCR, object signals, face signals, transcription, diarization, emotion, and embeddings
- **Storage:** SQLite + knowledge graph + Qdrant
- **Memory surface:** scene manifests, temporal index, projected run outputs
- **Core interpretation layer:** `scene_context_llm` with `primary_tags`, `contextual_tags`, and `structural_tags`
- **Identity layer:** speaker patterns, voice-pattern matches, identity candidates, supported identities, and evidence edges
- **Fusion layer:** Phase 6 / Phase 6b harmonization
- **Operator surface:** API + CLI + watchdog + validation and diagnostics

If you want the deeper technical picture:

- [`docs/architecture/README.md`](docs/architecture/README.md)
- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [`docs/architecture/ARCHITECTURE_REFERENCE.md`](docs/architecture/ARCHITECTURE_REFERENCE.md)
- [`docs/architecture/MEMORY_STORAGE.md`](docs/architecture/MEMORY_STORAGE.md)
- [`docs/architecture/diagrams/`](docs/architecture/diagrams/)
- [`docs/PHASE6_MULTIMODAL_FUSION.md`](docs/PHASE6_MULTIMODAL_FUSION.md)

## Start Here

- Install: [`docs/guides/install/INSTALL.md`](docs/guides/install/INSTALL.md)
- Quickstart: [`docs/guides/install/QUICKSTART.md`](docs/guides/install/QUICKSTART.md)
- Laptop profile: [`docs/guides/install/LAPTOP.md`](docs/guides/install/LAPTOP.md)
- Docs landing page: [`docs/README.md`](docs/README.md)
- API reference: [`docs/reference/API.md`](docs/reference/API.md)
- Current release checkpoint: [`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)

## Current Limitations

- This is pre-1.0 software. The supported runtime path is stable enough to use, but surrounding helpers and APIs may still evolve.
- A polished product UI is not part of the current shipping surface.
- Some optional enrichments can still fail on individual scenes without invalidating the whole ingest.
- Legacy audio vectors may lack current-run provenance; future CLAP Qdrant audio payloads now include run/timestamp metadata when available.
- Context weighting is now strong, but the project still treats some interpretation choices as policy-level texture rather than frozen truth.

## Security and Data Handling

- Secrets belong in `.env.local` only.
- The canonical runtime does not require cloud execution.
- Local storage is the source of truth.
- Public benchmark and eval materials describe outcomes and metrics, not copyrighted transcript dumps.

Reference:

- [`SECURITY.md`](SECURITY.md)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

## Documentation and Evidence

If you only read a few things, read these:

- [`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)
- [`docs/releases/SHIP_PROFILE.md`](docs/releases/SHIP_PROFILE.md)
- [`docs/goodq4all_agent_status.md`](docs/goodq4all_agent_status.md)
- [`docs/SYSTEM_SNAPSHOT.md`](docs/SYSTEM_SNAPSHOT.md)
- [`reports/README.md`](reports/README.md)
- [`docs/diagnostics/README.md`](docs/diagnostics/README.md)

Historical and superseded material is intentionally preserved under [`docs/archive/`](docs/archive/), but it is not the front door.

## License

MIT. See [`LICENSE`](LICENSE).
