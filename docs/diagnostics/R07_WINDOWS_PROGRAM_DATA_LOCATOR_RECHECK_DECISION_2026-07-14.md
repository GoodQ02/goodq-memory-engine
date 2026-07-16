<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows ProgramData Locator And Recheck Decision

## Outcome

Create one import-pure shared Windows ProgramData locator authority before
authenticated protected-member composition is implemented.

The exact next implementation/parity seam is four files:

1. add `steps/common/clean_memory_windows_program_data_locator.py`;
2. add `tests/unit/test_clean_memory_windows_program_data_locator.py`;
3. adapt `cli/clean_memory_external_pin.py`; and
4. adapt `tests/unit/test_clean_memory_external_pin.py`.

The completed protected-manifest reader and its tests remain unchanged. The
shared checkpoint extracts the current external-pin locator mechanics and
adapts that reader in the same rollback boundary. It does not implement
protected-member observation, authenticated composition, planning, approval,
or cleanup.

## Governing Invariant

There must be one production authority for the actual Windows
`FOLDERID_ProgramData` location. Environment, configuration, current directory,
repository discovery, caller input, a guessed default, and a second copied
resolver are never authority.

The shared module owns only native locator mechanics and the fixed clean-memory
pin-chain spelling. The external-pin reader continues to own physical and
security observation. Later composition owns invocation order, direct-output
rechecks, lexical membership exclusion, race classification, and outward
composition errors.

## No-Repeat Result

Keep these completed seams closed:

- the external-pin reader's exact four exports, no-argument operation,
  thirteen-error taxonomy, ten-key evidence, route policy, and physical and
  security race fences;
- the protected-manifest reader's exact four exports, fixed-child operation,
  direct pin-digest comparison, nine-key evidence, and mismatch-before-parser
  ownership;
- the shared held-handle, Windows security-mechanics, reader-identity, bounded
  read, manifest-validator, membership, filesystem-observer, and candidate-plan
  authorities; and
- enrollment, publication, rotation, recovery, Qdrant, jobs, tokens,
  MiniAgent, approval, and cleanup execution.

The authenticated protected-manifest reader is already implemented at
`66ee4f47`; it is not the missing reader. The remaining missing capability is
the shared ProgramData locator used by the existing external reader and later
composition.

## Reconciled Ownership Decision

Three bounded read-only traces considered two alternatives.

The selected owner is **shared extraction parity**. Today the only real
`SHGetKnownFolderPath` implementation is private to
`cli.clean_memory_external_pin`. Keeping it there would force future
composition to import a private CLI symbol or copy the GUID, ABI, cleanup,
lexical grammar, and failure semantics. Either choice creates a second
authority or reverses dependency direction.

A composition-local resolver was rejected even though composition owns the
recheck policy. Leaving the current private implementation intact and adding a
second resolver is duplication, not parity. Moving the one implementation into
composition would make the completed physical reader depend on a later
orchestration owner. The shared module removes the private production owner in
the same checkpoint that introduces the common one.

This refines earlier wording that called the locator "composition-owned":
composition owns **when and how** the locator is bracketed and compared; the
shared module owns the single native acquisition mechanism.

## Dependency Direction

The dependency direction is one-way:

```text
cli.clean_memory_external_pin
    -> steps.common.clean_memory_windows_program_data_locator

future authenticated composition owner
    -> steps.common.clean_memory_windows_program_data_locator
future authenticated composition owner
    -> cli.clean_memory_external_pin public reader
future authenticated composition owner
    -> cli.clean_memory_protected_manifest public reader
```

The shared locator imports no `cli` module, held-handle backend, security
mechanics, protected manifest, membership projection, configuration, service,
environment reader, or later composition owner.

## Exact Shared Public Surface

The new module has exactly five exports:

```python
__all__ = (
    "CleanMemoryWindowsProgramDataLocatorError",
    "CleanMemoryWindowsProgramDataLocation",
    "CleanMemoryWindowsProgramDataLocator",
    "verify_clean_memory_windows_program_data_locator_abi",
    "bind_clean_memory_windows_program_data_locator",
)
```

`verify_clean_memory_windows_program_data_locator_abi() -> None` is
capability-free. It requires an exact 8-byte pointer width and proves the exact
16-byte GUID layout before a consumer loads a DLL.

`bind_clean_memory_windows_program_data_locator(*, shell32: object,
ole32: object) -> CleanMemoryWindowsProgramDataLocator` accepts only
already-loaded libraries. It repeats the ABI gate, binds only
`SHGetKnownFolderPath` and `CoTaskMemFree`, performs no Known Folder call, and
returns one provenance-bound capability.

`CleanMemoryWindowsProgramDataLocator.resolve()` has no arguments and returns
one exact `CleanMemoryWindowsProgramDataLocation`. Neither public class can be
constructed directly, copied, deep-copied, pickled, reduced, or meaningfully
represented. Their representations contain only the class name and
`<redacted>`.

The immutable location exposes read-only exact values required by the two
consumers:

- `drive_root`, such as the accepted uppercase local drive root;
- `program_data_components`, the actual accepted Known Folder components;
- `fixed_directory_components`, exactly
  `("GoodQ", "authority", "clean-memory")`; and
- `pin_name`, exactly `"protected-boundaries.sha256"`.

Exact equality compares those four retained values without case folding or
normalization. The object exposes no full-path projection, digest, JSON,
mapping, iterator, filesystem capability, or log formatter.

## Shared Error Contract

`CleanMemoryWindowsProgramDataLocatorError` is an immutable path-free
`RuntimeError` with only these codes:

| Code | Meaning |
|---|---|
| `unsupported_platform` | wrong selected ABI, missing library/export, or unsupported Windows locator capability |
| `redirected_boundary` | a successful API output violates the fixed lexical grammar |
| `observation_failed` | call, output, decode, shape, cleanup-only, or unknown native observation failure |

Unknown codes are rejected. Messages, attributes, causes, and contexts never
contain a path, HRESULT, pointer, native exception text, or returned buffer.

The shared module deliberately has no `pin_member_overlap` or
`observation_raced` code. Those are later composition policy. A later
post-acceptance acquisition failure or unequal exact location is translated to
the composition boundary's path-free `observation_raced`; lexical intersection
is translated to its separate path-free overlap error.

The external adapter preserves phase-specific existing behavior:

- a shared locator ABI-preflight failure maps to existing
  `unsupported_security`, matching the current private GUID/pointer-layout
  preflight;
- shared binder/export `unsupported_platform` maps to existing
  `unsupported_platform`;
- resolve-time `unsupported_platform`, `redirected_boundary`, and
  `observation_failed` map to the identically named existing codes; and
- invalid caller shape or any unexpected shared failure maps to existing
  `observation_failed`.

No shared error escapes the reader. This phase-aware translation preserves the
frozen public error oracle rather than treating a shared mechanics code as the
consumer's outward phase policy.

## Native Acquisition Contract

The module owns the exact in-memory GUID
`{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}` and calls only:

```text
SHGetKnownFolderPath(FOLDERID_ProgramData, 0, NULL, &output)
CoTaskMemFree(output)
```

The HRESULT is a signed 32-bit result. Failure or success with a null output is
`observation_failed`. A non-null output produced on either success or failure
is owned immediately and freed exactly once. A failing HRESULT's output is
never dereferenced. On success the null-terminated Unicode string is detached,
validated, and the native buffer is freed before a location can return.

The frozen lexical grammar is exact:

- nonempty, NFC, and no more than 32,767 UTF-16 code units;
- uppercase `A` through `Z` local drive plus `:\\`;
- no trailing separator, forward slash, percent marker, UNC, device prefix, or
  relative form;
- one through 64 ProgramData components;
- no empty, `.` or `..` component;
- no component ending in dot or space; and
- no colon, C0 control, or DEL character in a component.

The module performs no `Path.resolve`, `abspath`, `normpath`, case
normalization, environment expansion, filesystem search, fallback, or
existence check. It appends only the fixed components and pin name after the
actual output passes the grammar.

## Cleanup And Control-Flow Precedence

Every non-null native buffer is released before return or propagation.

- A clean operation plus clean release returns the exact location.
- A clean operation plus release failure returns no location and raises
  `observation_failed`.
- An ordinary primary remains primary; a sanitized cleanup-only
  `observation_failed` is linked without replacing it.
- `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` keep object identity,
  traceback, cause/context topology, and suppression after raw links are
  sanitized; a release failure is linked without replacing the control-flow
  primary.
- Every public linked node is a closed shared locator error and graph handling
  is bounded against cycles or excessive depth.

The adapter translates the complete shared graph into the completed external
reader graph and preserves its existing backend, token-session, held-handle,
and cleanup ordering.

## External-Reader Extraction Parity

After adaptation, `cli.clean_memory_external_pin`:

1. runs the shared locator ABI verification and existing security ABI
   verification before native load;
2. preserves the exact DLL load order `kernel32`, `shell32`, `ole32`, then
   `advapi32`;
3. passes the already-loaded Shell32 and Ole32 libraries to the shared binder;
4. preserves the current token acquisition and effective-token brackets around
   `locator.resolve()`;
5. opens only `drive_root` by pathname;
6. traverses every actual ProgramData component, every fixed directory
   component, and the pin by the same held-handle/open-by-ID route;
7. preserves all physical, security, payload, membership, final-fence, and
   cleanup behavior; and
8. returns byte-identical canonical evidence and detached digests.

The external source no longer defines or assigns the GUID, ProgramData fields,
fixed child constants, pin name, Known Folder value class, lexical validator,
resolver, or Shell32/Ole32 ABI. It imports only the shared public names it uses.
Its exact four-symbol public API remains unchanged.

## Later Composition Recheck Contract

This checkpoint does not implement composition. The later owner must invoke
the public shared capability itself and must never accept a caller path or a
caller-constructed location.

The locator brackets direct evidence as follows:

1. resolve configuration;
2. acquire an initial exact location;
3. invoke the no-argument external-pin reader;
4. reacquire and require exact location equality;
5. invoke the no-argument protected-manifest reader and bind its direct digest
   to the direct pin evidence;
6. project exact protected membership from direct configuration and manifest
   outputs;
7. recheck exact direct types, private canonical bytes, and detached digests;
8. reacquire the location, require exact equality, and perform lexical
   pin-chain/member exclusion before protected-member I/O;
9. invoke the future protected observer with direct pin-chain physical
   exclusion identities; and
10. at the final fence, recheck every direct input and require one more exact
    locator reacquisition/equality before composition returns.

This stronger bracketing refines the earlier sequence because the external
reader intentionally emits no path. It does not invoke either physical reader
twice and does not treat a location object as proof that a reader ran.

For lexical comparison, composition converts the already-canonical location
and membership values into transient component tuples. It case-folds only the
comparison keys and compares drive plus complete component boundaries. String
prefix tests are forbidden. Equality or ancestor/descendant intersection with
any pin-chain prefix fails before protected-member I/O. No comparison key,
location, or raw member path enters evidence, logs, errors, API output, or
durable state.

The future protected observer, not this module, compares the five direct
path-free pin-chain physical identities against every protected parent and
member identity. Lexical checks never substitute for physical alias proof.

## Exact RED Matrix

Before production code, the new direct tests must fail for the absent shared
authority and prove at least:

1. the module and exact five exports are absent;
2. the current external source still owns the private GUID, ABI, validator,
   resolver, fixed children, and pin name;
3. exact class/function signatures and nonconstructible, noncopyable,
   nonserializable, repr-redacted capability and location values;
4. import purity and no import-time native, filesystem, environment, network,
   subprocess, logging, output, or path mutation;
5. exact GUID bytes, 8-byte pointer width, 16-byte layout, Shell32/Ole32 ABI,
   and binder-without-operation behavior;
6. exact GUID, flags `0`, null token, pointer output, signed HRESULT, and
   once-only release behavior;
7. success/null, failure/null, failure/non-null, decode, malformed text,
   cleanup-only, ordinary-primary, and control-flow-primary quadrants;
8. the complete lexical acceptance/rejection corpus, UTF-16 and component
   caps, and exact fixed-child append;
9. exact location equality and inequality without case normalization;
10. absence of caller path, environment, configuration, CWD, repository
    discovery, fallback, alternate loader, or filesystem capability;
11. external validation/binding/resolution order and byte-for-byte evidence,
    error, trace, traversal, and cleanup parity; and
12. AST containment that removes every private locator authority from the
    external source and rejects private imports or copied mutants.

Direct tests use independent golden ABI and lexical vectors. They must not
import private external-reader symbols or `_ReaderWorld`; test-only sharing
cannot prove that production has one authority.

## Verification Gate

Run sequentially through the explicit `goodq_core` interpreter:

- the direct new locator suite;
- the adapted external-pin suite with its frozen 499-node zero-drop receipt;
- the unchanged 148-test protected-manifest suite;
- unchanged 254-test security mechanics and 167-test held-handle suites;
- unchanged 46-test filesystem observer, 65-test reader-identity, and 205-test
  validator-plus-membership gates;
- the zero-drop 1,422-test pre-manifest authority union;
- the expanded reader-first combined authority gate, with the fresh total
  recorded against the prior 1,570 baseline;
- exact four-file compilation, source census, staged diff, and whitespace
  checks;
- import/API/AST containment and negative-mutant oracles;
- documentation authority, semantic drift, banned-token, dependency-drift,
  generated-index, and committed-diff gates; and
- at least two independent current-byte lifecycle/parity reviews after all
  corrections.

Checkpoint implementation and documentation separately. Only after this
four-file checkpoint may the roadmap advance to the protected-member observer
and pin-chain physical-exclusion boundary.

## Rejected Alternatives

- **Composition-local copy:** leaves two native locator authorities.
- **Import the external private resolver:** reverses dependency direction and
  makes a physical CLI reader shared authority.
- **Widen either reader API:** leaks path-bearing state and reopens completed
  reader contracts.
- **Environment or configured ProgramData:** replaces the Windows Known Folder
  authority with ambient input.
- **Caller path or location:** lets a caller select the trust root.
- **Full-path projection or digest:** creates durable path-bearing evidence not
  required by either consumer.
- **Filesystem normalization or search:** silently changes or guesses the
  selected location.
- **Shared overlap/race policy:** mixes later composition authority into native
  locator mechanics.
- **Second physical read during composition:** duplicates the completed pin or
  manifest readers instead of rechecking direct outputs.

## Independent Review And Evidence Boundary

Three bounded read-only audits traced current ownership, external-reader
parity, lifecycle/error precedence, later composition requirements, and the
smallest file/test census. Two selected shared extraction parity; the dissenting
composition-local proposal was rejected because it left the current private
resolver in place and therefore could not satisfy the one-authority invariant.

Current Microsoft Win32 documentation was also checked through Context7. It
confirms that `SHGetKnownFolderPath` returns a caller-owned null-terminated
Unicode buffer, accepts flags `0`, returns an HRESULT, omits the trailing
backslash, and requires `CoTaskMemFree`.

This decision read repository source, tests, contracts, checkpoint evidence,
and current public API documentation only. It did not resolve or inspect live
ProgramData, a production pin or manifest, token, ACL, descriptor, configured or
protected root, service, GoodQ data, Qdrant, evidence store, job, MiniAgent,
approval, or cleanup target.
