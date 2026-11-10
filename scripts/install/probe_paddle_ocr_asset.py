"""Exercise one packaged OCR graph in its isolated runtime, without downloads."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import onnxruntime as ort
import yaml


def main() -> int:
    graph = Path(sys.argv[1]).resolve(strict=True)
    device = sys.argv[2]
    if device not in {"cpu", "cuda", "cuda:0"}:
        raise ValueError("unsupported OCR probe device")
    provider = "CPUExecutionProvider" if device == "cpu" else "CUDAExecutionProvider"
    if provider not in ort.get_available_providers():
        raise RuntimeError(f"required provider unavailable: {provider}")
    if provider == "CUDAExecutionProvider":
        ort.preload_dlls(directory="")
    session = ort.InferenceSession(str(graph), providers=[provider])
    session.disable_fallback()
    if session.get_providers()[0] != provider:
        raise RuntimeError("selected OCR session provider was not established")
    config = yaml.safe_load(graph.with_suffix(".yml").read_text(encoding="utf-8"))
    name = config["Global"]["model_name"]
    shape = (1, 3, 64, 64) if name.endswith("_det") else (1, 3, 48, 320)
    outputs = session.run(None, {session.get_inputs()[0].name: np.zeros(shape, dtype=np.float32)})
    if not outputs or not all(np.isfinite(output).all() for output in outputs):
        raise RuntimeError("OCR graph returned missing or non-finite output")
    print(json.dumps({"device": device, "output": {
        "classification": "onnx_graph_inference", "model_name": name,
        "providers": session.get_providers(), "shapes": [list(value.shape) for value in outputs],
    }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
