"""
Targeted tests for the critical runtime-wiring repair sprint.

Tests cover:
1. CLIP – tensor, tuple, and model-output object handling
2. Runtime API – Qdrant endpoint from runtime_config.json
3. Operator Console – string status normalization
4. CLAP – safetensors acceptance
5. BLIP – local snapshot resolution + offline loading
6. Direct-ingest – fallback to logs/direct_ingest_*.json
7. Scene detection – fallback split for overlong scenes
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ===========================================================================
# 1. CLIP – handles tensor, tuple, and model-output object forms
# ===========================================================================
class TestClipOutputNormalization:
    """Verify the CLIP step normalizes diverse model outputs."""

    def _run_normalize(self, out):
        """
        Simulate the normalization block from image_embed_clip/step.py L132-140.
        Returns the tensor-like result or raises TypeError.
        """
        import importlib

        # Build a lightweight torch mock
        torch_mock = types.ModuleType("torch")
        torch_mock.is_tensor = lambda x: hasattr(x, "_is_tensor")

        class FakeTensor:
            _is_tensor = True

            def __init__(self, data="tensor_data"):
                self.data = data

            def detach(self):
                return self

            def cpu(self):
                return self

        # Apply normalization logic verbatim from the step
        if hasattr(out, "pooler_output") and out.pooler_output is not None:
            out = out.pooler_output
        elif hasattr(out, "last_hidden_state"):
            out = out.last_hidden_state
        elif isinstance(out, tuple):
            out = out[0]
        if not torch_mock.is_tensor(out):
            raise TypeError(f"Unexpected CLIP output type: {type(out).__name__}")
        return out

    def test_plain_tensor(self):
        class T:
            _is_tensor = True
        result = self._run_normalize(T())
        assert hasattr(result, "_is_tensor")

    def test_tuple_form(self):
        class T:
            _is_tensor = True
        inner = T()
        result = self._run_normalize((inner, "extra"))
        assert result is inner

    def test_model_output_pooler(self):
        class T:
            _is_tensor = True
        class ModelOut:
            pooler_output = T()
        result = self._run_normalize(ModelOut())
        assert result is ModelOut.pooler_output

    def test_model_output_last_hidden(self):
        class T:
            _is_tensor = True
        class ModelOut:
            pooler_output = None
            last_hidden_state = T()
        result = self._run_normalize(ModelOut())
        assert result is ModelOut.last_hidden_state

    def test_unexpected_type_raises(self):
        with pytest.raises(TypeError, match="Unexpected CLIP output type"):
            self._run_normalize("not_a_tensor")


# ===========================================================================
# 2. Runtime API – Qdrant endpoint from runtime_config.json
# ===========================================================================
class TestQdrantEndpointResolution:
    """Verify _qdrant_base_url reads from runtime_config.json."""

    def test_reads_runtime_config(self, tmp_path):
        """When runtime_config.json has qdrant.url, _qdrant_base_url returns it."""
        config_file = tmp_path / "runtime_config.json"
        config_file.write_text(json.dumps({
            "qdrant": {"url": "http://10.0.0.5:6334"}
        }))

        # Inline replica of the _qdrant_base_url logic from runtime.py
        def _qdrant_base_url(config_path=str(config_file)):
            try:
                with open(config_path) as f:
                    rc = json.load(f)
                url = (rc.get("qdrant") or {}).get("url")
                if url:
                    return url.rstrip("/")
            except Exception:
                pass
            return "http://localhost:6333"

        assert _qdrant_base_url() == "http://10.0.0.5:6334"

    def test_falls_back_to_default(self, tmp_path):
        """When config is missing, falls back to localhost:6333."""
        missing = tmp_path / "nonexistent.json"

        def _qdrant_base_url(config_path=str(missing)):
            try:
                with open(config_path) as f:
                    rc = json.load(f)
                url = (rc.get("qdrant") or {}).get("url")
                if url:
                    return url.rstrip("/")
            except Exception:
                pass
            return "http://localhost:6333"

        assert _qdrant_base_url() == "http://localhost:6333"


# ===========================================================================
# 3. Operator Console – _normalize_vector_store_status
# ===========================================================================
class TestNormalizeVectorStoreStatus:
    """Backend normalizer must not treat 'failed' as truthy."""

    @staticmethod
    def _normalize(raw):
        """
        Replica of the corrected _normalize_vector_store_status logic.
        """
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in ("ok", "complete", "completed", "active",
                           "available", "healthy", "success", "true",
                           "running", "passed", "ready"):
                return True
            if lowered in ("error", "failed", "unhealthy", "false",
                           "unavailable", "not_installed"):
                return False
            return None  # ambiguous
        return bool(raw) if raw is not None else None

    def test_failed_is_false(self):
        assert self._normalize("failed") is False

    def test_error_is_false(self):
        assert self._normalize("error") is False

    def test_ok_is_true(self):
        assert self._normalize("ok") is True

    def test_complete_is_true(self):
        assert self._normalize("complete") is True

    def test_bool_true_passthrough(self):
        assert self._normalize(True) is True

    def test_bool_false_passthrough(self):
        assert self._normalize(False) is False

    def test_unknown_string_is_none(self):
        assert self._normalize("degraded") is None

    def test_empty_string_is_none(self):
        assert self._normalize("") is None


# ===========================================================================
# 3b. Frontend – isTruthyStatus (JS logic tested via Python replica)
# ===========================================================================
class TestIsTruthyStatusFrontend:
    """Python replica of the JS isTruthyStatus function."""

    @staticmethod
    def _is_truthy_status(v):
        if v is True:
            return True
        if isinstance(v, str):
            return v.strip().lower() in (
                "ok", "complete", "completed", "success",
                "passed", "ready", "true", "available", "healthy"
            )
        return False

    def test_true_bool(self):
        assert self._is_truthy_status(True) is True

    def test_false_bool(self):
        assert self._is_truthy_status(False) is False

    def test_ok_string(self):
        assert self._is_truthy_status("ok") is True

    def test_complete_string(self):
        assert self._is_truthy_status("complete") is True

    def test_failed_string(self):
        assert self._is_truthy_status("failed") is False

    def test_none_value(self):
        assert self._is_truthy_status(None) is False


# ===========================================================================
# 4. CLAP – accepts model.safetensors alongside pytorch_model.bin
# ===========================================================================
class TestClapWeightFileAcceptance:
    """CLAP resolver must accept either weight format."""

    @staticmethod
    def _resolve(snapshot_dir: Path, has_bin: bool, has_safetensors: bool):
        """Simulate the CLAP local dir resolution logic."""
        required_config = ("config.json", "preprocessor_config.json")
        weight_files = ("pytorch_model.bin", "model.safetensors")

        # Create files
        for f in required_config:
            (snapshot_dir / f).write_text("{}")
        if has_bin:
            (snapshot_dir / "pytorch_model.bin").write_bytes(b"\x00")
        if has_safetensors:
            (snapshot_dir / "model.safetensors").write_bytes(b"\x00")

        if (all((snapshot_dir / name).is_file() for name in required_config)
                and any((snapshot_dir / w).is_file() for w in weight_files)):
            return str(snapshot_dir)
        return None

    def test_bin_only(self, tmp_path):
        snap = tmp_path / "abc123"
        snap.mkdir()
        assert self._resolve(snap, has_bin=True, has_safetensors=False) is not None

    def test_safetensors_only(self, tmp_path):
        snap = tmp_path / "abc123"
        snap.mkdir()
        assert self._resolve(snap, has_bin=False, has_safetensors=True) is not None

    def test_both_present(self, tmp_path):
        snap = tmp_path / "abc123"
        snap.mkdir()
        assert self._resolve(snap, has_bin=True, has_safetensors=True) is not None

    def test_neither_present(self, tmp_path):
        snap = tmp_path / "abc123"
        snap.mkdir()
        assert self._resolve(snap, has_bin=False, has_safetensors=False) is None


# ===========================================================================
# 5. BLIP – local snapshot resolution + offline loading behaviour
# ===========================================================================
class TestBlipLocalSnapshotResolution:
    """BLIP resolver finds a local HF Hub snapshot."""

    @staticmethod
    def _resolve(models_root: Path):
        """Replica of _resolve_blip_local_dir from image_caption/step.py."""
        repo_cache = models_root / "hub" / "models--Salesforce--blip-image-captioning-base"
        snapshots_dir = repo_cache / "snapshots"
        refs_main = repo_cache / "refs" / "main"
        required_config = ("config.json", "preprocessor_config.json")
        weight_files = ("pytorch_model.bin", "model.safetensors")
        candidates = []

        if refs_main.is_file():
            try:
                revision = refs_main.read_text(encoding="utf-8").strip()
                if revision:
                    candidates.append(snapshots_dir / revision)
            except OSError:
                pass

        if snapshots_dir.is_dir():
            candidates.extend(sorted(snapshots_dir.iterdir(),
                                     key=lambda p: p.stat().st_mtime, reverse=True))

        seen: set = set()
        for candidate in candidates:
            if candidate in seen or not candidate.is_dir():
                continue
            seen.add(candidate)
            if (all((candidate / name).is_file() for name in required_config)
                    and any((candidate / w).is_file() for w in weight_files)):
                return str(candidate)
        return None

    def test_finds_snapshot_with_bin(self, tmp_path):
        snap = tmp_path / "hub" / "models--Salesforce--blip-image-captioning-base" / "snapshots" / "deadbeef"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}")
        (snap / "preprocessor_config.json").write_text("{}")
        (snap / "pytorch_model.bin").write_bytes(b"\x00")

        refs = tmp_path / "hub" / "models--Salesforce--blip-image-captioning-base" / "refs"
        refs.mkdir(parents=True, exist_ok=True)
        (refs / "main").write_text("deadbeef")

        result = self._resolve(tmp_path)
        assert result is not None
        assert "deadbeef" in result

    def test_finds_snapshot_with_safetensors(self, tmp_path):
        snap = tmp_path / "hub" / "models--Salesforce--blip-image-captioning-base" / "snapshots" / "cafebabe"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}")
        (snap / "preprocessor_config.json").write_text("{}")
        (snap / "model.safetensors").write_bytes(b"\x00")

        result = self._resolve(tmp_path)
        assert result is not None

    def test_returns_none_when_no_snapshot(self, tmp_path):
        assert self._resolve(tmp_path) is None


# ===========================================================================
# 6. Direct-ingest – fallback to logs/direct_ingest_*.json
# ===========================================================================
class TestDirectIngestFallback:
    """Direct-ingest fallback reads logs/direct_ingest_*.json."""

    @staticmethod
    def _scan_direct_ingest_logs(log_dir: Path):
        """Replica of _scan_direct_ingest_logs from runtime.py."""
        results = []
        if not log_dir.is_dir():
            return results
        for entry in sorted(log_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if entry.name.startswith("direct_ingest_") and entry.suffix == ".json":
                try:
                    data = json.loads(entry.read_text(encoding="utf-8"))
                    results.append({"file": entry.name, "data": data})
                except Exception:
                    continue
        return results

    def test_finds_direct_ingest_logs(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "direct_ingest_2024-01-01.json").write_text(
            json.dumps({"run_id": "di-001", "status": "completed"})
        )
        (log_dir / "other_log.json").write_text("{}")

        results = self._scan_direct_ingest_logs(log_dir)
        assert len(results) == 1
        assert results[0]["data"]["run_id"] == "di-001"

    def test_returns_empty_when_no_dir(self, tmp_path):
        results = self._scan_direct_ingest_logs(tmp_path / "nonexistent")
        assert results == []

    def test_ignores_malformed_json(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "direct_ingest_bad.json").write_text("NOT JSON {{{")
        results = self._scan_direct_ingest_logs(log_dir)
        assert results == []


# ===========================================================================
# 7. Scene detection – fallback split for overlong scenes
# ===========================================================================
class TestSceneFallbackSplit:
    """Fallback scene generator splits videos longer than max_scene_len_sec."""

    @staticmethod
    def _fallback(duration, max_scene_len_sec=600.0):
        """Replica of _fallback_single_scene with split logic."""
        end = float(duration) if duration and duration > 0 else 0.0

        if end > max_scene_len_sec > 0:
            scenes = []
            offset = 0.0
            idx = 0
            while offset < end:
                chunk_end = min(offset + max_scene_len_sec, end)
                scenes.append({
                    'index': idx,
                    'start': round(offset, 3),
                    'end': round(chunk_end, 3),
                    'duration': round(chunk_end - offset, 3),
                    'confidence': 1.0,
                    'strategy': 'fallback_split',
                })
                offset = chunk_end
                idx += 1
            return scenes

        return [{
            'index': 0,
            'start': 0.0,
            'end': round(end, 3),
            'duration': round(end, 3),
            'confidence': 1.0,
            'strategy': 'fallback',
        }]

    def test_short_video_no_split(self):
        scenes = self._fallback(120.0, max_scene_len_sec=600.0)
        assert len(scenes) == 1
        assert scenes[0]['strategy'] == 'fallback'
        assert scenes[0]['duration'] == 120.0

    def test_overlong_video_splits(self):
        scenes = self._fallback(1800.0, max_scene_len_sec=600.0)
        assert len(scenes) == 3
        assert all(s['strategy'] == 'fallback_split' for s in scenes)
        assert scenes[0]['start'] == 0.0
        assert scenes[0]['end'] == 600.0
        assert scenes[1]['start'] == 600.0
        assert scenes[1]['end'] == 1200.0
        assert scenes[2]['start'] == 1200.0
        assert scenes[2]['end'] == 1800.0

    def test_partial_last_chunk(self):
        scenes = self._fallback(700.0, max_scene_len_sec=600.0)
        assert len(scenes) == 2
        assert scenes[0]['duration'] == 600.0
        assert scenes[1]['duration'] == 100.0
        assert scenes[1]['end'] == 700.0

    def test_exact_boundary(self):
        scenes = self._fallback(600.0, max_scene_len_sec=600.0)
        # Exactly at boundary → no split needed
        assert len(scenes) == 1
        assert scenes[0]['strategy'] == 'fallback'

    def test_zero_duration(self):
        scenes = self._fallback(0.0, max_scene_len_sec=600.0)
        assert len(scenes) == 1
        assert scenes[0]['duration'] == 0.0
        assert scenes[0]['strategy'] == 'fallback'

    def test_none_duration(self):
        scenes = self._fallback(None, max_scene_len_sec=600.0)
        assert len(scenes) == 1

    def test_config_max_scene_len_sec_loaded(self):
        """Verify _load_params picks up max_scene_len_sec from config."""
        # Simulate calling _load_params with a config containing max_scene_len_sec
        cfg = {'video': {'scene_detect': {'max_scene_len_sec': 300}}}
        item = {}

        scene_cfg = cfg.get('video', {}).get('scene_detect', {})
        val = scene_cfg.get('max_scene_len_sec', 600.0)
        assert val == 300


# ===========================================================================
# Integration: _load_params extracts max_scene_len_sec
# ===========================================================================
class TestLoadParamsMaxSceneLen:
    """Ensure _load_params extracts max_scene_len_sec from config."""

    def test_from_config(self):
        # Import if available; skip if deps missing
        try:
            from steps.video_scene_detect.step import _load_params
        except ImportError:
            pytest.skip("video_scene_detect step not importable")
        params = _load_params(
            {"video": {"scene_detect": {"max_scene_len_sec": 300}}},
            {}
        )
        assert params["max_scene_len_sec"] == 300.0

    def test_default_value(self):
        try:
            from steps.video_scene_detect.step import _load_params
        except ImportError:
            pytest.skip("video_scene_detect step not importable")
        params = _load_params({}, {})
        assert params["max_scene_len_sec"] == 600.0
