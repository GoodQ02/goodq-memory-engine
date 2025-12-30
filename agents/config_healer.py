"""
GoodQ4All Config Auto-Healer - Phase 2: Autonomous Recovery
============================================================

Extends Control Agent with the ability to modify configs and auto-recover
from known failure patterns.

Author: GoodQ4All Team
Version: 1.0.0
Date: 2025-11-16
"""

import json
import shutil
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.llm_client import LLMClient, ModelConfig


def _split_base_and_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(f"Invalid LLM URL: {url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.scheme}://{parsed.hostname}", port


def _build_llm_models(cfg: Dict[str, Any]) -> List[ModelConfig]:
    llm_cfg = cfg.get("llm", {}) or {}
    vllm_url = llm_cfg.get("vllm_url")
    ollama_url = llm_cfg.get("ollama_url")
    if not vllm_url or not ollama_url:
        raise ValueError("Missing llm.vllm_url or llm.ollama_url in config")

    vllm_base, vllm_port = _split_base_and_port(str(vllm_url))
    ollama_base, ollama_port = _split_base_and_port(str(ollama_url))

    vllm_model_id = llm_cfg.get(
        "vllm_model",
        "/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct",
    )
    ollama_model_id = llm_cfg.get("ollama_model", "phi4")

    return [
        ModelConfig(
            name="Llama-1B-Speed",
            base_url=vllm_base,
            port=vllm_port,
            model_id=vllm_model_id,
            backend="vllm",
            vram_gb=2.3,
            tokens_per_sec=178,
            context_length=131072,
            capabilities=["chat", "fast"],
            priority=100,
        ),
        ModelConfig(
            name="Phi4-Ollama",
            base_url=ollama_base,
            port=ollama_port,
            model_id=ollama_model_id,
            backend="ollama",
            vram_gb=8.4,
            tokens_per_sec=70,
            context_length=16384,
            capabilities=["chat", "fallback", "quality"],
            priority=90,
        ),
    ]


class ConfigHealer:
    """
    Autonomous config healing and optimization
    
    Responsibilities:
    - Parse error logs and identify root causes
    - Generate config patches based on LLM recommendations
    - Apply safe config modifications with backups
    - Track healing success rates
    - Learn optimal recovery strategies
    """
    
    # Known error patterns and their healing strategies
    HEALING_RULES = {
        "CUDA out of memory": {
            "actions": ["reduce_batch_size", "switch_to_cpu", "use_smaller_model"],
            "priority": "high",
            "auto_apply": True
        },
        "No audio stream found": {
            "actions": ["skip_audio_step", "mark_as_silent"],
            "priority": "medium",
            "auto_apply": True
        },
        "Connection timeout": {
            "actions": ["increase_timeout", "enable_retry"],
            "priority": "medium",
            "auto_apply": False  # Ask LLM first
        },
        "PyAnnote.*failed": {
            "actions": ["increase_warmup_delay", "switch_to_cpu_diarization", "skip_diarization"],
            "priority": "medium",
            "auto_apply": False
        },
        "Whisper.*RuntimeError": {
            "actions": ["use_smaller_whisper_model", "reduce_audio_chunk_size"],
            "priority": "high",
            "auto_apply": True
        }
    }
    
    def __init__(self, config_dir: Path = None, llm_client: LLMClient = None):
        """Initialize Config Healer"""
        self.root = Path(__file__).parent.parent
        self.config_dir = config_dir or self.root / "configs"
        if llm_client is None:
            raise ValueError("ConfigHealer requires an injected llm_client")
        self.llm = llm_client
        
        # Backup directory for config safety
        self.backup_dir = self.root / "data" / "config_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Load current configs
        self.config_path = self.config_dir / "config.yaml"
        self.gpu_config_path = None
        
        print("[CONFIG HEALER] Initialized")
        print(f"   Config: {self.config_path}")
        print(f"   Backup: {self.backup_dir}")
    
    def diagnose_error(self, error_log: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to diagnose error and suggest healing actions
        
        Args:
            error_log: The error message/stack trace
            context: Additional context (step name, GPU stats, etc.)
            
        Returns:
            Dictionary with diagnosis and recommended actions
        """
        # Check for known patterns first
        for pattern, rule in self.HEALING_RULES.items():
            if pattern.lower() in error_log.lower():
                return {
                    "pattern_matched": pattern,
                    "rule": rule,
                    "needs_llm": not rule["auto_apply"]
                }
        
        # Unknown error - ask LLM
        prompt = self._build_diagnostic_prompt(error_log, context)
        
        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": "You are a pipeline debugging expert. Analyze errors and suggest specific config changes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more deterministic diagnosis
                max_tokens=500
            )
            
            llm_diagnosis = ""
            if isinstance(response, dict):
                llm_diagnosis = response.get("content") or ""
                if not llm_diagnosis:
                    choices = response.get("choices") or []
                    if choices and isinstance(choices, list):
                        llm_diagnosis = (
                            (choices[0].get("message") or {}).get("content", "")
                        )
            else:
                llm_diagnosis = str(response)
            
            return {
                "pattern_matched": None,
                "llm_diagnosis": llm_diagnosis,
                "needs_manual_review": True
            }
            
        except Exception as e:
            print(f"[WARN]  LLM diagnosis failed: {e}")
            return {
                "pattern_matched": None,
                "error": str(e),
                "needs_manual_review": True
            }
    
    def _build_diagnostic_prompt(self, error_log: str, context: Dict[str, Any]) -> str:
        """Build LLM prompt for error diagnosis"""
        return f"""Analyze this pipeline error and suggest specific configuration changes:

ERROR LOG:
{error_log}

CONTEXT:
- Step: {context.get('step_name', 'Unknown')}
- GPU Memory: {context.get('gpu_memory_mb', 'Unknown')} MB
- File Size: {context.get('file_size_mb', 'Unknown')} MB
- Duration: {context.get('duration_sec', 'Unknown')} seconds

AVAILABLE CONFIG OPTIONS:
- Batch size adjustment
- Model switching (e.g., whisper-large → whisper-base)
- CPU/GPU toggling
- Timeout values
- Memory limits
- Retry policies

Provide:
1. Root cause analysis (2-3 sentences)
2. Specific config parameter to change
3. Recommended new value
4. Confidence level (high/medium/low)

Format your response as:
ROOT CAUSE: ...
CONFIG CHANGE: parameter_name = new_value
CONFIDENCE: high/medium/low
"""
    
    def apply_healing_action(self, action: str, error_context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Apply a specific healing action to the config
        
        Args:
            action: The healing action to apply
            error_context: Context about the error
            
        Returns:
            (success, message) tuple
        """
        # Backup config first
        backup_path = self._backup_config()
        
        try:
            if action == "reduce_batch_size":
                return self._reduce_batch_size()
            elif action == "switch_to_cpu":
                return self._switch_to_cpu(error_context.get("step_name"))
            elif action == "use_smaller_model":
                return self._use_smaller_model(error_context.get("step_name"))
            elif action == "increase_timeout":
                return self._increase_timeout()
            elif action == "skip_audio_step":
                return self._skip_step("audio_extraction")
            elif action == "mark_as_silent":
                return self._mark_as_silent()
            elif action == "increase_warmup_delay":
                return self._increase_warmup_delay()
            elif action == "switch_to_cpu_diarization":
                return self._switch_to_cpu("diarization")
            elif action == "use_smaller_whisper_model":
                return self._use_smaller_whisper()
            else:
                return False, f"Unknown action: {action}"
                
        except Exception as e:
            # Restore backup on failure
            shutil.copy(backup_path, self.config_path)
            return False, f"Healing failed, config restored: {e}"
    
    def _backup_config(self) -> Path:
        """Create timestamped backup of current config"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"config_open.yaml.backup_{timestamp}"
        shutil.copy(self.config_path, backup_path)
        return backup_path
    
    def _load_config(self) -> Dict[str, Any]:
        """Load current config"""
        with open(self.config_path) as f:
            return yaml.safe_load(f)
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save config with pretty formatting"""
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    # ========== Healing Actions ==========
    
    def _reduce_batch_size(self) -> Tuple[bool, str]:
        """Reduce batch size by 50%"""
        config = self._load_config()
        
        # Find batch size settings
        modified = False
        if "processing" in config and "batch_size" in config["processing"]:
            old_size = config["processing"]["batch_size"]
            new_size = max(1, old_size // 2)
            config["processing"]["batch_size"] = new_size
            modified = True
            msg = f"Reduced batch size: {old_size} → {new_size}"
        
        if modified:
            self._save_config(config)
            return True, msg
        return False, "No batch_size found in config"
    
    def _switch_to_cpu(self, step_name: Optional[str] = None) -> Tuple[bool, str]:
        """Switch specified step (or all) to CPU"""
        config = self._load_config()
        
        if step_name:
            # Switch specific step
            if "steps" in config and step_name in config["steps"]:
                config["steps"][step_name]["device"] = "cpu"
                self._save_config(config)
                return True, f"Switched {step_name} to CPU"
        else:
            # Switch all to CPU
            if "processing" in config:
                config["processing"]["device"] = "cpu"
                self._save_config(config)
                return True, "Switched all processing to CPU"
        
        return False, f"Could not switch {step_name or 'all'} to CPU"
    
    def _use_smaller_model(self, step_name: Optional[str] = None) -> Tuple[bool, str]:
        """Downgrade model size"""
        config = self._load_config()
        
        # Model downgrade mappings
        downgrades = {
            "whisper-large": "whisper-medium",
            "whisper-medium": "whisper-base",
            "whisper-base": "whisper-tiny"
        }
        
        modified = False
        msg = []
        
        if "models" in config:
            for key, value in config["models"].items():
                if isinstance(value, str) and value in downgrades:
                    old_model = value
                    new_model = downgrades[value]
                    config["models"][key] = new_model
                    modified = True
                    msg.append(f"{key}: {old_model} → {new_model}")
        
        if modified:
            self._save_config(config)
            return True, "Downgraded models: " + ", ".join(msg)
        return False, "No models to downgrade"
    
    def _use_smaller_whisper(self) -> Tuple[bool, str]:
        """Specifically downgrade Whisper model"""
        config = self._load_config()
        
        if "models" in config and "whisper" in config["models"]:
            current = config["models"]["whisper"]
            downgrades = {
                "large-v3": "medium",
                "large-v2": "medium",
                "large": "medium",
                "medium": "base",
                "base": "tiny"
            }
            
            new_model = downgrades.get(current)
            if new_model:
                config["models"]["whisper"] = new_model
                self._save_config(config)
                return True, f"Whisper model: {current} → {new_model}"
        
        return False, "Could not downgrade Whisper model"
    
    def _increase_timeout(self) -> Tuple[bool, str]:
        """Increase timeout by 50%"""
        config = self._load_config()
        
        if "processing" in config and "timeout_sec" in config["processing"]:
            old_timeout = config["processing"]["timeout_sec"]
            new_timeout = int(old_timeout * 1.5)
            config["processing"]["timeout_sec"] = new_timeout
            self._save_config(config)
            return True, f"Timeout: {old_timeout}s → {new_timeout}s"
        
        return False, "No timeout setting found"
    
    def _skip_step(self, step_name: str) -> Tuple[bool, str]:
        """Mark step as skippable"""
        config = self._load_config()
        
        if "steps" not in config:
            config["steps"] = {}
        if step_name not in config["steps"]:
            config["steps"][step_name] = {}
        
        config["steps"][step_name]["skip_on_error"] = True
        self._save_config(config)
        return True, f"Step {step_name} now skips on error"
    
    def _mark_as_silent(self) -> Tuple[bool, str]:
        """Mark file as silent (no audio processing needed)"""
        config = self._load_config()
        
        if "processing" not in config:
            config["processing"] = {}
        
        config["processing"]["assume_silent"] = True
        self._save_config(config)
        return True, "Audio will be treated as silent"
    
    def _increase_warmup_delay(self) -> Tuple[bool, str]:
        """Increase model warmup delay"""
        config = self._load_config()
        
        if "models" not in config:
            config["models"] = {}
        if "warmup_delay_sec" not in config["models"]:
            config["models"]["warmup_delay_sec"] = 5
        
        old_delay = config["models"]["warmup_delay_sec"]
        new_delay = old_delay + 3
        config["models"]["warmup_delay_sec"] = new_delay
        self._save_config(config)
        
        return True, f"Warmup delay: {old_delay}s → {new_delay}s"
    
    def auto_heal(self, error_log: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automatically diagnose and heal if safe
        
        Returns:
            Report of actions taken
        """
        diagnosis = self.diagnose_error(error_log, context)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "diagnosis": diagnosis,
            "actions_taken": [],
            "success": False
        }
        
        # If pattern matched and auto-apply is safe
        if diagnosis.get("pattern_matched") and not diagnosis.get("needs_llm"):
            rule = diagnosis["rule"]
            
            for action in rule["actions"]:
                success, message = self.apply_healing_action(action, context)
                
                report["actions_taken"].append({
                    "action": action,
                    "success": success,
                    "message": message
                })
                
                if success:
                    report["success"] = True
                    print(f"[PASS] Healing applied: {message}")
                    break  # Try one action at a time
                else:
                    print(f"[FAIL] Healing failed: {message}")
        
        # If needs LLM review
        elif diagnosis.get("needs_manual_review") or diagnosis.get("needs_llm"):
            report["recommendation"] = diagnosis.get("llm_diagnosis", "Manual review needed")
            print(f"[SYMBOL] Manual review recommended")
            if "llm_diagnosis" in diagnosis:
                print(f"   LLM says: {diagnosis['llm_diagnosis'][:200]}...")
        
        return report


def main():
    """Test the Config Healer"""
    from steps.common.config_loader import load_configs

    cfg = load_configs({})
    models = _build_llm_models(cfg)
    llm = LLMClient(
        models=models,
        health_check_interval=60,
        max_retries=3,
        timeout=30,
        cache_ttl=300,
        enable_health_checks=False,
    )
    healer = ConfigHealer(llm_client=llm)
    
    # Test error scenarios
    test_errors = [
        {
            "log": "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB",
            "context": {"step_name": "whisper", "gpu_memory_mb": 15000}
        },
        {
            "log": "ValueError: No audio stream found in file",
            "context": {"step_name": "audio_extraction", "file_size_mb": 500}
        }
    ]
    
    for i, test in enumerate(test_errors, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}: {test['log'][:50]}...")
        print(f"{'='*60}")
        
        report = healer.auto_heal(test["log"], test["context"])
        
        print(f"\n[SYMBOL] Healing Report:")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
