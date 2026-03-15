"""Focused integrity harness for WSL2 bridge masking seams."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import uuid

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wsl2_audio_bridge import WSL2AudioBridge


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class WSL2BridgeIntegrityTests(unittest.TestCase):
    TEST_UUID = "11111111-1111-1111-1111-111111111111"

    def _make_bridge(self) -> WSL2AudioBridge:
        bridge = WSL2AudioBridge()
        bridge._ensure_workspace_ready = lambda: True  # type: ignore[assignment]
        bridge.wsl_distro = "Ubuntu-22.04"
        bridge.audio_workspace = "/home/testuser/goodq_audio"
        return bridge

    def _make_scene_file(self, name: str) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="goodq_bridge_test_"))
        scene_file = tmp_dir / name
        scene_file.write_bytes(b"RIFF")
        return scene_file

    def test_nonzero_returncode_never_reports_success_with_stale_result(self) -> None:
        scene_file = self._make_scene_file("scene_0004.wav")
        bridge = self._make_bridge()

        def fake_run(cmd, capture_output=True, text=True, timeout=None):  # noqa: ANN001
            cmd_str = " ".join(str(part) for part in cmd)
            if "from torchvision.ops import nms" in cmd_str:
                return _Result(returncode=0, stdout="OK")
            if "process_audio.py" in cmd_str:
                return _Result(returncode=1, stderr="traceback: wsl process failed")
            if " cat " in f" {cmd_str} " and "result.json" in cmd_str:
                return _Result(
                    returncode=0,
                    stdout=f'{{"status":"success","audio_file":"/mnt/l/path/scene_0000.wav","request_uuid":"{self.TEST_UUID}"}}',
                )
            return _Result(returncode=0, stdout="")

        with patch("wsl2_audio_bridge.uuid.uuid4", return_value=uuid.UUID(self.TEST_UUID)), patch(
            "wsl2_audio_bridge.subprocess.run", side_effect=fake_run
        ):
            result = bridge.process_audio(str(scene_file), timeout=5)

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("bridge_error_reason"), "wsl_subprocess_nonzero")
        self.assertEqual(result.get("wsl_returncode"), 1)
        self.assertTrue(result.get("used_fallback_result_json"))
        self.assertEqual(result.get("requested_scene_file"), "scene_0004.wav")
        self.assertEqual(result.get("returned_scene_file"), "scene_0000.wav")
        self.assertEqual(result.get("requested_request_uuid"), self.TEST_UUID)
        self.assertEqual(result.get("returned_request_uuid"), self.TEST_UUID)

    def test_scene_mismatch_is_rejected(self) -> None:
        scene_file = self._make_scene_file("scene_0004.wav")
        bridge = self._make_bridge()

        def fake_run(cmd, capture_output=True, text=True, timeout=None):  # noqa: ANN001
            cmd_str = " ".join(str(part) for part in cmd)
            if "from torchvision.ops import nms" in cmd_str:
                return _Result(returncode=0, stdout="OK")
            if "process_audio.py" in cmd_str:
                return _Result(
                    returncode=0,
                    stdout=f'{{"status":"success","audio_file":"/mnt/l/path/scene_0000.wav","transcription":"hello","request_uuid":"{self.TEST_UUID}"}}',
                )
            if "stat -c %Y" in cmd_str:
                return _Result(returncode=0, stdout=str(int(time.time())))
            return _Result(returncode=0, stdout="")

        with patch("wsl2_audio_bridge.uuid.uuid4", return_value=uuid.UUID(self.TEST_UUID)), patch(
            "wsl2_audio_bridge.subprocess.run", side_effect=fake_run
        ):
            result = bridge.process_audio(str(scene_file), timeout=5)

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("bridge_error_reason"), "stale_or_mismatched_result")
        self.assertEqual(result.get("requested_scene_file"), "scene_0004.wav")
        self.assertEqual(result.get("returned_scene_file"), "scene_0000.wav")
        self.assertFalse(result.get("used_fallback_result_json"))
        self.assertEqual(result.get("wsl_returncode"), 0)
        self.assertEqual(result.get("requested_request_uuid"), self.TEST_UUID)
        self.assertEqual(result.get("returned_request_uuid"), self.TEST_UUID)

    def test_result_json_freshness_probe_retries_once(self) -> None:
        scene_file = self._make_scene_file("scene_0004.wav")
        bridge = self._make_bridge()
        stat_calls = {"count": 0}

        def fake_run(cmd, capture_output=True, text=True, timeout=None):  # noqa: ANN001
            cmd_str = " ".join(str(part) for part in cmd)
            if "from torchvision.ops import nms" in cmd_str:
                return _Result(returncode=0, stdout="OK")
            if "process_audio.py" in cmd_str:
                return _Result(
                    returncode=0,
                    stdout=(
                        f'{{"status":"success","audio_file":"/mnt/l/path/scene_0004.wav",'
                        f'"transcription":"hello","request_uuid":"{self.TEST_UUID}"}}'
                    ),
                )
            if "stat -c %Y" in cmd_str:
                stat_calls["count"] += 1
                if stat_calls["count"] == 1:
                    return _Result(returncode=1, stderr="stat: cannot stat result.json")
                return _Result(returncode=0, stdout=str(int(time.time())))
            return _Result(returncode=0, stdout="")

        with patch("wsl2_audio_bridge.uuid.uuid4", return_value=uuid.UUID(self.TEST_UUID)), patch(
            "wsl2_audio_bridge.subprocess.run", side_effect=fake_run
        ):
            result = bridge.process_audio(str(scene_file), timeout=5)

        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("requested_scene_file"), "scene_0004.wav")
        self.assertEqual(result.get("returned_scene_file"), "scene_0004.wav")
        self.assertEqual(result.get("requested_request_uuid"), self.TEST_UUID)
        self.assertEqual(result.get("returned_request_uuid"), self.TEST_UUID)
        self.assertEqual(stat_calls["count"], 2)
        self.assertIn("result_json_freshness_probe_retried", result.get("stderr_warnings", []))

    def test_abi_gate_fails_early_and_returns_fix_command(self) -> None:
        scene_file = self._make_scene_file("scene_0004.wav")
        bridge = self._make_bridge()

        def fake_run(cmd, capture_output=True, text=True, timeout=None):  # noqa: ANN001
            cmd_str = " ".join(str(part) for part in cmd)
            if "from torchvision.ops import nms" in cmd_str:
                return _Result(returncode=1, stderr="RuntimeError: operator torchvision::nms does not exist")
            if "md.version('torch')" in cmd_str:
                return _Result(returncode=0, stdout="2.8.0")
            if "md.version('torchvision')" in cmd_str:
                return _Result(returncode=0, stdout="0.20.1+cu121")
            if "md.version('torchaudio')" in cmd_str:
                return _Result(returncode=0, stdout="2.8.0")
            if "process_audio.py" in cmd_str:
                self.fail("process_audio.py should not be called when ABI preflight fails")
            return _Result(returncode=0, stdout="")

        with patch("wsl2_audio_bridge.uuid.uuid4", return_value=uuid.UUID(self.TEST_UUID)), patch(
            "wsl2_audio_bridge.subprocess.run", side_effect=fake_run
        ):
            result = bridge.process_audio(str(scene_file), timeout=5)

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("bridge_error_reason"), "wsl_env_abi_mismatch")
        self.assertEqual(result.get("wsl_returncode"), 1)
        self.assertEqual(result.get("requested_scene_file"), "scene_0004.wav")
        self.assertEqual(result.get("requested_request_uuid"), self.TEST_UUID)
        self.assertFalse(result.get("used_fallback_result_json"))
        details = result.get("bridge_error_details") or {}
        versions = details.get("detected_versions") or {}
        self.assertEqual(versions.get("torch"), "2.8.0")
        self.assertEqual(versions.get("torchvision"), "0.20.1+cu121")
        self.assertEqual(versions.get("torchaudio"), "2.8.0")
        self.assertEqual(
            details.get("recommended_install_command"),
            "pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128",
        )


if __name__ == "__main__":
    unittest.main()
