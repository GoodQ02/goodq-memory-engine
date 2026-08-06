<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-08-06 -->

# Managed Offline Release Build

## Purpose

Produce a baseline installer from the verified local cache while proving that
the build had no public egress, without disabling Windows network adapters.
This is the reusable operator method for private release builds before a
portable follower validation.

## Invariant

Network adapters are never disabled, disconnected, or re-enabled. The wrapper
creates one uniquely named outbound Windows Firewall rule in the active policy
store, removes that exact rule in `finally`, and records the before/after
adapter state plus connectivity probes.

## Preconditions

1. Private `dev` is clean and contains the intended installer change.
2. The staged dependency cache and manifest verification are current.
3. The desktop launcher resolves the project-local
   `run_offline_release_with_network_toggle.ps1` wrapper.
4. The operator can approve UAC elevation. If elevation is declined, no
   containment rule is created and no build is attempted.

## Operator sequence

1. Start **Build GoodQ4All Offline Release.bat** from the desktop.
2. Approve UAC when prompted. The wrapper passes the resolved local Conda
   launcher and release output root into the elevated process.
3. The wrapper records `network-toggle-receipt.json`, adds its temporary
   outbound rule, and invokes the ordinary release build.
4. The ordinary preflight proves containment with a bounded direct public TCP
   egress probe; it must not rely on a cacheable DNS lookup.
5. The build produces the four-file asset set, release manifest, checksum
   receipt, and build log below one timestamped output root.
6. The wrapper removes its exact firewall rule, verifies adapter state remains
   unchanged, and probes restored public connectivity.

## Acceptance receipt

The output root must contain all of the following:

- `network-toggle-receipt.json` with `containment_applied: true`,
  `containment_removed: true`, `build_exit_code: 0`, and unchanged adapter
  state.
- `offline_build.log` showing the preflight and local-cache build.
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
