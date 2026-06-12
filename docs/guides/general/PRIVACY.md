<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-03 -->

# GoodQ4All Data Privacy Statement

GoodQ4All is a local-first, privacy-respecting multimodal AI memory and intelligence system. It is designed to run entirely on your own local hardware without requiring cloud dependencies or sharing your data with external services.

---

## 1. Local Data Residency

All assets, data tables, search indexes, and models are stored on your local disk:
*   **Media and Manifests:** Ingested media files and scene manifests are stored in your configured data directory (defaults to `%USERPROFILE%\GoodQ_Data\` or the environment override `${GOODQ_DATA_ROOT}`).
*   **Relational Memories:** Structured metadata, timestamps, transcripts, and entities are written to SQLite databases (`memory.db` and `knowledge_graph.db`) residing in the local epoch workspace.
*   **Vector Search Indices:** Multi-modal embeddings (Text, Audio, Vision) are persisted locally in a Qdrant collection directory (defaults to `%APPDATA%\GoodQ4All\qdrant\storage` on Windows, or standard Library/XDG paths on macOS/Linux).
*   **Model Weights:** Preflight model caches (Whisper, Qwen, CLAP, CLIP) are prefetched to your local system folder (defaults to `%APPDATA%\GoodQ4All\models\` or `$HOME/.cache/goodq4all/models/`).

---

## 2. Zero-Telemetry Policy

GoodQ4All operates under a strict **Zero-Telemetry Boundary**:
*   No analytical pings or usage reports are sent to any remote servers.
*   No logging endpoints or error-reporting tools communicate with the internet.
*   Qdrant telemetry is explicitly disabled via the configuration parameter `telemetry_disabled: true` in the default YAML configuration.

---

## 3. Network Boundaries

*   **Offline Mode:** Once model weights are downloaded during initial installation, the application requires **zero network connectivity** to function. Ingestion, perception, vector generation, and search queries execute 100% offline.
*   **Local UI Server:** The Retro Memory Explorer and Classic Operator Console dashboards run on a local HTTP port (`http://127.0.0.1:30000`). No traffic leaves your machine.
*   **Optional Hosted Extensions:** The optional "Ask GoodQ" voice agent is a hosted extension using ElevenLabs APIs. Using it is entirely optional, requires an active internet connection, and is gated by user actions. The core GoodQ4All system is fully operational without this extension.
