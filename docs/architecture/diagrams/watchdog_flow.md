<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

# Watchdog Flow Diagram

**Status:** Active architecture reference
**Rendering target:** GitHub Markdown with native Mermaid support

The Watchdog is the zero-touch ingestion monitor. It watches the configured
import inbox and delegates video ingestion to the canonical ingestion runtime.
It is not a second pipeline and does not make hidden runtime decisions outside
the resolved config surface.

Primary references:

- [WATCHDOG_SYSTEM.md](../../systems/WATCHDOG_SYSTEM.md)
- [WATCHDOG_GUIDE.md](../../guides/watchdog/WATCHDOG_GUIDE.md)
- [INGEST_ORCHESTRATION_CONTRACT.md](../INGEST_ORCHESTRATION_CONTRACT.md)

---

## Watchdog Runtime Flow

```mermaid
flowchart TB
    INBOX["Configured import_inbox"] --> MONITOR["Monitor thread"]
    MONITOR --> STABILITY["File stability check"]
    STABILITY --> HASH["SHA-256 hash"]
    HASH --> REGISTRY{"Known hash in watchdog_state.json?"}

    REGISTRY -- yes --> SKIP["mark processed / skip duplicate"]
    REGISTRY -- no --> QUEUE["FIFO processing queue"]

    QUEUE --> WORKER["Worker thread"]
    WORKER --> ROUTE{"File type"}

    ROUTE -- video --> INGEST["cli/run_ingestion.py"]
    ROUTE -- audio image document --> STEPS["configured step flow"]

    INGEST --> ARTIFACTS["epoch processing artifacts"]
    STEPS --> ARTIFACTS

    ARTIFACTS --> SUCCESS{"Success?"}
    SUCCESS -- yes --> PROCESSED["configured processed directory"]
    SUCCESS -- no --> FAILED["configured failed directory"]

    SUCCESS --> STATE["watchdog_state.json"]
    SUCCESS --> LOGS["watchdog.log"]

    classDef watch fill:#ecfeff,stroke:#0891b2,color:#164e63
    classDef decision fill:#fefce8,stroke:#ca8a04,color:#713f12
    classDef canonical fill:#f0fdf4,stroke:#16a34a,color:#14532d
    classDef output fill:#f5f3ff,stroke:#7c3aed,color:#3b0764

    class INBOX,MONITOR,STABILITY,HASH,QUEUE,WORKER watch
    class REGISTRY,ROUTE,SUCCESS decision
    class INGEST,ARTIFACTS canonical
    class SKIP,PROCESSED,FAILED,STATE,LOGS,STEPS output
```

---

## State Machine

```mermaid
flowchart TB
    START["start"] --> UNKNOWN["Unknown"]
    UNKNOWN -- file appears --> PENDING["Pending"]
    PENDING -- file still changing --> PENDING
    PENDING -- stable window elapsed --> STABLE["Stable"]
    STABLE -- hash computed --> HASHED["Hashed"]
    HASHED -- already processed --> SKIPPED["Skipped"]
    HASHED -- new hash --> QUEUED["Queued"]
    QUEUED -- worker claims file --> PROCESSING["Processing"]
    PROCESSING -- pipeline succeeds --> PROCESSED["Processed"]
    PROCESSING -- pipeline fails --> FAILED["Failed"]
    SKIPPED --> END["end"]
    PROCESSED --> END
    FAILED --> END

    classDef state fill:#ecfeff,stroke:#0891b2,color:#164e63
    classDef terminal fill:#f8fafc,stroke:#64748b,color:#0f172a
    classDef outcome fill:#f5f3ff,stroke:#7c3aed,color:#3b0764

    class UNKNOWN,PENDING,STABLE,HASHED,QUEUED,PROCESSING state
    class START,END terminal
    class SKIPPED,PROCESSED,FAILED outcome
```

---

## Canonical Boundaries

```mermaid
flowchart LR
    WATCHDOG["cli.watchdog"] --> CONFIG["config_loader runtime paths"]
    WATCHDOG --> INBOX["import_inbox"]
    WATCHDOG --> INGEST["cli/run_ingestion.py"]
    WATCHDOG --> LOGS["epoch logs"]

    INGEST --> MANIFEST["scene_manifest.json"]
    INGEST --> TEMPORAL["temporal_index.json"]
    INGEST --> SUMMARY["scene_ingest_results.json"]

    WATCHDOG -. does not replace .-> INGEST
    WATCHDOG -. does not own .-> PHASE6["Phase 6"]
    WATCHDOG -. does not hide .-> ERRORS["visible errors"]

    classDef watch fill:#ecfeff,stroke:#0891b2,color:#164e63
    classDef truth fill:#f0fdf4,stroke:#16a34a,color:#14532d
    classDef boundary fill:#fee2e2,stroke:#dc2626,color:#7f1d1d

    class WATCHDOG,CONFIG,INBOX,LOGS watch
    class INGEST,MANIFEST,TEMPORAL,SUMMARY truth
    class PHASE6,ERRORS boundary
```

Current path families are resolved from config and environment overlays:

- inbox: `${GOODQ_DATA_ROOT}/GoodQ_Data/import_inbox`
- processing: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing`
- processed: `${GOODQ_DATA_ROOT}/GoodQ_Data/processed`
- failed: `${GOODQ_DATA_ROOT}/GoodQ_Data/failed`
- logs: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/logs`

Control Agent state may be recorded by the runtime, but AI diagnosis remains
conditional on explicit `llm_client` injection. The read-only recurrence report
is a separate observer and does not enable healing.
