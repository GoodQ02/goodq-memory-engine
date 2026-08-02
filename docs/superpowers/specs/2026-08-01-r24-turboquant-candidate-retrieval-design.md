<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: HISTORICAL_REFERENCE -->
<!-- DOC_LAST_VERIFIED: 2026-08-02 -->

# R-24 TurboQuant Candidate Retrieval Design

## Purpose

Turn the completed one-scene TurboQuant ingest into an honest retrieval A/B
gate. The candidate must compare an active sidecar pre-filter against the
existing full-precision FAISS route without changing canonical retrieval,
epochs, or source media.

## Scope and authority

- The change is limited to `FaissMemory.query` and the R-24 witness snapshot.
- Active mode is permitted only when all of these are true: runtime isolation,
  a non-promoting witness, an artifact root, a SQLite database under that root,
  and `witness.allow_turboquant_active_retrieval: true`.
- Every other configuration retains the current full-precision FAISS behavior.
- Candidate retrieval opens SQLite read-only and writes no telemetry, sidecar,
  FAISS, Qdrant, or canonical data.

## Candidate retrieval flow

1. Read the complete, same-dimension TurboQuant sidecars from the candidate
   SQLite database through the existing read authority.
2. Estimate distances for every complete sidecar and select a configurable
   pre-filter pool, never smaller than requested `top_k`.
3. Read full-precision vectors only for that pool and exactly re-rank them with
   the same L2 score semantics as FAISS.
4. Return the exact reranked hits with unchanged provenance handling.
5. If a sidecar is missing, malformed, has the wrong dimension, or the read
   fails, emit one visible warning and fall back to the existing FAISS path.

## A/B receipt

The one-scene gate runs the same fixed vector queries through both routes and
records only aggregate evidence below the witness root:

- candidate count, sidecar completeness, and per-query latency;
- top-k overlap and exact-rerank agreement with FAISS;
- fallback count and named reason, if any.

The gate passes only if every query has identical final top-k IDs and scores
within floating-point tolerance, no fallback occurs, and median active-route
latency is not slower than the full-precision route. The query pack is fixed
and recorded before a run: one query per stored candidate vector plus at least
one cross-vector query for every modality with two or more vectors. A
performance miss or any retrieval mismatch pauses the staged movie workflow;
it is not auto-tuned or promoted.

## Non-goals

- No canonical cutover, model change, Qdrant change, full-movie ingest, or
  sidecar backfill.
- No claim that one-scene timings predict corpus-scale speed. A passed scene
  unlocks exactly one full-movie candidate, whose larger query pack is the
  first corpus-scale decision gate.

## Validation plan

1. TDD unit tests prove active mode is rejected outside an approved isolated
   witness and that incomplete sidecars fall back unchanged to FAISS.
2. Unit tests prove candidate active results exactly match full precision on a
   fixture with a deliberately distractor-rich pool.
3. Run the aggregate, read-only A/B receipt against the completed one-scene
   witness before starting any additional media ingest.
