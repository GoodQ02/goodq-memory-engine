# Operational State Checklist

Reflects current runtime sources; see `docs/RUNTIME_AUTHORITY_MEMO.md` for authority.

Checked by:
Checked at:

- [ ] Active epoch (per `docs/data_epochs.md`): `epoch_2025_12_22`
- [ ] Epoch root (per `configs/config.yaml` `paths.db_dir`): `L:/_DATA/GoodQ_Data/epochs/epoch_2025_12_22`
- [ ] Canonical inbox (per `configs/config.yaml` `paths.import_inbox`): `L:/_DATA/GoodQ_Data/import_inbox`
- [ ] Canonical Qdrant storage (per `vendor/qdrant/config.yaml` `storage_path`): `L:/_DATA/qdrant_storage`
- [ ] Required service reachable: Qdrant `http://localhost:6333` (per `docs/architecture/MEMORY_STORAGE.md`)
- [ ] Required service reachable: vLLM port `38005` (per `docs/technical/LIB_COMPONENTS.md`)
- [ ] Required service reachable: Ollama port `31434` (per `docs/technical/LIB_COMPONENTS.md`)
- [ ] Safe to ingest? [ ] Yes [ ] No

Notes:
