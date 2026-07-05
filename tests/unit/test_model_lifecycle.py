import unittest
from unittest.mock import MagicMock, patch
from lib.model_lifecycle import ModelLifecycleManager, _RESIDENT_MODELS


class TestModelLifecycleManager(unittest.TestCase):

    def setUp(self):
        # Clear global resident models tracking
        _RESIDENT_MODELS.clear()
        
        # Build mock config with explicit VRAM budgets
        self.config = {
            "gpu_budget": {
                "total_vram_gb": 16.0,
                "reserved_display_gb": 1.5,
                "reserved_cuda_fragmentation_gb": 1.0,
                "usable_target_gb": 13.5,
                "emergency_stop_gb": 14.5
            },
            "huggingface_models": {
                "mock_stable_model": {
                    "vram_estimate_gb": 2.0,
                    "load_policy": "concurrent_safe",
                    "engines": {
                        "Transformers": "yes",
                        "llama.cpp/GGUF": "no"
                    }
                },
                "mock_heavy_model": {
                    "vram_estimate_gb": 12.0,
                    "load_policy": "sequential_only",
                    "engines": {
                        "Ollama": "yes"
                    }
                },
                "mock_massive_model": {
                    "vram_estimate_gb": 15.0,
                    "load_policy": "sequential_only"
                }
            }
        }
        self.manager = ModelLifecycleManager(self.config)

    def tearDown(self):
        _RESIDENT_MODELS.clear()

    @patch("lib.model_lifecycle.ModelLifecycleManager.get_free_vram_gb")
    def test_preflight_check_success(self, mock_free_vram):
        mock_free_vram.return_value = 12.0
        # Should pass because 2.0GB estimate + (16 - 12) = 6.0GB which is well under 13.5GB limit
        self.assertTrue(self.manager.preflight_check("mock_stable_model"))

    @patch("lib.model_lifecycle.ModelLifecycleManager.get_free_vram_gb")
    def test_preflight_check_emergency_oom_block(self, mock_free_vram):
        mock_free_vram.return_value = 2.0  # Only 2.0GB free VRAM
        # Loading a 12.0GB model would require 14.0GB total VRAM usage (exceeding free ceiling)
        # And projected system usage = (16.0 - 2.0) + 12.0 = 26.0GB which exceeds 14.5GB emergency limit
        with self.assertRaises(MemoryError):
            self.manager.preflight_check("mock_heavy_model")

    @patch("lib.model_lifecycle.ModelLifecycleManager.get_free_vram_gb")
    def test_context_manager_lifecycle(self, mock_free_vram):
        mock_free_vram.return_value = 12.0
        
        load_called = False
        unload_called = False
        
        def load_fn():
            nonlocal load_called
            load_called = True
            return "mock_instance"
            
        def unload_fn():
            nonlocal unload_called
            unload_called = True
            
        # Using context manager
        with self.manager.load("mock_stable_model", load_fn, unload_fn) as model:
            self.assertEqual(model, "mock_instance")
            self.assertTrue(load_called)
            self.assertIn("mock_stable_model", _RESIDENT_MODELS)
            self.assertFalse(unload_called)
            
        # Assert clean unload on exit
        self.assertTrue(unload_called)
        self.assertNotIn("mock_stable_model", _RESIDENT_MODELS)

    @patch("lib.model_lifecycle.ModelLifecycleManager.get_free_vram_gb")
    def test_sequential_eviction(self, mock_free_vram):
        mock_free_vram.return_value = 15.0
        
        # Load a model and keep it resident
        self.manager.load("mock_stable_model", lambda: "inst1")
        self.assertIn("mock_stable_model", _RESIDENT_MODELS)
        
        # Preflight of another heavy model should trigger eviction of the resident model
        self.manager.preflight_check("mock_heavy_model")
        
        # Assert first model was evicted
        self.assertNotIn("mock_stable_model", _RESIDENT_MODELS)

    @patch("lib.model_lifecycle.ModelLifecycleManager.get_free_vram_gb")
    def test_preflight_check_engine_compatibility_success(self, mock_free_vram):
        mock_free_vram.return_value = 12.0
        # Should pass when target_engine is supported (case-insensitive matching)
        self.assertTrue(self.manager.preflight_check("mock_stable_model", target_engine="transformers"))
        self.assertTrue(self.manager.preflight_check("mock_stable_model", target_engine="Transformers"))

    @patch("lib.model_lifecycle.ModelLifecycleManager.get_free_vram_gb")
    def test_preflight_check_engine_compatibility_failure(self, mock_free_vram):
        mock_free_vram.return_value = 12.0
        # Should raise ValueError when target_engine is unsupported
        with self.assertRaises(ValueError):
            self.manager.preflight_check("mock_stable_model", target_engine="llama.cpp/GGUF")
        with self.assertRaises(ValueError):
            self.manager.preflight_check("mock_stable_model", target_engine="Ollama")
        with self.assertRaises(ValueError):
            self.manager.preflight_check("mock_massive_model", target_engine="Transformers")

    @patch("lib.model_lifecycle.ModelLifecycleManager.get_free_vram_gb")
    def test_preflight_check_cpu_bypass(self, mock_free_vram):
        mock_free_vram.return_value = 0.5  # Crucially low VRAM
        # Loading massive model on CUDA would fail preflight
        with self.assertRaises(MemoryError):
            self.manager.preflight_check("mock_massive_model")
            
        # Loading massive model on CPU should bypass VRAM checks and return True
        self.assertTrue(self.manager.preflight_check("mock_massive_model", device="cpu"))


if __name__ == "__main__":
    unittest.main()
