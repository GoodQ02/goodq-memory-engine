from __future__ import annotations

import importlib

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
