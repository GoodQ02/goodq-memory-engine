from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from agents.config_healer import ConfigHealer
from agents.control_agent import ControlAgent
from agents.self_healing_monitor import SelfHealingMonitor


class _FakeRecoveryDb:
    def record_recovery_attempt(self, **kwargs):
        return 1


class _RecordingHealer:
    def __init__(self, success: bool = True, message: str = "ok"):
        self.success = success
        self.message = message
        self.calls = []

    def apply_healing_action(self, action: str, error_context: dict):
        self.calls.append((action, error_context))
        return self.success, self.message


def test_config_healer_enable_retry_updates_pipeline_retry_fields(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"pipeline": {"retry_on_failure": False, "max_retries": 1}}, sort_keys=False),
        encoding="utf-8",
    )

    healer = ConfigHealer(config_dir=config_dir, llm_client=object())

    success, _ = healer.apply_healing_action("enable_retry", {"max_retries": 5})

    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert success is True
    assert updated["pipeline"]["retry_on_failure"] is True
    assert updated["pipeline"]["max_retries"] == 5


def test_self_healing_monitor_delegates_supported_fixes_to_healer() -> None:
    healer = _RecordingHealer(success=True)
    monitor = SelfHealingMonitor({}, healer=healer)

    result = asyncio.run(
        monitor._apply_pattern_fix(
            {
                "workflow_id": "wf_001",
                "workflow_name": "diarization",
                "error": "CUDA out of memory",
                "result": {"failed_step": "diarization"},
            },
            {"fix_type": "fallback_to_cpu", "params": {}},
        )
    )

    assert result["success"] is True
    assert healer.calls == [("switch_to_cpu", {"step_name": "diarization"})]


def test_self_healing_monitor_refuses_unimplemented_fix_types() -> None:
    monitor = SelfHealingMonitor({}, healer=_RecordingHealer())

    result = asyncio.run(
        monitor._apply_pattern_fix(
            {
                "workflow_id": "wf_002",
                "workflow_name": "model_loader",
                "error": "model not found",
                "result": {"failed_step": "model_loader"},
            },
            {"fix_type": "download_model", "params": {}},
        )
    )

    assert result["success"] is False
    assert result["error"] == "No real healing action is mapped for fix_type=download_model"


def test_control_agent_attempt_recovery_delegates_known_strategy() -> None:
    healer = _RecordingHealer(success=True)
    agent = ControlAgent.__new__(ControlAgent)
    agent.healer = healer
    agent.recovery_db = _FakeRecoveryDb()

    success = agent.attempt_recovery(
        failure_id=1,
        strategy="switch_to_cpu",
        config_changes={"step_name": "diarization"},
    )

    assert success is True
    assert healer.calls == [("switch_to_cpu", {"step_name": "diarization"})]


def test_control_agent_attempt_recovery_rejects_unknown_strategy() -> None:
    healer = _RecordingHealer(success=True)
    agent = ControlAgent.__new__(ControlAgent)
    agent.healer = healer
    agent.recovery_db = _FakeRecoveryDb()

    success = agent.attempt_recovery(
        failure_id=1,
        strategy="download_model",
        config_changes={"step_name": "transcription"},
    )

    assert success is False
    assert healer.calls == []
