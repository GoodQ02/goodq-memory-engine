from __future__ import annotations
import json
import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict

from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_models_root() -> str:
    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


class StepExecutionError(Exception):
    """Raised when a step fails to execute properly"""
    pass


def run_conda_step(env_name: str, step_name: str, item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a step in an isolated conda env via the CLI runner.

    This mirrors scripts/ingest_*.ps1 behavior to keep per-step isolation while
    allowing orchestration from higher-level runtime surfaces.
    
    Raises:
        StepExecutionError: If the step fails, times out, or produces invalid output
    """
    from .tool_paths import resolve_conda

    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "in.json")
        out_path = os.path.join(td, "out.json")
        cfg_path = os.path.join(td, "cfg.json")
        with open(in_path, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
        
        # Build environment variables for model caching
        env = os.environ.copy()
        models_root = _resolve_models_root()
        env["HF_HOME"] = models_root
        env["TORCH_HOME"] = models_root
        env.setdefault("TRANSFORMERS_CACHE", os.path.join(models_root, "transformers"))
        env.setdefault("HF_DATASETS_CACHE", os.path.join(models_root, "hf", "datasets"))
        env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        env.setdefault("PYTHONNOUSERSITE", "1")
        
        conda_exe = resolve_conda()
        cmd = [
            conda_exe,
            "run",
            "-n",
            env_name,
            "python",
            "-m",
            "cli.step_runner",
            "--step",
            step_name,
            "--in",
            in_path,
            "--out",
            out_path,
            "--cfg",
            cfg_path,
        ]
        if os.environ.get("GOODQ_VERBOSE", "").strip() in ("1", "true", "TRUE", "yes"):
            cmd.append("--verbose")
        
        timeout_env = os.environ.get("GOODQ_STEP_TIMEOUT_MS")
        timeout_s = None
        try:
            if timeout_env:
                timeout_s = max(1.0, float(timeout_env) / 1000.0)
        except Exception as e:
            timeout_s = None
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=timeout_s,
                cwd=str(REPO_ROOT),
                env=env,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
        except subprocess.TimeoutExpired as e:
            error_msg = f"[TIMER]  Mission timeout: {step_name} in {env_name} (exceeded {timeout_s}s)"
            logger.error(error_msg)
            raise StepExecutionError(error_msg) from e
        except subprocess.CalledProcessError as e:
            error_msg = f"[FAIL] Mission failed: {step_name} in {env_name} (exit code {e.returncode})"
            if e.stderr:
                error_msg += f"\nSTDERR: {e.stderr.strip()}"
            if e.stdout:
                error_msg += f"\nSTDOUT: {e.stdout.strip()}"
            logger.error(error_msg)
            raise StepExecutionError(error_msg) from e
        
        if not os.path.isfile(out_path):
            error_msg = f"[FAIL] Mission failed: {step_name} produced no output file"
            logger.error(error_msg)
            raise StepExecutionError(error_msg)
        
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                result_data = json.load(f)
        except json.JSONDecodeError as e:
            error_msg = f"[FAIL] Mission failed: {step_name} produced invalid JSON"
            logger.error(error_msg)
            raise StepExecutionError(error_msg) from e
        
        # Check for error markers in result
        if isinstance(result_data, dict) and "_error" in result_data:
            error_msg = f"[FAIL] Mission failed: {step_name} returned error: {result_data['_error']}"
            logger.error(error_msg)
            raise StepExecutionError(error_msg)
        
        logger.debug(f"[SYMBOL] Mission complete: {step_name}")
        return result_data
