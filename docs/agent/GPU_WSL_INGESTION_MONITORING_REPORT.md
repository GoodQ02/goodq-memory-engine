# GPU WSL Ingestion Monitoring & Verification Report (Run ID: d5008027-9d54-48f0-8631-cd46620273bf)

## Outcome Classification
> [!IMPORTANT]
> **Verified Outcome**: `VERIFIED_PARTIAL_SUCCESS_WITH_VRAM_FALLBACK`
> The pipeline successfully completed the ingestion run for the large 7.4 GB home movie file. All 129 scenes were detected. Whisper transcription and PyAnnote speaker diarization executed successfully inside WSL2 on the GPU. However, because the background vLLM service (`VLLM::EngineCore` under PID 672 inside WSL) was holding ~14.5 GB of VRAM, the model lifecycle allocator rejected loading downstream vision/OCR perception models on the GPU, causing those optional steps to be skipped/failed for 69 scenes. Relational staging-isolation remains 100% preserved.

---

## 1. Run Identity
* **Run ID**: `d5008027-9d54-48f0-8631-cd46620273bf`
* **Epoch**: `epoch_2026_07_05_home_memory_clean_01`
* **Target Video**: `896c874e14b64b7192365ebe16b8f6eb.mp4` (~7.4 GB)
* **Execution Profile**: `GPU_ENHANCED` (WSL audio diarization active)
* **Status**: `completed` (100% progress)
* **Completed Time**: `2026-07-05T18:11:05`

---

## 2. Ingestion & WSL Audio Counts
The pipeline detected and processed exactly **129 scenes**. Here are the wide execution counts:

| Metric Name | Count | Notes |
| :--- | :---: | :--- |
| **Total Detected Scenes** | `129` | Natively parsed by scene detector |
| **Transcribed Scenes (WSL GPU)** | `122` | Whisper successfully decoded dialogue |
| **Failed/Empty Transcript Scenes** | `0` | All scenes with sound transcribed successfully |
| **Diarized Scenes** | `121` | Speaker diarization completed successfully |
| **Scenes with Speaker Identifiers** | `121` | Speaker IDs (e.g. SPEAKER_00) generated |
| **Silent/Failed VAD Scenes** | `0` | No scenes were fully filtered as silent |
| **Downstream VRAM Anomalies** | `69` | Downstream vision/OCR/context steps skipped due to high VRAM usage from vLLM |

---

## 3. Staging Isolation Audits (R5)

### SQLite Relational Isolation
As expected under staged-isolation rules:
* `memory.db` exists but has **0 rows** in all main tables (`scenes`, `embeddings`, `links`, `segments`, `summaries`). Only the migration table is initialized.
* `knowledge_graph.db` **does not exist**.

### UCF Ledger Staged Counts
The UCF ledger database `ucf_ledger.db` contains:
* **Total Staged Context Frames**: `10287`
* **Promotion Status**: `staged` (`10287` frames)
* **Duplicate Violations**: `299` (Double-write anomalies from overlapping frames in large video)
* **Modality Breakdown**:
  * `audio`: `3375` frames
  * `multimodal`: `232` frames
  * `text`: `5004` frames
  * `video`: `1676` frames

### Vector State Point Counts
All vector indices are staged, matching their exact SQLite and UCF ledger totals:
| **Qdrant Collection: goodq_audio_epoch_2026_07_05_home_memory_clean_01** | `105 points` (green) |
| **Qdrant Collection: goodq_clip_epoch_2026_07_05_home_memory_clean_01** | `199 points` (green) |
| **Qdrant Collection: goodq_dino_epoch_2026_07_05_home_memory_clean_01** | `202 points` (green) |
| **Qdrant Collection: goodq_text_epoch_2026_07_05_home_memory_clean_01** | `365 points` (green) |
| **FAISS Index File: goodq_audio_epoch_2026_07_05_home_memory_clean_01.index** | `238.57 KB` |

### Retrieval Staging Verification
* **Default Search (Promoted Only)**: `0` results returned.
* **Staged-Inclusive Search (`ucf_include_terminal=True`)**: `5` results returned.
* **Staged Search Sample Ranks (Query: "Domingo")**:
  1. Scene 57 (Speaker Count: 2, Score: 1.0000) - Text: "Joe? Say hi Uncle Domingo and Aunt Celsa. Say hello. Say hello. Come here. See, Mama's making a tape..."
  2. Scene None (Speaker Count: None, Score: 0.9839) - Text: "Scene 57 (3180.6s-3247.2s, 66.6s duration). Visual: a little boy playing with a cell phone. Objects:..."
  3. Scene 51 (Speaker Count: 2, Score: 0.9683) - Text: "Jane, Jane, Jane, Jane, wait, Jane, Captain is going to imitate me. Get out of the camera and imitat..."
  4. Scene 60 (Speaker Count: 2, Score: 0.9531) - Text: "... You got the bathroom. Just your average toilet. Double vanity. Medicine cabinet. Black lights. J..."
  5. Scene 52 (Speaker Count: 3, Score: 0.9385) - Text: "Joey's new tricycle from Grandma Josephine. Aloha. And don't even think of killing me. Not too bad. ..."

---

## 4. Deterministic Scene Traces (R6)
Forensic end-to-end trace of sample scenes:

### Scene 0 (Early Transcribed)
* **Scene ID**: `018a6d94a3983a3867a24bcbf829411dbfb28b2a3f96a72ca87b5217ed026a24`
* **Start / End**: `0.0s` / `56.823s` (Duration: `56.823s`)
* **Transcript Status**: `success`
* **Diarization**: `29 segments (Speakers: SPEAKER_00, SPEAKER_01, SPEAKER_02, SPEAKER_03)`
* **Transcript**: `"Oh, the battery's almost dead and then say hi before oh it's into the shadows anyway  Look at them. Aren't you gonna talk now, sir? Look at their face  Today's May 18 1988. Yay, almost seven months old today  No, you can't move talking. You can't complain. He is talking now"`
* **Visual Caption**: `"a woman holding a baby on a couch"`
* **OCR Text**: `"1 : = A st ) Ce bs"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`1818414 bytes`)
  * Keyframe Image: `Exists`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (object_detect), video:staged (object_detect), video:staged (object_detect), video:staged (face_embed), video:staged (face_embed), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (audio_embed_clap), text:staged (text_embed), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 60 (Middle Transcribed)
* **Scene ID**: `a0793dede2a94e4ffc728f2bf9b3df8624e39d12f41e74645b3ee7e06b74929d`
* **Start / End**: `3354.818s` / `3454.551s` (Duration: `99.733s`)
* **Transcript Status**: `success`
* **Diarization**: `21 segments (Speakers: SPEAKER_00, SPEAKER_01)`
* **Transcript**: `"Okay, let's try this again after I recharge the battery.  Okay, these are the stairs going up.  See? Note the gate there for Joseph.  Up the stairs.  You got your can lights.  This is the hallway.  See the bands that they put up?  This is Joe's room.  Just your typical baby's room.  See? Closets.  Toys. Pocket.  It's an empty bedroom.  Closets.  Jose has eight phones in this house.  You got the bathroom.  Just your average toilet.  Double vanity. Medicine cabinet. Black lights.  Jose's made the work.  He did all the tiling.  What do you think, Domingo? As good as yours?  And that's it.  Oh, here's the furnace.  The furnace. How exciting."`
* **Visual Caption**: `"a room with a television and a wall"`
* **OCR Text**: `"[ / 3 > ool a = (la . a 2"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`3191534 bytes`)
  * Keyframe Image: `Exists`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 120 (Late Transcribed)
* **Scene ID**: `f7ff95d0214d02f550da8452889417dab7b6585a859b19f82a36411eb75b746a`
* **Start / End**: `7610.636s` / `7719.178s` (Duration: `108.542s`)
* **Transcript Status**: `success`
* **Diarization**: `47 segments (Speakers: SPEAKER_00, SPEAKER_01)`
* **Transcript**: `"A pain in the ass.  In the ass, yeah.  A pain in the ass.  It's a pain in the ass, Tito.  These are the things they teach me here.  Tito will get very mad.  No.  What?  No.  Okay.  You run, you can run.  You can run.  You always fall down if you run.  I'm going to enter the house.  No, wait. Come here.  No. No.  There are cars. There are cars.  Okay. Say hi.  Look. Look.  Look.  The house of Jim.  And what?  The parents of Jamie.  Summer house?  The parents of Jamie.  Goodbye, dad.  Yeah.  Yeah.  In the house."`
* **Visual Caption**: `"Skipped due to VRAM safety preflight"`
* **OCR Text**: `"om « ts > 7 — i _* — <p — . & So » i ~_ —_ ag i —"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`3473422 bytes`)
  * Keyframe Image: `Exists`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 128 (Vad Silence)
* **Scene ID**: `e2b2307308d736c8d9d63df0b248f445e7c18f89836c3a5bfb2ada7fe6d8c86f`
* **Start / End**: `8054.68s` / `8083.375s` (Duration: `28.695s`)
* **Transcript Status**: `success`
* **Diarization**: `16 segments (Speakers: SPEAKER_00, SPEAKER_01)`
* **Transcript**: `"Say hi to Tito. I miss you Tito. No I don't. Not that much. He just hit his schnoz on"`
* **Visual Caption**: `"two women talking"`
* **OCR Text**: `"{ * - = r Tr in = = a ee — an | a_i — = a be ~ = ail! _ —— = ’ ame = i a r — L 4 5 a= - 32 ae San —_ ————s. . q ee ll a4 ~~ ss 4 = 4 a - =..* i ni a _ . " — = 2S Se >. ' —-* mn =— i , eee . oe"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`918318 bytes`)
  * Keyframe Image: `Exists`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (object_detect), video:staged (object_detect), video:staged (object_detect), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`

### Scene 57 (Visually Rich)
* **Scene ID**: `a22f0a54b0686c9e37d2a4464f9290f85862d04eab7c84ae279a189c2d8b5f5a`
* **Start / End**: `3180.644s` / `3247.244s` (Duration: `66.600s`)
* **Transcript Status**: `success`
* **Diarization**: `19 segments (Speakers: SPEAKER_00, SPEAKER_01)`
* **Transcript**: `"Joe? Say hi Uncle Domingo and Aunt Celsa. Say hello. Say hello. Come here.  See, Mama's making a tape for Uncle Domingo. Come here. Show him how great you walk. Come on.  Oh, I have to go upstairs for him too. I want to go upstairs and put that on the tape for him.  Say hi. You're gonna see them in a couple days anyway. Say hi. What are you doing there Joe?"`
* **Visual Caption**: `"a little boy playing with a cell phone"`
* **OCR Text**: `"te. 1 ——-"`
* **Files on Disk**:
  * Audio Wave Chunk: `Exists` (`2131278 bytes`)
  * Keyframe Image: `Exists`
* **UCF Ledger Staged Frames**: `text:staged (image_ocr), multimodal:staged (image_caption), video:staged (object_detect), video:staged (image_embed_dino), video:staged (image_embed_clip), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), text:staged (audio_transcribe), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (speaker_merge), audio:staged (audio_embed_clap), text:staged (text_embed), video:staged (scene_visual_embeddings_clip), video:staged (scene_visual_embeddings_dino)`
