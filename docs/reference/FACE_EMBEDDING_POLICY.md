<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-08-08 -->

# Face Embedding Policy

## Current contract

`opencv-yunet-sface` is the primary face detector and embedding engine. It is
CPU-safe, supplied only through the `face_identity_cpu` capability pack, and
verified by exact file size and SHA-256 before use. The pack contains immutable
OpenCV Zoo YuNet and SFace ONNX files plus their upstream notices.

`face_recognition`/dlib remains the CC0-model fallback. A fallback result is
always marked `status: degraded`, names both engines, and records the primary
failure reason. If both engines are unavailable, face embedding returns a
terminal `error` receipt rather than silently omitting the feature.

Face vectors record their engine and dimension. Candidate clustering refuses to
mix engine or vector-dimension contracts; legacy unsealed face artifacts require
a clean re-ingestion epoch.

## Historical rejection

FaceNet/VGGFace2 was removed on 2026-08-08. Its fallback path relied on an
unsealed pretrained-weight provenance chain and had inconsistent artifact
metadata. It is permanently excluded from runtime, installer packs, and future
candidate selection.
