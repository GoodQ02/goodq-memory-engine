<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# GoodQ4All Birth Certificate & Promotion Witness Report
**Epoch ID:** `epoch_2026_07_05_home_memory_clean_01`
**Status:** `VALIDATED & PROMOTED (100% GREEN)`

---

## 1. UCF Ledger Promotion Summary (`ucf_ledger.db`)
| Category | Metric Value | Check Status |
| :--- | :--- | :--- |
| **Total Frames Promoted in Epoch** | 75094 | ✅ Completed |
| **Frames Remaining Staged in Epoch** | 0 | ✅ 0 Remaining |
| **Frames Rejected in Database** | 0 | ✅ 0 Rejected |
| **Frames Superseded in Database** | 0 | ✅ 0 Superseded |
| **Impossible Time Ranges (start > end)** | 0 | ✅ 0 Impossible |

---

## 2. Materialized Relational Memory (`memory.db`)
| Table Name | Materialized Row Count |
| :--- | :--- |
| `embeddings` | 8736 |
| `links` | 42800 |
| `scenes` | 1648 |
| `segments` | 16535 |
| `summaries` | 0 |
| `sqlite_sequence` | 1 |
| `schema_migrations` | 1 |
| `scene_text_fts` | 2826 |
| `scene_text_fts_data` | 172 |
| `scene_text_fts_idx` | 167 |
| `scene_text_fts_content` | 2826 |
| `scene_text_fts_docsize` | 2826 |
| `scene_text_fts_config` | 1 |
| `ucf_provenance_mapping` | 2487118 |
| `retrieval_events` | 80 |

---

## 3. Knowledge Graph Memory (`knowledge_graph.db`)
| Entity Layer Table | Element Count |
| :--- | :--- |
| `nodes` | 93289 |
| `edges` | 1928045 |
| `sqlite_sequence` | 4 |
| `media_nodes` | 2914 |
| `node_media` | 19449 |
| `events` | 0 |
| `event_nodes` | 0 |

---

## 4. Qdrant Vector Collection Points
| Collection Name | Points Count |
| :--- | :--- |
| `goodq_clip_epoch_2026_07_05_home_memory_clean_01` | 2913 |
| `goodq_dino_epoch_2026_07_05_home_memory_clean_01` | 2913 |
| `goodq_text_epoch_2026_07_05_home_memory_clean_01` | 4292 |
| `goodq_audio_epoch_2026_07_05_home_memory_clean_01` | 1453 |

---

## 5. Integrity & Healing Checks
* **Video 5 Scene 21 Diarization Turn Count**: `26` (Expected: `26` raw turns resolved cleanly, no duplicates/overwrites).
* **Video 4 Scene 64 Diarization Turn Count**: `25` (Expected: `25` raw turns resolved cleanly, no duplicates/overwrites).
* **Orphaned Video 4 Points Verification**: Staged count for Video 4 in `ucf_ledger`: `0`. (Expected: `0` staged, proving no orphaned points remained).
* **Impossible time ranges check**: `0` frames failed. (Expected: `0` failed).

---

## 6. Live RAG Search & Retrieval Tests

### A. Promoted-Only Text Search ("mountain bike surprise")
* **Match 1**: Video `8d1a38dc` Scene `122` | Score: `1.0000` | Text: `"as ti\ os a person is riding a bike through a forest..."`
* **Match 2**: Video `39fc7459` Scene `165` | Score: `0.9839` | Text: `"MAR. 28 1993 a boat is in the water near a mountain..."`
* **Match 3**: Video `8d1a38dc` Scene `c2dd6bfe3da32dc65d80cb6418fc3d0d4ad3ef4673fb295417aa389f249b5031` | Score: `0.9683` | Text: `"Scene 27 (1647.9s-1677.9s, 30.0s duration). Visual: a man riding a bike down a street. Transcript: "It's great, yeah.  Did you see it on TV ..."`

### B. Temporal Search ("Christmas 1993")
* **Match 1**: Video `8d1a38dc` Scene `07cbecaddba66d87fa6cfce5e415c449730bb11574db7a2c23b7768e70b5c0a2` | Score: `0.5000` | Text: `"Scene 55 (3075.2s-3106.2s, 31.1s duration). Visual: a young boy is playing with a toy. Objects: person. Transcript: "I love it.  Merry Chris..."`
* **Match 2**: Video `b17dbd87` Scene `132f17bbdce6c322e38a0a3856a132b782905ff25ab2d1e5ace0eeb642e0da10` | Score: `0.5000` | Text: `"Sophia, you're doing great.  Aww, how sweet.  Here's Jack, he doesn't stop eating.  He doesn't stop munching.  Aww, Sophia.  Here, Frank.  S..."`
* **Match 3**: Video `3f796d20` Scene `a731ce64dbaefaca5e2995f7c057fbaea0ca3ca27f505835d2705a9f8edc83e2` | Score: `0.4919` | Text: `"Scene 74 (5849.1s-5897.2s, 48.0s duration). Visual: a baby is sitting in a high chair. Objects: person. Transcript: "say Merry Christmas! Me..."`

### C. Entity/Speaker Search ("Dad speaker")
* **Match 1**: Video `35bfbfdf` Scene `35` | Score: `1.0000` | Text: `"Whatever. Look at that kid. Where's Debra? Say something for our studio audience. Dad? What do you have to say for yourself? What was that? ..."`
* **Match 2**: Video `59c1eac2` Scene `94` | Score: `0.9839` | Text: `"Now let's see how this goes. Daddy doesn't even know. Who made this? Grandma and Grandpa, no no. That's good. I'm going to try to do it like..."`
* **Match 3**: Video `237eb8d7` Scene `109` | Score: `0.9683` | Text: `"That's right. Earmuffs. Father, I don't want to hear that kind of talk of you. You didn't see that? We're going to sing for you...."`

---
*Report generated automatically by Antigravity on behalf of the developer.*
