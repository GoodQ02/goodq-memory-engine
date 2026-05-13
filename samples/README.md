# Samples

This directory contains example artifacts used for ingestion and smoke-testing workflows.

## Structure

- `samples/ingestion/`
  - Placeholder location for local ingestion examples and operator-provided test
    inputs.
- `samples/smoke/`
  - Placeholder location for smoke test media inputs and quick-run test fixtures.
- `samples/assets/`
  - Documentation/demo media assets (for example, reference PNG assets).

## Usage Notes

- These files are for testing, validation, and demonstration.
- They are not required for core runtime operation.
- Production ingestion should continue to use normal runtime inbox/workflow paths.
- Large or ignored media that may exist under `samples/ingestion/` is local
  scaffold material only. It is not base installer content, product memory, or
  a public demo fixture unless a separate owned-fixture manifest explicitly
  selects it.
- The future public preflight/demo lane should use an owned synthetic debug kit,
  not Seinfeld/test-run media or private home media.
