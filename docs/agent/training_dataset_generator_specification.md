# Fine-Tuning Training Dataset Generator Specification (v1.0.0)
**Status:** `APPROVED SPECIFICATION`
**Epoch ID:** `epoch_2026_07_05_home_memory_clean_01`
**Author:** Antigravity & Developer Pair

---

## 1. Goal & Context
This specification outlines the filtering, curation, and generation protocol for synthesizing a fine-tuning dataset from the truth-locked multimodal memory of the 12-movie home-movie epoch (`epoch_2026_07_05_home_memory_clean_01`). 

The output will be a conversation-style JSONL dataset suitable for training Visual-Language Models (VLMs) or Large Language Models (LLMs) to understand what the home-movie memories mean (family lore, names, events) rather than just describing raw pixels.

---

## 2. Ingestion-to-Training Invariants
To prevent training on noise (Whisper hallucinations, VHS tracking pops, garbled text overlays), the dataset generator must enforce the following strict filters during extraction.

### Filter 1: Three-Bucket OCR Filtering
Raw visual OCR nodes contain significant VHS noise (32.06% noise ratio). We process OCR payloads into three buckets:
* **Bucket A: Date/Time Overlays** (e.g., `"APR 23 2000"`, `"2000"`): **KEEP** and structure as primary temporal timeline anchors in the training prompt.
* **Bucket B: Legible Semantic OCR**: **KEEP** as weak visual evidence to supplement scene context.
* **Bucket C: Tracking & Punctuation Junk** (e.g., `"—— , . 4 - katie : = > -)"`): **EXCLUDE** entirely. Do not include in training prompts.

### Filter 2: Speech Transcript Length Threshold
* **Hallucination Guard**: Exclude transcript segments containing **3 words or fewer** (e.g., "hi", "no", Whisper microphone pops, or static alignment fragments). Only include dialogue turns with $\ge 4$ words to guarantee rich semantic dialogue structure.

### Filter 3: Local Speaker ID Boundary (Diarization Scoping)
* **Identity Isolation**: Speaker labels (`SPEAKER_00`, `SPEAKER_01`, etc.) are video-scoped (local) and are **not** stable human identities across different home movies. 
* **Constraint**: Do **not** map `SPEAKER_00` to a generic family identity (like "Dad" or "Joe") during training pair synthesis. Keep speaker markers as local conversational turn structure only, or exclude them until cross-video voice embedding clustering is performed.

### Filter 4: Strict Provenance Requirement
* Every training instance (conversational prompt-response pair) must map back to a set of validated and promoted UCF context frame IDs. If a scene has no promoted frames in `ucf_provenance_mapping`, it must be skipped.

### Filter 5: Case Normalization & Casing Deduplication
* Standardize entity references casing (e.g. map both "dad" and "Dad" to "Dad") to prevent vocabulary fragmentation in the fine-tuned model weights.

---

## 3. Training Pair Structure & Format
The generated dataset will use the standard conversational format (`messages` schema):

```json
{
  "messages": [
    {"role": "user", "content": "Tell me about the scene in Video 237eb8d7 from 10:15 to 11:30."},
    {"role": "assistant", "content": "This was the Christmas gathering where Jack was playing with his toys and Mom knit the itchy sweater. Sophia was present."}
  ],
  "provenance": {
    "video_hash": "237eb8d79c5e03362194a95b87f13a64228a521697b2c0fa0cf29752af4f1494",
    "scene_id": "2e1dbe0fd3f4f33ad3a0809dbbcd06d828f4e2ebf757e4e7a3c729aec86144c1",
    "ucf_frame_ids": [2603, 2604, 2605]
  }
}
```

---
*End of APPROVED SPECIFICATION.*
