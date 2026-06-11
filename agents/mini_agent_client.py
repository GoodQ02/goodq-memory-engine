"""
MiniAgentClient - Secure policy-gated wrapper client for GoodQ4All agents.
Integrates goodq_mini_agent checks with the unified codebase LLMClient.
"""

from __future__ import annotations
import os
import sys
import uuid
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Setup dynamic home root for the agent trace logs
REPO_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("GOODQ_MINI_AGENT_HOME", str(REPO_ROOT / ".goodq-mini-agent"))

# Codebase configuration and client imports
from steps.common.config_loader import load_configs
from steps.common.llm_model_factory import build_llm_models
from lib.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Explicit tool safety classification lists for fallback gating
READ_ONLY_ALLOW_ON_AGENT_FAILURE = {
    "qdrant_query",
    "faiss_search",
    "status_read",
    "manifest_read",
    "timeline_read",
    "memory_search",
}

MUTATING_DENY_ON_AGENT_FAILURE = {
    "home_assistant_call_service",
    "qdrant_upsert",
    "faiss_write",
    "kg_write",
    "config_write",
    "file_delete",
    "file_move",
    "run_ingestion",
    "watchdog_trigger",
    "process_start",
    "process_stop",
}

# Module-level deferred bootstrapping of the policy engine package
_DEFAULT_AGENT_AVAILABLE = False
_DEFAULT_LAST_ERROR_TYPE: Optional[str] = None
_DEFAULT_LAST_ERROR_MESSAGE: Optional[str] = None
_DEFAULT_RUNNER = None
_DEFAULT_ASSETS_DIR: Optional[Path] = None


def _bootstrap_module_layer() -> None:
    global _DEFAULT_AGENT_AVAILABLE, _DEFAULT_LAST_ERROR_TYPE, _DEFAULT_LAST_ERROR_MESSAGE, _DEFAULT_RUNNER, _DEFAULT_ASSETS_DIR
    try:
        # 1. Attempt package imports
        import goodq_mini_agent.paths
        import goodq_mini_agent.stack_runner
        
        # 2. Check if we already monkeypatched to prevent nested wrapping
        if not getattr(goodq_mini_agent.paths, "_goodq_monkeypatched", False):
            original_assets_dir = goodq_mini_agent.paths.ASSETS_DIR
            goodq_mini_agent.paths.ASSETS_DIR = Path(__file__).resolve().parent / "stack"
            goodq_mini_agent.paths.assets_script = lambda name: original_assets_dir / "scripts" / name
            goodq_mini_agent.paths._goodq_monkeypatched = True
            
        _DEFAULT_RUNNER = goodq_mini_agent.stack_runner
        _DEFAULT_ASSETS_DIR = goodq_mini_agent.paths.ASSETS_DIR
        _DEFAULT_AGENT_AVAILABLE = True
        logger.info("MiniAgentClient module successfully bootstrapped goodq_mini_agent stack runner")
    except Exception as e:
        _DEFAULT_AGENT_AVAILABLE = False
        _DEFAULT_LAST_ERROR_TYPE = type(e).__name__
        _DEFAULT_LAST_ERROR_MESSAGE = str(e)
        logger.warning(
            f"MiniAgentClient module could not bootstrap goodq_mini_agent on import. "
            f"Fallback policy active. Details: {_DEFAULT_LAST_ERROR_TYPE}: {_DEFAULT_LAST_ERROR_MESSAGE}"
        )


# Run bootstrap immediately on import
_bootstrap_module_layer()


class MiniAgentClient:
    """
    A policy-gated client wrapping LLM invocations and tool execution in GoodQ4All.

    Execution Mode (GOODQ_AGENT_EXECUTION_MODE):
      Default: in-process for speed and simplicity. Use subprocess for stronger
      isolation during hardening or release validation.
    """
    
    def __init__(self, profile: str = "safe", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the client.
        
        Args:
            profile: "safe" or "offline" (determines policy strictness)
            config: Optional config dictionary (falls back to load_configs({}))

        Note on execution mode configuration:
            Can be configured via environment variable `GOODQ_AGENT_EXECUTION_MODE`
            or config settings `agent.execution_mode`. Allowed values are:
            - `in_process`: runs within the current process context (default).
            - `subprocess`: executes validation checks via the `goodq` CLI wrapper.
        """
        self.profile = profile
        self.config = config or load_configs({})
        
        # Retrieve execution mode config setting: 'in_process' or 'subprocess'
        self.execution_mode = os.environ.get(
            "GOODQ_AGENT_EXECUTION_MODE",
            self.config.get("agent", {}).get("execution_mode", "in_process")
        ).lower()
        if self.execution_mode not in ("in_process", "subprocess"):
            self.execution_mode = "in_process"
            
        # Bind status from module-level bootstrap
        self.agent_available = _DEFAULT_AGENT_AVAILABLE
        self.last_error_type = _DEFAULT_LAST_ERROR_TYPE
        self.last_error_message = _DEFAULT_LAST_ERROR_MESSAGE
        self._runner = _DEFAULT_RUNNER
        self._assets_dir = _DEFAULT_ASSETS_DIR
        
        self.llm_client: Optional[LLMClient] = None
        self._init_llm_client()
        
    def _init_llm_client(self) -> None:
        """Initialize the unified LLM client using codebase endpoints."""
        try:
            models = build_llm_models(self.config)
            llm_cfg = self.config.get("llm", {}) or {}
            self.llm_client = LLMClient(
                models=models,
                health_check_interval=int(llm_cfg.get("health_check_interval", 60)),
                max_retries=int(llm_cfg.get("max_retries", 3)),
                timeout=int(llm_cfg.get("timeout", 30)),
                cache_ttl=int(llm_cfg.get("cache_ttl", 300)),
                enable_health_checks=bool(llm_cfg.get("enable_health_checks", False))
            )
            logger.info("MiniAgentClient successfully bound LLMClient")
        except Exception as e:
            logger.warning("MiniAgentClient starting without LLMClient: %s", e)
            self.llm_client = None

    def _offline_fallback_validation(
        self,
        task: Dict[str, Any],
        tool_name: str,
        error_exc: Optional[Exception] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Deterministic offline fallback policy.
        Allows read-only actions, blocks mutating actions, and formats a safe result envelope.
        """
        request_id = task.get("request_id", f"task-{uuid.uuid4().hex[:8]}")
        
        # Log error traceback safely if an exception occurred, but do not return it in the envelope
        if error_exc:
            logger.error(
                f"Agent layer encountered a runtime exception during validation for tool '{tool_name}'. "
                f"Invoking offline fallback policy.",
                exc_info=True
            )
            
        # Determine safety based on tool safety lists
        if not tool_name:
            # Empty tool or prompt-only validation: allow by default in fallback mode
            allowed = True
            status = "ok"
            errors = []
            rc = 0
        elif tool_name in READ_ONLY_ALLOW_ON_AGENT_FAILURE:
            allowed = True
            status = "ok"
            errors = []
            rc = 0
        else:
            # Deny by default for mutating actions or any undeclared actions
            allowed = False
            status = "error"
            errors = [{
                "code": "agent_offline_mutation_blocked",
                "message": f"Tool '{tool_name}' blocked under offline fallback policy (agent layer unavailable)."
            }]
            rc = 1
            
        envelope = {
            "request_id": request_id,
            "profile": self.profile,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "result": {
                "allowed": allowed,
                "offline_fallback_active": True
            },
            "events": [{
                "ts": datetime.utcnow().isoformat() + "Z",
                "kind": "offline_fallback",
                "tool": tool_name,
                "allowed": allowed
            }],
            "errors": errors,
            "artifacts": []
        }
        return envelope, rc

    def _validate_action_subprocess(
        self,
        task: Dict[str, Any],
        confirm: bool,
        confirmation_token: str,
        contract_path: Path,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Runs policy check validation in an isolated subprocess calling the `goodq` CLI.
        """
        import tempfile
        import subprocess
        import json
        
        # Write task to a temp JSON file
        fd, temp_path_str = tempfile.mkstemp(suffix=".json", prefix="gq_task_")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(task, f, ensure_ascii=False)
            
            cmd = [
                sys.executable,
                "-m", "goodq_mini_agent.cli",
                "run",
                "--profile", self.profile,
                "--input", temp_path_str,
                "--contract", str(contract_path)
            ]
            if confirm:
                cmd.append("--confirm")
            if confirmation_token:
                cmd.extend(["--confirmation-token", confirmation_token])
                
            # Execute subprocess
            cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if cp.returncode not in (0, 1, 2, 3) or not cp.stdout.strip():
                # Subprocess returned unexpected exit code or empty stdout: treat as failure and trigger fallback
                raise RuntimeError(
                    f"Subprocess agent execution failed (exit code {cp.returncode}). stderr: {cp.stderr.strip()}"
                )
                
            envelope = json.loads(cp.stdout)
            return envelope, cp.returncode
            
        except Exception as e:
            return self._offline_fallback_validation(task, task.get("context", {}).get("tool_name", ""), error_exc=e)
        finally:
            # Clean up temp file
            try:
                os.remove(temp_path_str)
            except Exception:
                pass

    def validate_action(
        self,
        prompt: str,
        mode: str = "research",
        tool_name: str = "",
        tool_args: Optional[Dict[str, Any]] = None,
        confirm: bool = False,
        confirmation_token: str = "",
        context_overrides: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Runs policy check validations for a prompt and a proposed tool execution.
        
        Returns:
            Tuple of (run_envelope dict, return_code int)
        """
        request_id = f"task-{uuid.uuid4().hex[:8]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Build base context conforming to validation schemas
        context = {
            "risk_tier": "low" if mode == "research" else "medium",
            "task_type": "research" if mode == "research" else ("code" if mode == "coding" else "ops"),
            "intents": "research" if mode == "research" else "coding,verification",
            "estimated_steps": 2,
            "requires_tools": bool(tool_name),
            "requires_external_integration": False,
            "simulate_workers": True,  # Keep worker commands simulated by default
            "tool_name": tool_name,
            "tool_args": tool_args or {},
            "proposed_action": tool_name,
            "action_source": "agent_call",
        }
        
        if context_overrides:
            context.update(context_overrides)
            
        task = {
            "request_id": request_id,
            "mode": mode,
            "prompt": prompt,
            "confirm": confirm,
            "context": context,
        }
        
        if not self.agent_available:
            return self._offline_fallback_validation(task, tool_name)
            
        contract_filename = "goodq-coding-agent.contract.json" if mode == "coding" else "goodq-o2-local.contract.json"
        contract_path = self._assets_dir / "contracts" / contract_filename
        
        try:
            if self.execution_mode == "subprocess":
                return self._validate_action_subprocess(task, confirm, confirmation_token, contract_path)
            
            envelope, rc = self._runner.run_task(
                profile=self.profile,
                task=task,
                confirm_flag=confirm,
                confirmation_token=confirmation_token,
                contract_override=str(contract_path),
            )
            return envelope, rc
        except Exception as e:
            return self._offline_fallback_validation(task, tool_name, error_exc=e)

    def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        prompt: str = "Execute tool",
        mode: str = "research",
        confirm: bool = False,
        confirmation_token: str = "",
    ) -> Tuple[Dict[str, Any], int]:
        """
        Policy-gates and executes a native Python tool implementation.
        
        Returns:
            Tuple of (result_envelope dict, return_code int)
        """
        started_at = datetime.utcnow().isoformat() + "Z"
        start_time = time.monotonic()
        
        # 1. Run policy check
        envelope, rc = self.validate_action(
            prompt=prompt,
            mode=mode,
            tool_name=tool_name,
            tool_args=tool_args,
            confirm=confirm,
            confirmation_token=confirmation_token
        )
        
        if rc != 0:
            # Rejections or confirmation requests are returned directly
            return envelope, rc
            
        # 2. Route and execute tool logic
        tool_result: Dict[str, Any] = {}
        try:
            if tool_name == "qdrant_query":
                tool_result = self._execute_qdrant_query(tool_args)
            elif tool_name == "qdrant_upsert":
                tool_result = self._execute_qdrant_upsert(tool_args)
            elif tool_name == "faiss_search":
                tool_result = self._execute_faiss_search(tool_args)
            elif tool_name == "llm_chat_local":
                tool_result = self._execute_llm_chat_local(tool_args)
            elif tool_name == "home_assistant_get_state":
                tool_result = self._execute_home_assistant_get_state(tool_args)
            elif tool_name == "home_assistant_call_service":
                tool_result = self._execute_home_assistant_call_service(tool_args)
            else:
                raise ValueError(f"No native handler for tool: {tool_name}")
            
            status = "success"
            error_msg = None
        except Exception as e:
            status = "fatal_error"
            error_msg = str(e)
            logger.error(f"Execution of tool {tool_name} failed: {e}", exc_info=True)
            
        completed_at = datetime.utcnow().isoformat() + "Z"
        duration_ms = int((time.monotonic() - start_time) * 1000)
        
        # 3. Construct result envelope matching tool-result-v1.schema.json
        result_envelope: Dict[str, Any] = {
            "request_id": envelope.get("request_id"),
            "tool_name": tool_name,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "side_effect_report": {
                "mutated": tool_name in ("qdrant_upsert", "home_assistant_call_service"),
                "targets": [tool_name]
            }
        }
        
        if status == "success":
            result_envelope["output"] = tool_result
        else:
            result_envelope["error"] = {
                "code": "execution_failed",
                "message": error_msg or "Tool execution error"
            }
            
        return result_envelope, 0 if status == "success" else 1

    def _execute_qdrant_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from steps.common.qdrant_client import build_qdrant_client
        collection = args.get("collection", "text").lower()
        key = "text"
        if "audio" in collection:
            key = "audio"
        elif "clip" in collection:
            key = "clip"
        elif "dino" in collection:
            key = "dino"
            
        vector = args["query_vector"]
        top_k = args.get("top_k", 5)
        
        q_client = build_qdrant_client(self.config, dim=len(vector), key=key)
        if not q_client:
            raise RuntimeError("Qdrant client could not be built from config")
            
        hits = q_client.query(vector, top_k=top_k)
        return {"matches": hits}

    def _execute_qdrant_upsert(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from steps.common.qdrant_client import build_qdrant_client
        points = args.get("points", [])
        if not points:
            return {"written": 0}
            
        dim = 384
        if "vector" in points[0]:
            dim = len(points[0]["vector"])
            
        collection = args.get("collection", "text").lower()
        key = "text"
        if "audio" in collection:
            key = "audio"
        elif "clip" in collection:
            key = "clip"
        elif "dino" in collection:
            key = "dino"
            
        q_client = build_qdrant_client(self.config, dim=dim, key=key)
        if not q_client:
            raise RuntimeError("Qdrant client could not be built from config")
            
        success = q_client.upsert(points)
        return {"written": len(points) if success else 0}

    def _execute_faiss_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        import faiss
        import numpy as np
        from steps.common.faiss_utils import FaissLock
        
        index_path = args["index_path"]
        query_vector = args["query_vector"]
        top_k = args.get("top_k", 5)
        
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found: {index_path}")
            
        with FaissLock(index_path):
            idx = faiss.read_index(str(index_path))
            vec_np = np.array([query_vector], dtype="float32")
            D, I = idx.search(vec_np, k=top_k)
            
        matches = []
        for score, fid in zip(D[0], I[0]):
            matches.append({
                "id": int(fid),
                "score": float(score)
            })
        return {"matches": matches}

    def _execute_llm_chat_local(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self.llm_client:
            raise RuntimeError("LLMClient is not initialized")
            
        res = self.llm_client.chat(
            messages=args["messages"],
            temperature=float(args.get("temperature", 0.7)),
            max_tokens=int(args.get("max_tokens", 2048))
        )
        content = res["choices"][0]["message"]["content"]
        return {"content": content}

    def _execute_home_assistant_get_state(self, args: Dict[str, Any]) -> Dict[str, Any]:
        entity_ids = args.get("entity_ids", [])
        states = [{"entity_id": eid, "state": "off"} for eid in entity_ids]
        return {"states": states}

    def _execute_home_assistant_call_service(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True}
