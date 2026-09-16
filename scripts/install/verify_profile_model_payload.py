"""Load and minimally exercise every selected installed model without networking."""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterator

if __package__:
    from .installer_contract import (
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
        MODEL_MEMBER_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_SCHEMA_VERSION,
    )
else:
    from installer_contract import (
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
        MODEL_MEMBER_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_SCHEMA_VERSION,
    )


ProbeLoader = Callable[[Path, str], dict[str, Any]]
_OFFLINE_ENVIRONMENT = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "PIP_NO_INDEX": "1",
    "GOODQ_OFFLINE_BUILD": "1",
    "NETWORK_POLICY": "blocked",
}


class _NetworkBlocked(OSError):
    pass


def _require_fields(
    value: dict[str, Any], required_fields: frozenset[str], label: str
) -> None:
    missing = sorted(required_fields - set(value))
    if missing:
        raise ValueError(f"{label} is missing required field: {missing[0]}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _offline_environment_is_set() -> bool:
    return all(os.environ.get(key) == value for key, value in _OFFLINE_ENVIRONMENT.items())


@contextmanager
def _blocked_network() -> Iterator[list[str]]:
    attempts: list[str] = []
    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection

    def blocked_connect(_socket, address):
        attempts.append(str(address)[:200])
        raise _NetworkBlocked("network access blocked during offline model probe")

    def blocked_create_connection(address, *args, **kwargs):
        attempts.append(str(address)[:200])
        raise _NetworkBlocked("network access blocked during offline model probe")

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    socket.create_connection = blocked_create_connection  # type: ignore[assignment]
    try:
        yield attempts
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


def _shape(value: Any) -> list[int]:
    return [int(item) for item in getattr(value, "shape", ())]


def _tensor_from_output(value: Any) -> Any:
    if _shape(value):
        return value
    for attribute in (
        "audio_embeds",
        "image_embeds",
        "pooler_output",
        "last_hidden_state",
    ):
        candidate = getattr(value, attribute, None)
        if candidate is not None and _shape(candidate):
            return candidate
    if isinstance(value, (tuple, list)) and value:
        return _tensor_from_output(value[0])
    raise RuntimeError("model probe did not return a shaped tensor")


def _cuda_device(device: str):
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required by this installed model probe")
    return torch


def _finish_model(model: Any, device: str) -> None:
    del model
    if device == "cuda":
        import torch

        torch.cuda.empty_cache()


def _probe_transformers_token_classification(path: Path, device: str) -> dict[str, Any]:
    torch = _cuda_device(device)
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = {key: value.to(device) for key, value in tokenizer("GoodQ", return_tensors="pt").items()}
    with torch.no_grad():
        logits = model(**inputs).logits
    output = {"classification": "token_logits", "shape": _shape(logits)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_text_classification(path: Path, device: str) -> dict[str, Any]:
    torch = _cuda_device(device)
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = {key: value.to(device) for key, value in tokenizer("GoodQ", return_tensors="pt").items()}
    with torch.no_grad():
        logits = model(**inputs).logits
    output = {"classification": "sequence_logits", "shape": _shape(logits)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _blank_image():
    from PIL import Image

    return Image.new("RGB", (32, 32), color=(0, 0, 0))


def _probe_transformers_blip_caption(path: Path, device: str) -> dict[str, Any]:
    torch = _cuda_device(device)
    from transformers import BlipForConditionalGeneration, BlipProcessor

    processor = BlipProcessor.from_pretrained(path, local_files_only=True)
    model = BlipForConditionalGeneration.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = {key: value.to(device) for key, value in processor(images=_blank_image(), return_tensors="pt").items()}
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=1, do_sample=False)
    output = {"classification": "caption_token", "shape": _shape(generated)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_vit_gpt2_caption(path: Path, device: str) -> dict[str, Any]:
    torch = _cuda_device(device)
    from transformers import AutoImageProcessor, VisionEncoderDecoderModel

    processor = AutoImageProcessor.from_pretrained(path, local_files_only=True)
    model = VisionEncoderDecoderModel.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    pixel_values = processor(images=_blank_image(), return_tensors="pt").pixel_values.to(device)
    with torch.no_grad():
        generated = model.generate(pixel_values, max_new_tokens=1, do_sample=False)
    output = {"classification": "caption_token", "shape": _shape(generated)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_clip_image(path: Path, device: str) -> dict[str, Any]:
    torch = _cuda_device(device)
    from transformers import AutoProcessor, CLIPModel

    processor = AutoProcessor.from_pretrained(path, local_files_only=True)
    model = CLIPModel.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = processor(images=_blank_image(), return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(device)
    with torch.no_grad():
        embedding = _tensor_from_output(
            model.get_image_features(pixel_values=pixel_values)
        )
    output = {"classification": "image_embedding", "shape": _shape(embedding)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_dino_image(path: Path, device: str) -> dict[str, Any]:
    torch = _cuda_device(device)
    from transformers import AutoImageProcessor, AutoModel

    processor = AutoImageProcessor.from_pretrained(path, local_files_only=True)
    model = AutoModel.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = {key: value.to(device) for key, value in processor(images=_blank_image(), return_tensors="pt").items()}
    with torch.no_grad():
        output_tensor = model(**inputs).last_hidden_state
    output = {"classification": "vision_embedding", "shape": _shape(output_tensor)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_clap_audio(path: Path, device: str) -> dict[str, Any]:
    import numpy as np

    torch = _cuda_device(device)
    from transformers import AutoProcessor, ClapModel

    processor = AutoProcessor.from_pretrained(path, local_files_only=True)
    model = ClapModel.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = processor(audios=np.zeros(48_000, dtype=np.float32), sampling_rate=48_000, return_tensors="pt")
    model_inputs = {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in inputs.items()
    }
    with torch.no_grad():
        embedding = _tensor_from_output(model.get_audio_features(**model_inputs))
    output = {"classification": "audio_embedding", "shape": _shape(embedding)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_audio_classification(path: Path, device: str) -> dict[str, Any]:
    import numpy as np

    torch = _cuda_device(device)
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

    extractor = AutoFeatureExtractor.from_pretrained(path, local_files_only=True)
    model = AutoModelForAudioClassification.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = extractor(np.zeros(16_000, dtype=np.float32), sampling_rate=16_000, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits
    output = {"classification": "audio_logits", "shape": _shape(logits)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_audio_ctc(path: Path, device: str) -> dict[str, Any]:
    import numpy as np

    torch = _cuda_device(device)
    from transformers import AutoModelForCTC, AutoProcessor

    processor = AutoProcessor.from_pretrained(path, local_files_only=True)
    model = AutoModelForCTC.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    inputs = processor(np.zeros(16_000, dtype=np.float32), sampling_rate=16_000, return_tensors="pt")
    input_values = inputs.input_values.to(device)
    with torch.no_grad():
        logits = model(input_values).logits
    output = {"classification": "ctc_logits", "shape": _shape(logits)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_transformers_whisper_generate(path: Path, device: str) -> dict[str, Any]:
    import numpy as np

    torch = _cuda_device(device)
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    processor = AutoProcessor.from_pretrained(path, local_files_only=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        path, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    features = processor(
        np.zeros(16_000, dtype=np.float32), sampling_rate=16_000, return_tensors="pt"
    ).input_features.to(device)
    with torch.no_grad():
        generated = model.generate(features, max_new_tokens=1, do_sample=False)
    output = {"classification": "speech_token", "shape": _shape(generated)}
    _finish_model(model, device)
    return {"device": device, "output": output}


def _probe_faster_whisper(path: Path, device: str) -> dict[str, Any]:
    import numpy as np
    from faster_whisper import WhisperModel

    if device == "cuda":
        _cuda_device(device)
    model = WhisperModel(
        str(path),
        device=device,
        compute_type="float16" if device == "cuda" else "int8",
        local_files_only=True,
    )
    segments, _info = model.transcribe(
        np.zeros(16_000, dtype=np.float32),
        language="en",
        beam_size=1,
        vad_filter=False,
    )
    segment_count = sum(1 for _segment in segments)
    return {
        "device": device,
        "output": {"classification": "transcription", "segment_count": segment_count},
    }


def _onnx_file(path: Path) -> Path:
    if path.is_file() and path.suffix.casefold() == ".onnx":
        return path
    candidates = sorted(path.rglob("*.onnx"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one ONNX graph under {path}")
    return candidates[0]


def _probe_opencv_dnn_graph(path: Path, device: str) -> dict[str, Any]:
    import cv2

    graph = _onnx_file(path)
    network = cv2.dnn.readNet(str(graph))
    if device == "cuda":
        if cv2.cuda.getCudaEnabledDeviceCount() < 1:
            raise RuntimeError("OpenCV CUDA device is unavailable")
        network.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
        network.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
    layer_count = len(network.getLayerNames())
    if layer_count < 1:
        raise RuntimeError("OpenCV graph contains no layers")
    return {
        "device": device,
        "output": {"classification": "graph_open", "layer_count": layer_count},
    }


def _probe_opencv_yunet_graph(path: Path, device: str) -> dict[str, Any]:
    import cv2

    if device == "cuda":
        _cuda_device(device)
    detector = cv2.FaceDetectorYN.create(str(_onnx_file(path)), "", (32, 32))
    return {
        "device": device,
        "output": {"classification": "graph_open", "type": type(detector).__name__},
    }


def _probe_opencv_sface_graph(path: Path, device: str) -> dict[str, Any]:
    import cv2

    if device == "cuda":
        _cuda_device(device)
    recognizer = cv2.FaceRecognizerSF.create(str(_onnx_file(path)), "")
    return {
        "device": device,
        "output": {"classification": "graph_open", "type": type(recognizer).__name__},
    }


def _probe_pyannote_via_wsl(
    path: Path,
    device: str,
    *,
    kind: str,
) -> dict[str, Any]:
    """Load the exact installed Pyannote path in the preserved WSL owner."""

    distro = os.environ.get("GOODQ_WSL_DISTRO", "Ubuntu-22.04").strip()
    translated = subprocess.run(
        ["wsl", "-d", distro, "--", "wslpath", "-a", "-u", str(path.resolve())],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if translated.returncode != 0 or not translated.stdout.strip():
        raise RuntimeError(
            "failed to resolve the exact installed Pyannote path in WSL: "
            + (translated.stderr or translated.stdout or "unknown error").strip()[-500:]
        )
    script = """
import json
import pathlib
import sys
import torch
from pyannote.audio import Model, Pipeline

path = pathlib.Path(sys.argv[1])
kind = sys.argv[2]
device = sys.argv[3]
if kind == "pipeline":
    source = path / "config.yaml" if (path / "config.yaml").is_file() else path
    loaded = Pipeline.from_pretrained(str(source))
    if device == "cuda":
        loaded.to(torch.device("cuda"))
    classification = "pipeline_open"
else:
    loaded = Model.from_pretrained(str(path))
    loaded.to(torch.device(device)).eval()
    classification = "model_open"
print(json.dumps({"device": device, "output": {"classification": classification, "type": type(loaded).__name__}}, sort_keys=True))
""".strip()
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    workspace = os.environ.get("GOODQ_WSL_WORKSPACE", "").strip()
    shell_command = (
        "set -euo pipefail; "
        ': "${GOODQ_PROBE_WORKSPACE:=$HOME/goodq_audio}"; '
        'source "$GOODQ_PROBE_WORKSPACE/setup_cuda_env.sh" >/dev/null 2>&1; '
        "python3 -c 'import base64,sys;payload=sys.argv.pop(1);"
        "exec(base64.b64decode(payload))' \"$1\" \"$2\" \"$3\" \"$4\""
    )
    command = ["wsl", "-d", distro, "--", "env"]
    if workspace:
        command.append(f"GOODQ_PROBE_WORKSPACE={workspace}")
    command.extend(
        [
            "HF_HUB_OFFLINE=1",
            "TRANSFORMERS_OFFLINE=1",
            "HF_DATASETS_OFFLINE=1",
            "bash",
            "-lc",
            shell_command,
            "goodq-pyannote-probe",
            encoded,
            translated.stdout.strip(),
            kind,
            device,
        ]
    )
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "exact installed Pyannote WSL probe failed: "
            + (completed.stderr or completed.stdout or "unknown error").strip()[-900:]
        )
    try:
        result = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError("exact installed Pyannote WSL probe returned invalid evidence") from exc
    if not isinstance(result, dict):
        raise RuntimeError("exact installed Pyannote WSL probe returned invalid evidence")
    return result


def _probe_pyannote_pipeline(path: Path, device: str) -> dict[str, Any]:
    return _probe_pyannote_via_wsl(path, device, kind="pipeline")


def _probe_pyannote_model(path: Path, device: str) -> dict[str, Any]:
    return _probe_pyannote_via_wsl(path, device, kind="model")


def _probe_sentence_transformer(path: Path, device: str) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(path), device=device, local_files_only=True)
    embedding = model.encode(["GoodQ"], convert_to_numpy=True, normalize_embeddings=True)
    return {
        "device": device,
        "output": {"classification": "text_embedding", "shape": _shape(embedding)},
    }


def _probe_silero_vad(path: Path, device: str) -> dict[str, Any]:
    import onnxruntime as ort

    if device == "cuda":
        _cuda_device(device)
    graph = _onnx_file(path)
    session = ort.InferenceSession(str(graph), providers=["CPUExecutionProvider"])
    return {
        "device": "cpu",
        "output": {
            "classification": "graph_open",
            "input_count": len(session.get_inputs()),
        },
    }


def _probe_lexicon(path: Path, device: str) -> dict[str, Any]:
    files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
    if not files:
        raise RuntimeError("installed lexicon contains no files")
    return {
        "device": "cpu",
        "output": {"classification": "lexicon_open", "member_count": len(files)},
    }


DEFAULT_PROBE_LOADERS: dict[str, ProbeLoader] = {
    "transformers_token_classification": _probe_transformers_token_classification,
    "transformers_text_classification": _probe_transformers_text_classification,
    "transformers_text_classification_safetensors": _probe_transformers_text_classification,
    "transformers_blip_caption": _probe_transformers_blip_caption,
    "transformers_vit_gpt2_caption": _probe_transformers_vit_gpt2_caption,
    "transformers_clip_image": _probe_transformers_clip_image,
    "transformers_dino_image": _probe_transformers_dino_image,
    "transformers_clap_audio": _probe_transformers_clap_audio,
    "transformers_audio_classification": _probe_transformers_audio_classification,
    "transformers_audio_ctc": _probe_transformers_audio_ctc,
    "transformers_whisper_generate": _probe_transformers_whisper_generate,
    "faster_whisper_transcribe": _probe_faster_whisper,
    "opencv_dnn_graph": _probe_opencv_dnn_graph,
    "opencv_yunet_graph": _probe_opencv_yunet_graph,
    "opencv_sface_graph": _probe_opencv_sface_graph,
    "pyannote_pipeline_load": _probe_pyannote_pipeline,
    "pyannote_model_load": _probe_pyannote_model,
    "sentence_transformer_encode": _probe_sentence_transformer,
    "silero_vad_load": _probe_silero_vad,
    "lexicon_open": _probe_lexicon,
}


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{description} must be a JSON object")
    return payload


def _verify_installed_members(
    *,
    models_root: Path,
    manifest: dict[str, Any],
) -> None:
    _require_fields(
        manifest,
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        "installed model member manifest",
    )
    if manifest.get("schema_version") != MODEL_MEMBER_MANIFEST_SCHEMA_VERSION:
        raise ValueError("installed model member manifest must use schema version 2")
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("installed model member manifest has no members")
    if any(not isinstance(member, dict) for member in members):
        raise ValueError("installed model member manifest contains an invalid member")
    for member in members:
        _require_fields(member, MODEL_MEMBER_REQUIRED_FIELDS, "installed model member")
    paths = [str(member.get("path") or "") for member in members]
    if int(manifest.get("member_count") or -1) != len(members):
        raise ValueError("installed model member count mismatch")
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError("installed model member paths are not unique and sorted")
    for member in members:
        relative = Path(str(member.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe installed member path: {relative}")
        path = models_root / relative
        if not path.is_file():
            raise ValueError(f"installed member is missing: {relative.as_posix()}")
        if path.stat().st_size != int(member.get("size_bytes") or -1):
            raise ValueError(f"installed member size mismatch: {relative.as_posix()}")
        if _sha256(path).casefold() != str(member.get("sha256") or "").casefold():
            raise ValueError(f"installed member hash mismatch: {relative.as_posix()}")
    actual_paths = {
        path.relative_to(models_root).as_posix()
        for path in models_root.rglob("*")
        if path.is_file()
        and path.name not in {
            "model_member_manifest.json",
            "selected_capabilities.json",
        }
    }
    if actual_paths != set(paths):
        extra = sorted(actual_paths - set(paths))
        missing = sorted(set(paths) - actual_paths)
        detail = extra[0] if extra else missing[0] if missing else "unknown"
        raise ValueError(f"installed model membership mismatch: {detail}")
    inventory_sha256 = hashlib.sha256(
        json.dumps(members, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if inventory_sha256 != manifest.get("inventory_sha256"):
        raise ValueError("installed member inventory digest mismatch")


def verify(
    *,
    install_dir: Path,
    models_root: Path,
    probe_loaders: dict[str, ProbeLoader] | None = None,
) -> dict[str, Any]:
    selected_path = install_dir / "configs" / "selected_capabilities.json"
    selected = _load_json(selected_path, "selected capability receipt")
    _require_fields(
        selected,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        "selected capability receipt",
    )
    if selected.get("schema_version") != SELECTED_CAPABILITIES_SCHEMA_VERSION:
        raise ValueError("selected capability receipt must use schema version 2")
    entries = selected.get("payloads")
    if not isinstance(entries, list) or not entries:
        raise ValueError("selected capability receipt declares no model or lexicon payloads")
    asset_closure = selected.get("asset_closure")
    if not isinstance(asset_closure, dict):
        raise ValueError("selected capability receipt has no asset closure")
    capability_dispositions = asset_closure.get("capability_dispositions") or {}
    for capability in ("local_vlm", "local_llm_serving"):
        if (capability_dispositions.get(capability) or {}).get("status") != "policy_excluded":
            raise ValueError(f"{capability} must remain policy-excluded")
    assets_by_id = asset_closure.get("assets_by_id")
    if not isinstance(assets_by_id, dict):
        raise ValueError("selected capability receipt has no asset records")
    manifest_record = selected.get("model_member_manifest")
    if not isinstance(manifest_record, dict):
        raise ValueError("selected capability receipt has no model member manifest")
    manifest_path = install_dir / "configs" / str(manifest_record.get("path") or "")
    if not manifest_path.is_file() or _sha256(manifest_path) != manifest_record.get("sha256"):
        raise ValueError("installed model member manifest hash mismatch")
    member_manifest = _load_json(manifest_path, "model member manifest")
    if member_manifest.get("inventory_sha256") != manifest_record.get("inventory_sha256"):
        raise ValueError("installed model member inventory identity mismatch")
    _verify_installed_members(models_root=models_root, manifest=member_manifest)

    install_text = str(install_dir.resolve())
    if install_text not in sys.path:
        sys.path.insert(0, install_text)
    os.environ.update(_OFFLINE_ENVIRONMENT)
    os.environ["GOODQ_DATA_ROOT"] = str(models_root.parent)
    os.environ["GOODQ_MODELS_DIR"] = str(models_root)
    loaders = DEFAULT_PROBE_LOADERS if probe_loaders is None else probe_loaders
    probes: list[dict[str, Any]] = []
    with _blocked_network() as network_attempts:
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("selected capability receipt contains an invalid payload")
            asset_id = str(entry.get("asset_id") or "")
            closure = assets_by_id.get(asset_id)
            if not isinstance(closure, dict):
                raise ValueError(f"selected payload has no asset closure: {asset_id}")
            runtime_relative = Path(str(entry.get("runtime_path") or ""))
            if runtime_relative.is_absolute() or ".." in runtime_relative.parts:
                raise ValueError(f"unsafe installed runtime path: {asset_id}")
            runtime_path = models_root / runtime_relative
            if not runtime_path.exists():
                raise ValueError(f"{asset_id} payload is missing: {runtime_relative}")
            probe_name = str(closure.get("probe") or "")
            loader = loaders.get(probe_name)
            if loader is None:
                raise ValueError(f"missing installed model probe: {asset_id}:{probe_name}")
            if probe_name.startswith("transformers_") and not any(
                runtime_path.rglob("*.safetensors")
            ):
                raise ValueError(
                    f"{asset_id} requires installed safetensors weights; bin-only fallback is forbidden"
                )
            requested_device = (
                "cuda" if closure.get("hardware_profile") == "gpu" else "cpu"
            )
            started = time.perf_counter()
            try:
                result = loader(runtime_path, requested_device)
            except _NetworkBlocked as exc:
                raise ValueError(str(exc)) from exc
            if network_attempts:
                raise ValueError("network access blocked during offline model probe")
            if not isinstance(result, dict) or not isinstance(result.get("output"), dict):
                raise ValueError(f"installed model probe returned invalid evidence: {asset_id}")
            effective_device = str(result.get("device") or "")
            if requested_device == "cuda" and effective_device != "cuda":
                raise ValueError(
                    f"{asset_id} required cuda but reported {effective_device or 'unknown'}"
                )
            probes.append(
                {
                    "asset_id": asset_id,
                    "model_id": str(entry.get("repo_id") or asset_id),
                    "revision": str(entry.get("revision") or entry.get("source_revision") or ""),
                    "loader": probe_name,
                    "runtime_path": runtime_relative.as_posix(),
                    "requested_device": requested_device,
                    "effective_device": effective_device,
                    "output": result["output"],
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
    return {
        "schema_version": 2,
        "status": "ok",
        "profile": selected.get("profile"),
        "verified_asset_ids": [record["asset_id"] for record in probes],
        "probe_count": len(probes),
        "network_attempt_count": 0,
        "model_member_inventory_sha256": member_manifest.get("inventory_sha256"),
        "probes": probes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--receipt-path", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = verify(install_dir=args.install_dir, models_root=args.models_root)
        if args.receipt_path:
            args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
            args.receipt_path.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(receipt, sort_keys=True))
    except Exception as exc:
        print(f"profile payload verification failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
