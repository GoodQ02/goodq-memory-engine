<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R-08 Workspace Hygiene Audit — 2026-07-29

## Scope

This audit classified the private repository's active `dev` worktree, the
historical root worktree, and every registered GoodQ worktree. It did not
inspect or remove corpus data, epoch stores, Qdrant snapshots, model caches,
machine-control-plane files, or public-release files.

## Active worktree classification

The active `dev` worktree was clean. All product folders, including `api`,
`cli`, `configs`, `docs`, `scripts`, `steps`, `tests`, `ui`, `vendor`, and
`wsl2_audio`, are tracked product authority. The 99 diagnostics files are
tracked evidence, not disposable logs. The only generated residue there was
the ordinary ignored Python bytecode and pytest cache.

## Historical-root classification

The historical root remains an unmerged, dirty worktree and is preserved.
Its installer executables, `logs`, `snapshots`, `dist`, `scratch`, and runtime
folders require independent artifact-retention decisions; none were removed.

The ignored root pytest/bytecode residue was separately classified as generated
and had no active code-path references. The unignored `.pytest_temp_clean`
directory was preserved for a future root-worktree decision.

## Worktree classification and executed prune

The fresh Git audit found 22 registered worktrees:

- 16 clean historical worktrees whose exact `HEAD` was already an ancestor of
  private `dev`;
- the active clean `dev` worktree; and
- five unmerged and/or dirty worktrees requiring retention decisions.

The user-approved first prune used `git worktree remove` sequentially for only
the 16 clean ancestors. Branch refs were retained. It also removed only ignored
pytest/bytecode cache directories from the active and historical roots.

Result: 16 worktrees (5,870.02 MB by pre-action file census) and 9.65 MB of
ignored cache residue were removed. The observed free-space increase was
5,316.78 MB. Git now reports six registered worktrees.

The exact paths, heads, cache paths, and before/after free-space values are in
The detailed private development receipt is intentionally not included in the public release.

## Preserved worktrees

| Worktree | Reason preserved |
| --- | --- |
| Historical root (`feature/semantic-identity-layer`) | Unmerged and dirty (89 changes) |
| Active `dev` runtime worktree | Product-development authority |
| `r05-api-authority` | Unmerged and dirty (5 changes) |
| `r08-identity-workbench` | Unmerged, clean evidence branch |
| `r08-reconciliation-20260720` | Unmerged and dirty (15 changes) |
| `r22-hermes-goodq` | Unmerged, clean evidence branch |

## Next decisions

1. Reconcile or explicitly retire the five preserved non-`dev` worktrees;
   never delete them merely because they are old.
2. Establish an installer/log/snapshot retention policy for the historical
   root before moving or removing its release artifacts.
3. Do not remove tracked diagnostics or current-state evidence as a space
   cleanup mechanism; they are the audit chain for this stabilized state.
