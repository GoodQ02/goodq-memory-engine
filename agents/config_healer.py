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

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.llm_client import LLMClient
from steps.common.llm_model_factory import build_llm_models

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
            step_name = error_context.get("step_name") or error_context.get("step")

            if action == "reduce_batch_size":
                return self._reduce_batch_size()
            elif action in {"switch_to_cpu", "fallback_to_cpu"}:
                return self._switch_to_cpu(step_name)
            elif action in {"use_smaller_model", "downgrade_model"}:
                return self._use_smaller_model(step_name, target_model=error_context.get("to_model"))
            elif action == "fallback_local_model":
                return self._use_smaller_model(step_name, target_model=error_context.get("to_model"))
            elif action == "increase_timeout":
                return self._increase_timeout()
            elif action in {"skip_audio_step", "skip_step", "skip_missing_file"}:
                return self._skip_step(step_name or "audio_extraction")
            elif action == "partition_audio":
                return self._partition_audio(error_context)
            elif action in {"enable_retry", "retry_with_backoff"}:
                return self._enable_retry(error_context)
            elif action == "adjust_thresholds":
                return self._adjust_thresholds(error_context)
            elif action == "skip_diarization":
                return self._skip_step("diarization")
            elif action == "skip_audio_steps":
                return self._skip_step("audio_extraction")
            elif action == "mark_as_silent":
                return self._mark_as_silent()
            elif action == "increase_warmup_delay":
                return self._increase_warmup_delay()
            elif action == "switch_to_cpu_diarization":
                return self._switch_to_cpu("diarization")
            elif action == "use_smaller_whisper_model":
                return self._use_smaller_whisper(error_context.get("to_model"))
            else:
                return False, f"Unknown action: {action}"
                
        except Exception as e:
            # Restore backup on failure
            shutil.copy(backup_path, self.config_path)
            return False, f"Healing failed, config restored: {e}"
    
    def _backup_config(self) -> Path:
        """Create timestamped backup of current config"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{self.config_path.name}.backup_{timestamp}"
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

    @staticmethod
    def _get_nested(config: Dict[str, Any], path: List[str], default: Any = None) -> Any:
        current: Any = config
        for part in path:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    @staticmethod
    def _set_nested(config: Dict[str, Any], path: List[str], value: Any) -> bool:
        current: Dict[str, Any] = config
        for part in path[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                current[part] = next_value
            current = next_value
        old_value = current.get(path[-1])
        current[path[-1]] = value
        return old_value != value
    
    # ========== Healing Actions ==========
    
    def _reduce_batch_size(self) -> Tuple[bool, str]:
        """Reduce batch size by 50%"""
        config = self._load_config()

        candidate_paths = [
            ["segmentation", "phase5", "batch_size"],
            ["pipeline", "batch_size"],
            ["processing", "batch_size"],
        ]

        changes: List[str] = []
        modified = False
        for path in candidate_paths:
            old_size = self._get_nested(config, path)
            if isinstance(old_size, (int, float)) and old_size > 1:
                new_size = max(1, int(old_size) // 2)
                modified = self._set_nested(config, path, new_size) or modified
                changes.append(f"{'.'.join(path)}: {old_size} -> {new_size}")

        if modified:
            self._save_config(config)
            return True, "Reduced batch size: " + ", ".join(changes)
        return False, "No adjustable batch_size found in config"
    
    def _switch_to_cpu(self, step_name: Optional[str] = None) -> Tuple[bool, str]:
        """Switch specified step (or all) to CPU"""
        config = self._load_config()

        targets = []
        normalized = (step_name or "").strip().lower()
        if normalized in {"diarization", "audio_diarize", "phase2"}:
            targets.append((["segmentation", "phase2", "device"], "cpu"))
        elif normalized in {"scene_detection", "video_scene_detect", "phase5"}:
            targets.append((["segmentation", "phase5", "use_gpu"], False))
        elif normalized in {"all", ""}:
            targets.extend(
                [
                    (["segmentation", "phase2", "device"], "cpu"),
                    (["segmentation", "phase5", "use_gpu"], False),
                    (["gpu", "enabled"], False),
                ]
            )
        else:
            targets.extend(
                [
                    (["segmentation", "phase2", "device"], "cpu"),
                    (["segmentation", "phase5", "use_gpu"], False),
                    (["gpu", "enabled"], False),
                ]
            )

        changes: List[str] = []
        modified = False
        for path, value in targets:
            changed = self._set_nested(config, path, value)
            modified = changed or modified
            if changed:
                changes.append(f"{'.'.join(path)}={value}")

        if modified:
            self._save_config(config)
            return True, f"Switched {step_name or 'processing'} to CPU-safe mode ({', '.join(changes)})"

        return False, f"No CPU fallback change applied for {step_name or 'processing'}"

    def _use_smaller_model(self, step_name: Optional[str] = None, target_model: Optional[str] = None) -> Tuple[bool, str]:
        """Downgrade model size"""
        config = self._load_config()

        normalized = (step_name or "").strip().lower()
        if normalized in {"transcription", "whisper", "audio_transcribe", "phase4", ""}:
            return self._use_smaller_whisper(target_model)

        return False, f"No smaller-model mapping is defined for {step_name or 'unspecified step'}"

    def _use_smaller_whisper(self, target_model: Optional[str] = None) -> Tuple[bool, str]:
        """Specifically downgrade Whisper model"""
        config = self._load_config()

        current = self._get_nested(config, ["segmentation", "phase4", "whisper_model"])
        if not isinstance(current, str):
            return False, "Could not locate segmentation.phase4.whisper_model"

        downgrades = {
            "large-v3": "medium",
            "large-v2": "medium",
            "large": "medium",
            "medium": "base",
            "base": "tiny",
        }

        new_model = target_model or downgrades.get(current)
        if not new_model or new_model == current:
            return False, f"Could not downgrade Whisper model from {current}"

        self._set_nested(config, ["segmentation", "phase4", "whisper_model"], new_model)
        self._save_config(config)
        return True, f"Whisper model: {current} -> {new_model}"
    
    def _increase_timeout(self) -> Tuple[bool, str]:
        """Increase timeout by 50%"""
        config = self._load_config()

        candidate_paths = [
            ["segmentation", "phase4", "chunk_timeout"],
            ["segmentation", "phase4", "diarize_timeout"],
            ["processing", "timeout_sec"],
        ]
        changes: List[str] = []
        modified = False
        for path in candidate_paths:
            old_timeout = self._get_nested(config, path)
            if isinstance(old_timeout, (int, float)) and old_timeout > 0:
                new_timeout = int(float(old_timeout) * 1.5)
                modified = self._set_nested(config, path, new_timeout) or modified
                changes.append(f"{'.'.join(path)}: {old_timeout}s -> {new_timeout}s")

        if modified:
            self._save_config(config)
            return True, "Timeouts increased: " + ", ".join(changes)

        return False, "No timeout setting found"
    
    def _skip_step(self, step_name: str) -> Tuple[bool, str]:
        """Mark step as skippable"""
        config = self._load_config()

        normalized = (step_name or "").strip().lower()
        mapped_paths = {
            "transcription": ["segmentation", "phase4", "enable_transcription"],
            "audio_transcribe": ["segmentation", "phase4", "enable_transcription"],
            "diarization": ["segmentation", "phase4", "enable_diarization"],
            "audio_diarize": ["segmentation", "phase4", "enable_diarization"],
            "embeddings": ["segmentation", "phase4", "enable_embeddings"],
            "audio_embed": ["segmentation", "phase4", "enable_embeddings"],
            "emotion": ["segmentation", "phase4", "enable_emotion"],
            "audio_emotion": ["segmentation", "phase4", "enable_emotion"],
            "music_detection": ["segmentation", "phase4", "enable_music_detection"],
            "audio_music_events": ["segmentation", "phase4", "enable_music_detection"],
        }

        path = mapped_paths.get(normalized)
        if path:
            changed = self._set_nested(config, path, False)
            if changed:
                self._save_config(config)
            return (True, f"Disabled {normalized} via {'.'.join(path)}") if changed else (False, f"{normalized} already disabled")

        if "steps" not in config:
            config["steps"] = {}
        if step_name not in config["steps"]:
            config["steps"][step_name] = {}

        changed = self._set_nested(config, ["steps", step_name, "skip_on_error"], True)
        if changed:
            self._save_config(config)
        return (True, f"Step {step_name} now skips on error") if changed else (False, f"Step {step_name} already skips on error")
    
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

        old_delay = self._get_nested(config, ["segmentation", "phase4", "warmup_delay_sec"], 5)
        new_delay = int(old_delay) + 3
        self._set_nested(config, ["segmentation", "phase4", "warmup_delay_sec"], new_delay)
        self._save_config(config)

        return True, f"Warmup delay: {old_delay}s -> {new_delay}s"

    def _enable_retry(self, error_context: Dict[str, Any]) -> Tuple[bool, str]:
        """Enable bounded pipeline retry behavior."""
        config = self._load_config()
        max_retries = int(error_context.get("max_retries") or 3)

        changed = False
        changed = self._set_nested(config, ["pipeline", "retry_on_failure"], True) or changed
        changed = self._set_nested(config, ["pipeline", "max_retries"], max_retries) or changed

        if changed:
            self._save_config(config)
            return True, f"Enabled retry with pipeline.max_retries={max_retries}"
        return False, "Retry policy already enabled with requested settings"

    def _adjust_thresholds(self, error_context: Dict[str, Any]) -> Tuple[bool, str]:
        """Lower scene-detection thresholds when an empty scene result indicates under-detection."""
        config = self._load_config()
        step_name = str(error_context.get("step_name") or error_context.get("step") or "").strip().lower()
        error_text = str(error_context.get("error_text") or error_context.get("error") or "").lower()

        scene_step_names = {"scene_detect", "video_scene_detect", "scene_detection"}
        scene_error = "no scenes detected" in error_text
        if step_name not in scene_step_names and not scene_error:
            return False, f"No bounded threshold adjustment is defined for {step_name or 'unspecified step'}"

        candidate_paths = [
            ["video", "scene_threshold"],
            ["scene_detect", "threshold"],
        ]
        changes: List[str] = []
        modified = False
        for path in candidate_paths:
            current = self._get_nested(config, path)
            if isinstance(current, (int, float)) and current > 5.0:
                new_value = max(5.0, round(float(current) * 0.9, 2))
                modified = self._set_nested(config, path, new_value) or modified
                changes.append(f"{'.'.join(path)}: {current} -> {new_value}")

        if modified:
            self._save_config(config)
            return True, "Adjusted scene-detection thresholds: " + ", ".join(changes)
        return False, "No adjustable scene-detection thresholds found"

    def _partition_audio(self, error_context: Dict[str, Any]) -> Tuple[bool, str]:
        """Tune chunking to favor smaller diarization workloads."""
        config = self._load_config()

        chunk_minutes = error_context.get("chunk_size") or error_context.get("chunk_size_minutes") or 15
        try:
            chunk_minutes = float(chunk_minutes)
        except (TypeError, ValueError):
            chunk_minutes = 15.0
        chunk_minutes = max(1.0, min(chunk_minutes, 20.0))

        changed = False
        changed = self._set_nested(config, ["segmentation", "phase4", "chunk_size_minutes"], chunk_minutes) or changed
        changed = self._set_nested(config, ["segmentation", "phase4", "max_parallel_chunks"], 1) or changed

        if changed:
            self._save_config(config)
            return True, f"Enabled audio partitioning with {chunk_minutes:.0f} minute chunks and single-chunk concurrency"
        return False, "Audio partitioning already matched the requested safety settings"
    
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
    models = build_llm_models(cfg)
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
