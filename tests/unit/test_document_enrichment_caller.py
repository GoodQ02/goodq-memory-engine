"""Standalone document text must reach the existing production analysis workers."""
from types import SimpleNamespace

import pytest

from cli.step_runner import run_step

TEXT = "Alice visited Chicago and felt happy about the successful family reunion."


@pytest.mark.parametrize("worker", ["sentiment", "emotion_classify", "tagger"])
def test_document_text_reaches_analysis_through_step_dispatch(monkeypatch, worker):
    import torch
    from steps.emotion_classify import step as emotion
    from steps.sentiment import step as sentiment
    from steps.tagger import step as tagger

    received = []

    class Inputs(dict):
        def to(self, _device):
            return self

    def tokenize(text, **_kwargs):
        received.append(text)
        return Inputs()

    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.delenv("HF_DATASETS_OFFLINE", raising=False)
    if worker == "sentiment":
        monkeypatch.setattr(sentiment, "_load", lambda _device: True)
        monkeypatch.setattr(sentiment, "_preferred_device", lambda: "cpu")
        monkeypatch.setattr(sentiment, "_SENT", {
            "tok": tokenize, "model": lambda **_kwargs: SimpleNamespace(logits=torch.tensor([[0., 2.]])),
            "device": "cpu",
        })
    elif worker == "emotion_classify":
        monkeypatch.setattr(emotion, "_load_emotion", lambda: None)
        monkeypatch.setattr(emotion, "_EMO", {
            "tok": tokenize, "model": lambda **_kwargs: SimpleNamespace(logits=torch.tensor([[0., 2.]])),
            "labels": ["sadness", "joy"], "device": "cpu", "requested_device": "cpu",
            "model_id": "fixture-model", "model_revision": "fixture-revision",
            "problem_type": "single_label_classification", "fallback_chain": [],
        })
    else:
        def extract(text, _cfg):
            received.append(text)
            return ["Alice", "Chicago"], [
                {"name": "Alice", "type": "PERSON", "source_step": "tagger", "source_modality": "text"},
                {"name": "Chicago", "type": "LOCATION", "source_step": "tagger", "source_modality": "text"},
            ]
        monkeypatch.setattr(tagger, "_extract_entities_transformers", extract)

    item = {"source_kind": "document", "document_text": TEXT, "frame_text": TEXT,
            "video_hash": "a" * 64, "scene_id": "b" * 64}
    result = run_step(worker, item, {"ingestion_isolation": True})
    assert received == [TEXT]
    assert "transcript" not in item and "ocr_text" not in item
    if worker == "sentiment":
        assert result["sentiment"]["label"] == "POSITIVE"
    elif worker == "emotion_classify":
        assert result["emotions"][0]["label"] == "joy"
    else:
        assert result["ner_entities"][0]["name"] == "Alice"
