from __future__ import annotations
import json
import os
import subprocess
import tempfile
from typing import Any, Dict


def run_conda_step(env_name: str, step_name: str, item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a step in an isolated conda env via the CLI runner.

    This mirrors scripts/ingest_*.ps1 behavior to keep per-step isolation while
    allowing orchestration from a ZenML pipeline.
    """
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
        env.setdefault("HF_HOME", "L:/models")
        env.setdefault("TORCH_HOME", "L:/models")
        env.setdefault("TRANSFORMERS_CACHE", "L:/models/transformers")
        env.setdefault("HF_DATASETS_CACHE", "L:/models/datasets")
        env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        
        cmd = [
            "conda",
            "run",
            "-n",
            env_name,
            "python",
            "-m",
            "zenml_project.cli.step_runner",
            "--step",
            step_name,
            "--in",
            in_path,
            "--out",
            out_path,
            "--cfg",
            cfg_path,
        ]
        if os.environ.get("GOODQ_VERBOSE", "").strip() in ("1", "true", "TRUE", "yes"):  # pass through verbosity
            cmd.append("--verbose")
        timeout_env = os.environ.get("GOODQ_STEP_TIMEOUT_MS")
        timeout_s = None
        try:
            if timeout_env:
                timeout_s = max(1.0, float(timeout_env) / 1000.0)
        except Exception:
            timeout_s = None
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_s, env=env)
        except subprocess.TimeoutExpired:
            return {"_error": f"{step_name} timeout in {env_name}", "advisory": "partial_results"}
        except subprocess.CalledProcessError as e:
            return {"_error": f"{step_name} failed in {env_name}: {e}"}
        if os.path.isfile(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    return {"_error": f"invalid JSON from {step_name}"}
        return {}
