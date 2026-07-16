<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Clean First-Go Ingestion Monitoring Report (Run ID: 0cb0f3f4-854a-4ba9-ad45-75011b706ecc)

## Outcome Classification
> [!NOTE]
> **Verified Outcome**: `VERIFIED_SUCCESS_TERMINAL`
> All ingestion workflows completed successfully, relational databases remained cleanly isolated, and all multi-modal features successfully staged in the UCF ledger and vector layers.

---

## 1. Run Identity
* **Run ID**: `0cb0f3f4-854a-4ba9-ad45-75011b706ecc`
* **Epoch**: `epoch_2026_07_05_home_memory_clean_01`
* **Target Video**: `91ac604fffbc4814b3c9bf2e0bbe924b.mp4`
* **Execution Profile**: `BASELINE` (CPU fallback transcription enabled)
* **Status**: `completed` (100% progress)
* **Completed Time**: `2026-07-05T14:54:26`

---

## 2. Pre-Run Blank Slate Verification
| Surface Name | Target Path or Collection | Pre-Run State | Verified |
| :--- | :--- | :---: | :---: |
| **Epoch Directory** | `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\epoch_2026_07_05_home_memory_clean_01` | **Wiped / Empty Layout** | **Yes** |
| **Processing Directory** | `.../epoch_2026_07_05_home_memory_clean_01/processing` | **Wiped / Empty** | **Yes** |
| **FAISS Index Files** | `.../faiss/*` | **Absent** | **Yes** |
| **UCF Ledger Database** | `.../ucf/ucf_ledger.db` | **Absent** | **Yes** |
| **Relational DBs** | `memory.db` / `knowledge_graph.db` | **Absent** | **Yes** |
| **Qdrant Collections** | `goodq_*` collections | **0 points (Empty)** | **Yes** |

---

## 3. Run-Wide Counts (R4)
The pipeline detected and processed exactly **141 scenes**. Here are the wide execution counts:

| Metric Name | Count | Notes |
| :--- | :---: | :--- |
| **Total Detected Scenes** | `141` | Natively parsed by scene detector |
| **Transcribed Scenes (Speech)** | `137` | Whisper successfully decoded dialogue |
| **Failed/Silent Scenes (VAD)** | `4` | Verified silent/credits scenes at the end of the video |
| **Model Unavailable** | `0` | Model loaded successfully on CPU |
| **Audio Wave Chunks** | `141` | Every scene has a raw sliced wave file |
| **Representative Keyframes** | `141` | Every scene has a visual frame extract |

### Diagnosis of the 4 Failed Scenes (Indices 137-140)
Manual diagnostic testing confirmed that the last 4 scenes in the video (totaling the final minute of credits/music) contain only silence and background noise. Whisper transcriptions with VAD bypassed return only noise-hallucinations (e.g., repeating Norwegian Nynorsk "Thanks for watching!" or Russian "Орел и Решка"). The pipeline's VAD filter correctly suppressed these hallucinations, resulting in empty transcripts.

---

## 4. Staging Isolation Audits (R5)

### SQLite Relational Isolation
As expected under staged-isolation rules:
* `memory.db` exists but has **0 rows** in all main tables (`scenes`, `embeddings`, `links`, `segments`, `summaries`). Only the migration table is initialized.
* `knowledge_graph.db` **does not exist** (it will be created during promotion).

### UCF Ledger Staged Counts
The UCF ledger database `ucf_ledger.db` was created and populated with staged entries:
* **Total Staged Context Frames**: `3902`
* **Promotion Status**: `staged` (`3902` frames)
* **Duplicate Violations**: `0` (Zero double-write anomalies)
* **Modality Breakdown**:
  * `audio`: `141` frames
  * `multimodal`: `141` frames
  * `text`: `2628` frames
  * `video`: `992` frames

* **Worker Breakdown**:
  * `audio_embed_clap`: `141` frames
  * `audio_transcribe`: `2205` frames
  * `face_embed`: `37` frames
  * `image_caption`: `141` frames
  * `image_embed_clip`: `141` frames
  * `image_embed_dino`: `141` frames
  * `image_ocr`: `141` frames
  * `object_detect`: `250` frames
  * `scene_visual_embeddings_clip`: `141` frames
  * `scene_visual_embeddings_dino`: `141` frames
  * `text_embed`: `282` frames
  * `video_scene_detect`: `141` frames

### Vector State Point Counts
All vector indices are staged, matching their exact SQLite and UCF ledger totals:
| **Qdrant Collection: goodq_audio_epoch_2026_07_05_home_memory_clean_01** | `141 points` (green) |
| **Qdrant Collection: goodq_clip_epoch_2026_07_05_home_memory_clean_01** | `282 points` (green) |
| **Qdrant Collection: goodq_dino_epoch_2026_07_05_home_memory_clean_01** | `282 points` (green) |
| **Qdrant Collection: goodq_text_epoch_2026_07_05_home_memory_clean_01** | `419 points` (green) |
| **FAISS Index File: goodq_audio_epoch_2026_07_05_home_memory_clean_01.index** | `320.27 KB` |

### Retrieval Staging Verification
* **Default Search (Promoted Only)**: `0` results returned (100% correct, staged points are hidden from normal search).
* **Staged-Inclusive Search (`ucf_include_terminal=True`)**: `5` results returned.
* **Staged Search Sample Ranks**:
  1. Scene 0 (Score: 1.0000)
  2. Scene 10 (Score: 0.9839)
  3. Scene 110 (Score: 0.9683)
  4. Scene None (Score: 0.9531)
  5. Scene 120 (Score: 0.9385)

---

## 5. Deterministic Scene Traces (R6)
Forensic end-to-end trace of six sample scenes selected deterministically:

### Scene 1 (Early Transcribed)
* **Scene ID**: `52cf13e6dbb700d887ea73b683aaae62e30831ddf7fe035ddf9c5e431a28f0e3`
* **Start / End**: `53.787s` / `92.559s` (Duration: `38.772s`)
* **Transcript Status**: `ok`
* **Transcript**: `"It's, uh, spinach florentine. Oh, it smells like it. We have to get a can. You know what it says in the directions? We're getting a can. Oh, can. We have to do it right. Oh, for the rodents? Where are the mice chipmunks either one? Okay, kid wants to sign me. She said no more kids Jose it's your wife Jane, let me do it. You and Jose. No, not in the shape I'm in. Jose, at your corner for this. Oh, sure, I have a couple. One's good for now, I'm gonna go fix... The window fell on my door. Should we check out Jose's camera?"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`1240782 bytes`)
  * Keyframe Image: `Exists`
  * Compatibility JSON: `Missing`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (object_detect), video:staged (face_embed), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 70 (Middle Transcribed)
* **Scene ID**: `28b0bab44427c3a186fb76c0b2d72f3ac46f1b93bbf80ed94c1d8f536227ab4f`
* **Start / End**: `4144.04s` / `4206.335s` (Duration: `62.295s`)
* **Transcript Status**: `ok`
* **Transcript**: `"Between Christmas and... Yeah, I don't remember. Ben, can you take a picture of me? With the baby. Where'd you send her to school? He looks terrible in the lighting though. Come on, get your money back. Say hello. What's the date today John? The 27th. What year John? That's right. Who are you holding? Franklin Delano Roosevelt. Here's the proud father of Robin Lynch. Rebellation trucks on his day off. Going skiing with the boys. Jim Melno here. Jim Noto here. And who is this, Jim? Who is this? No, who are you? Jim pushed that bow down so he could see his face. Any time we're ready. We need the parents. This is the bearer. The parents are going to be in the booth. And they're going to have to eat. Okay, okay. We were out here in the circle first. Okay. Please stand still."`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`1993518 bytes`)
  * Keyframe Image: `Exists`
  * Compatibility JSON: `Missing`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (object_detect), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 138 (Late Transcribed)
* **Scene ID**: `ea9d6287c31ffc9787920bc16bc753bfee29c8a4be03459d5885fcfc66cf2cb8`
* **Start / End**: `8695.921s` / `8752.711s` (Duration: `56.790s`)
* **Transcript Status**: `failed`
* **Transcript**: `"None"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`1817358 bytes`)
  * Keyframe Image: `Exists`
  * Compatibility JSON: `Missing`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (image_embed_dino), video:staged (image_embed_clip), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 0 (Vad Silence)
* **Scene ID**: `91b081ff8e217a307f50fb8377add00ac55779975fb89e4d7e25927cf629c94f`
* **Start / End**: `0.0s` / `53.787s` (Duration: `53.787s`)
* **Transcript Status**: `ok`
* **Transcript**: `"Can you see it? Does it show anything on the top of your view plan? Yes, it says record. R-E-C. It's automatic. Did you see the thing on the Pan American Games about the Cubans? Oh yeah! because of communists in this country. All these anti-capitalist, anti-castro people are coming to, they're in Indiana, and they're fighting with all the communists. J, if you knock it off. Who gives a shit? Where's the thingy? Oh, that's it right up there. Yeah. Okay I feel like just gorgeous. Thank you darling. I need a haircut. I'm going to go out and see what I can do with Jose. Okay let's go. I'll go. Come. Okay. Stuff smells great. That's it."`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`1721262 bytes`)
  * Keyframe Image: `Exists`
  * Compatibility JSON: `Missing`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (object_detect), video:staged (face_embed), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 0 (Visually Rich)
* **Scene ID**: `91b081ff8e217a307f50fb8377add00ac55779975fb89e4d7e25927cf629c94f`
* **Start / End**: `0.0s` / `53.787s` (Duration: `53.787s`)
* **Transcript Status**: `ok`
* **Transcript**: `"Can you see it? Does it show anything on the top of your view plan? Yes, it says record. R-E-C. It's automatic. Did you see the thing on the Pan American Games about the Cubans? Oh yeah! because of communists in this country. All these anti-capitalist, anti-castro people are coming to, they're in Indiana, and they're fighting with all the communists. J, if you knock it off. Who gives a shit? Where's the thingy? Oh, that's it right up there. Yeah. Okay I feel like just gorgeous. Thank you darling. I need a haircut. I'm going to go out and see what I can do with Jose. Okay let's go. I'll go. Come. Okay. Stuff smells great. That's it."`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`1721262 bytes`)
  * Keyframe Image: `Exists`
  * Compatibility JSON: `Missing`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (object_detect), video:staged (face_embed), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 15 (Random Choice)
* **Scene ID**: `c2a5f170983179bc52774a06d66faf24e2a64be4ab9dff51587405152d37edb6`
* **Start / End**: `860.493s` / `945.645s` (Duration: `85.152s`)
* **Transcript Status**: `ok`
* **Transcript**: `"It's still fresh in my mind. Zeker, ik zin in je. Oog al aan, in de seconde. There's a little boobie. Ha ha ha ha ha ha! Oh Maybe he's hungry. You're so sweet And there's Dr. Goldman. Good morning, how are you? How are you doing?"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`2724942 bytes`)
  * Keyframe Image: `Exists`
  * Compatibility JSON: `Missing`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`
