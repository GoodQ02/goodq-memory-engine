<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_RUNBOOK -->
<!-- DOC_LAST_VERIFIED: 2026-09-26 -->
<!-- INSTRUCTION_REVIEW: 2026-09-26; documentation review, not a live ingestion witness -->

# Clean Memory Start Workflow

Use this procedure for an approved isolated ingestion probe, or cleanup of exact
operator-approved targets. A fresh probe does not require deleting prior epochs
or every collection named `goodq_`.

## Resolve Scope And Preserve Recovery

1. Read the applicable repository guidance. Identify the requested probe or
   cleanup, the owning runtime, and the intended checkout.
2. Resolve configuration using the existing project environment:

   ```powershell
   conda run --no-capture-output -n goodq_core python -m cli.print_config
   ```

   Keep output local and redact credentials before sharing it. Current-state
   documents are routing snapshots; verify the resolved epoch, data root, Qdrant
   endpoint, collection names, SQLite/KG paths, FAISS targets, and writer ownership.
3. Record exact paths and collection names in a dated local manifest. Distinguish
   source media, promoted memory, probe evidence, caches, and shared control state.
   Old labels and prefixes are not deletion criteria.
4. Prefer new isolated targets. If existing data must be removed, require explicit
   authorization for the listed targets, verify resolved absolute paths stay within
   the approved boundary, quiesce their writers through established controls, and
   preserve a consistent recoverable backup. Include SQLite sidecars in writer and
   backup handling. Do not delete shared control/recovery databases, watchdog state,
   or processing caches merely to obtain an empty probe epoch.

## Establish An Isolated Empty Probe

1. Select a fresh epoch through the existing local configuration mechanism. Do not
   reuse an occupied epoch or infer emptiness from its name.
2. Confirm every resolved probe store belongs to that epoch and is separate from
   retained stores. Record the active collection names and their point counts.
   Preserve other epochs' collections, even when they share a `goodq_` prefix.
3. If collection creation is needed and authorized, use the existing initializer:

   ```powershell
   conda run --no-capture-output -n goodq_core python scripts/init_qdrant_collections.py
   ```

   Inspect its resolved targets first. It skips existing collections, so successful
   execution is not proof that they are empty or have the correct schema.
4. Verify the selected collections have zero points and dimensions consistent with
   the active model configuration. Confirm selected relational stores are absent
   or logically empty, and selected FAISS stores contain no prior probe vectors.
   Existing explicit-ID index format alone does not establish emptiness.
5. Record the baseline. `scripts/generate_post_manifest.py` can collect supporting
   evidence only when its assumptions match the task: it currently queries a
   fixed loopback Qdrant endpoint and all `goodq_` collections, rather than only
   the resolved epoch. It can still write a report after a Qdrant query fails.
   Inspect query errors and match endpoint, collection names, and epoch explicitly;
   an empty report is not proof of empty stores. Its file-size observations do not
   prove logical SQLite emptiness. Do not use this helper as an acceptance gate
   for isolated-epoch cleanup or infer row counts from database file size.

## Run One Scene And Inspect Its Evidence

Use the established ingestion entrypoint for one operator-approved small scene.
Inspect the configured API's `/api/status`, `/api/runs/latest/evidence`, and
`/ui/operator_console_v1/` where available, alongside the durable run artifacts.

Bind observations to the new run and epoch. Check current-run audio, scene context,
temporal indexing, retrieval, and applicable KG/vector evidence. An HTTP success,
old populated collection, or earlier successful scene is not this run's proof.

Do not expand into broad ingestion or promotion without authorization for that
scope and useful scene-level evidence. Update the workflow's existing evidence
owner; do not hand-edit generated current-state projections.

## Public Reference Boundary

Private historical cleanup procedures and workstation receipts are omitted from
this public source. Use this current procedure and your own resolved configuration;
old epoch names, model dimensions, and deletion examples in Git history are not
current instructions or authorization.
