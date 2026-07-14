<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — add the projection-neutral same-handle bounded-read
primitive required by the future Windows external-pin reader.

## Outcome

Extend the completed shared Windows held-handle backend with one bounded-read
method that returns both the exact prefix read and whether synchronous EOF was
observed, without exposing a raw handle or changing the filesystem observer.

This mission corrects a prerequisite discovered before external-pin reader
implementation. The reader cannot securely inspect or parse content through
the current exact seven-method opaque-handle boundary, and no private-handle or
pathname workaround is permitted.

## Governing evidence

- held-handle extraction checkpoint `0f567557`;
- `docs/diagnostics/R07_WINDOWS_HELD_HANDLE_EXTRACTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_READER_CAPABILITY_GAP_AUDIT_2026-07-13.md`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

Raw Windows handles remain backend-owned and opaque. The future reader may
consume only explicit shared capabilities operating on the same held token; it
may never import private symbols, reopen descendants by pathname, duplicate the
handle, or copy held-handle mechanics.

## Exact implementation scope

- Modify only `steps/common/windows_held_handle.py` and
  `tests/unit/test_windows_held_handle.py` during the source/test seam.
- Add exactly:

  ```python
  def read_file_bounded(
      self,
      handle: object,
      *,
      maximum_bytes: int,
  ) -> tuple[bytes, bool]:
      ...
  ```

- Require an exact integer limit from 1 through 66. Invalid limits fail as the
  existing path-free `observation_failed` before native I/O.
- Rewind and read only the existing live backend token. Return
  `(prefix, True)` only after a successful zero-byte synchronous read proves
  EOF; reaching the cap first returns `(prefix, False)` without reading beyond
  the cap.
- Preserve existing sharing/error/cause translation and token lifecycle.
- Keep `hash_file()` unchanged and prove both read operations are order-
  independent because each rewinds first.
- Preserve the exact four-symbol module `__all__`; the backend public method
  set gains only `read_file_bounded`.

## Boundaries

- Do not modify the filesystem observer, configuration, protected membership,
  candidate plan, job, approval, MiniAgent, or cleanup contracts.
- Do not add or select `READ_CONTROL`, token, security-descriptor, ACL,
  `AccessCheck`, Known Folder, external-pin evidence, or reader behavior in this
  seam.
- Do not add enrollment, publication, rotation, recovery, authenticated
  composition, protected-member observation, Qdrant observation, runnable
  planning, or execution behavior.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  service, GoodQ data, Qdrant, evidence store, or cleanup target.
- A native witness may use only a temporary test-created file reached through
  root enumeration and `open_by_id`.

## Completion gate

Witness RED before production code. Then prove the exact signature, 65-byte EOF,
66-byte cap, empty/short reads, invalid limits, invalid-token lifecycle,
impossible native counts, and `hash_file` interoperability. Run the native
temporary-file witness, focused shared/adapter suite, approved authority union,
compile/import/documentation/drift/banned-token/dependency/diff gates, and three
independent current-byte reviews before a private checkpoint.

After that checkpoint, return to a read-only decision on the opaque token,
security-descriptor, and `AccessCheck` capability boundary. Do not begin the
external-pin reader until that security prerequisite is selected and verified.
