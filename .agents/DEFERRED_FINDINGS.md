# Deferred Findings

The following findings were surfaced by Codex during its read-only audit. These findings are deferred to future roadmap items and must not be implemented during this cycle.

1. **`cli/clean_memory.py:200-209`** — `_validate_path_component()` does not reject `/`, `\`, C0 controls, or DEL.
   - **Future Owner:** R-08.

2. **`snapshot_manifest()`** — equal-value distinct exact `bytes` oracle gap.
   - **Future Owner:** R-08.

3. **Nested final location type-parameterization oracle gap.**
   - **Future Owner:** R-08.

4. **`invoke()` dependency public-error graph leakage** — re-raises exact dependency public errors unchanged.
   - **Future Owner:** R-08.
