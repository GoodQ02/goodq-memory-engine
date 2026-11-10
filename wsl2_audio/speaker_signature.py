"""Pinned ECAPA embedding contract shared by the standalone worker and KG."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
REVISION = "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
SPACE = f"ecapa:{REVISION}:concat16k-l2-v1"
DIMENSION = 192
THRESHOLD = 0.25
FILES = {
    "classifier.ckpt": "fd9e3634fe68bd0a427c95e354c0c677374f62b3f434e45b78599950d860d535",
    "embedding_model.ckpt": "0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2",
    "hyperparams.yaml": "6f78854fa04ba59e761437b76a2575d3aba5e5016de3e9b69f0c9a5077fb1a41",
    "label_encoder.ckpt": "e13c3a167bb4112685670ee896d20e2b565af16b3a4ceeaa8689fa4d22adb8b9",
    "mean_var_norm_emb.ckpt": "cd70225b05b37be64fc5a95e24395d804231d43f74b2e1e5a513db7b69b34c33",
}


def metadata() -> dict:
    return {"embedding_space": SPACE, "model_id": MODEL_ID,
            "model_revision": REVISION, "aggregation": "concat16k-l2-v1"}


def validate_metadata(signature: dict) -> str | None:
    """Untagged historical vectors remain legacy; tagged vectors must be exact."""
    if not any(key in signature for key in metadata()):
        return None
    if any(signature.get(key) != value for key, value in metadata().items()):
        raise ValueError("Unsupported or incomplete speaker embedding space")
    if signature.get("embedding_dim") != DIMENSION:
        raise ValueError("Invalid ECAPA speaker embedding dimension")
    return SPACE


def resolve_model(cache_dir: str | None = None) -> Path:
    """Resolve and seal-check local assets only; provisioning is never inference."""
    override = os.environ.get("GOODQ_ECAPA_MODEL_DIR")
    if override:
        root = Path(override)
    else:
        from huggingface_hub import snapshot_download
        cache_dir = cache_dir or os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_HUB_CACHE")
        root = Path(snapshot_download(MODEL_ID, revision=REVISION,
                                     cache_dir=cache_dir, local_files_only=True))
    for name, expected in FILES.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise OSError(f"ECAPA asset missing or hash mismatch: {name}; provision pinned {MODEL_ID}@{REVISION}")
    return root


def load_encoder(device: str, savedir: str, cache_dir: str | None = None):
    root = resolve_model(cache_dir)
    from speechbrain.inference.speaker import SpeakerRecognition
    return SpeakerRecognition.from_hparams(
        source=str(root), savedir=savedir,
        overrides={"pretrained_path": str(root)}, run_opts={"device": device},
    )
