"""Behavior contracts for text-emotion model semantics and fallback provenance."""

from __future__ import annotations

import sys
import types
from pathlib import Path


MODEL_LABELS = {
    "0": "anger",
    "1": "anticipation",
    "2": "disgust",
    "3": "fear",
    "4": "joy",
    "5": "love",
    "6": "optimism",
    "7": "pessimism",
    "8": "sadness",
    "9": "surprise",
    "10": "trust",
}


def test_retired_cardiff_multilabel_alias_is_absent_from_active_paths():
    """The old unsealed Cardiff model may not remain runnable or cataloged."""

    repo_root = Path(__file__).resolve().parents[2]
    retired_model = "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest"
    active_paths = (
        repo_root / "configs" / "offline_asset_catalog.yaml",
        repo_root / "scripts" / "audit_vision_gpu.py",
        repo_root / "scripts" / "optimize_vision_gpu.py",
        repo_root / "scripts" / "run_vision_optimization.bat",
    )

    for path in active_paths:
        assert retired_model not in path.read_text(encoding="utf-8"), path


def _reset_emotion_cache(monkeypatch, emotion_step, **values):
    baseline = {"model": None, "tok": None, "labels": [], "device": "cpu", "error": None}
    baseline.update(values)
    for key, value in baseline.items():
        monkeypatch.setitem(emotion_step._EMO, key, value)


def test_load_emotion_uses_loaded_model_id2label(monkeypatch):
    """The sealed model configuration, not a handwritten list, owns label order."""

    from steps.common.model_provisioner import ModelProvisionResult
    from steps.emotion_classify import step as emotion_step

    monkeypatch.setattr(
        "steps.common.model_provisioner.ensure_model_cached",
        lambda *args, **kwargs: ModelProvisionResult(
            status="cached",
            repo_id="cardiffnlp/twitter-roberta-base-emotion-latest",
            revision="415620c4fbc8bd82b82b9fd46642fcec6519d537",
            local_path="/sealed/cardiff",
            gated=False,
            required=True,
            elapsed_seconds=0.1,
        ),
    )
    monkeypatch.setattr(emotion_step, "setup_step_gpu", lambda _: {"device": "cpu"})
    monkeypatch.setattr("steps.common.config_loader.load_configs", lambda *_: {"verification": {"offline_mode": True}})
    monkeypatch.setattr(emotion_step.os.path, "exists", lambda path: path.endswith("model.safetensors"))

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    class FakeModel:
        config = types.SimpleNamespace(id2label=MODEL_LABELS, problem_type="multi_label_classification")

        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def to(self, _device):
            return self

        def eval(self):
            return self

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = FakeTokenizer
    fake_transformers.AutoModelForSequenceClassification = FakeModel
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    _reset_emotion_cache(monkeypatch, emotion_step)

    emotion_step._load_emotion()

    assert emotion_step._EMO["labels"] == list(MODEL_LABELS.values())
    assert emotion_step._EMO["problem_type"] == "multi_label_classification"


def test_emotion_classify_preserves_complete_model_ranking_and_semantics(monkeypatch):
    """All model outputs reach downstream consumers with their actual labels."""

    from steps.emotion_classify import step as emotion_step

    class Inputs(dict):
        def to(self, _device):
            return self

    class FakeTokenizer:
        def __call__(self, *args, **kwargs):
            return Inputs()

    class FakeLogits:
        def cpu(self):
            return self

        def numpy(self):
            return self

        def tolist(self):
            return [[0.11, 0.92, 0.03, 0.44, 0.87, 0.25, 0.79, 0.09, 0.66, 0.51, 0.38]]

    class FakeModel:
        def __call__(self, **kwargs):
            return types.SimpleNamespace(logits=FakeLogits())

    class NoGrad:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_torch = types.ModuleType("torch")
    fake_torch.sigmoid = lambda logits: logits
    fake_torch.no_grad = NoGrad
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("steps.common.memory.update_fields", lambda *args, **kwargs: None)
    monkeypatch.setattr("steps.text_embed.step._content_fingerprint", lambda _item: "scene-hash")
    _reset_emotion_cache(
        monkeypatch,
        emotion_step,
        model=FakeModel(),
        tok=FakeTokenizer(),
        labels=list(MODEL_LABELS.values()),
        problem_type="multi_label_classification",
        model_id="cardiffnlp/twitter-roberta-base-emotion-latest",
        model_revision="415620c4fbc8bd82b82b9fd46642fcec6519d537",
    )

    result = emotion_step.emotion_classify({"transcript": "A complete emotion contract"}, {"config": {}})

    assert len(result["emotions"]) == len(MODEL_LABELS)
    assert [entry["label"] for entry in result["emotions"]] == [
        "anticipation", "joy", "optimism", "sadness", "surprise", "fear",
        "trust", "love", "anger", "pessimism", "disgust",
    ]
    assert result["emotion_meta"] == {
        "engine": "cardiffnlp",
        "status": "ok",
        "source": "model",
        "problem_type": "multi_label_classification",
        "label_count": 11,
        "model_id": "cardiffnlp/twitter-roberta-base-emotion-latest",
        "model_revision": "415620c4fbc8bd82b82b9fd46642fcec6519d537",
    }


def test_emotion_classify_marks_nrc_as_a_distinct_complete_fallback(monkeypatch):
    """NRC may supply a fallback, but it must never be conflated with model output."""

    from steps.emotion_classify import step as emotion_step

    _reset_emotion_cache(monkeypatch, emotion_step, error="model cache unavailable")
    monkeypatch.setattr(emotion_step, "_load_emotion", lambda: None)
    monkeypatch.setattr(
        emotion_step,
        "score_nrc_emotions",
        lambda *_: {"joy": 0.8, "trust": 0.6, "anger": 0.2, "fear": 0.1, "sadness": 0.05, "surprise": 0.01},
    )

    result = emotion_step.emotion_classify(
        {"transcript": "A clearly positive but uncertain scene"},
        {"config": {"analysis": {"use_nrc_lexicon": True}}},
    )

    assert result["emotions"] == [
        {"label": "joy", "score": 0.8},
        {"label": "trust", "score": 0.6},
        {"label": "anger", "score": 0.2},
        {"label": "fear", "score": 0.1},
        {"label": "sadness", "score": 0.05},
        {"label": "surprise", "score": 0.01},
    ]
    assert result["emotion_meta"] == {
        "engine": "nrc-lex",
        "status": "fallback",
        "source": "lexicon",
        "label_count": 6,
        "reason": "model_unavailable",
    }


def test_emotion_classify_uses_cached_model_while_offline(monkeypatch):
    """Offline mode may forbid downloads, but not inference from a verified local cache."""

    from steps.emotion_classify import step as emotion_step

    class Inputs(dict):
        def to(self, _device):
            return self

    class FakeTokenizer:
        def __call__(self, *args, **kwargs):
            return Inputs()

    class FakeLogits:
        def cpu(self):
            return self

        def numpy(self):
            return self

        def tolist(self):
            return [[0.2, 0.8]]

    class FakeModel:
        def __call__(self, **kwargs):
            return types.SimpleNamespace(logits=FakeLogits())

    class NoGrad:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_torch = types.ModuleType("torch")
    fake_torch.sigmoid = lambda logits: logits
    fake_torch.no_grad = NoGrad
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("steps.common.memory.update_fields", lambda *args, **kwargs: None)
    monkeypatch.setattr("steps.text_embed.step._content_fingerprint", lambda _item: "scene-hash")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    _reset_emotion_cache(
        monkeypatch,
        emotion_step,
        model=FakeModel(),
        tok=FakeTokenizer(),
        labels=["anger", "joy"],
        problem_type="multi_label_classification",
        model_id="cardiffnlp/twitter-roberta-base-emotion-latest",
        model_revision="415620c4fbc8bd82b82b9fd46642fcec6519d537",
    )

    result = emotion_step.emotion_classify({"transcript": "Offline but cached"}, {"config": {}})

    assert result["emotions"] == [{"label": "joy", "score": 0.8}, {"label": "anger", "score": 0.2}]
    assert result["emotion_meta"]["engine"] == "cardiffnlp"
    assert result["emotion_meta"]["status"] == "ok"


def test_emotion_classify_emits_terminal_receipt_when_model_and_nrc_fail(monkeypatch):
    """A failed model inference may not disappear when the lexicon fallback is unavailable."""

    from steps.emotion_classify import step as emotion_step

    class FailingTokenizer:
        def __call__(self, *args, **kwargs):
            raise RuntimeError("bad tokenizer state")

    _reset_emotion_cache(monkeypatch, emotion_step, model=object(), tok=FailingTokenizer(), labels=["joy"])
    monkeypatch.setattr(emotion_step, "score_nrc_emotions", lambda *_: None)

    result = emotion_step.emotion_classify({"transcript": "Failure must remain visible"}, {"config": {}})

    assert result["emotions"] is None
    assert result["emotion_meta"]["engine"] == "cardiffnlp"
    assert result["emotion_meta"]["status"] == "error"
    assert result["emotion_meta"]["reason"] == "model_inference_failed"
    assert "bad tokenizer state" in result["emotion_meta"]["error"]


def test_phase6_ranking_preserves_all_model_emotion_rows():
    """The complete classifier ranking survives the Phase 6 handoff without truncation."""

    from steps.video.cross_modal_harmonizer import _rank_text_emotions

    raw_emotions = [
        {"label": label, "score": (index + 1) / 100}
        for index, label in enumerate(MODEL_LABELS.values())
    ]

    ranking = _rank_text_emotions(raw_emotions)

    assert len(ranking) == len(MODEL_LABELS)
    assert ranking[0] == {"label": "trust", "score": 0.11, "rank": 1}
    assert ranking[-1] == {"label": "anger", "score": 0.01, "rank": 11}
