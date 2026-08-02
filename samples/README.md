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
- No media fixture is shipped in this repository. The existing
  `scripts/bootstrap_onboarding.py` helper is an operator workflow, not an
  approved public fixture contract; any source it uses must be reviewed before
  a release workflow relies on it.
- Use a short clip you own or are licensed to process for any other local
  validation.
- A future public demo lane must use an owned synthetic debug kit, not
  third-party test-run media or private home media.
