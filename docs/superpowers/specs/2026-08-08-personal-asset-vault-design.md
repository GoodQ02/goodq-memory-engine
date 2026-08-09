<!-- DOC_BADGE: EXPERIMENTAL -->
<!-- DOC_STATUS: DRAFT_REVIEW -->
<!-- DOC_LAST_VERIFIED: 2026-08-08 -->

# Personal Asset Vault Design

## Goal

Create an immutable personal asset vault from which GoodQ4All can reproduce
offline installer packs without relying on an upstream service being available.
The vault retains source artifacts and their terms; it is not an installer
payload and does not grant redistribution rights.

## Boundaries

- The vault receives only complete, hash-verified source snapshots.
- A resumable acquisition workspace is quarantined and never serves packs.
- Each source revision is append-only after its seal is written.
- Personal, agreement-gated, and research-only assets remain distinct from
  distributable installer packs.
- A distributable pack is a derived, independently signed artifact with its
  own compatibility manifest. It must be reproducible from vault material.

## Vault Record

Each source snapshot contains:

- `source-manifest.json`: upstream origin, revision, acquisition time,
  filename, byte count, and SHA-256 for every source file.
- `terms/`: source license, terms, notices, and any required acceptance text.
- `disposition.json`: personal, agreement-gated, research-only, distributable,
  or excluded status, together with the reason and restrictions.
- `README.md`: restoration procedure, licensing obligations, and pack-derivation
  rules.
- `duplicates.json`: exact duplicate records, including the retained canonical
  source member and excluded duplicate members.

The snapshot directory name is derived from asset family, upstream revision,
and the canonical source-manifest digest. A later acquisition with any changed
file is a new snapshot; it never overwrites the sealed one.

## Capability Packs

The installer selects signed packs by capability and hardware compatibility:

- core CPU
- vision CPU
- audio CPU
- local GPU model, one model per large asset
- agreement-gated packs, one explicit acceptance receipt per upstream agreement
- personal-only packs, unavailable to distributable installers

Each pack contains a signed compatibility manifest, source-snapshot reference,
complete content list, SHA-256 records, notices, hardware profile, runtime
requirements, and pack-level digest. An installer accepts the pack only when
its compatibility contract matches; it never substitutes, downloads, or
partially installs content.

## NRC First-Asset Procedure

NRC is a personal/research-only, non-redistributable source snapshot. Its
official terms require appropriate license selection, acknowledgment, and no
redistribution of the data. The vault may retain the operator-acquired original
only with those terms and provenance preserved.

1. Inventory every downloaded NRC archive and compute its SHA-256.
2. Capture the official terms with the acquisition record.
3. Record the source disposition as personal/research-only.
4. Copy the complete canonical source set into a new vault snapshot.
5. Re-hash the copied set and verify it matches the source manifest.
6. Atomically write the vault seal only after all files and terms verify.
7. Remove the accidental duplicate source download only after the seal passes.
8. Retire the scratch source directory only after its retained files match the
   sealed vault inventory; do not alter the sealed vault.

## Failure Rules

- Missing terms, source identity, or any expected hash blocks sealing.
- An incomplete transfer stays quarantined and cannot be copied into the vault.
- A mismatch after copy blocks cleanup and leaves the source untouched.
- An agreement-gated asset requires a local acceptance receipt before it can
  become a personal installer input.
- No personal-only source may be emitted into a distributable pack.

## Verification

The first implementation must prove:

1. duplicate detection uses content hash, not filename;
2. the sealed manifest contains every retained source member and terms record;
3. copied vault bytes match the source manifest exactly;
4. an intentionally modified file prevents sealing and cleanup;
5. a pack manifest cannot reference an unsealed source snapshot.

## Non-Goals

- No GoodQ installation on the canonical desktop in this phase.
- No public release or public model redistribution in this phase.
- No silent deletion, source mutation, or partial-download adoption.
