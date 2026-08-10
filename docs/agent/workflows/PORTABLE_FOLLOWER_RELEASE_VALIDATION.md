<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-08-08 -->

# Portable Follower Release Validation

## Purpose

Validate a baseline installer on an approved follower without reusing a prior
install, canonical corpus, or SSH client lifetime as evidence. This workflow
applies to named followers such as GR-16 and GS-32.

## Required evidence before installation

1. Preserve the offline-build output folder, build log, release receipt, and
   four-file asset set.
2. Re-run the release-asset verifier against the exact source version and
   commit before transferring anything.
3. Record the follower identity, free space, existing GoodQ roots, and the
   intended validation root read-only.
4. If an old install must be removed, enumerate exact program and data roots,
   obtain approval, and retain the removal result. Never infer a clean baseline
   from a successful installer exit alone.
5. If the follower also holds an obsolete GoodQ release bundle, validation
   cache, or development snapshot, include only its exact approved roots in a
   compact pre-removal manifest. Preserve that manifest beneath the new
   validation root, remove the approved roots once, and verify each exact path
   is absent before staging the new release. Do not sweep unrelated user files
   or repositories.
6. Before removal, snapshot any active GoodQ installer, scheduled task, or
   runtime process. An old silent installer can keep its bundled Python wheel
   phase alive and lock the program tree. Do not overlap it with a replacement.
   If it is confirmed obsolete and its stop is approved, retain before/after
   process evidence, stop that exact process tree, then verify the approved
   roots are absent before launching the new installer.

## Installation and baseline gates

1. Transfer the complete release asset set once and verify its hashes on the
   follower before execution.
2. Install the verified setup executable. Preserve its exit code and install
   receipt.
3. Run `verify_offline_suite.ps1` from the installed program root, then run the
   Qdrant restore smoke. The offline suite verifies bundled media tools plus
   the required OCR engine and Python binding; both gates must pass before a
   scene is staged. If that script is absent, the installer is incomplete.
4. Confirm the installed runtime exposes both commands:

   ```powershell
   & "<installed-runtime>" -m cli.remote_witness --help
   & "<installed-runtime>" -m cli.run_ingestion --help
   ```

   A missing command is a packaging failure; rebuild before staging a scene.

## First-use and witness gates

1. Stage one private test clip only beneath the follower validation root.
2. Launch scene `0` with the durable runner in
   `REMOTE_WITNESS_OVER_SSH.md`. It must use a fresh non-promoting witness
   root.
3. Read the remote receipt rather than treating an SSH timeout as a scene
   result. It must reach `runner_finished` or `failed`.
4. For a cold model load, preserve `[MODEL]` progress output and the model
   download log. A silent client is not evidence of a hang while the remote
   receipt or model status continues to advance.
5. Inspect the sealed receipt, scene ledger, combined scene log, and the
   ingestion result file at `output/results.json` under the witness root.
   Audio transcription requires a terminal result; `pending` is incomplete
   evidence, not a pass.

## Completion record

Keep the build receipt, pre-removal manifest and active-process snapshot when
applicable, transfer-hash result, installer exit, offline-suite result,
restore-smoke result, remote receipt, sealed witness receipt, and a short
operator finding together. When the durable runner uses a scheduled worker,
also record that the task is absent after terminal completion; a replayable
task makes the witness receipt non-final. Do not promote the witness or
broaden ingestion as part of this workflow.

After the current candidate is verified, record its source commit and outcome
in the release roadmap before pruning superseded timestamped build outputs.
Retain the current candidate until it is replaced by a newer verified one; do
not retain old installers as alternate release authorities.
