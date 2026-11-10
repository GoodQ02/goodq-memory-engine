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
    if len(argv) not in (3, 4):
        print("usage: python fw_transcribe.py <input_wav> <output_json> [options_json]", file=sys.stderr)
        return 1

    input_wav = argv[1]
    output_json = argv[2]

    model_size = os.environ.get("GOODQ_FW_MODEL_SIZE", "medium").strip() or "medium"
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
        try:
            from .transcription_contract import transcribe_file
        except ImportError:
            from transcription_contract import transcribe_file
        options = json.loads(argv[3]) if len(argv) == 4 else {}
        model_size = str(options.pop('model', None) or model_size)
        model = WhisperModel(model_size, device=device, compute_type=compute_type,
                             local_files_only=os.environ.get('HF_HUB_OFFLINE') == '1')
        payload = transcribe_file(model, input_wav, **options)
        payload.update(model=model_size, device=str(getattr(model, 'device', device) or device), telemetry=telemetry)
        _write_json(output_json, payload)
        return 0 if payload['status'] == 'success' else 1
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
