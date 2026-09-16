<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-09-01 -->

# Managed Offline Release Build

## Purpose

Produce a profiled installer from verified local inputs while proving that the
build had no public egress, without disabling Windows network adapters. This is
the reusable operator method for private release builds before portable
follower validation.

## Invariant

Network adapters are never disabled, disconnected, or re-enabled. The wrapper
creates one uniquely named outbound Windows Firewall rule in the active policy
store, removes that exact rule in `finally`, and records the before/after
adapter state plus connectivity probes.

## Preconditions

1. Private `dev` is clean and contains the intended installer change.
2. A terminal `goodq.prebuild-readiness.v1` receipt is bound to the exact source
   commit and tree selected for the build.
3. The staged dependency cache and manifest verification are current.
4. The installer semantic compatibility checker passes from that source tree.
5. The desktop launcher resolves the project-local
   `run_offline_release_with_network_toggle.ps1` wrapper.
6. The operator can approve UAC elevation. If elevation is declined, no
   containment rule is created and no build is attempted.

## Semantic compatibility and source-bound receipt gate

Run the read-only checker from the exact clean release source before allowing
network preflight, output-root creation, staging-directory creation, or junction
creation:

```powershell
conda run --no-capture-output -n goodq_core python scripts/install/verify_installer_semantic_contract.py --check --repo-root .
```

Exit `0` means the compared installer projections are compatible, exit `2`
means a semantic mismatch, and exit `1` means the checker could not execute or
load its contract. Only exit `0` may advance. The outer release entrypoint runs
this gate after receipt revalidation and before network preflight or output
creation. The inner installer builder runs it after source-identity verification
and before staging or junction creation. CI runs the same named gate before the
test suite.

The checker protects the cross-language projections owned by
`installer_contract.py`, `goodq_version.py`, and the installer profile contract:
schema versions, required manifest and receipt fields, release profiles, CLI
flags, payload bindings, authenticated manifest transport, one-handle pack
processing, WSL argument transport, and gate ordering. Do not duplicate those
values into release prose or bypass the checker with a local wrapper.

A source-bound receipt is exact-tree evidence. Any later code or documentation
commit makes the older receipt historical for build authorization, even when no
installer behavior changed. Generate and verify one fresh receipt from a clean
dedicated worktree before packing from the newer tree.

The authenticated application boundary is also invariant:

- the Go launcher reads each payload manifest once, verifies the Ed25519
  signature over those bytes, parses schema version 2 from the same bytes, and
  streams those exact authenticated bytes to Python through stdin;
- NSIS invokes that one authenticated apply path and does not start an elevated
  Python process that reopens a manifest by pathname;
- Python accepts the manifest only through `--manifest-stdin` and holds one
  write/delete-denying pack handle from size/hash verification through ZIP
  membership validation and extraction; and
- the WSL probe uses a fixed shell program while workspace, model path, probe,
  and device values travel as arguments or environment entries.

## Operator sequence

1. Start **Build GoodQ4All Offline Release.bat** from the desktop.
2. Approve UAC when prompted. The wrapper passes the resolved local Conda
   launcher and release output root into the elevated process.
3. The wrapper records `network-toggle-receipt.json`, adds its temporary
   outbound rule, and invokes the ordinary release build.
4. The ordinary release build revalidates the exact source-bound readiness
   receipt and semantic compatibility before creating its output root.
5. The ordinary preflight proves containment with a bounded direct public TCP
   egress probe; it must not rely on a cacheable DNS lookup.
6. The build produces the declared profile asset set, release manifest,
   checksum receipt, and build log below one timestamped output root.
7. The wrapper removes its exact firewall rule, verifies adapter state remains
   unchanged, and probes restored public connectivity.

## Acceptance receipt

The output root must contain all of the following:

- `network-toggle-receipt.json` with `containment_applied: true`,
  `containment_removed: true`, `build_exit_code: 0`, and unchanged adapter
  state.
- `offline_build.log` showing successful source-receipt revalidation and the
  semantic compatibility gate before output or staging activity, followed by
  the network preflight and local-cache build.
- `offline_build_receipt.txt` reporting `pass: true`, the expected version,
  exact source commit, and four named assets.
- `assets/` containing the setup executable, launcher, manifest, and checksum
  file.

## Failure handling

- A missing nested build log means the elevated wrapper did not pass a required
  launch input; repair that handoff before retrying.
- A failed egress preflight means containment was not proved; inspect the
  wrapper receipt and preflight log, then repair the containment seam.
- A failed restoration probe is a warning requiring inspection; do not retry
  until the receipt confirms the temporary rule was removed. If the rule is
  absent, adapters match their recorded state, and a fresh bounded TCP probe
  succeeds after a short recovery window, record delayed probe recovery rather
  than treating the successful build as a containment failure.
- Do not replace this method with adapter toggles. Those alter persistent
  machine state and are outside this workflow.

## Next gate

After a complete acceptance receipt, follow
`PORTABLE_FOLLOWER_RELEASE_VALIDATION.md` on one named follower. Preserve the
release output and transfer-hash evidence; do not promote or broaden ingestion
as part of installer validation.

## Candidate retention and pruning

The newest complete, hash-verified profile candidate is the only installer
output retained for the active follower-validation lane. Before removing an
older timestamped installer output, verify the newer candidate's exact source
commit, clean-tree declaration, asset set, release manifest, checksum, and
network-containment receipt. Distill any reusable lesson into the applicable
workflow or the release roadmap first, then remove only the explicitly
inventoried older timestamped build roots.

The release output directory is not an asset vault, dependency cache,
repository, or runtime-validation root. Never use a pruning operation against
those boundaries. Git history, the signed current manifest, and durable
workflow/roadmap evidence are the retained authority for superseded builds;
old executable copies are not a second release authority.
