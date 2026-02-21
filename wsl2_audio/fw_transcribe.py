#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    out_dir = os.path.dirname(os.path.abspath(path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def _build_error_payload(
    model_size: str,
    device: str,
    telemetry: Dict[str, Any],
    error: str,
) -> Dict[str, Any]:
    return {
        "status": "error",
        "engine": "faster-whisper",
        "model": model_size,
        "device": device,
        "language": None,
        "segments": [],
        "error": error,
        "telemetry": telemetry,
    }


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print("usage: python fw_transcribe.py <input_wav> <output_json>", file=sys.stderr)
        return 1

    input_wav = argv[1]
    output_json = argv[2]

    model_size = os.environ.get("GOODQ_FW_MODEL_SIZE", "tiny").strip() or "tiny"
    compute_type = os.environ.get("GOODQ_FW_COMPUTE_TYPE", "float16").strip() or "float16"
    device = "cuda"

    torch_cuda = False
    device_name = None
    try:
        import torch  # type: ignore

        torch_cuda = bool(torch.cuda.is_available())
        if torch_cuda:
            device_name = torch.cuda.get_device_name(0)
    except Exception:
        pass

    telemetry = {
        "torch_cuda": torch_cuda,
        "device_name": device_name,
    }

    try:
        from faster_whisper import WhisperModel  # type: ignore

        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(input_wav)

        segments = []
        for seg in segments_iter:
            text = (getattr(seg, "text", "") or "").strip()
            segments.append(
                {
                    "start": float(getattr(seg, "start", 0.0) or 0.0),
                    "end": float(getattr(seg, "end", 0.0) or 0.0),
                    "text": text,
                }
            )

        payload = {
            "status": "success",
            "engine": "faster-whisper",
            "model": model_size,
            "device": str(getattr(model, "device", device) or device),
            "language": getattr(info, "language", None),
            "segments": segments,
            "telemetry": telemetry,
        }
        _write_json(output_json, payload)
        return 0
    except Exception as e:
        payload = _build_error_payload(
            model_size=model_size,
            device=device,
            telemetry=telemetry,
            error=f"{type(e).__name__}: {e}",
        )
        try:
            _write_json(output_json, payload)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
