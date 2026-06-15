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

import threading
from contextlib import contextmanager

class ReentrantFileLock:
    def __init__(self, lock_file_path: Path):
        self.lock_file_path = lock_file_path
        self._local = threading.local()

    @contextmanager
    def lock(self):
        if not hasattr(self._local, 'depth'):
            self._local.depth = 0
            self._local.fd = None
            
        if self._local.depth > 0:
            self._local.depth += 1
            try:
                yield
            finally:
                self._local.depth -= 1
            return

        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.time()
        timeout = 5.0
        fd = None
        while True:
            try:
                fd = open(self.lock_file_path, "a")
                if sys.platform == "win32":
                    import msvcrt
                    fd.seek(0)
                    msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (IOError, OSError, PermissionError) as e:
                if fd is not None:
                    try:
                        fd.close()
                    except Exception:
                        pass
                    fd = None
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Timeout acquiring lock on {self.lock_file_path}: {e}")
                time.sleep(0.01)
                
        self._local.fd = fd
        self._local.depth = 1
        try:
            yield
        finally:
            self._local.depth -= 1
            if self._local.depth == 0:
                try:
                    if sys.platform == "win32":
                        import msvcrt
                        self._local.fd.seek(0)
                        msvcrt.locking(self._local.fd.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._local.fd.fileno(), fcntl.LOCK_UN)
                finally:
                    self._local.fd.close()
                    self._local.fd = None

logger = logging.getLogger(__name__)

# Explicit tool safety classification lists for fallback gating
READ_ONLY_ALLOW_ON_AGENT_FAILURE = {
    "qdrant_query",
    "faiss_search",
    "status_read",
    "manifest_read",
    "timeline_read",
    "memory_search",
    "validate_ucf_epoch",
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
    "promote_ucf_to_memory",
    "validate_ucf_frames",
}

def _load_ucf_ledger() -> Any:
    """Dynamically imports ucf_ledger from the scripts directory."""
    import importlib.util
    import sys
    from pathlib import Path
    
    repo_root = Path(__file__).resolve().parent.parent
    ucf_ledger_path = repo_root / 'scripts' / 'ucf' / 'ucf_ledger.py'
    
    if not ucf_ledger_path.exists():
        raise FileNotFoundError(f"ucf_ledger.py not found at {ucf_ledger_path}")
        
    spec = importlib.util.spec_from_file_location("ucf_ledger", str(ucf_ledger_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create spec for {ucf_ledger_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ucf_ledger"] = module
    spec.loader.exec_module(module)
    return module

class UCFValidationError(Exception):
    def __init__(self, details: List[str]):
        self.details = details
        super().__init__("Validation failed.")

class OrphanVectorError(Exception):
    def __init__(self, vector_key: str):
        self.vector_key = vector_key
        super().__init__(f"Orphan vector {vector_key} blocked from injection.")

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
        self.profile = profile.lower() if profile else "safe"
        if self.profile not in ("safe", "offline", "unrestricted"):
            self.profile = "safe"
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

    def sanitize_envelope(self, data: Any) -> Any:
        import re
        if isinstance(data, dict):
            return {k: self.sanitize_envelope(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_envelope(v) for v in data]
        elif isinstance(data, str):
            # 1. Drive letter pattern supporting spaces
            drive_pat = r'[a-zA-Z]:[\\/](?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*[\\/])|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'
            # 2. UNC pattern supporting spaces
            unc_pat = r'\\\\(?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*[\\/])|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'
            # 3. WSL pattern supporting spaces
            wsl_pat = r'/mnt/[a-zA-Z]/(?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*/)|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'
            # 4. Linux standard path pattern supporting spaces
            linux_pat = r'/(?:home|tmp|usr|var|etc|opt|srv|root)/(?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*/)|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'

            res = data
            def replace_drive(match):
                p = match.group(0)
                basename = os.path.basename(p.replace('\\', '/'))
                return f"relative/{basename}"
                
            res = re.sub(drive_pat, replace_drive, res)
            res = re.sub(unc_pat, replace_drive, res)
            res = re.sub(wsl_pat, replace_drive, res)
            res = re.sub(linux_pat, replace_drive, res)
            return res
        return data

    @contextmanager
    def _lock_token_store(self):
        home_dir = Path(os.environ.get("GOODQ_MINI_AGENT_HOME", str(REPO_ROOT / ".goodq-mini-agent")))
        lock_file_path = home_dir / "confirmation_tokens.lock"
        if not hasattr(self, "_token_store_lock"):
            self._token_store_lock = ReentrantFileLock(lock_file_path)
        with self._token_store_lock.lock():
            yield

    def _load_tokens(self) -> Dict[str, Any]:
        with self._lock_token_store():
            import json
            home_dir = Path(os.environ.get("GOODQ_MINI_AGENT_HOME", str(REPO_ROOT / ".goodq-mini-agent")))
            token_store_path = home_dir / "confirmation_tokens.json"
            if token_store_path.exists():
                try:
                    with open(token_store_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return {}
            return {}

    def _save_tokens(self, tokens: Dict[str, Any]) -> None:
        with self._lock_token_store():
            import json
            home_dir = Path(os.environ.get("GOODQ_MINI_AGENT_HOME", str(REPO_ROOT / ".goodq-mini-agent")))
            token_store_path = home_dir / "confirmation_tokens.json"
            home_dir.mkdir(parents=True, exist_ok=True)
            try:
                with open(token_store_path, "w", encoding="utf-8") as f:
                    json.dump(tokens, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to save tokens: {e}")

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
        return self.sanitize_envelope(envelope), rc

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
            return self.sanitize_envelope(envelope), cp.returncode
            
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
        request_id = f"task-{uuid.uuid4().hex[:8]}"
        tool_args = tool_args or {}
        
        # 1. Confirmation token validation if provided
        NATIVELY_GATED_TOOLS = {"promote_ucf_to_memory", "validate_ucf_frames"}
        if confirmation_token:
            with self._lock_token_store():
                tokens = self._load_tokens()
                if confirmation_token not in tokens and tool_name not in NATIVELY_GATED_TOOLS:
                    # Non-native token for a non-native tool: delegate to subprocess
                    pass
                else:
                    if confirmation_token not in tokens:
                        envelope = {
                            "request_id": request_id,
                            "profile": self.profile,
                            "status": "error",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "result": {"allowed": False},
                            "errors": [{"code": "invalid_confirmation_token", "message": "Invalid confirmation token."}],
                        }
                        return self.sanitize_envelope(envelope), 1
                    tok_info = tokens[confirmation_token]
                    if tok_info.get("operation") != tool_name:
                        envelope = {
                            "request_id": request_id,
                            "profile": self.profile,
                            "status": "error",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "result": {"allowed": False},
                            "errors": [{"code": "token_operation_mismatch", "message": "Token was not issued for this operation."}],
                        }
                        return self.sanitize_envelope(envelope), 1
                    if tok_info.get("used"):
                        envelope = {
                            "request_id": request_id,
                            "profile": self.profile,
                            "status": "error",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "result": {"allowed": False},
                            "errors": [{"code": "token_already_used", "message": "Token has already been used."}],
                        }
                        return self.sanitize_envelope(envelope), 1

                    # Check expiration
                    expired = False
                    if tool_args.get("simulate_expired_token") or tok_info.get("tool_args", {}).get("simulate_expired_token"):
                        expired = True
                    else:
                        ts_str = tok_info.get("timestamp")
                        if ts_str:
                            try:
                                if ts_str.endswith("Z"):
                                    ts_str = ts_str[:-1]
                                t_val = datetime.fromisoformat(ts_str)
                                if t_val.tzinfo is not None:
                                    from datetime import timezone
                                    t_val = t_val.astimezone(timezone.utc).replace(tzinfo=None)
                                if (datetime.utcnow() - t_val).total_seconds() > 600:
                                    expired = True
                            except Exception:
                                pass
                    if expired:
                        envelope = {
                            "request_id": request_id,
                            "profile": self.profile,
                            "status": "error",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "result": {"allowed": False},
                            "errors": [{"code": "token_expired", "message": "Confirmation token expired."}],
                        }
                        return self.sanitize_envelope(envelope), 1

        # 2. Profile Routing (Offline Profile check)
        if self.profile == "offline":
            mutating_ops = MUTATING_DENY_ON_AGENT_FAILURE
            if tool_name in mutating_ops:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False},
                    "errors": [{"code": "offline_blocked", "message": f"Operation '{tool_name}' is blocked in offline profile."}],
                }
                return self.sanitize_envelope(envelope), 1

        # 3. Agent Availability / Fallback (Gated Execution)
        if not self.agent_available:
            if tool_name in READ_ONLY_ALLOW_ON_AGENT_FAILURE or tool_name == "validate_ucf_epoch":
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "ok",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": True, "offline_fallback_active": True},
                    "errors": [],
                }
                return self.sanitize_envelope(envelope), 0
            else:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False, "offline_fallback_active": True},
                    "errors": [{"code": "agent_offline_mutation_blocked", "message": f"Tool '{tool_name}' blocked under offline fallback policy."}],
                }
                return self.sanitize_envelope(envelope), 1

        # 4. Human-in-the-Loop Gating Validation
        if tool_name in ("promote_ucf_to_memory", "validate_ucf_frames"):
            if not confirm:
                token = f"token-{tool_name.replace('_', '-')}-{uuid.uuid4().hex[:8]}"
                with self._lock_token_store():
                    tokens = self._load_tokens()
                    tokens[token] = {
                        "operation": tool_name,
                        "timestamp": datetime.utcnow().isoformat(),
                        "used": False,
                        "tool_args": tool_args or {}
                    }
                    self._save_tokens(tokens)
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "needs_confirmation",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False, "confirmation_token": token},
                    "errors": [{"code": "mutability_requires_confirmation", "message": f"{tool_name} requires human confirmation."}],
                }
                return self.sanitize_envelope(envelope), 3
            else:
                # Must have validation token passed (validated above)
                if not confirmation_token:
                    envelope = {
                        "request_id": request_id,
                        "profile": self.profile,
                        "status": "error",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "result": {"allowed": False},
                        "errors": [{"code": "invalid_confirmation_token", "message": "Invalid confirmation token."}],
                    }
                    return self.sanitize_envelope(envelope), 1

        # 5. Native tool validation bypass
        if tool_name in ("run_ingestion", "promote_ucf_to_memory", "validate_ucf_frames", "file_delete", "validate_ucf_epoch"):
            envelope = {
                "request_id": request_id,
                "profile": self.profile,
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "result": {"allowed": True},
                "errors": [],
            }
            return self.sanitize_envelope(envelope), 0

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
            "tool_args": tool_args,
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
            return self.sanitize_envelope(envelope), rc
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
            
        # Consume token atomically under lock if confirm is True
        if confirm and confirmation_token:
            with self._lock_token_store():
                tokens = self._load_tokens()
                if confirmation_token in tokens:
                    tokens[confirmation_token]["used"] = True
                    self._save_tokens(tokens)
            
        # 2. Route and execute tool logic
        tool_result: Dict[str, Any] = {}
        status = "success"
        error_msg = None
        errors_list = []
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
            elif tool_name == "run_ingestion":
                tool_result = self._execute_run_ingestion(tool_args)
            elif tool_name == "validate_ucf_epoch":
                tool_result = self._execute_validate_ucf_epoch(tool_args)
            elif tool_name == "promote_ucf_to_memory":
                tool_result = self._execute_promote_ucf_to_memory(tool_args)
            elif tool_name == "validate_ucf_frames":
                tool_result = self._execute_validate_ucf_frames(tool_args)
            elif tool_name == "file_delete":
                tool_result = self._execute_file_delete(tool_args)
            else:
                raise ValueError(f"No native handler for tool: {tool_name}")
        except UCFValidationError as e:
            status = "fatal_error"
            errors_list = [{"code": "ucf_validation_failed", "message": "Validation failed.", "details": e.details}]
            logger.error(f"Validation failed for tool {tool_name}: {e.details}")
        except OrphanVectorError as e:
            status = "error"
            errors_list = [{"code": "orphan_vector_blocked", "message": str(e)}]
            logger.error(f"Orphan vector blocked: {e}")
        except Exception as e:
            status = "fatal_error"
            errors_list = [{"code": "execution_failed", "message": str(e)}]
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
                "mutated": tool_name in ("qdrant_upsert", "home_assistant_call_service", "run_ingestion", "promote_ucf_to_memory", "validate_ucf_frames", "file_delete"),
                "targets": [tool_name]
            }
        }
        
        # Set artifacts
        if "absolute_path_artifacts" in tool_args:
            result_envelope["artifacts"] = tool_args["absolute_path_artifacts"]
        elif "artifacts" in tool_args:
            result_envelope["artifacts"] = tool_args["artifacts"]
        else:
            if tool_name == "file_delete":
                result_envelope["artifacts"] = [tool_args.get("path")]
            else:
                result_envelope["artifacts"] = []
                
        if status == "success":
            result_envelope["output"] = tool_result
        else:
            result_envelope["errors"] = errors_list
            # Also set deprecated 'error' field for backward compatibility
            result_envelope["error"] = errors_list[0] if errors_list else {"code": "execution_failed", "message": "Tool execution error"}
            
        return self.sanitize_envelope(result_envelope), 0 if status == "success" else 1

    def _get_ucf_db_path(self) -> Path:
        db_dir = self.config.get('paths', {}).get('db_dir')
        epoch_id = os.path.basename(db_dir) if db_dir else "default_epoch"
        data_root = os.getenv("GOODQ_DATA_ROOT") or self.config.get('paths', {}).get('data_root')
        if data_root:
            root_path = Path(data_root)
            if root_path.name == "GoodQ_Data":
                root_path = root_path.parent
            ucf_db_dir = root_path / 'epochs' / epoch_id / 'ucf'
        elif db_dir:
            ucf_db_dir = Path(db_dir) / 'ucf'
        else:
            ucf_db_dir = Path("epochs/default_epoch/ucf")
        ucf_db_dir.mkdir(parents=True, exist_ok=True)
        return ucf_db_dir / 'ucf_ledger.db'

    def _cleanup_backfilled_vectors(self, records: List[Dict[str, Any]], inserted_ids: List[int]) -> None:
        import requests
        import sqlite3
        qdrant_host = self.config.get("qdrant", {}).get("host", "http://127.0.0.1:6333")
        import uuid
        GOODQ_POINT_ID_NAMESPACE = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")
        
        for r in records:
            v_key = r.get("vector_key")
            v_backend = r.get("vector_backend")
            if v_key and v_backend == "qdrant":
                collection = r.get("vector_collection", "default")
                s = v_key.strip()
                hex_candidate = s.replace("-", "")
                if len(hex_candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in hex_candidate):
                    normalized_key = str(uuid.UUID(hex_candidate))
                elif s.isdigit():
                    normalized_key = s
                else:
                    normalized_key = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))
                
                url = f"{qdrant_host}/collections/{collection}/points/delete"
                try:
                    requests.post(url, json={"points": [normalized_key]}, timeout=5)
                except Exception as e:
                    logger.warning(f"Failed to delete Qdrant point {normalized_key} during rollback: {e}")

        # FAISS sidecar DBs cleanup
        clip_map_db = self.config.get("paths", {}).get("clip_id_map_db")
        dino_map_db = self.config.get("paths", {}).get("dino_id_map_db")
        clap_map_db = self.config.get("paths", {}).get("clap_id_map_db")
        
        for db_path, table_name in [
            (clip_map_db, "clip_id_map"),
            (dino_map_db, "dino_id_map"),
            (clap_map_db, "clap_id_map")
        ]:
            if db_path and Path(db_path).exists() and inserted_ids:
                try:
                    s_conn = sqlite3.connect(db_path)
                    placeholders = ",".join("?" for _ in inserted_ids)
                    s_conn.execute(f"DELETE FROM {table_name} WHERE ucf_frame_id IN ({placeholders})", tuple(inserted_ids))
                    s_conn.commit()
                    s_conn.close()
                except Exception as e:
                    logger.warning(f"Failed to clean up FAISS sidecar DB {table_name} during rollback: {e}")

    def _execute_run_ingestion(self, args: Dict[str, Any]) -> Dict[str, Any]:
        import sqlite3
        import requests
        
        records = args.get("ucf_records", [])
        validation_errors = []
        
        if args.get("simulate_validation_fail"):
            validation_errors.append("Simulated validation failure.")
            
        ucf_db_path = self._get_ucf_db_path()
        
        # Open connection to media_sources to check registered sources
        conn = sqlite3.connect(str(ucf_db_path))
        # Ensure schema is initialized
        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient
        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()
        
        for idx, r in enumerate(records):
            video_hash = r.get("video_hash")
            
            # Check registration in media_sources
            cursor = conn.execute("SELECT duration FROM media_sources WHERE video_hash = ?", (video_hash,))
            row = cursor.fetchone()
            if not row:
                validation_errors.append(f"Record {idx}: Unregistered media source {video_hash}.")
                duration = 0.0
            else:
                duration = row[0]
                
            if r.get("ucf_schema_version", "ucf.v0.1") != "ucf.v0.1":
                validation_errors.append(f"Record {idx}: Schema version mismatch.")
                
            t_start = r.get("t_start", 0.0)
            t_end = r.get("t_end", 0.0)
            if t_start < 0.0:
                validation_errors.append(f"Record {idx}: Negative t_start.")
            if t_end < t_start:
                validation_errors.append(f"Record {idx}: t_end before t_start.")
            elif row and t_end > duration + 0.05:
                validation_errors.append(f"Record {idx}: t_end exceeds duration.")
                
            payload = r.get("payload", {})
            for k, v in payload.items():
                if not isinstance(v, (str, int, float, bool, type(None))):
                    validation_errors.append(f"Record {idx}: Non-flat payload key {k}.")
                    
            spatial = r.get("spatial_region")
            if spatial is not None:
                if len(spatial) != 4:
                    validation_errors.append(f"Record {idx}: Spatial region must be 4 floats.")
                else:
                    for val in spatial:
                        if not (0.0 <= val <= 1.0):
                            validation_errors.append(f"Record {idx}: Bbox value {val} not normalized.")
                    if spatial[0] > spatial[2] or spatial[1] > spatial[3]:
                        validation_errors.append(f"Record {idx}: Bbox bounds invalid.")
                        
        conn.close()
        
        if validation_errors:
            raise UCFValidationError(validation_errors)
            
        # Log UCF frames
        inserted_ids = []
        try:
            for r in records:
                fid = client.log_frame(
                    video_hash=r.get("video_hash"),
                    epoch_id=r.get("epoch_id"),
                    run_id=r.get("run_id"),
                    t_start=r.get("t_start"),
                    t_end=r.get("t_end"),
                    modality=r.get("modality"),
                    worker_name=r.get("worker_name"),
                    model_tag=r.get("model_tag"),
                    confidence=r.get("confidence", 1.0),
                    spatial_region=r.get("spatial_region"),
                    spatial_space=r.get("spatial_space", "normalized_yxyx_top_left"),
                    vector_key=r.get("vector_key"),
                    vector_backend=r.get("vector_backend"),
                    vector_collection=r.get("vector_collection"),
                    vector_dim=r.get("vector_dim"),
                    vector_model_tag=r.get("vector_model_tag"),
                    source_artifact_id=r.get("source_artifact_id"),
                    raw_ref=r.get("raw_ref"),
                    payload=r.get("payload"),
                    promotion_status="staged"
                )
                inserted_ids.append(fid)
                
                # Backfill Qdrant / FAISS
                v_key = r.get("vector_key")
                v_backend = r.get("vector_backend")
                if v_key and v_backend:
                    if v_backend == "qdrant":
                        qdrant_host = self.config.get("qdrant", {}).get("host", "http://127.0.0.1:6333")
                        collection = r.get("vector_collection", "default")
                        import uuid
                        GOODQ_POINT_ID_NAMESPACE = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")
                        s = v_key.strip()
                        hex_candidate = s.replace("-", "")
                        if len(hex_candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in hex_candidate):
                            normalized_key = str(uuid.UUID(hex_candidate))
                        elif s.isdigit():
                            normalized_key = s
                        else:
                            normalized_key = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))
                            
                        url = f"{qdrant_host}/collections/{collection}/points/payload"
                        try:
                            requests.post(url, json={
                                "payload": {"ucf_frame_id": fid},
                                "points": [normalized_key]
                            }, timeout=5)
                        except Exception as e:
                            logger.warning(f"Could not backfill Qdrant point {normalized_key}: {e}")
                    elif v_backend == "faiss":
                        clip_map_db = self.config.get("paths", {}).get("clip_id_map_db")
                        dino_map_db = self.config.get("paths", {}).get("dino_id_map_db")
                        clap_map_db = self.config.get("paths", {}).get("clap_id_map_db")
                        if r.get("worker_name") == "image_embed_clip":
                            sidecar_db_path = clip_map_db
                            table_name = "clip_id_map"
                        elif r.get("worker_name") == "audio_embed_clap":
                            sidecar_db_path = clap_map_db
                            table_name = "clap_id_map"
                        else:
                            sidecar_db_path = dino_map_db
                            table_name = "dino_id_map"
                        if sidecar_db_path:
                            try:
                                Path(sidecar_db_path).parent.mkdir(parents=True, exist_ok=True)
                                s_conn = sqlite3.connect(sidecar_db_path)
                                # Check schema and drop if outdated
                                cursor = s_conn.execute(f"PRAGMA table_info({table_name})")
                                info = cursor.fetchall()
                                pk_cols = [row[1] for row in info if row[5] > 0]
                                if info and set(pk_cols) != {"video_hash", "faiss_id"}:
                                    s_conn.execute(f"DROP TABLE {table_name}")

                                s_conn.execute(f"""
                                    CREATE TABLE IF NOT EXISTS {table_name} (
                                        video_hash TEXT,
                                        faiss_id INTEGER,
                                        hash TEXT,
                                        source_path TEXT,
                                        epoch_id TEXT,
                                        scene_id TEXT,
                                        worker_name TEXT,
                                        vector_model_tag TEXT,
                                        modality TEXT,
                                        ucf_frame_id INTEGER,
                                        PRIMARY KEY (video_hash, faiss_id)
                                    )
                                """)
                                p_payload = r.get("payload", {})
                                faiss_id = p_payload.get("faiss_id")
                                if faiss_id is not None:
                                    cursor = s_conn.execute(f"UPDATE {table_name} SET ucf_frame_id = ? WHERE video_hash = ? AND faiss_id = ?", (fid, r.get("video_hash"), int(faiss_id)))
                                    if cursor.rowcount == 0:
                                        s_conn.execute(f"""
                                            INSERT INTO {table_name} (video_hash, faiss_id, hash, source_path, epoch_id, scene_id, worker_name, vector_model_tag, modality, ucf_frame_id)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (
                                            r.get("video_hash"),
                                            int(faiss_id),
                                            r.get("vector_key"),
                                            r.get("raw_ref", ""),
                                            r.get("epoch_id"),
                                            r.get("source_artifact_id"),
                                            r.get("worker_name"),
                                            r.get("model_tag"),
                                            r.get("modality"),
                                            fid
                                        ))
                                    s_conn.commit()
                                s_conn.close()
                            except Exception as e:
                                logger.warning(f"Could not backfill FAISS sidecar DB: {e}")
            client.close()
        except Exception as insert_err:
            try:
                self._cleanup_backfilled_vectors(records, inserted_ids)
            except Exception as clean_err:
                logger.warning(f"Failed to clean up backfilled vectors on insert error: {clean_err}")
            if inserted_ids:
                try:
                    client.delete_frames(inserted_ids)
                except Exception as del_err:
                    logger.warning(f"Failed to rollback inserted frames {inserted_ids}: {del_err}")
            client.close()
            raise insert_err
            
        # Run validate_ucf_epoch validation
        from scripts.ucf.validate_ucf_epoch import run_validation
        validation_failed = False
        val_errors = []
        try:
            val_rc = run_validation(mode="offline")
            if val_rc != 0:
                validation_failed = True
                val_errors.append("validate_ucf_epoch validator script returned non-zero exit code.")
        except Exception as ve:
            validation_failed = True
            val_errors.append(f"validate_ucf_epoch failed to execute: {ve}")
            
        if validation_failed:
            # Try reading report for details
            reports_dir = Path(self.config.get('paths', {}).get('reports_dir', REPO_ROOT / 'reports'))
            report_path = reports_dir / 'ucf_validation_report.json'
            details = []
            if report_path.exists():
                try:
                    with open(report_path, "r", encoding="utf-8") as f:
                        rep_data = json.load(f)
                        for cat_key, cat_val in rep_data.items():
                            if isinstance(cat_val, dict) and "errors" in cat_val:
                                details.extend(cat_val["errors"])
                except Exception:
                    pass
            if not details:
                details = val_errors
                
            # ROLLBACK
            try:
                self._cleanup_backfilled_vectors(records, inserted_ids)
            except Exception as clean_err:
                logger.warning(f"Failed to clean up backfilled vectors on validation failure: {clean_err}")
            if inserted_ids:
                try:
                    rollback_client = UCFLedgerClient(str(ucf_db_path))
                    try:
                        rollback_client.delete_frames(inserted_ids)
                    finally:
                        rollback_client.close()
                except Exception as del_err:
                    logger.warning(f"Failed to rollback inserted frames on validation failure {inserted_ids}: {del_err}")
            raise UCFValidationError(details)
            
        return {"ingested_count": len(records), "status": "staged_complete"}

    def _execute_validate_ucf_epoch(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.ucf.validate_ucf_epoch import run_validation
        validation_errors = []
        try:
            val_rc = run_validation(mode="offline")
            success = (val_rc == 0)
            if not success:
                reports_dir = Path(self.config.get('paths', {}).get('reports_dir', REPO_ROOT / 'reports'))
                report_path = reports_dir / 'ucf_validation_report.json'
                if report_path.exists():
                    try:
                        with open(report_path, "r", encoding="utf-8") as f:
                            rep_data = json.load(f)
                            for cat_key, cat_val in rep_data.items():
                                if isinstance(cat_val, dict) and "errors" in cat_val:
                                    validation_errors.extend(cat_val["errors"])
                    except Exception:
                        pass
                if not validation_errors:
                    validation_errors.append("Validator script returned non-zero exit code.")
        except Exception as e:
            success = False
            validation_errors.append(str(e))
            
        return {
            "success": success,
            "errors": validation_errors,
        }

    def _execute_validate_ucf_frames(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Transitions in-scope context frames from 'staged' to 'validated'.

        This is the required intermediate step between ingestion and promotion.
        Only frames in 'staged' status are updated; already-validated or promoted
        frames are untouched. The operation is idempotent.

        Expected lifecycle: staged -> [validate_ucf_frames] -> validated
                                   -> [promote_ucf_to_memory] -> promoted
        """
        ucf_db_path = self._get_ucf_db_path()
        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient
        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()
        video_hash = args.get("video_hash") or args.get("video_id")
        epoch_id = args.get("epoch_id")
        validated_count = client.mark_frames_validated(
            video_hash=video_hash,
            epoch_id=epoch_id,
        )
        client.close()
        return {"validated_count": validated_count, "status": "validated_complete"}

    def _execute_promote_ucf_to_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Promotes context frames from 'validated' to 'promoted'.

        Requires all in-scope frames to have already passed through 'validated'
        status (via validate_ucf_frames). Any frames still in 'staged' status
        will cause this call to return a blocked error — run validate_ucf_frames
        first.

        Expected lifecycle: staged -> validated -> [promote_ucf_to_memory] -> promoted
        """
        import sqlite3
        ucf_db_path = self._get_ucf_db_path()
        
        # Ensure schema is initialized
        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient
        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()
        client.close()
        
        conn = sqlite3.connect(str(ucf_db_path))
        
        attempted_vectors = args.get("vectors", [])
        video_hash = args.get("video_hash") or args.get("video_id")
        epoch_id = args.get("epoch_id")
        
        # Auto-resolve scope from validated records (staged is now an error state here)
        if not video_hash:
            cursor = conn.execute("SELECT DISTINCT video_hash FROM context_frames WHERE promotion_status = 'validated'")
            rows = cursor.fetchall()
            if len(rows) == 1:
                video_hash = rows[0][0]
        if not epoch_id:
            cursor = conn.execute("SELECT DISTINCT epoch_id FROM context_frames WHERE promotion_status = 'validated'")
            rows = cursor.fetchall()
            if len(rows) == 1:
                epoch_id = rows[0][0]

        # 0. Pre-check: block promotion if any in-scope frames are still staged (not validated).
        #    Staged frames indicate validate_ucf_frames has not yet been run.
        check_staged = "SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'"
        check_args: list = []
        if video_hash:
            check_staged += " AND video_hash = ?"
            check_args.append(video_hash)
        if epoch_id:
            check_staged += " AND epoch_id = ?"
            check_args.append(epoch_id)
        staged_count = conn.execute(check_staged, tuple(check_args)).fetchone()[0]
        if staged_count > 0:
            conn.close()
            return {
                "status": "blocked",
                "reason": "promotion_blocked_unvalidated_frames",
                "staged_count": staged_count,
                "message": (
                    f"Cannot promote: {staged_count} context frame(s) are still in "
                    "'staged' status. Run validate_ucf_frames (with confirmation) "
                    "before calling promote_ucf_to_memory."
                ),
            }

        # 1. Orphan vector check (scoped per epoch/video to prevent cross-video vector injections).
        #    Only validated and already-promoted vectors are considered legitimate.
        query = "SELECT vector_key FROM context_frames WHERE promotion_status IN ('validated', 'promoted')"
        query_args: list = []
        if video_hash:
            query += " AND video_hash = ?"
            query_args.append(video_hash)
        if epoch_id:
            query += " AND epoch_id = ?"
            query_args.append(epoch_id)
            
        cursor = conn.execute(query, tuple(query_args))
        valid_vector_keys = {row[0] for row in cursor.fetchall() if row[0]}
        
        for v_key in attempted_vectors:
            if v_key not in valid_vector_keys:
                conn.close()
                raise OrphanVectorError(v_key)

        # 2. Promote validated records (validated -> promoted, scoped per epoch/video).
        select_validated = "SELECT count(*) FROM context_frames WHERE promotion_status = 'validated'"
        update_validated = "UPDATE context_frames SET promotion_status = 'promoted' WHERE promotion_status = 'validated'"
        promote_args: list = []
        if video_hash:
            select_validated += " AND video_hash = ?"
            update_validated += " AND video_hash = ?"
            promote_args.append(video_hash)
        if epoch_id:
            select_validated += " AND epoch_id = ?"
            update_validated += " AND epoch_id = ?"
            promote_args.append(epoch_id)
            
        promoted_count = conn.execute(select_validated, tuple(promote_args)).fetchone()[0]
        conn.execute(update_validated, tuple(promote_args))
        conn.commit()
        conn.close()
        
        return {"promoted_count": promoted_count, "status": "promoted_complete"}

    def _execute_file_delete(self, args: Dict[str, Any]) -> Dict[str, Any]:
        target = args.get("path")
        if target:
            target_path = Path(target)
            exists = False
            try:
                exists = target_path.exists()
            except OSError as e:
                logger.warning(f"OS error checking existence of {target}: {e}")
            if exists:
                try:
                    if target_path.is_dir():
                        import shutil
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()
                except Exception as e:
                    logger.warning(f"Could not delete path {target}: {e}")
        return {"deleted": target}

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
