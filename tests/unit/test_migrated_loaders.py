from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest


# Mocks for PyTorch, PIL, and Torchvision used by this test module only.
fake_torch = types.ModuleType("torch")
fake_torch.__version__ = "1.13.0"

class DummyDevice:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name

fake_torch.device = DummyDevice

class DummyCuda:
    @staticmethod
    def is_available():
        return False
    @staticmethod
    def empty_cache():
        pass
fake_torch.cuda = DummyCuda

class DummyMps:
    @staticmethod
    def is_available():
        return False

fake_torch.backends = types.SimpleNamespace(mps=DummyMps)

class DummyNoGrad:
    def __enter__(self):
        pass
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

fake_torch.no_grad = DummyNoGrad

def dummy_load(*args, **kwargs):
    return "mock_state_dict"
fake_torch.load = dummy_load

def dummy_sigmoid(*args, **kwargs):
    class DummyTensor:
        def cpu(self):
            return self
        def numpy(self):
            class DummyNumpy:
                def tolist(self):
                    return [[0.1, 0.2, 0.3]]
            return DummyNumpy()
    return DummyTensor()
fake_torch.sigmoid = dummy_sigmoid

# Mock PIL
fake_pil = types.ModuleType("PIL")
class MockImage:
    @classmethod
    def open(cls, path):
        return MockImage()
    def convert(self, mode):
        return self
    def crop(self, box):
        return self
    def resize(self, size):
        return self
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
fake_pil.Image = MockImage

# Mock torchvision
fake_torchvision = types.ModuleType("torchvision")
class MockToTensor:
    def __call__(self, img):
        class MockTensor:
            def unsqueeze(self, dim):
                return self
            def to(self, device):
                return self
        return MockTensor()
fake_torchvision.transforms = types.SimpleNamespace(ToTensor=lambda: MockToTensor())


@pytest.fixture(autouse=True)
def _install_fake_runtime_modules(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "torchvision", fake_torchvision)

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

# Ensure vendor dir is in sys.path
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists() and str(_VENDOR_DIR) not in sys.path:
    sys.path.append(str(_VENDOR_DIR))


def test_emotion_classify_safetensors_autodetect(tmp_path, monkeypatch):
    """Verify that steps/emotion_classify/step.py checks for model.safetensors and uses the correct use_safetensors flag."""
    from steps.common.model_provisioner import ModelProvisionResult

    model_root = tmp_path / "cardiff"
    model_root.mkdir()
    (model_root / "pytorch_model.bin").write_bytes(b"\x00")
    monkeypatch.setattr(
        "steps.common.model_provisioner.ensure_model_cached",
        lambda *args, **kwargs: ModelProvisionResult(
            status="cached",
            repo_id="cardiffnlp/twitter-roberta-base-emotion-latest",
            revision="415620c4fbc8bd82b82b9fd46642fcec6519d537",
            local_path=str(model_root),
            gated=False,
            required=True,
            elapsed_seconds=0.1,
        ),
    )
    
    # Mock config loader to enable offline mode
    import steps.common.config_loader
    monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda *args: {"verification": {"offline_mode": True}})
    
    # Mock Transformers AutoTokenizer and AutoModelForSequenceClassification
    tokenizer_calls = []
    model_calls = []
    
    class MockTokenizer:
        @classmethod
        def from_pretrained(cls, path, local_files_only):
            tokenizer_calls.append((path, local_files_only))
            return "mock_tokenizer"
            
    class MockModel:
        @classmethod
        def from_pretrained(cls, path, use_safetensors, local_files_only):
            model_calls.append((path, use_safetensors, local_files_only))
            class EvalModel:
                def to(self, device):
                    return self
                def eval(self):
                    return self
                config = types.SimpleNamespace(
                    id2label={"0": "anger", "1": "joy"},
                    problem_type="multi_label_classification",
                )
            return EvalModel()
            
    import sys
    transformers_mock = types.ModuleType("transformers")
    transformers_mock.AutoTokenizer = MockTokenizer
    transformers_mock.AutoModelForSequenceClassification = MockModel
    monkeypatch.setitem(sys.modules, "transformers", transformers_mock)
    
    # Reset _EMO cache
    from steps.emotion_classify.step import _EMO, _load_emotion
    _EMO.update({"model": None, "tok": None, "labels": [], "device": "cpu", "error": None})
    
    _load_emotion()
    
    assert _EMO["model"] is not None
    assert len(tokenizer_calls) == 1
    assert len(model_calls) == 1
    assert model_calls[0][1] is False  # use_safetensors should be False because model.safetensors is missing
    
    # 2. Setup mock cached model WITH safetensors
    _EMO.update({"model": None, "tok": None, "labels": [], "device": "cpu", "error": None})
    (model_root / "model.safetensors").write_bytes(b"\x00")
    tokenizer_calls.clear()
    model_calls.clear()
    
    _load_emotion()
    assert model_calls[0][1] is True  # use_safetensors should be True because model.safetensors exists


def test_face_embed_governed_loading(tmp_path, monkeypatch):
    """Verify that steps/face_embed/step.py loads FaceNet via ensure_model_cached."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    # Setup mock cached facenet_vggface2 file
    checkpoint_file = tmp_path / "checkpoints" / "20180402-114759-vggface2.pt"
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_file.write_bytes(b"\x00" * 2000)
    
    # Mock config loader to enable offline mode
    import steps.common.config_loader
    monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda *args: {"verification": {"offline_mode": True}})
    
    # Mock InceptionResnetV1 and MTCNN
    inception_calls = []
    load_state_dict_calls = []
    
    class MockInceptionResnetV1:
        def __init__(self, pretrained=None, device=None):
            inception_calls.append(pretrained)
            self.device = device
        def eval(self):
            return self
        def load_state_dict(self, state_dict):
            load_state_dict_calls.append(state_dict)
            return None
        def __call__(self, tensor):
            class DummyEmbedding:
                def cpu(self):
                    return self
                def numpy(self):
                    import numpy as np
                    return np.array([[0.1, 0.2, 0.3]], dtype=float)
            return DummyEmbedding()
            
    class MockMTCNN:
        def __init__(self, keep_all=True, device=None):
            pass
        def detect(self, img):
            import numpy as np
            return np.array([[1, 2, 3, 4]]), None
            
    facenet_mock = types.ModuleType("facenet_pytorch")
    facenet_mock.InceptionResnetV1 = MockInceptionResnetV1
    facenet_mock.MTCNN = MockMTCNN
    monkeypatch.setitem(sys.modules, "facenet_pytorch", facenet_mock)
    
    from steps.face_embed.step import face_embed
    
    # Create a mock source image file
    src_file = tmp_path / "frame.jpg"
    src_file.write_bytes(b"")
    
    # Run face_embed which falls back to facenet-pytorch
    monkeypatch.setattr("steps.face_embed.step._face_recognition_stack_available", lambda: False)
    res = face_embed({"source_path": str(src_file)}, {})
    
    assert res["faces_meta"]["status"] == "ok"
    assert res["faces_meta"]["engine"] == "facenet-pytorch"
    assert len(inception_calls) == 1
    assert inception_calls[0] is None  # pretrained should be None so it loads locally
    assert load_state_dict_calls == ["mock_state_dict"]


def test_tagger_governed_loading(tmp_path, monkeypatch):
    """Verify that steps/tagger/step.py loads NER pipeline via ensure_model_cached."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    # Setup mock cached bert_ner model
    repo_cache_dir = tmp_path / "hub" / "models--dslim--bert-base-NER"
    snapshots_dir = repo_cache_dir / "snapshots" / "d1a3e8f13f8c3566299d95fcfc9a8d2382a9affc"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshots_dir / "model.safetensors").write_bytes(b"\x00")
    
    # Write refs/main
    refs_dir = repo_cache_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "main").write_text("d1a3e8f13f8c3566299d95fcfc9a8d2382a9affc", encoding="utf-8")
    
    # Mock config loader to enable offline mode
    import steps.common.config_loader
    monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda *args: {"verification": {"offline_mode": True}})
    
    pipeline_calls = []
    
    def mock_pipeline(task, model, local_files_only, aggregation_strategy):
        pipeline_calls.append((task, model, local_files_only))
        return lambda text: [{"word": "Alice", "entity_group": "PER"}]
        
    transformers_mock = types.ModuleType("transformers")
    transformers_mock.pipeline = mock_pipeline
    transformers_mock.logging = types.SimpleNamespace(set_verbosity_error=lambda: None)
    monkeypatch.setitem(sys.modules, "transformers", transformers_mock)
    
    from steps.tagger.step import _NER_PIPELINES, tagger
    _NER_PIPELINES.clear()
    
    item = {"transcript": "Hello my name is Alice."}
    cfg = {"config": {"tagger": {"ner_model": "dslim/bert-base-NER"}}}
    
    res = tagger(item, cfg)
    
    assert "Alice" in res["entities"]
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0][0] == "token-classification"
    assert Path(pipeline_calls[0][1]) == snapshots_dir.absolute()
    assert pipeline_calls[0][2] is True  # local_files_only should be True


def test_object_detect_governed_loading(tmp_path, monkeypatch):
    """Verify that steps/object_detect/step.py loads YOLO model via ensure_model_cached."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    # Setup mock cached yolo_v8n file
    yolo_file = tmp_path / "yolo" / "yolov8n.pt"
    yolo_file.parent.mkdir(parents=True, exist_ok=True)
    yolo_file.write_bytes(b"\x00" * 2000)
    
    # Mock config loader to enable offline mode
    import steps.common.config_loader
    monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda *args: {"verification": {"offline_mode": True}})
    
    yolo_init_calls = []
    
    class MockYOLO:
        def __init__(self, model_path):
            yolo_init_calls.append(model_path)
        def predict(self, source, device, verbose):
            class MockTensor:
                def __getitem__(self, idx):
                    return self
                def tolist(self):
                    return [10.0, 20.0, 100.0, 200.0]
            class MockBox:
                def __init__(self):
                    self.xyxy = MockTensor()
                    self.conf = [0.9]
                    self.cls = [0]
            class MockResult:
                def __init__(self):
                    self.boxes = [MockBox()]
                    self.names = {0: "person"}
            return [MockResult()]
            
    ultralytics_mock = types.ModuleType("ultralytics")
    ultralytics_mock.YOLO = MockYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics_mock)
    
    from steps.object_detect.step import _YOLO, object_detect
    # Reset _YOLO cache
    import steps.object_detect.step
    steps.object_detect.step._YOLO = None
    
    # Create mock source image file
    src_file = tmp_path / "frame.jpg"
    src_file.write_bytes(b"")
    
    cfg = {}
    res = object_detect({"source_path": str(src_file)}, cfg)
    print("DEBUG_RES:", res)
    assert res["objects"][0]["label"] == "person"
    assert len(yolo_init_calls) == 1
    assert Path(yolo_init_calls[0]) == yolo_file.absolute()
