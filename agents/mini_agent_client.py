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
from steps.common.memory import ensure_id_map_table_schema

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
                        # Swallowing close exception is intentional and safe when lock acquisition fails
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
    "reject_ucf_frames",
    "supersede_ucf_frames",
}

PROMOTE_UCF_SCOPE_FIELDS = ("video_hash", "epoch_id")
SCOPE_BOUND_UCF_TOOLS = {"promote_ucf_to_memory"}


def _validate_promote_ucf_scope(tool_args: Dict[str, Any]) -> List[str]:
    """Validate the exact, non-ambiguous promotion scope."""
    violations: List[str] = []
    expected = set(PROMOTE_UCF_SCOPE_FIELDS)
    actual = set(tool_args)

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        violations.append(f"missing required scope fields: {', '.join(missing)}")
    if extra:
        violations.append(f"unsupported scope fields: {', '.join(extra)}")

    for field in PROMOTE_UCF_SCOPE_FIELDS:
        value = tool_args.get(field)
        if field in tool_args and (not isinstance(value, str) or not value.strip()):
            violations.append(f"{field} must be a non-empty string")

    return violations

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
                except Exception as e:
                    logger.warning(f"Failed to load tokens from {token_store_path}: {e}", exc_info=True)
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

    def _confirmation_token_error(
        self,
        tokens: Dict[str, Any],
        confirmation_token: str,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Optional[Dict[str, str]]:
        if confirmation_token not in tokens:
            return {
                "code": "invalid_confirmation_token",
                "message": "Invalid confirmation token.",
            }
        token_info = tokens[confirmation_token]
        if token_info.get("operation") != tool_name:
            return {
                "code": "token_operation_mismatch",
                "message": "Token was not issued for this operation.",
            }
        if token_info.get("used"):
            return {
                "code": "token_already_used",
                "message": "Token has already been used.",
            }
        if tool_name in SCOPE_BOUND_UCF_TOOLS and token_info.get("tool_args", {}) != tool_args:
            return {
                "code": "token_scope_mismatch",
                "message": "Confirmation token was not issued for this exact UCF scope.",
            }

        expired = bool(
            tool_args.get("simulate_expired_token")
            or token_info.get("tool_args", {}).get("simulate_expired_token")
        )
        if not expired:
            timestamp = token_info.get("timestamp")
            if timestamp:
                try:
                    normalized = timestamp[:-1] if timestamp.endswith("Z") else timestamp
                    issued_at = datetime.fromisoformat(normalized)
                    if issued_at.tzinfo is not None:
                        from datetime import timezone

                        issued_at = issued_at.astimezone(timezone.utc).replace(tzinfo=None)
                    expired = (datetime.utcnow() - issued_at).total_seconds() > 600
                except Exception:
                    expired = False
        if expired:
            return {
                "code": "token_expired",
                "message": "Confirmation token expired.",
            }
        return None

    def _confirmation_error_envelope(
        self,
        request_id: str,
        error: Dict[str, str],
    ) -> Tuple[Dict[str, Any], int]:
        envelope = {
            "request_id": request_id,
            "profile": self.profile,
            "status": "error",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "result": {"allowed": False},
            "errors": [error],
        }
        return self.sanitize_envelope(envelope), 1

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
                # Swallowing file removal exception is safe as this is a temporary file cleanup attempt
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
        NATIVELY_GATED_TOOLS = {"promote_ucf_to_memory", "validate_ucf_frames", "reject_ucf_frames", "supersede_ucf_frames"}
        if confirmation_token:
            with self._lock_token_store():
                tokens = self._load_tokens()
                if confirmation_token not in tokens and tool_name not in NATIVELY_GATED_TOOLS:
                    # Non-native token for a non-native tool: delegate to subprocess
                    pass
                else:
                    token_error = self._confirmation_token_error(
                        tokens,
                        confirmation_token,
                        tool_name,
                        tool_args,
                    )
                    if token_error:
                        return self._confirmation_error_envelope(request_id, token_error)

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

        if tool_name == "promote_ucf_to_memory":
            scope_violations = _validate_promote_ucf_scope(tool_args)
            if scope_violations:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False},
                    "errors": [{
                        "code": "invalid_tool_arguments",
                        "message": "promote_ucf_to_memory requires an explicit video_hash and epoch_id scope.",
                        "details": {"violations": scope_violations},
                    }],
                }
                return self.sanitize_envelope(envelope), 1

        # 4. Human-in-the-Loop Gating Validation
        if self.profile != "unrestricted" and tool_name in ("promote_ucf_to_memory", "validate_ucf_frames", "reject_ucf_frames", "supersede_ucf_frames"):
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

        # 5. Native tool validation bypass & Destructive break-glass check
        if tool_name == "file_delete" and self.profile in ("safe", "offline") and os.environ.get("GOODQ_BREAK_GLASS") != "1":
            envelope = {
                "request_id": request_id,
                "profile": self.profile,
                "status": "error",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "result": {"allowed": False},
                "errors": [{"code": "break_glass_required", "message": f"Destructive operation '{tool_name}' requires break-glass override."}],
            }
            return self.sanitize_envelope(envelope), 1

        if tool_name in ("run_ingestion", "promote_ucf_to_memory", "validate_ucf_frames", "reject_ucf_frames", "supersede_ucf_frames", "file_delete", "validate_ucf_epoch"):
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
            elif tool_name == "reject_ucf_frames":
                tool_result = self._execute_reject_ucf_frames(tool_args)
            elif tool_name == "supersede_ucf_frames":
                tool_result = self._execute_supersede_ucf_frames(tool_args)
            elif tool_name == "file_delete":
                tool_result = self._execute_file_delete(tool_args)
            else:
                raise ValueError(f"No native handler for tool: {tool_name}")
        except UCFValidationError as e:
            status = "fatal_error"
            errors_list = [{"code": "ucf_validation_failed", "message": "Validation failed.", "details": e.details}]
            logger.error(f"Validation failed for tool {tool_name}: {e.details}")
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
                "mutated": tool_name in ("qdrant_upsert", "home_assistant_call_service", "run_ingestion",
                                          "promote_ucf_to_memory", "validate_ucf_frames",
                                          "reject_ucf_frames", "supersede_ucf_frames", "file_delete"),
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
            if isinstance(tool_result, dict) and "warnings" in tool_result:
                result_envelope["warnings"] = tool_result["warnings"]
        else:
            result_envelope["errors"] = errors_list
            # Also set deprecated 'error' field for backward compatibility
            result_envelope["error"] = errors_list[0] if errors_list else {"code": "execution_failed", "message": "Tool execution error"}
            
        return self.sanitize_envelope(result_envelope), 0 if status == "success" else 1

    def _get_ucf_db_path(self) -> Path:
        db_dir = self.config.get('paths', {}).get('db_dir')
        if db_dir:
            ucf_db_dir = Path(db_dir) / 'ucf'
        else:
            epoch_id = "default_epoch"
            ucf_db_dir = Path("epochs") / epoch_id / "ucf"
        ucf_db_dir.mkdir(parents=True, exist_ok=True)
        return ucf_db_dir / 'ucf_ledger.db'

    def _sync_ucf_status_to_qdrant(self, frames_to_sync: List[Tuple[Any, Any, Any]], status_val: str) -> Dict[str, Any]:
        import logging
        logger = logging.getLogger(__name__)
        import requests
        import uuid
        
        qdrant_updates = {}
        for v_key, v_coll, v_backend in frames_to_sync:
            if not v_key or not v_coll or not v_backend:
                continue
            if str(v_backend).strip().lower() == "qdrant":
                qdrant_updates.setdefault(v_coll, []).append(v_key)
                
        attempted = len(qdrant_updates) > 0
        collections_attempted = list(qdrant_updates.keys())
        points_attempted = sum(len(v) for v in qdrant_updates.values())
        failed_collections = []
        
        if attempted:
            qdrant_host = self.config.get("qdrant", {}).get("host", "http://127.0.0.1:6333")
            GOODQ_POINT_ID_NAMESPACE = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")

            for v_coll, keys in qdrant_updates.items():
                success = False
                try:
                    # Normalize point IDs
                    normalized_ids = []
                    for k in keys:
                        s = k.strip()
                        hex_candidate = s.replace("-", "")
                        if len(hex_candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in hex_candidate):
                            normalized_ids.append(str(uuid.UUID(hex_candidate)))
                        elif s.isdigit():
                            normalized_ids.append(s)
                        else:
                            normalized_ids.append(str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s)))

                    if not normalized_ids:
                        continue

                    # Use direct REST with the exact collection name from UCF ledger
                    # (avoids double-prefix bug from build_qdrant_client)
                    resp = requests.post(
                        f"{qdrant_host}/collections/{v_coll}/points/payload",
                        json={
                            "payload": {"ucf_promotion_status": status_val},
                            "points": normalized_ids,
                        },
                        timeout=10,
                    )
                    if resp.status_code in (200, 202):
                        success = True
                    else:
                        logger.warning(
                            "Row sync payload update failed for %s: %s %s",
                            v_coll, resp.status_code, resp.text[:200] if resp.text else "",
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to sync ucf status to qdrant for collection %s: %s",
                        v_coll,
                        e
                    )
                
                if not success:
                    failed_collections.append(v_coll)
            
            status = "warning" if failed_collections else "ok"
        else:
            status = "skipped"
            
        return {
            "attempted": attempted,
            "status": status,
            "collections_attempted": collections_attempted,
            "points_attempted": points_attempted,
            "failed_collections": failed_collections,
        }

    def _sync_qdrant_by_scope(self, epoch_id: str, status_val: str,
                               video_hash: Optional[str] = None) -> Dict[str, Any]:
        """Scope-based Qdrant sync for points not tracked by UCF (e.g. Phase 6a).

        Scrolls all epoch-scoped Qdrant collections and updates any points
        missing ucf_promotion_status or having a stale value.
        """
        import logging
        import requests
        logger = logging.getLogger(__name__)

        qdrant_host = self.config.get("qdrant", {}).get("host", "http://127.0.0.1:6333")
        collections_swept = []
        points_updated = 0
        failed = []

        # Discover epoch-scoped collections
        try:
            resp = requests.get(f"{qdrant_host}/collections", timeout=5)
            if resp.status_code != 200:
                return {"status": "error", "error": f"collections list failed: {resp.status_code}"}
            all_colls = resp.json().get("result", {}).get("collections", [])
        except Exception as e:
            return {"status": "error", "error": str(e)}

        epoch_colls = [c["name"] for c in all_colls if epoch_id in c.get("name", "")]
        if not epoch_colls:
            return {"status": "skipped", "reason": "no_epoch_collections",
                    "collections_swept": [], "points_updated": 0}

        for coll_name in epoch_colls:
            try:
                offset = None
                coll_updated = 0
                while True:
                    scroll_body = {"limit": 100, "with_payload": True}
                    if offset is not None:
                        scroll_body["offset"] = offset

                    scroll_resp = requests.post(
                        f"{qdrant_host}/collections/{coll_name}/points/scroll",
                        json=scroll_body, timeout=10
                    )
                    if scroll_resp.status_code != 200:
                        failed.append(coll_name)
                        break

                    result = scroll_resp.json().get("result", {})
                    points = result.get("points", [])
                    next_offset = result.get("next_page_offset")

                    # Find points needing update
                    points_to_update = []
                    for pt in points:
                        payload = pt.get("payload", {})
                        current_status = payload.get("ucf_promotion_status")
                        if current_status != status_val:
                            points_to_update.append(pt["id"])

                    # Batch update
                    if points_to_update:
                        update_resp = requests.post(
                            f"{qdrant_host}/collections/{coll_name}/points/payload",
                            json={
                                "payload": {"ucf_promotion_status": status_val},
                                "points": points_to_update,
                            },
                            timeout=10,
                        )
                        if update_resp.status_code == 200:
                            coll_updated += len(points_to_update)
                        else:
                            logger.warning(
                                "Scope sync payload update failed for %s: %s",
                                coll_name, update_resp.status_code
                            )

                    if not next_offset or not points:
                        break
                    offset = next_offset

                collections_swept.append(coll_name)
                points_updated += coll_updated
            except Exception as e:
                logger.warning("Scope sync failed for collection %s: %s", coll_name, e)
                failed.append(coll_name)

        return {
            "status": "warning" if failed else "ok",
            "collections_swept": collections_swept,
            "points_updated": points_updated,
            "failed_collections": failed,
        }

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
                                ensure_id_map_table_schema(sidecar_db_path, table_name)
                                s_conn = sqlite3.connect(sidecar_db_path)
                                p_payload = r.get("payload", {})
                                faiss_id = p_payload.get("faiss_id")
                                if faiss_id is not None:
                                    cursor = s_conn.execute(
                                        f"UPDATE {table_name} SET ucf_frame_id = ?, video_hash = ? WHERE (video_hash = ? OR video_hash = '' OR video_hash IS NULL) AND faiss_id = ?",
                                        (fid, r.get("video_hash"), r.get("video_hash"), int(faiss_id))
                                    )
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
                except Exception as e:
                    logger.warning(f"Failed to load or parse UCF validation report from {report_path}: {e}", exc_info=True)
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
                    except Exception as e:
                        logger.warning(f"Failed to load or parse UCF validation report from {report_path}: {e}", exc_info=True)
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

    def _fetch_vector_from_qdrant(self, collection: str, vector_key: str) -> Optional[List[float]]:
        import requests
        import uuid
        qdrant_host = self.config.get("qdrant", {}).get("host", "http://127.0.0.1:6333")
        GOODQ_POINT_ID_NAMESPACE = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")
        
        s = vector_key.strip()
        hex_candidate = s.replace("-", "")
        if len(hex_candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in hex_candidate):
            normalized_key = str(uuid.UUID(hex_candidate))
        elif s.isdigit():
            normalized_key = s
        else:
            normalized_key = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))
            
        try:
            resp = requests.post(
                f"{qdrant_host}/collections/{collection}/points",
                json={"ids": [normalized_key], "with_vector": True, "with_payload": False},
                timeout=5
            )
            if resp.status_code == 200:
                result = resp.json().get("result", [])
                if result and isinstance(result, list):
                    vector = result[0].get("vector")
                    if isinstance(vector, list):
                        return vector
        except Exception as e:
            logger.warning(f"Failed to fetch vector from Qdrant for key {normalized_key}: {e}")
        return None

    def _dematerialize_active_views(self, video_hash: str) -> None:
        import sqlite3
        import json
        from pathlib import Path
        from lib.kg_realtime_integration import _resolve_graph_db_path
        from lib.knowledge_graph import KnowledgeGraph

        # Fetch file_path from media_sources in ucf_ledger.db
        file_path = None
        ucf_db_path = self._get_ucf_db_path()
        if ucf_db_path and Path(ucf_db_path).exists():
            try:
                conn_ucf = sqlite3.connect(str(ucf_db_path))
                cursor = conn_ucf.execute("SELECT file_path FROM media_sources WHERE video_hash = ?", (video_hash,))
                row = cursor.fetchone()
                if row:
                    file_path = row[0]
                conn_ucf.close()
            except Exception:
                pass

        scene_ids = []
        seg_ids = []
        # 1. Dematerialize memory.db
        db_path = self.config.get("paths", {}).get("db_path")
        if db_path and Path(db_path).exists():
            try:
                conn = sqlite3.connect(str(db_path))
                with conn:
                    # Fetch scenes in this video to clean up links and embeddings
                    cursor = conn.execute("SELECT id FROM scenes WHERE video_hash = ?", (video_hash,))
                    scene_ids = [r[0] for r in cursor.fetchall()]
                    
                    # Fetch segments in this video
                    cursor = conn.execute("SELECT id FROM segments WHERE video_hash = ?", (video_hash,))
                    seg_ids = [r[0] for r in cursor.fetchall()]
                    
                    # Collect frame_hash and audio_hash from scene metadata if possible
                    frame_hashes = set()
                    audio_hashes = set()
                    for sid in scene_ids:
                        cursor = conn.execute("SELECT meta FROM scenes WHERE id = ?", (sid,))
                        row = cursor.fetchone()
                        if row and row[0]:
                            try:
                                meta = json.loads(row[0])
                                k_hash = meta.get("keyframe", {}).get("hash")
                                if k_hash:
                                    frame_hashes.add(k_hash)
                                a_hash = meta.get("audio", {}).get("hash")
                                if a_hash:
                                    audio_hashes.add(a_hash)
                            except Exception:
                                pass
                                
                    # Ensure ucf_provenance_mapping table exists
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS ucf_provenance_mapping (
                            record_type TEXT,
                            record_id TEXT,
                            ucf_frame_id INTEGER,
                            PRIMARY KEY (record_type, record_id, ucf_frame_id)
                        )
                    """)

                    # Fetch embedding hashes before deleting them
                    emb_hashes = []
                    if scene_ids:
                        placeholders = ",".join("?" for _ in scene_ids)
                        cursor = conn.execute(f"SELECT hash FROM embeddings WHERE scene_id IN ({placeholders})", tuple(scene_ids))
                        emb_hashes = [r[0] for r in cursor.fetchall()]

                    # Delete from scenes, scene_text_fts, segments, embeddings
                    conn.execute("DELETE FROM scenes WHERE video_hash = ?", (video_hash,))
                    conn.execute("DELETE FROM scene_text_fts WHERE video_hash = ?", (video_hash,))
                    conn.execute("DELETE FROM segments WHERE video_hash = ?", (video_hash,))
                    
                    if scene_ids:
                        placeholders = ",".join("?" for _ in scene_ids)
                        conn.execute(f"DELETE FROM embeddings WHERE scene_id IN ({placeholders})", tuple(scene_ids))

                    # Clean up ucf_provenance_mapping
                    if scene_ids:
                        placeholders = ",".join("?" for _ in scene_ids)
                        conn.execute(f"DELETE FROM ucf_provenance_mapping WHERE record_type = 'scene' AND record_id IN ({placeholders})", tuple(scene_ids))
                    if seg_ids:
                        placeholders = ",".join("?" for _ in seg_ids)
                        conn.execute(f"DELETE FROM ucf_provenance_mapping WHERE record_type = 'segment' AND record_id IN ({placeholders})", tuple(seg_ids))
                    if emb_hashes:
                        placeholders = ",".join("?" for _ in emb_hashes)
                        conn.execute(f"DELETE FROM ucf_provenance_mapping WHERE record_type = 'embedding' AND record_id IN ({placeholders})", tuple(emb_hashes))
                        
                    # Delete from links
                    conn.execute("DELETE FROM links WHERE parent_hash = ? OR child_hash = ?", (video_hash, video_hash))
                    
                    for sid in scene_ids:
                        conn.execute("DELETE FROM links WHERE parent_hash = ? OR child_hash = ?", (sid, sid))
                    for sgid in seg_ids:
                        conn.execute("DELETE FROM links WHERE parent_hash = ? OR child_hash = ?", (sgid, sgid))
                    for fh in frame_hashes:
                        conn.execute("DELETE FROM links WHERE parent_hash = ? OR child_hash = ?", (fh, fh))
                    for ah in audio_hashes:
                        conn.execute("DELETE FROM links WHERE parent_hash = ? OR child_hash = ?", (ah, ah))
                        
                conn.close()
                logger.info(f"Dematerialized memory.db records for video_hash: {video_hash}")
            except Exception as e:
                logger.warning(f"Failed to dematerialize memory.db for video_hash {video_hash}: {e}")
                
        # 2. Dematerialize knowledge_graph.db
        graph_db_path = _resolve_graph_db_path(self.config)
        if graph_db_path and Path(graph_db_path).exists():
            try:
                with KnowledgeGraph(str(graph_db_path)) as kg:
                    # Resolve media_ids for this video
                    query_kg = "SELECT id, scene_id FROM media_nodes WHERE media_path = ?"
                    params_kg: list = [video_hash]
                    if file_path:
                        query_kg += " OR media_path = ?"
                        params_kg.append(file_path)
                    if scene_ids:
                        placeholders = ",".join("?" for _ in scene_ids)
                        query_kg += f" OR scene_id IN ({placeholders})"
                        params_kg.extend(scene_ids)
                    cursor = kg.conn.execute(query_kg, tuple(params_kg))
                    media_rows = cursor.fetchall()
                    
                    media_ids = []
                    scene_ids_kg = []
                    for row in media_rows:
                        m_id = row[0]
                        sc_id = row[1]
                        
                        prop_cursor = kg.conn.execute("SELECT properties, media_path FROM media_nodes WHERE id = ?", (m_id,))
                        prop_row = prop_cursor.fetchone()
                        is_ours = False
                        if prop_row:
                            m_path = prop_row[1] or ""
                            if video_hash in m_path or (file_path and Path(file_path).name in m_path):
                                is_ours = True
                            else:
                                try:
                                    props = json.loads(prop_row[0]) if prop_row[0] else {}
                                    if props.get("video_path") and (video_hash in props["video_path"]):
                                        is_ours = True
                                except Exception:
                                    pass
                        if is_ours:
                            media_ids.append(m_id)
                            if sc_id:
                                scene_ids_kg.append(sc_id)
                                
                    if media_ids:
                        placeholders = ",".join("?" for _ in media_ids)
                        cursor = kg.conn.execute(f"SELECT DISTINCT node_id FROM node_media WHERE media_id IN ({placeholders})", tuple(media_ids))
                        candidate_node_ids = [r[0] for r in cursor.fetchall()]
                        
                        kg.conn.execute(f"DELETE FROM node_media WHERE media_id IN ({placeholders})", tuple(media_ids))
                        kg.conn.execute(f"DELETE FROM media_nodes WHERE id IN ({placeholders})", tuple(media_ids))
                        
                        # Node IDs to prune
                        nodes_to_delete_ids = []
                        
                        for name in scene_ids_kg:
                            cursor = kg.conn.execute("SELECT id FROM nodes WHERE node_type = 'scene' AND name = ?", (name,))
                            for r in cursor.fetchall():
                                nodes_to_delete_ids.append(r[0])
                        
                        video_names = [video_hash]
                        if file_path:
                            video_names.append(Path(file_path).stem)
                            video_names.append(Path(file_path).name)
                        for name in video_names:
                            cursor = kg.conn.execute("SELECT id FROM nodes WHERE node_type = 'video' AND name = ?", (name,))
                            for r in cursor.fetchall():
                                nodes_to_delete_ids.append(r[0])
                                
                        # Add segments matching memory.db segment IDs
                        if seg_ids:
                            for name in seg_ids:
                                cursor = kg.conn.execute("SELECT id FROM nodes WHERE node_type = 'segment' AND name = ?", (name,))
                                for r in cursor.fetchall():
                                    nodes_to_delete_ids.append(r[0])

                        # Add segments connected to scene nodes via has_segment edges
                        scene_node_ids_list = []
                        for name in scene_ids_kg:
                            cursor = kg.conn.execute("SELECT id FROM nodes WHERE node_type = 'scene' AND name = ?", (name,))
                            scene_node_ids_list.extend([r[0] for r in cursor.fetchall()])
                        if scene_node_ids_list:
                            placeholders_sc = ",".join("?" for _ in scene_node_ids_list)
                            cursor = kg.conn.execute(
                                f"SELECT target_id FROM edges WHERE source_id IN ({placeholders_sc}) AND edge_type IN ('has_segment', 'scene_has_segment')",
                                tuple(scene_node_ids_list)
                            )
                            for r in cursor.fetchall():
                                nodes_to_delete_ids.append(r[0])

                        # Fallback matching
                        cursor = kg.conn.execute("SELECT id, name, properties FROM nodes WHERE node_type = 'segment'")
                        for r in cursor.fetchall():
                            n_id = r[0]
                            n_name = r[1]
                            if video_hash in n_name:
                                nodes_to_delete_ids.append(n_id)
                            else:
                                try:
                                    props = json.loads(r[2]) if r[2] else {}
                                    if video_hash in str(props):
                                        nodes_to_delete_ids.append(n_id)
                                except Exception:
                                    pass

                        # Query evidence nodes corresponding to the video's frames from the ledger
                        video_frame_ids = []
                        if ucf_db_path and Path(ucf_db_path).exists():
                            try:
                                conn_ucf = sqlite3.connect(str(ucf_db_path))
                                cursor = conn_ucf.execute("SELECT frame_id FROM context_frames WHERE video_hash = ?", (video_hash,))
                                video_frame_ids = [r[0] for r in cursor.fetchall()]
                                conn_ucf.close()
                            except Exception:
                                pass

                        evidence_node_ids = []
                        if video_frame_ids:
                            for fid in video_frame_ids:
                                cursor = kg.conn.execute("SELECT id FROM nodes WHERE node_type = 'evidence' AND name = ?", (f"ucf_frame_{fid}",))
                                for r in cursor.fetchall():
                                    evidence_node_ids.append(r[0])

                        # Support-aware evidence node pruning
                        for ev_id in evidence_node_ids:
                            if nodes_to_delete_ids:
                                placeholders_del = ",".join("?" for _ in nodes_to_delete_ids)
                                cursor = kg.conn.execute(
                                    f"SELECT count(*) FROM edges WHERE (source_id = ? OR target_id = ?) AND (source_id NOT IN ({placeholders_del}) AND target_id NOT IN ({placeholders_del}))",
                                    (ev_id, ev_id) + tuple(nodes_to_delete_ids) * 2
                                )
                                other_edge_count = cursor.fetchone()[0]
                            else:
                                cursor = kg.conn.execute("SELECT count(*) FROM edges WHERE source_id = ? OR target_id = ?", (ev_id, ev_id))
                                other_edge_count = cursor.fetchone()[0]

                            if other_edge_count == 0:
                                nodes_to_delete_ids.append(ev_id)

                        if nodes_to_delete_ids:
                            nodes_to_delete_ids = list(set(nodes_to_delete_ids))
                            nodes_placeholders = ",".join("?" for _ in nodes_to_delete_ids)
                            kg.conn.execute(f"DELETE FROM edges WHERE source_id IN ({nodes_placeholders}) OR target_id IN ({nodes_placeholders})", tuple(nodes_to_delete_ids) * 2)
                            kg.conn.execute(f"DELETE FROM nodes WHERE id IN ({nodes_placeholders})", tuple(nodes_to_delete_ids))
                            
                        # Support-aware entity pruning
                        for nid in candidate_node_ids:
                            if nid in nodes_to_delete_ids:
                                continue
                            link_count = kg.conn.execute("SELECT count(*) FROM node_media WHERE node_id = ?", (nid,)).fetchone()[0]
                            edge_count = kg.conn.execute("SELECT count(*) FROM edges WHERE source_id = ? OR target_id = ?", (nid, nid)).fetchone()[0]
                            if link_count == 0 and edge_count == 0:
                                kg.conn.execute("DELETE FROM nodes WHERE id = ?", (nid,))
                                
                        kg.conn.commit()
                        logger.info(f"Dematerialized knowledge_graph.db records for video_hash: {video_hash}")
            except Exception as e:
                logger.warning(f"Failed to dematerialize knowledge_graph.db for video_hash {video_hash}: {e}")

    def _execute_promote_ucf_to_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Promotes context frames from 'validated' to 'promoted' and materializes active views."""
        import sqlite3
        import json
        import requests
        import numpy as np
        from pathlib import Path
        from steps.common.memory import to_faiss_id, _make_id, _connect
        from lib.kg_realtime_integration import _resolve_graph_db_path
        from lib.knowledge_graph import KnowledgeGraph

        ucf_db_path = self._get_ucf_db_path()
        
        # Ensure schema is initialized
        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient
        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()
        client.close()
        
        conn = sqlite3.connect(str(ucf_db_path))
        
        video_hash = args["video_hash"]
        epoch_id = args["epoch_id"]

        # 0. Pre-check: block promotion if any staged frames exist
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

        # Query vector_key, vector_collection, vector_backend for frames to be promoted
        select_sync = "SELECT vector_key, vector_collection, vector_backend FROM context_frames WHERE promotion_status = 'validated'"
        sync_args = []
        if video_hash:
            select_sync += " AND video_hash = ?"
            sync_args.append(video_hash)
        if epoch_id:
            select_sync += " AND epoch_id = ?"
            sync_args.append(epoch_id)
        cursor = conn.execute(select_sync, tuple(sync_args))
        frames_to_sync = cursor.fetchall()

        # Update ucf ledger status inside transaction
        select_validated = "SELECT count(*) FROM context_frames WHERE promotion_status = 'validated'"
        update_validated = "UPDATE context_frames SET promotion_status = 'promoted' WHERE promotion_status = 'validated'"
        if video_hash:
            select_validated += " AND video_hash = ?"
            update_validated += " AND video_hash = ?"
        if epoch_id:
            select_validated += " AND epoch_id = ?"
            update_validated += " AND epoch_id = ?"
        promote_args = list(sync_args)
        promoted_count = conn.execute(select_validated, tuple(promote_args)).fetchone()[0]
        
        conn.execute("BEGIN TRANSACTION")
        conn.execute(update_validated, tuple(promote_args))

        scenes_count = 0
        segments_count = 0
        embeddings_count = 0
        kg_nodes_count = 0
        kg_edges_count = 0

        db_path = self.config.get("paths", {}).get("db_path")
        graph_db_path = _resolve_graph_db_path(self.config)
        scene_manifest_path = Path()
        temporal_index_path = Path()

        try:
            cursor_ms = conn.execute("SELECT file_path FROM media_sources WHERE video_hash = ?", (video_hash,))
            row_ms = cursor_ms.fetchone()
            file_path = row_ms[0] if row_ms else None
            video_stem = Path(file_path).stem if file_path else video_hash

            processing_root = Path(self.config.get("paths", {}).get("processing", "processing"))
            video_processing_dir = processing_root / video_stem
            
            scene_manifest_path = video_processing_dir / "video" / "scene_manifest.json"
            if not scene_manifest_path.exists():
                scene_manifest_path = video_processing_dir / "scene_manifest.json"
                
            temporal_index_path = video_processing_dir / "temporal_index.json"
            if not temporal_index_path.exists():
                temporal_index_path = video_processing_dir / "video" / "temporal_index.json"

            scene_manifest = {}
            if scene_manifest_path.exists():
                with open(scene_manifest_path, "r", encoding="utf-8") as f:
                    scene_manifest = json.load(f)
            
            temporal_index = {}
            if temporal_index_path.exists():
                with open(temporal_index_path, "r", encoding="utf-8") as f:
                    temporal_index = json.load(f)

            cursor_f = conn.execute(
                "SELECT frame_id, source_artifact_id, worker_name, vector_key, vector_collection, payload, t_start, t_end, modality "
                "FROM context_frames WHERE video_hash = ? AND promotion_status = 'promoted'",
                (video_hash,)
            )
            promoted_frames = cursor_f.fetchall()
            promoted_frame_ids = [row[0] for row in promoted_frames]

            frames_by_scene = {}
            for r_f in promoted_frames:
                fid, scene_id, worker_name, vector_key, vector_collection, payload_str, t_start, t_end, modality = r_f
                if scene_id:
                    frames_by_scene.setdefault(scene_id, []).append({
                        "frame_id": fid,
                        "worker_name": worker_name,
                        "vector_key": vector_key,
                        "vector_collection": vector_collection,
                        "payload": json.loads(payload_str) if payload_str else {},
                        "t_start": t_start,
                        "t_end": t_end,
                        "modality": modality
                    })

            if not db_path:
                raise RuntimeError("db_path is not defined in config paths")
            
            conn_mem = _connect(str(db_path))
            conn_mem.execute("PRAGMA foreign_keys = ON;")
            
            for table in ("scenes", "segments"):
                try:
                    cur_info = conn_mem.execute(f"PRAGMA table_info('{table}')")
                    cols = {r[1] for r in cur_info.fetchall()}
                    if "ucf_provenance" not in cols:
                        conn_mem.execute(f"ALTER TABLE {table} ADD COLUMN ucf_provenance TEXT")
                except Exception as ex_alter:
                    logger.warning(f"Could not check/alter table {table} schema: {ex_alter}")

            try:
                cur_info = conn_mem.execute("PRAGMA table_info('embeddings')")
                cols = {r[1] for r in cur_info.fetchall()}
                if "ucf_provenance" not in cols:
                    conn_mem.execute("ALTER TABLE embeddings ADD COLUMN ucf_provenance TEXT")
            except Exception as ex_alter:
                logger.warning(f"Could not check/alter embeddings table schema: {ex_alter}")

            try:
                conn_mem.execute("""
                    CREATE TABLE IF NOT EXISTS ucf_provenance_mapping (
                        record_type TEXT,
                        record_id TEXT,
                        ucf_frame_id INTEGER,
                        PRIMARY KEY (record_type, record_id, ucf_frame_id)
                    )
                """)
            except Exception as ex_create:
                logger.warning(f"Could not create ucf_provenance_mapping table: {ex_create}")

            manifest_scenes = {s.get("id") or s.get("scene_id"): s for s in scene_manifest.get("scenes", []) if isinstance(s, dict)}

            with conn_mem:
                now_str = datetime.utcnow().isoformat()
                for scene_id, s_frames in frames_by_scene.items():
                    scene_fids = [f["frame_id"] for f in s_frames]

                    manifest_scene = manifest_scenes.get(scene_id)
                    if manifest_scene:
                        start = float(manifest_scene.get("start") or 0.0)
                        end = float(manifest_scene.get("end") or start)
                        scene_meta = manifest_scene.get("meta", {}) or manifest_scene
                    else:
                        start = min(f["t_start"] for f in s_frames)
                        end = max(f["t_end"] for f in s_frames)
                        scene_meta = {}

                    merged_meta = dict(scene_meta)
                    merged_meta["ucf_provenance"] = scene_fids
                    merged_meta_json = json.dumps(merged_meta, ensure_ascii=False)

                    conn_mem.execute(
                        "INSERT OR REPLACE INTO scenes(id, video_hash, start, end, meta, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (scene_id, video_hash, start, end, merged_meta_json, now_str)
                    )
                    scenes_count += 1

                    for fid in scene_fids:
                        conn_mem.execute(
                            "INSERT OR REPLACE INTO ucf_provenance_mapping(record_type, record_id, ucf_frame_id) VALUES ('scene', ?, ?)",
                            (scene_id, fid)
                        )

                    ocr_text = None
                    transcript_text = None
                    if manifest_scene:
                        ocr_text = manifest_scene.get("keyframe", {}).get("ocr_text")
                        transcript_text = manifest_scene.get("audio", {}).get("transcript")
                    
                    for f in s_frames:
                        if not ocr_text and f["worker_name"] == "image_ocr":
                            ocr_text = f["payload"].get("ocr_text")
                        if not transcript_text and f["worker_name"] == "audio_transcribe":
                            transcript_text = f["payload"].get("transcript") or f["payload"].get("text")

                    conn_mem.execute("DELETE FROM scene_text_fts WHERE scene_id=?", (scene_id,))
                    if ocr_text:
                        conn_mem.execute(
                            "INSERT INTO scene_text_fts(scene_id, video_hash, content_type, text) VALUES (?, ?, 'ocr', ?)",
                            (scene_id, video_hash, str(ocr_text))
                        )
                    if transcript_text:
                        conn_mem.execute(
                            "INSERT INTO scene_text_fts(scene_id, video_hash, content_type, text) VALUES (?, ?, 'transcript', ?)",
                            (scene_id, video_hash, str(transcript_text))
                        )

                    conn_mem.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, scene_id, 'scene_of'))
                    conn_mem.execute(
                        "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?, ?, 'scene_of', ?, ?, ?)",
                        (video_hash, scene_id, start, json.dumps({'duration': end - start}, ensure_ascii=False), now_str)
                    )

                    frame_hash = None
                    if manifest_scene and manifest_scene.get("keyframe"):
                        kframe = manifest_scene["keyframe"]
                        frame_hash = kframe.get("hash")
                        frame_path = kframe.get("path")
                        if frame_hash:
                            conn_mem.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (scene_id, frame_hash, 'keyframe_of'))
                            conn_mem.execute(
                                "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?, ?, 'keyframe_of', NULL, ?, ?)",
                                (scene_id, frame_hash, json.dumps({'path': frame_path}, ensure_ascii=False), now_str)
                            )
                            conn_mem.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, frame_hash, 'frame_of'))
                            conn_mem.execute(
                                "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?, ?, 'frame_of', ?, ?, ?)",
                                (video_hash, frame_hash, start + (end - start)/2.0, json.dumps({'scene_id': scene_id}, ensure_ascii=False), now_str)
                            )

                    audio_hash = None
                    if manifest_scene and manifest_scene.get("audio"):
                        aud = manifest_scene["audio"]
                        audio_hash = aud.get("hash")
                        audio_path = aud.get("path")
                        if audio_hash:
                            conn_mem.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (scene_id, audio_hash, 'audio_of_scene'))
                            conn_mem.execute(
                                "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?, ?, 'audio_of_scene', NULL, ?, ?)",
                                (scene_id, audio_hash, json.dumps({'path': audio_path}, ensure_ascii=False), now_str)
                            )
                            conn_mem.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, audio_hash, 'audio_of'))
                            conn_mem.execute(
                                "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?, ?, 'audio_of', ?, ?, ?)",
                                (video_hash, audio_hash, start, json.dumps({'scene_id': scene_id}, ensure_ascii=False), now_str)
                            )

                    segments_list = []
                    if manifest_scene and manifest_scene.get("audio") and isinstance(manifest_scene["audio"].get("speaker_transcript"), list):
                        segments_list = manifest_scene["audio"]["speaker_transcript"]
                    elif isinstance(temporal_index.get("segments"), list):
                        segments_list = [seg for seg in temporal_index["segments"] if str(seg.get("scene_id")) == str(scene_id)]
                    
                    if not segments_list:
                        for f in s_frames:
                            if f["worker_name"] == "audio_transcribe" and f["payload"]:
                                p = f["payload"]
                                segments_list.append({
                                    "start": f["t_start"],
                                    "end": f["t_end"],
                                    "speaker": p.get("speaker") or p.get("speaker_id") or "unknown",
                                    "text": p.get("transcript") or p.get("text")
                                })

                    for seg in segments_list:
                        if not isinstance(seg, dict):
                            continue
                        seg_start = float(seg.get("start", start))
                        seg_end = float(seg.get("end", end))
                        speaker = seg.get("speaker") or "unknown"
                        seg_id = _make_id("segment", [video_hash, f"{seg_start:.3f}", f"{seg_end:.3f}", speaker])
                        
                        seg_fids = []
                        for f in s_frames:
                            if f["t_start"] < seg_end and f["t_end"] > seg_start:
                                seg_fids.append(f["frame_id"])
                        if not seg_fids:
                            seg_fids = scene_fids

                        seg_meta = {k: v for k, v in seg.items() if k not in ("start", "end")}
                        seg_meta["ucf_provenance"] = seg_fids
                        seg_meta_json = json.dumps(seg_meta, ensure_ascii=False)

                        conn_mem.execute(
                            "INSERT OR REPLACE INTO segments(id, video_hash, start, end, speaker, meta, created_at) VALUES (?,?,?,?,?,?,?)",
                            (seg_id, video_hash, seg_start, seg_end, speaker, seg_meta_json, now_str)
                        )
                        segments_count += 1

                        for fid in seg_fids:
                            conn_mem.execute(
                                "INSERT OR REPLACE INTO ucf_provenance_mapping(record_type, record_id, ucf_frame_id) VALUES ('segment', ?, ?)",
                                (seg_id, fid)
                            )

                        conn_mem.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, seg_id, 'segment_of'))
                        conn_mem.execute(
                            "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?, ?, 'segment_of', ?, ?, ?)",
                            (video_hash, seg_id, seg_start, json.dumps({'scene_id': scene_id}, ensure_ascii=False), now_str)
                        )

                        overlap_dur = max(0.0, min(end, seg_end) - max(start, seg_start))
                        conn_mem.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (scene_id, seg_id, 'overlaps'))
                        conn_mem.execute(
                            "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?, ?, 'overlaps', NULL, ?, ?)",
                            (scene_id, seg_id, json.dumps({'overlap': overlap_dur, 'speaker': speaker}, ensure_ascii=False), now_str)
                        )

                    for f in s_frames:
                        v_key = f["vector_key"]
                        v_collection = f["vector_collection"]
                        if v_key and v_collection:
                            vector = self._fetch_vector_from_qdrant(v_collection, v_key)
                            if vector:
                                vector_bytes = np.array(vector, dtype=np.float32).tobytes()
                                faiss_id = to_faiss_id(v_key)
                                
                                conn_mem.execute(
                                    "INSERT OR REPLACE INTO embeddings (hash, faiss_id, source_path, modality, scene_id, created_at, vector, ucf_provenance) "
                                    "VALUES (?, ?, '', ?, ?, ?, ?, ?)",
                                    (v_key, faiss_id, f["modality"], scene_id, now_str, vector_bytes, json.dumps([f["frame_id"]]))
                                )
                                embeddings_count += 1

                                conn_mem.execute(
                                    "INSERT OR REPLACE INTO ucf_provenance_mapping(record_type, record_id, ucf_frame_id) VALUES ('embedding', ?, ?)",
                                    (v_key, f["frame_id"])
                                )
            conn_mem.close()

            if not graph_db_path:
                raise RuntimeError("knowledge_graph_db path is not defined")
            
            with KnowledgeGraph(str(graph_db_path)) as kg:
                v_node_id = kg.add_node("video", video_stem, {"ucf_provenance": promoted_frame_ids})
                kg_nodes_count += 1
                
                conn_mem_read = sqlite3.connect(str(db_path))
                cursor_sc = conn_mem_read.execute("SELECT id, start, end, meta FROM scenes WHERE video_hash = ?", (video_hash,))
                scenes_rows = cursor_sc.fetchall()
                
                cursor_seg = conn_mem_read.execute("SELECT id, start, end, speaker, meta FROM segments WHERE video_hash = ?", (video_hash,))
                segments_rows = cursor_seg.fetchall()
                conn_mem_read.close()

                scene_node_ids = {}
                for sid, s_start, s_end, s_meta_str in scenes_rows:
                    s_meta = json.loads(s_meta_str) if s_meta_str else {}
                    prov = s_meta.get("ucf_provenance", promoted_frame_ids)
                    
                    media_id = kg.add_media_node(
                        media_type="video_scene",
                        media_path=file_path or "unknown.mp4",
                        scene_id=sid,
                        timestamp_start=s_start,
                        timestamp_end=s_end,
                        properties={"duration": s_end - s_start, "ucf_provenance": prov}
                    )
                    
                    sc_node_id = kg.add_node("scene", sid, {"ucf_provenance": prov})
                    scene_node_ids[sid] = sc_node_id
                    kg_nodes_count += 1
                    
                    kg.link_node_to_media(sc_node_id, media_id, confidence=1.0)
                    kg.add_edge(v_node_id, sc_node_id, "video_contains_scene", weight=1.0, properties={"ucf_provenance": prov})
                    kg_edges_count += 1

                    for fid in prov:
                        ev_node_id = kg.add_node("evidence", f"ucf_frame_{fid}", {"ucf_provenance": [fid]})
                        kg_nodes_count += 1
                        kg.add_edge(sc_node_id, ev_node_id, "scene_supported_by_ucf_frame", weight=1.0, properties={"ucf_provenance": [fid]})
                        kg_edges_count += 1

                for seg_id, seg_start, seg_end, speaker, seg_meta_str in segments_rows:
                    seg_meta = json.loads(seg_meta_str) if seg_meta_str else {}
                    prov = seg_meta.get("ucf_provenance", promoted_frame_ids)
                    
                    conn_mem_read = sqlite3.connect(str(db_path))
                    cursor_link = conn_mem_read.execute(
                        "SELECT parent_hash FROM links WHERE child_hash = ? AND relation = 'overlaps' LIMIT 1",
                        (seg_id,)
                    )
                    link_row = cursor_link.fetchone()
                    conn_mem_read.close()
                    sc_id = link_row[0] if link_row else None
                    
                    seg_node_id = kg.add_node("segment", seg_id, {"start": seg_start, "end": seg_end, "ucf_provenance": prov})
                    kg_nodes_count += 1
                    
                    media_id = None
                    if sc_id:
                        cur_media = kg.conn.execute("SELECT id FROM media_nodes WHERE scene_id = ? AND media_path = ?", (sc_id, file_path or "unknown.mp4"))
                        media_row = cur_media.fetchone()
                        if media_row:
                            media_id = media_row[0]
                    
                    if media_id:
                        kg.link_node_to_media(seg_node_id, media_id, confidence=1.0)
                        
                    if sc_id and sc_id in scene_node_ids:
                        sc_node_id = scene_node_ids[sc_id]
                        kg.add_edge(sc_node_id, seg_node_id, "scene_has_segment", weight=1.0, properties={"ucf_provenance": prov})
                        kg_edges_count += 1

                    for fid in prov:
                        ev_node_id = kg.add_node("evidence", f"ucf_frame_{fid}", {"ucf_provenance": [fid]})
                        kg_nodes_count += 1
                        kg.add_edge(seg_node_id, ev_node_id, "segment_supported_by_ucf_frame", weight=1.0, properties={"ucf_provenance": [fid]})
                        kg_edges_count += 1

            conn.commit()
            conn.close()

        except Exception as materialization_err:
            logger.error(f"Materialization failed for video_hash {video_hash}: {materialization_err}", exc_info=True)
            try:
                conn.execute("ROLLBACK")
                conn.close()
            except Exception:
                pass
            self._dematerialize_active_views(video_hash=video_hash)
            raise materialization_err

        val_errors = []
        try:
            val_res = self._execute_validate_ucf_epoch({})
            if not val_res.get("success", False):
                val_errors = val_res.get("errors", ["Validation failed."])
        except Exception as ve:
            val_errors = [str(ve)]

        # Construct report
        report = {
            "status": "success" if not val_errors else "warning",
            "counts": {
                "scenes_materialized": scenes_count,
                "segments_materialized": segments_count,
                "embeddings_materialized": embeddings_count,
                "kg_nodes_materialized": kg_nodes_count,
                "kg_edges_materialized": kg_edges_count
            },
            "scope": {
                "video_hash": video_hash,
                "epoch_id": epoch_id,
                "promoted_frame_ids": promoted_frame_ids
            },
            "inputs": {
                "scene_manifest_path": str(scene_manifest_path.resolve()) if scene_manifest_path.exists() else None,
                "temporal_index_path": str(temporal_index_path.resolve()) if temporal_index_path.exists() else None
            },
            "outputs": {
                "db_path": str(db_path),
                "knowledge_graph_db": str(graph_db_path)
            },
            "errors": val_errors,
            "validation_reference": "validate_ucf_epoch --mode strict"
        }

        qdrant_sync = self._sync_ucf_status_to_qdrant(frames_to_sync, "promoted")
        scope_sync = self._sync_qdrant_by_scope(epoch_id=epoch_id or "", status_val="promoted", video_hash=video_hash)
        res = {
            "promoted_count": promoted_count,
            "status": "promoted_complete",
            "qdrant_sync": qdrant_sync,
            "scope_sync": scope_sync,
            "materialization_report": report
        }
        if qdrant_sync["status"] == "warning":
            res["warnings"] = ["qdrant_payload_sync_failed"]
        return res

    def _execute_reject_ucf_frames(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Transitions in-scope context frames from 'staged' or 'validated' to 'rejected'.

        Requires a non-empty 'reason' argument. This is a terminal state —
        rejected frames cannot be promoted. The operation is idempotent:
        frames already in 'rejected' status are not counted.

        Cannot reject 'promoted' or 'superseded' frames — those are already
        canonical or superseded and must be addressed through supersede_ucf_frames
        or a new ingestion run.

        Expected lifecycle: staged | validated -> [reject_ucf_frames] -> rejected
        """
        reason = args.get("reason", "").strip()
        if not reason:
            return {
                "status": "error",
                "reason": "missing_reason",
                "message": "reject_ucf_frames requires a non-empty 'reason' argument.",
            }
        ucf_db_path = self._get_ucf_db_path()
        video_hash = args.get("video_hash") or args.get("video_id")
        epoch_id = args.get("epoch_id")
        
        # Query vector_key, vector_collection, vector_backend, video_hash for frames to be rejected before updating
        import sqlite3
        conn = sqlite3.connect(str(ucf_db_path))

        # Check for already-promoted or superseded frames in target scope
        check_query = "SELECT count(*) FROM context_frames WHERE promotion_status IN ('promoted', 'superseded')"
        check_params = []
        if video_hash:
            check_query += " AND video_hash = ?"
            check_params.append(video_hash)
        if epoch_id:
            check_query += " AND epoch_id = ?"
            check_params.append(epoch_id)
        
        promoted_or_superseded_count = conn.execute(check_query, tuple(check_params)).fetchone()[0]
        if promoted_or_superseded_count > 0:
            conn.close()
            return {
                "status": "blocked",
                "reason": "cannot_reject_promoted_frames",
                "message": "Cannot reject: frames in the scope are already promoted or superseded. Use supersede_ucf_frames instead."
            }

        query_sync = "SELECT vector_key, vector_collection, vector_backend, video_hash FROM context_frames WHERE promotion_status IN ('staged', 'validated')"
        params_sync = []
        if video_hash:
            query_sync += " AND video_hash = ?"
            params_sync.append(video_hash)
        if epoch_id:
            query_sync += " AND epoch_id = ?"
            params_sync.append(epoch_id)
        cursor = conn.execute(query_sync, tuple(params_sync))
        frames_to_sync = cursor.fetchall()
        conn.close()

        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient
        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()
        rejected_count = client.mark_frames_rejected(
            reason=reason,
            video_hash=video_hash,
            epoch_id=epoch_id,
        )
        client.close()
        
        frames_for_sync = [(f[0], f[1], f[2]) for f in frames_to_sync]
        qdrant_sync = self._sync_ucf_status_to_qdrant(frames_for_sync, "rejected")
        scope_sync = self._sync_qdrant_by_scope(epoch_id=epoch_id or "", status_val="rejected", video_hash=video_hash)
        
        # Dematerialize active views
        affected_video_hashes = set()
        if video_hash:
            affected_video_hashes.add(video_hash)
        else:
            for f in frames_to_sync:
                if len(f) > 3 and f[3]:
                    affected_video_hashes.add(f[3])
        for vh in affected_video_hashes:
            self._dematerialize_active_views(video_hash=vh)

        res = {
            "rejected_count": rejected_count,
            "status": "rejected_complete",
            "reason": reason,
            "qdrant_sync": qdrant_sync,
            "scope_sync": scope_sync,
        }
        if qdrant_sync["status"] == "warning":
            res["warnings"] = ["qdrant_payload_sync_failed"]
        return res

    def _execute_supersede_ucf_frames(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Transitions in-scope context frames from 'promoted' or 'validated' to 'superseded'.

        Used when a previously promoted epoch is replaced by a new ingestion run.
        'staged' and 'rejected' frames cannot be superseded — staged frames must
        first be explicitly validated or rejected, and rejected frames are terminal.

        Superseded frames cannot be promoted.

        Expected lifecycle: promoted | validated -> [supersede_ucf_frames] -> superseded
        """
        ucf_db_path = self._get_ucf_db_path()
        video_hash = args.get("video_hash") or args.get("video_id")
        epoch_id = args.get("epoch_id")
        
        # Query vector_key, vector_collection, vector_backend, video_hash for frames to be superseded before updating
        import sqlite3
        conn = sqlite3.connect(str(ucf_db_path))
        query_sync = "SELECT vector_key, vector_collection, vector_backend, video_hash FROM context_frames WHERE promotion_status IN ('promoted', 'validated')"
        params_sync = []
        if video_hash:
            query_sync += " AND video_hash = ?"
            params_sync.append(video_hash)
        if epoch_id:
            query_sync += " AND epoch_id = ?"
            params_sync.append(epoch_id)
        cursor = conn.execute(query_sync, tuple(params_sync))
        frames_to_sync = cursor.fetchall()
        conn.close()

        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient
        client = UCFLedgerClient(str(ucf_db_path))
        client.init_schema()
        superseded_count = client.mark_frames_superseded(
            video_hash=video_hash,
            epoch_id=epoch_id,
        )
        client.close()
        
        frames_for_sync = [(f[0], f[1], f[2]) for f in frames_to_sync]
        qdrant_sync = self._sync_ucf_status_to_qdrant(frames_for_sync, "superseded")
        scope_sync = self._sync_qdrant_by_scope(epoch_id=epoch_id or "", status_val="superseded", video_hash=video_hash)
        
        # Dematerialize active views
        affected_video_hashes = set()
        if video_hash:
            affected_video_hashes.add(video_hash)
        else:
            for f in frames_to_sync:
                if len(f) > 3 and f[3]:
                    affected_video_hashes.add(f[3])
        for vh in affected_video_hashes:
            self._dematerialize_active_views(video_hash=vh)

        res = {
            "superseded_count": superseded_count,
            "status": "superseded_complete",
            "qdrant_sync": qdrant_sync,
            "scope_sync": scope_sync,
        }
        if qdrant_sync["status"] == "warning":
            res["warnings"] = ["qdrant_payload_sync_failed"]
        return res

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

        ucf_status_filter = args.get("ucf_status_filter")  # "promoted"|"rejected"|"superseded"|None
        ucf_include_terminal = args.get("ucf_include_terminal", False)

        VALID_UCF_FILTERS = {"promoted", "rejected", "superseded"}

        if ucf_status_filter is not None and ucf_status_filter not in VALID_UCF_FILTERS:
            return {
                "status": "error",
                "reason": "invalid_ucf_status_filter",
                "message": f"ucf_status_filter must be one of {sorted(VALID_UCF_FILTERS)}, got '{ucf_status_filter}'",
            }

        payload_filter = args.get("payload_filter") or {}
        # Ensure payload_filter is a copy to avoid mutating source args
        import copy
        payload_filter = copy.deepcopy(payload_filter)

        if ucf_status_filter:
            # Explicit exact-match; suppress default exclusion
            payload_filter.setdefault("must", []).append(
                {"key": "ucf_promotion_status", "match": {"value": ucf_status_filter}}
            )
        elif not ucf_include_terminal:
            # Default: exclude explicitly rejected or superseded frames
            payload_filter.setdefault("must_not", []).extend([
                {"key": "ucf_promotion_status", "match": {"value": "rejected"}},
                {"key": "ucf_promotion_status", "match": {"value": "superseded"}},
            ])
        
        q_client = build_qdrant_client(self.config, dim=len(vector), key=key)
        if not q_client:
            raise RuntimeError("Qdrant client could not be built from config")
            
        hits = q_client.query(vector, top_k=top_k, payload_filter=payload_filter)
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
