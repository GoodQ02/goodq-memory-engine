# Seinfeld Control Benchmark Summary

This document provides a sanitized summary of the private Season 1 control benchmark used to validate GoodQ4All's ingestion reliability and semantic retrieval behavior.

The underlying media, transcripts, runtime snapshots, and scene-level analysis artifacts are intentionally not published in the public repository.

## Dataset Profile

- five privately held benchmark episodes
- sitcom-style dialogue with recurring characters, recurring locations, and short conversational scenes
- used as a stable control set for segmentation, retrieval, and optional-step reliability checks

## Witness Metrics

- scenes processed: `185`
- transcript-bearing scenes: `182 / 185`
- empty scenes: `3`
- processing-error scenes: `0`
- WSL audio effective: `185 / 185`

## Persistence Snapshot

- Qdrant points:
  - `clip=185`
  - `dino=185`
  - `text=182`
  - `audio=185`
- knowledge graph:
  - `310` nodes
  - `315` edges
  - typed edges present for `appears_in`, `interacts_with`, and `located_in`

## Reliability Outcome

The benchmark was used to harden optional enrichment behavior for:

- sentiment analysis
- CLAP audio embeddings

Current public-summary baseline:

- sentiment: `181 ok`, `4 skipped`, `0 error`
- audio_embed_clap: `185 ok`, `0 skipped`, `0 error`

The remaining non-`ok` rows are expected, explicit skips for empty or too-short scenes. No optional-step failure breaks ingestion.

## Retrieval Outcome

The benchmark confirmed that retrieval quality improved after:

- knowledge-graph authority cleanup
- entity normalization
- metadata filtering
- dialogue-intent hints
- artifact-aware reranking
- subject-aware retrieval weighting

## Publication Policy

- published: counts, aggregate metrics, reliability totals, and high-level analysis
- not published: transcripts, dialogue excerpts, runtime config snapshots, local machine paths, or copyrighted media derivatives
