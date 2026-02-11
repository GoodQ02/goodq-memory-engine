from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional


_PROFILE_BASELINE = "BASELINE"
_PROFILE_GPU_ENHANCED = "GPU_ENHANCED"
_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}
_LOGGED_CONTEXTS: set[str] = set()


def _normalize_profile(raw: Optional[str]) -> str:
    value = (raw or "").strip().upper()
    if value in {_PROFILE_BASELINE, _PROFILE_GPU_ENHANCED}:
        return value
    return ""


def _parse_bool_env(name: str) -> bool:
    return (os.getenv(name, "").strip().lower() in _TRUTHY)


def _parse_optional_bool(raw: Optional[str]) -> Optional[bool]:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    return None


def get_host_profile() -> str:
    return _normalize_profile(os.getenv("GOODQ_HOST_PROFILE"))


def is_baseline() -> bool:
    return get_host_profile() == _PROFILE_BASELINE


def is_gpu_enhanced() -> bool:
    return get_host_profile() == _PROFILE_GPU_ENHANCED


def require_gpu() -> bool:
    return _parse_bool_env("GOODQ_REQUIRE_GPU")


def require_wsl_audio() -> bool:
    return _parse_bool_env("GOODQ_REQUIRE_WSL_AUDIO")


def gpu_auto_config_enabled() -> bool:
    if is_baseline():
        return False
    return os.getenv("GOODQ_NO_AUTO_GPU") != "1"


def wsl_audio_auto_enabled() -> bool:
    return not is_baseline()


def resolve_wsl_gpu_config(gpu_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize WSL audio GPU config according to host profile semantics.
    Unset profile and GPU_ENHANCED preserve existing behavior.
    BASELINE defaults to CPU/int8 with mixed precision disabled unless overridden via env.
    """
    resolved: Dict[str, Any] = dict(gpu_cfg or {})
    if not is_baseline():
        return resolved

    device_override = os.getenv("GOODQ_WSL_AUDIO_DEVICE")
    compute_override = os.getenv("GOODQ_WSL_AUDIO_COMPUTE_TYPE")
    mixed_override = _parse_optional_bool(os.getenv("GOODQ_WSL_AUDIO_MIXED_PRECISION"))

    resolved["device"] = (device_override or "cpu").strip().lower()
    if compute_override:
        resolved["compute_type"] = compute_override.strip().lower()
    else:
        resolved["compute_type"] = "int8"
    resolved["mixed_precision"] = False if mixed_override is None else mixed_override
    return resolved


def log_runtime_profile_state(
    logger: logging.Logger,
    *,
    context: str,
    gpu_enabled: Optional[bool] = None,
    wsl_enabled: Optional[bool] = None,
) -> None:
    if context in _LOGGED_CONTEXTS:
        return
    _LOGGED_CONTEXTS.add(context)

    logger.info(
        "[PROFILE] context=%s profile=%s gpu_auto=%s wsl_default=%s require_gpu=%s require_wsl_audio=%s gpu_enabled=%s wsl_enabled=%s",
        context,
        get_host_profile() or "UNSET",
        gpu_auto_config_enabled(),
        wsl_audio_auto_enabled(),
        require_gpu(),
        require_wsl_audio(),
        gpu_enabled if gpu_enabled is not None else "n/a",
        wsl_enabled if wsl_enabled is not None else "n/a",
    )

