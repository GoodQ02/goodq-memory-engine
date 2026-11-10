<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: ACTIVE_CONTRACT -->
<!-- DOC_LAST_VERIFIED: 2026-10-25 -->

# Object Detection Policy

GoodQ4All uses sealed OpenCV Zoo ONNX capability packs for object detection.
The runtime never downloads a detector model.

| Capability | Pack | Model | Runtime | License |
|---|---|---|---|---|
| Quality detector | `object_detection_gpu` | YOLOX | ONNX Runtime, CUDA when available, otherwise CPU | Apache-2.0 |
| Missing-pack baseline | `object_detection_cpu` | NanoDet | OpenCV DNN / CPU | Apache-2.0 |

YOLOX is selected whenever its pack is installed. On the October 25 frozen
held-out set it met the detector criteria on both CPU and CUDA (recall 14/20,
box-reviewed precision 0.938) while NanoDet missed the precision threshold
(11/20, 0.786). Evidence: `tmp/visual-criteria-20261025-001/RESULT.md`.

Both packs are built only from the pinned OpenCV Zoo revision recorded in
`configs/model_registry.yaml`. The installer stages a model only after the
source vault manifest, model SHA-256, size, license notice, and package receipt
all agree. A missing or invalid pack is reported as `detect_meta.status =
unavailable`; it is never fetched at first use.

The worker runs in the locked project-local runtime described in
`envs/object_detect/README.md`. A CUDA session must confirm
`CUDAExecutionProvider` after creation; a provider list alone is not proof.
If CUDA initialization or inference fails, the same YOLOX model retries on CPU
and the result records `detect_meta.fallback_from = opencv_yolox:cuda` and
`detect_meta.fallback_reason`. This is an explicit continuity path, not a
silent quality claim. Object detection is separate from OCR and emits COCO
object labels with bounding boxes and confidence scores (`detect_meta.engine`
names `onnxruntime` or `opencv-dnn`).

The prior external detector stack is retired from active dependencies,
bootstrap, registry, and installer inputs because its distribution terms do not
fit the permissive baseline. Historical records remain only under `archive/`.
Packaged installs do not yet carry an `object-detect-runtime`; installer
delivery of this runtime is unqualified.
