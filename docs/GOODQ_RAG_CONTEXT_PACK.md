<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-18 -->

# GoodQ RAG Context Pack

This document serves as the canonical context pack for GoodQ retrieval augmented generation (RAG) agents (e.g., Hermes) to understand the active epoch, vector collections, relational database schemas, query examples, and privacy boundaries.

---

## 1. Active Epoch

The current active system epoch is:
```text
epoch_2026_06_16_r0_smoke
```
*(Defined dynamically in `configs/config.local.yaml`)*

---

## 2. Collection Glossary

The active Qdrant vector database collections for the current epoch are defined as follows:

| Collection Name | Modality | Dimension | Embedding Model / Tag | Description |
|---|---|---|---|---|
| `goodq_text_epoch_2026_06_16_r0_smoke` | Text | 384 | `sentence-transformers/all-MiniLM-L6-v2` | Sentence-level and chunk-level transcript text embeddings |
| `goodq_audio_epoch_2026_06_16_r0_smoke` | Audio | 512 | `laion/clap-htsat-unfused` | Scene-level CLAP audio feature and sound event embeddings |
| `goodq_clip_epoch_2026_06_16_r0_smoke` | Vision | 768 | `openai/clip-vit-large-patch14` | Visual frame embeddings extracted uniformly per scene |
| `goodq_dino_epoch_2026_06_16_r0_smoke` | Vision | 1024 | `facebook/dinov2-large` | Dense visual feature representations for frame-level objects |

---

## 3. Vector Payload Fields

Every point stored in the Qdrant collections contains the following structured metadata payload fields:

*   **`video_hash`** *(string)*: Unique SHA-256 identifier of the source video file.
*   **`scene_id`** *(string)*: The canonical scene identifier (corresponds to `source_artifact_id` in staged context frames).
*   **`scene_hash`** *(string)*: The 16-character prefix of the scene's canonical SHA-256 hash.
*   **`modality`** *(string)*: The data modality (`"video"`, `"audio"`, `"text"`).
*   **`worker_name`** *(string)*: The name of the pipeline step that generated the vector (`"image_embed_clip"`, `"image_embed_dino"`, `"audio_embed_clap"`, `"text_embed"`).
*   **`vector_model_tag`** *(string)*: Hugging Face model identifier used for generating the embedding.
*   **`epoch_id`** *(string)*: The epoch identifier matching the active storage tree.
*   **`ucf_frame_id`** *(integer)*: Primary key pointer back to the context frame in `memory.db`.
*   **`text`** *(string, text collection only)*: The raw textual content or transcription chunk.
*   **`speaker`** *(string, text collection only)*: Identifies the speaker of the corresponding text block.
*   **`t_start`** *(float)*: Start timestamp of the segment/scene in seconds.
*   **`t_end`** *(float)*: End timestamp of the segment/scene in seconds.
*   **`run_id`** *(string)*: Execution ID of the ingestion run that committed the vector.

---

## 4. SQLite Table Meanings

GoodQ4All splits relational and graph storage into two separate epoch-scoped databases.

### A. `memory.db` (Relational Memory)

Stores scene segmentations, transcriptions, embedding sidecars, and verification transitions.

*   **`media_sources`**: Ingested raw media parameters.
    *   `video_hash` (TEXT, PK), `file_path` (TEXT), `duration` (REAL), `fps` (REAL), `width` (INT), `height` (INT), `created_at` (TIMESTAMP).
*   **`context_frames`**: The staging area for ingestion context frames before canonical promotion.
    *   `frame_id` (INT, PK), `video_hash` (TEXT), `ucf_schema_version` (TEXT), `epoch_id` (TEXT), `run_id` (TEXT), `t_start` (REAL), `t_end` (REAL), `modality` (TEXT), `worker_name` (TEXT), `model_tag` (TEXT), `confidence` (REAL), `spatial_region` (TEXT), `spatial_space` (TEXT), `vector_key` (TEXT), `vector_backend` (TEXT), `vector_collection` (TEXT), `vector_dim` (INT), `vector_model_tag` (TEXT), `source_artifact_id` (TEXT), `raw_ref` (TEXT), `payload` (TEXT), `payload_hash` (TEXT), `promotion_status` (TEXT - `'staged'` or `'promoted'`).
*   **`ucf_status_transitions`**: Ingestion verification audit trails.
    *   `id` (INT, PK), `frame_ids` (TEXT), `video_hash` (TEXT), `epoch_id` (TEXT), `old_status` (TEXT), `new_status` (TEXT), `tool_name` (TEXT), `reason` (TEXT), `scope` (TEXT), `evidence` (TEXT), `transitioned_at` (TEXT).
*   **`scenes`**: Authorized canonical scene chunks.
    *   `id` (TEXT, PK), `video_hash` (TEXT), `start` (REAL), `end` (REAL), `meta` (TEXT - JSON properties), `created_at` (TEXT).
*   **`segments`**: Authoritative sub-scene chunks (e.g. diarized dialogue clips).
    *   `id` (TEXT, PK), `video_hash` (TEXT), `start` (REAL), `end` (REAL), `speaker` (TEXT), `meta` (TEXT - JSON properties), `created_at` (TEXT).
*   **`embeddings`**: High-precision vector sidecars and TurboQuant parameters.
    *   `hash` (TEXT), `modality` (TEXT), `faiss_id` (INT), `source_path` (TEXT), `scene_id` (TEXT), `sentiment_label` (TEXT), `sentiment_score` (REAL), `emotions_json` (TEXT), `vector` (BLOB), `tq_indices` (BLOB), `tq_norm` (REAL), `tq_qjl_sign` (BLOB), `tq_norm_residual` (REAL), `created_at` (TEXT). (Composite PK: `hash`, `modality`).
*   **`links`**: Semantic connections between memories.
    *   `parent_hash` (TEXT), `child_hash` (TEXT), `relation` (TEXT), `timestamp` (REAL), `meta` (TEXT), `created_at` (TEXT).
*   **`summaries`**: Extracted narrative overviews.
    *   `id` (INT, PK), `summary_type` (TEXT), `category` (TEXT), `content` (TEXT), `created_at` (TEXT).
*   **`memory_commit_events`**: Audit trail logs of memory commits.
*   **`retrieval_events`**: Observability logs of query retrieval events.

### B. `knowledge_graph.db` (Graph Memory)

Stores entities, relationships, temporal context, and identity patterns.

*   **`nodes`**: Vertices representing entities, speakers, or concepts.
    *   `id` (INT, PK), `node_type` (TEXT), `name` (TEXT), `properties` (TEXT), `occurrence_count` (INT), `first_seen` (REAL), `last_seen` (REAL), `created_at` (TEXT).
*   **`edges`**: Directed semantic connections.
    *   `id` (INT, PK), `source_id` (INT), `target_id` (INT), `edge_type` (TEXT), `weight` (REAL), `properties` (TEXT), `created_at` (TEXT).
*   **`media_nodes`**: Linkages back to specific video files or scene chunks.
    *   `id` (INT, PK), `media_type` (TEXT), `media_path` (TEXT), `scene_id` (TEXT), `timestamp_start` (REAL), `timestamp_end` (REAL), `properties` (TEXT), `created_at` (TEXT).
*   **`node_media`**: Connects entities to the media segments where they appeared.
    *   `id` (INT, PK), `node_id` (INT), `media_id` (INT), `confidence` (REAL), `context` (TEXT), `created_at` (TEXT).
*   **`events`**: System and physical temporal events.
    *   `id` (INT, PK), `event_type` (TEXT), `timestamp` (REAL), `duration` (REAL), `properties` (TEXT), `created_at` (TEXT).
*   **`event_nodes`**: Links nodes/entities involved in specific events.
    *   `id` (INT, PK), `event_id` (INT), `node_id` (INT), `role` (TEXT), `created_at` (TEXT).

---

## 5. Safe Read-Only Examples

RAG agents must use read-only queries to access databases safely without risking schema drift or unpromoted data contamination.

### A. Python SQLite Safe Query
```python
import sqlite3
import json

db_path = "data/epochs/epoch_2026_06_16_r0_smoke/memory.db"

# Open read-only connection
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

cursor = conn.cursor()
# Retrieve only promoted scenes
cursor.execute("SELECT id, video_hash, start, end, meta FROM scenes LIMIT 5")
for row in cursor.fetchall():
    print(f"Scene ID: {row['id']} | Start: {row['start']}s | End: {row['end']}s")
    meta = json.loads(row['meta'])
    print(f"  Meta: {meta}")

conn.close()
```

### B. Python Qdrant Safe Search
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

# Query text embeddings in the active collection
results = client.search(
    collection_name="goodq_text_epoch_2026_06_16_r0_smoke",
    query_vector=[0.0] * 384,  # Replace with real MiniLM embedding
    limit=3
)

for point in results:
    payload = point.payload
    print(f"Score: {point.score:.4f}")
    print(f"  Speaker: {payload.get('speaker')} | Text: {payload.get('text')}")
    print(f"  Source Video: {payload.get('video_hash')} | Timestamps: {payload.get('t_start')}s - {payload.get('t_end')}s")
```

---

## 6. Privacy Notes & Boundaries

1.  **Zero Telemetry Boundary**: All database entries and Qdrant collections reside strictly on local NVMe disk storage. No diagnostic metrics, payloads, or search queries leave the system host context.
2.  **Derived Conduits Sanitization**: When sharing context or data with external models, dashboards, or user interfaces:
    *   Redact raw absolute system file paths (e.g. drive-root or user folders). Use relative abstract tokens.
    *   Never transmit raw float32 vectors over external channels.
    *   Groom transcripts and nodes to ensure that sensitive personal credentials or variables are masked or pruned.
