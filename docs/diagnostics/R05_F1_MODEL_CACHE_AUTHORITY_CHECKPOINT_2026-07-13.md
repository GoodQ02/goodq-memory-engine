<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Model-Cache Authority Checkpoint

## Outcome

Text and CLIP retrieval query encoders now load only exact registry-pinned
snapshots already present under the configured models root. A missing,
incomplete, unpinned, or redirected snapshot degrades to the existing
unavailable/zero-vector behavior without calling a model library or creating
cache state.

Private implementation checkpoint:

```text
658678fa fix: keep retrieval models local only
```

The four retrieval operations remain `automatic_mutation`. This checkpoint
closes only model-cache authority; retrieval telemetry and SQLite effects remain
open under R-05-F1.

## Exact Implementation

`steps/common/model_cache_inspector.py` is a side-effect-free reader that:

- accepts an explicit models root and registry key;
- reads `repo_id` and exact `revision` from `configs/model_registry.yaml`;
- inspects only
  `hub/models--<repository>/snapshots/<revision>` beneath that root;
- requires model configuration, caller-specific files, and safetensors or
  PyTorch weights;
- rejects unsafe registry path components;
- rejects POSIX symlinks and Windows reparse points in every directory
  component below the resolved models root; and
- returns the exact existing lexical snapshot path or `None` without importing
  the provisioner, changing process state, creating directories, acquiring
  locks, downloading, or logging.

`retrieval/multimodal_search.py` now resolves the snapshot before importing
either model library. Successful calls are exactly:

- `SentenceTransformer(<absolute snapshot>, local_files_only=True)`;
- `CLIPProcessor.from_pretrained(<absolute snapshot>,
  local_files_only=True)`; and
- `CLIPModel.from_pretrained(<absolute snapshot>, use_safetensors=True,
  local_files_only=True)`.

Audio/CLAP loading, ingestion loading, the model registry, provisioning,
telemetry, SQLite, dependencies, routes, response contracts, and route-effect
classification were not changed.

## Mutation-Sensitive RED Evidence

The first focused run produced five intended failures:

- the inspector module did not exist;
- absent caches still called all three model-library loaders; and
- seeded caches still received remote identifiers without local-only flags.

After the initial implementation, independent review found an authority bypass:
the pinned revision directory could redirect through a symlink or Windows
junction to an arbitrary complete directory elsewhere under the models root.
A real temporary-directory redirect witness failed before the correction:

```text
expected: None
observed: <models root>/arbitrary-snapshot
```

The correction checks each exact directory component with `lstat()` and rejects
symlinks/reparse points while retaining ordinary Hugging Face file links inside
a genuine snapshot. The redirect witness then passed.

Focused oracles also prove:

- fresh child-interpreter import leaves `sys.path` and environment unchanged;
- import does not load the provisioner, locking, Hub, Transformers, or Sentence
  Transformers stacks;
- an absent models root remains absent;
- an unpinned snapshot is never selected through `refs/main` or directory scan;
- an exact but incomplete snapshot is rejected;
- missing-cache encoders return the existing zero-vector shapes; and
- seeded cache paths, bytes, sizes, and modification times remain unchanged.

## Fresh Verification

The post-review gate used the explicit `goodq_core` interpreter and passed:

| Gate | Result |
|---|---:|
| Retrieval/model-cache unit and identity regressions | 23 passed, 8 skipped |
| UCF retrieval bridge and stress integration | 26 passed |
| Provisioner/bootstrap/cache regressions | 42 passed |
| Route-effect authority | 74 passed |
| **Passing tests** | **165 passed** |

Additional gates:

- four changed Python files parsed successfully;
- the registry, provisioner, route-effect registry, dependency files, and
  runtime packages remained unchanged;
- no download/provisioner/`refs/main` path entered the new inspector;
- staged and working-tree diff checks passed; and
- independent re-review returned `CLEAN` after the redirect correction.

No live endpoint, Qdrant service, model, configured cache, configured data root,
ingestion, identity surface, WSL distribution, public checkout, or mixed main
checkout was exercised.

## Current Library Contract

The implementation follows current primary documentation:

- [SentenceTransformer constructor](https://www.sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html)
  accepts a local path and an explicit `local_files_only` control.
- [Transformers offline mode](https://github.com/huggingface/transformers/blob/main/docs/source/en/installation.md)
  documents local-directory loading with `local_files_only=True`.

## Next Bounded Mission

Do not repeat the already-completed SQLite comparison. Its temporary Windows
witness established that ordinary connect can create a missing database,
`mode=ro` sees committed live-WAL rows and rejects writes, `mode=ro` may maintain
WAL coordination sidecars, and `immutable=1` can miss committed WAL content.

The next seam is summary-only SQLite read authority. Its governing invariant is:
live committed WAL truth outranks byte-identical sidecar purity. Retrieval
SQLite and retrieval telemetry remain separate, frozen seams.
