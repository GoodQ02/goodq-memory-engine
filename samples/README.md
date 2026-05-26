# Samples

This directory contains documentation assets and optional local sample scaffolding.

## Structure

- `samples/assets/`
  - Documentation/demo media assets (for example, reference PNG assets).
- `samples/ingestion/`
  - Optional local location for operator-provided ingestion examples. It is not
    a first-run inbox and may contain ignored local media on developer machines.

## Usage Notes

- These files are for testing, validation, and demonstration.
- They are not required for core runtime operation.
- Production ingestion should continue to use normal runtime inbox/workflow paths.
- Root-level `smoke_inbox/` and `test_input/` are local scratch inbox names, not
  supported first-run drop zones, and are intentionally ignored.
- Large or ignored media that may exist under `samples/ingestion/` is local
  scaffold material only. It is not base installer content, product memory, or
  a public demo fixture unless a separate owned-fixture manifest explicitly
  selects it.
- There is no public `sample.mp4` fixture. Use your own small owned media file
  for video ingestion tests.
- The future public preflight/demo lane should use an owned synthetic debug kit,
  not Seinfeld/test-run media or private home media.
