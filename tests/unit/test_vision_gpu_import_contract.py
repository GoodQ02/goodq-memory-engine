from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "steps.image_caption.step",
        "steps.object_detect.step",
        "steps.face_embed.step",
        "steps.image_embed_clip.step",
        "steps.image_embed_dino.step",
    ],
)
def test_vision_steps_use_scripts_gpu_config(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.setup_step_gpu.__module__ == "scripts.gpu_config"
    assert module.GPUManager.__module__ == "scripts.gpu_config"


def test_scripts_gpu_config_preserves_image_step_budgets(monkeypatch) -> None:
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(cudnn=SimpleNamespace(benchmark=False)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    gpu_config = importlib.reload(importlib.import_module("scripts.gpu_config"))

    caption = gpu_config.setup_step_gpu("image_caption")
    dino = gpu_config.setup_step_gpu("image_embed_dino")
    clip = gpu_config.setup_step_gpu("image_embed_clip")

    assert caption["env_name"] == "goodq_image_caption"
    assert caption["memory_fraction"] == 0.20
    assert dino["env_name"] == "goodq_image_caption"
    assert dino["memory_fraction"] == 0.25
    assert clip["env_name"] == "goodq_image_caption"
    assert clip["memory_fraction"] == 0.25
