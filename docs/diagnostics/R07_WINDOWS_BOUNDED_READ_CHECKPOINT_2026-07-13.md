<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Windows Bounded-Read Checkpoint

## Outcome

The projection-neutral same-handle bounded-read capability is implemented and
privately checkpointed:

```text
73430481 feat: add bounded Windows held-handle reads
```

`WindowsHeldHandleBackend.read_file_bounded()` accepts only an exact integer
limit from 1 through 66, validates the existing opaque live token, rewinds that
same native handle, and returns detached `(prefix, eof_observed)` evidence. It
observes EOF only after a successful zero-byte synchronous read. Reaching the
cap returns `False` without an extra probe or reading byte 67.

## Closed Contract

- The exact signature is:

  ```python
  def read_file_bounded(
      self,
      handle: object,
      *,
      maximum_bytes: int,
  ) -> tuple[bytes, bool]:
      ...
  ```

- Invalid booleans, integer subclasses, non-integers, zero, negative values,
  and values above 66 fail path-free before native I/O.
- Foreign, closed, and post-context tokens fail before seek or read.
- Every native read request is positive and bounded by remaining capacity.
- A native count larger than the requested remainder fails closed.
- Existing sharing/error/cause translation and handle ownership remain intact.
- `hash_file()` remains byte-unchanged; both operations independently rewind
  and are order-independent.
- Module `__all__` remains the exact four-symbol export. The backend public
  method set gains only `read_file_bounded`.

## TDD and Oracle Correction

The first RED proved the public method and exact signature were absent. A second
behavioral RED proved the initial deliberate stub could not satisfy EOF, cap,
or hash-interoperability behavior.

Independent test-oracle review then found that three passing assertions selected
one incidental `ReadFile` chunk schedule. Those assertions were replaced before
checkpoint with invariant-level receipts: positive requests, remaining-cap
bounds, native count bounds, exact cumulative bytes, final zero-byte EOF, and no
post-cap probe. All three final reviewers read the corrected bytes.

## Fresh Verification

The committed implementation bytes passed with the explicit `goodq_core`
interpreter:

| Gate | Result |
|---|---:|
| Shared backend plus observer adapter | 114 passed |
| Native drive-root/open-by-ID witnesses | 3 passed |
| Approved clean-memory authority union | 398 passed |
| Python compilation | passed |
| Exact export/import-purity gates | passed in focused suite |
| Documentation authority and semantic drift | passed |
| Banned-token and dependency drift | passed |
| Staged file census | exactly 2 implementation files |
| Staged diff check | passed |
| Independent backend/lifecycle review | CLEAN |
| Independent adapter/parity review | CLEAN |
| Independent test-oracle review | CLEAN after oracle correction |

Two inherited temporary-tree observations reported the finite
`observation_raced` outcome during broader suite attempts. Each exact witness
passed immediately in isolation, and fresh complete focused and authority-union
runs then passed without source changes. The failures were not converted into a
weaker oracle or hidden retry.

The reviewed committed working-tree hashes are:

```text
steps/common/windows_held_handle.py
0D219E20ADE904128AD00C3303B6015319AF809C7ACBB1928D4FF573993CA694

tests/unit/test_windows_held_handle.py
58774882770F70EC35AF6BB48DF89E930AA706F56479C8BDD4AF67872EC15823
```

## Preserved Boundaries

No filesystem-observer, configuration, membership, candidate-plan, job,
approval, MiniAgent, cleanup, token, descriptor, ACL, `AccessCheck`, Known
Folder, external-pin reader, Qdrant, or execution contract changed.

No live ProgramData location, pin, token, ACL, configured root, service, GoodQ
data, Qdrant store, evidence store, job, MiniAgent, or cleanup authority was
read or changed. Native access was limited to pytest-created temporary files.
Backend observation reached them through drive-root enumeration and
`open_by_id`; the incompatible-writer fixture separately opened only its own
temporary file by pathname to establish the exclusive-writer precondition.

## Next Bounded Seam

Return to a read-only decision on the opaque token, security descriptor,
process token, generic mapping, and `AccessCheck` boundary. Do not implement the
external-pin reader until that security prerequisite is selected, implemented,
and independently verified.
