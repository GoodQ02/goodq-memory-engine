<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/bootstrap/doc_authority_map.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

GoodQ4All Authority Memo

Historical note: this memo is preserved as a runtime-authority consolidation
snapshot. It no longer outranks the current documentation authority map,
architecture contracts, bootstrap contracts, or live persisted runtime truth
surfaces.

Status: Declarative; Zero-Change; Canonical
Effective Date: Upon commit
Scope: Runtime authority only (no architectural change)

1. Purpose
This memo consolidates runtime authority statements already present in GoodQ4All documentation.
It exists to reduce ambiguity caused by distributed documentation.
It introduces no new behavior, refactors, or code changes.

2. Relationship to the Sealed Basement
Basement phase status: "Basement phase sealed + truth plumbing sealed (read-only)."
Active epoch + stores: `docs/data_epochs.md` + `configs/config.yaml` (`paths.*`, `qdrant.collections.*`, `phase6.*`).
This memo does not modify basement contracts; it only consolidates them.

3. Canonical Configuration Authority
Canonical runtime config: `configs/config.yaml`.
Epoch selection is performed by updating the canonical configuration:
`paths.db_path`
`paths.knowledge_graph_db`
`paths.processing`
`paths.faiss_dir`
`paths.faiss_audio_path`
`qdrant.collections.*`
`phase6.clip_collection`
`phase6.dino_collection`

4. Data Root Authority
System Data Root: `<GOODQ_DATA_ROOT>`.
All data is in: `<GOODQ_DATA_ROOT>\GoodQ_Data\`.

5. Epoch Authority
Epoch: `epoch_2025_12_22` (Clean).
Status: ACTIVE (clean; intended for the first ingestion after WSL2 audio hardening).
Epoch root: `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22`.
Stores (authoritative targets for runtime):
SQLite (memory): `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/memory.db`
SQLite (knowledge graph): `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/knowledge_graph.db`
Processing root: `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/processing`
FAISS directory: `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/faiss`
FAISS (audio): `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/faiss/goodq_audio_epoch_2025_12_22.index`
Qdrant collections (epoch-suffixed):
clip: `goodq_clip_epoch_2025_12_22`
dino: `goodq_dino_epoch_2025_12_22`
text: `goodq_text_epoch_2025_12_22`
audio: `goodq_audio_epoch_2025_12_22`
Legacy status examples in `docs/data_epochs.md` include: "Status: LEGACY (do not write; preserved for comparison)" and "Status: LEGACY (preserved; do not write)".

6. Qdrant Authority
Qdrant Vector Database location: `<GOODQ_DATA_ROOT>\qdrant_storage`.
Qdrant service config `storage_path`: `<GOODQ_DATA_ROOT>/qdrant_storage`.
`configs/config.yaml` collections:
clip: `goodq_clip_epoch_2025_12_22`
dino: `goodq_dino_epoch_2025_12_22`
text: `goodq_text_epoch_2025_12_22`
audio: `goodq_audio_epoch_2025_12_22`

7. Import Inbox Authority
`configs/config.yaml` import_inbox: `<GOODQ_DATA_ROOT>/GoodQ_Data/import_inbox`.
Watchdog system monitors: `<project_root>/import_inbox` every 2 seconds.

8. Watchdog Authority
Watchdog location: `cli/watchdog.py` (Canonical; file locations are hardcoded in `cli/watchdog.py`).

9. Conflict Resolution (Memo Declaration)
In the event of conflicting declarations, authority precedence is:
This memo
Sealed basement documents
`configs/config.yaml`
`docs/data_epochs.md`
Architecture documentation
Scripts and code comments

10. Non-Goals
This memo does not propose fixes.
This memo does not mandate refactors.
This memo does not remove legacy data.
This memo does not enforce behavior at runtime.
This memo does not introduce new paths, epochs, or collections.

11. Status
This memo is declarative and zero-change.
This memo is intended as the consolidated reference for runtime authority.
