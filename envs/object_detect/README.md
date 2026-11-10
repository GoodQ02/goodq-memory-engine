# Object detection runtime

Object detection uses the project-local `envs/object_detect/.venv` interpreter,
resolved as `goodq_object_detect`. It does not inherit any Conda environment;
a missing runtime is a launch error, never a silent switch to another env.
The lock targets Windows x64 / Python 3.10 and is not a portable recipe.

Create it offline from a local wheelhouse holding the exact
`envs/locks/object_detect.lock.txt` packages (the sealed Paddle OCR wheelhouse
contains all of them):

```text
python -m venv envs/object_detect/.venv
envs/object_detect/.venv/Scripts/python -m pip install --no-index --find-links <local-wheelhouse> -r envs/object_detect/requirements.txt
envs/object_detect/.venv/Scripts/python -m pip check
```

YOLOX (`opencv_yolox`) runs through ONNX Runtime on CUDA when the provider is
available and otherwise on CPU. CUDA 12 / cuDNN 9 come from the pinned NVIDIA
wheels and are loaded with `onnxruntime.preload_dlls()`; without that call ONNX
Runtime silently creates a CPU session. No global CUDA install or PATH edit is
used. Model files are sealed assets under `paths.models_cache`; the worker never
downloads. CUDA qualification on the 16 GB host does not qualify 8/6 GB followers.
