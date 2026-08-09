<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: ACTIVE_CONTRACT -->
<!-- DOC_LAST_VERIFIED: 2026-08-08 -->

# Object Detection Policy

GoodQ4All uses sealed OpenCV Zoo ONNX capability packs for object detection.
The runtime never downloads a detector model.

| Capability | Pack | Model | Runtime | License |
|---|---|---|---|---|
| CPU baseline | `object_detection_cpu` | NanoDet | OpenCV DNN / CPU | Apache-2.0 |
| GPU-enhanced | `object_detection_gpu` | YOLOX | OpenCV DNN / CUDA when available | Apache-2.0 |

Both packs are built only from the pinned OpenCV Zoo revision recorded in
`configs/model_registry.yaml`. The installer stages a model only after the
source vault manifest, model SHA-256, size, license notice, and package receipt
all agree. A missing or invalid pack is reported as `detect_meta.status =
unavailable`; it is never fetched at first use.

GPU inference may fall back to the sealed CPU pack only when the GPU execution
fails. That result remains visible through `detect_meta.fallback_from` and
`detect_meta.fallback_reason`. This is an explicit continuity path, not a
silent quality claim. Object detection is separate from OCR and emits COCO
object labels with bounding boxes and confidence scores.

The prior external detector stack is retired from active dependencies,
bootstrap, registry, and installer inputs because its distribution terms do not
fit the permissive baseline. Historical records remain only under `archive/`.
