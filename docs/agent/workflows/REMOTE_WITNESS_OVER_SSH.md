<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-08-04 -->

# Remote Witness over SSH

## Purpose

Run one isolated, non-promoting witness on an approved follower without making
the SSH client responsible for the worker lifetime. On Windows, the launcher
uses a temporary Task Scheduler job because OpenSSH can otherwise terminate an
ordinary detached child when its client disconnects. The remote process writes
a durable receipt beside the witness root so an interrupted SSH session is an
observable transport event, not an ambiguous pipeline result.

## Scope and invariants

- Use only a named, approved follower such as GR-16 or GS-32.
- Use a private test clip staged under that device's validation root; do not
  add media to the release package or canonical corpus.
- Use a fresh witness root and scene `0` unless a different scene is explicitly
  approved.
- The witness stays non-promoting. A completed receipt is evidence, not a
  canonical ingestion approval.

## Operator sequence

1. Verify SSH identity, reachability, free space, and the installed GoodQ
   version read-only.
2. Stage the test clip once under the follower validation root.
3. On the follower, launch the durable runner from the installed runtime:

   ```powershell
   & "<installed-runtime>" -m cli.remote_witness launch `
     --artifact-root "<validation-root>\\witness_<id>" `
     --input-file "<validation-root>\\input\\clip.mp4" `
     --scene-indices 0
   ```

   The runner caps each child ingestion step at 600 seconds. This is a
   witness-only containment boundary; it does not change the production
   ingestion default for long scenes. A timed-out step must produce a terminal
   runner receipt and is not a passing witness.

4. Reconnect at any time and read the remote receipt:

   ```powershell
   & "<installed-runtime>" -m cli.remote_witness status `
     --artifact-root "<validation-root>\\witness_<id>"
   ```

5. When the receipt reaches `runner_finished`, inspect the sealed receipt,
   scene ledger, and `scene-zero.log`. If it reaches `failed`, repair the
   owning seam before another scene attempt.

## Receipt contract

The receipt is atomically replaced at each phase:

- `launch_requested` / `launcher_started`: durable remote worker accepted. On
  Windows, the latter records the temporary scheduler task and worker path.
- `preflight_started` / `preflight_sealed`: isolated root passed its strict
  checks and its prepared receipt was sealed.
- `runner_started`: records runner PID, command, and combined scene log path.
- `runner_finished`: records the runner exit code and finish time.
- `failed`: records the preflight or launcher exception.

The runner redirects child stderr into `scene-zero.log`. Do not wrap it in an
SSH command with `ErrorActionPreference=Stop`; nonfatal media warnings must not
terminate the remote parent before the ledger has a terminal result.

## First-use model behavior

Cold model downloads and CPU model initialization can take minutes. The
provisioner emits `[MODEL]` status before each first-use fetch and when the
model becomes ready. Treat those messages and receipt phase changes as progress;
do not classify an active first load as a hang solely because an SSH client is
quiet.
