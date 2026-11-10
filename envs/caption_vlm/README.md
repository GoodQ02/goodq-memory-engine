# Caption runtime (WeVisOne-VL-2B)

Scene captioning uses the project-local `envs/caption_vlm/.venv` interpreter,
resolved as `goodq_caption_vlm`. A missing runtime is a launch error; it never
falls back to the `goodq_image_caption` Conda env (which still serves CLIP,
DINO and EXIF). The lock targets Windows x64 / Python 3.10.

Create it offline from a local wheelhouse holding the exact
`envs/locks/caption_vlm.lock.txt` packages (torch/torchvision from the PyTorch
cu121 index; verify wheel SHA-256 against the index before sealing):

```text
python -m venv envs/caption_vlm/.venv
envs/caption_vlm/.venv/Scripts/python -m pip install --no-index --find-links <local-wheelhouse> -r envs/caption_vlm/requirements.txt
envs/caption_vlm/.venv/Scripts/python -m pip check
```

The model is the sealed `wevisone_vl_2b` registry asset (pinned revision,
per-file SHA-256) under `paths.models_cache`; the worker never downloads.
Small files are hashed on every load; the 9.8 GB weights are hashed at
provisioning and size-checked at load. Callers send all sampled frames of a
scene in one `samples` request so the model loads once per scene. CUDA uses
bfloat16 (about 5 GB); without CUDA the model runs on CPU in float32, slowly.
Captions are model-generated descriptions (`caption_meta.inference_kind`), not
confirmed observations. Qualification covers the 16 GB Windows host only.
