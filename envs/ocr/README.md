# Paddle OCR runtime

Image/video OCR uses the project-local `envs/ocr/.venv` interpreter, resolved as
`goodq_ocr`. It does not inherit the caption, core or retired Conda OCR environment.
The lock targets Windows x64 / Python 3.10. Other platforms require qualification;
the Windows lock must not be presented as a portable installation recipe.

Create a local wheelhouse using the exact `envs/locks/ocr.lock.txt`, then run with
Python 3.10:

```text
python scripts/setup/install_ocr_runtime.py --wheelhouse <local-wheelhouse>
```

Installation uses `--no-index` and `pip check`. `timezonefinder` is deliberately
absent: its older cffi requirement conflicted with the experimental shared overlay.
The Paddle environment keeps its own pinned cffi/cryptography versions. CUDA DLLs
are local NVIDIA wheels loaded by ONNX Runtime; no global CUDA or PATH edit is used.

Pinned PP-OCRv6 medium detector and recognizer records in `model_registry.yaml`
own the model identities, relative paths and file hashes. Provision those exact
files beneath resolved `paths.models_cache`; worker startup does not download.
`image_ocr.device` selects `cpu` or `cuda:0`. A missing selected provider is an
error. CUDA qualification on the 16 GB host does not qualify 8/6 GB followers.

Packaged installs require a separate `ocr-runtime` payload with this locked
environment. Their shared embedded interpreter uses a different NumPy lane.
The installer now fails explicitly if the OCR payload is absent; no new installer
payload/build is qualified by the local replacement. The retired Tesseract
installation is not deleted and remains available only for deployment rollback.
