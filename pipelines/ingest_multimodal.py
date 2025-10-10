"""
DEPRECATED: Legacy scaffold pipeline for multimodal ingestion.

This file is kept for reference only. The production pipeline is now:
    pipelines/ingest_multimodal_conda.py

DO NOT USE THIS FILE. It contains placeholder code and is not functional.
Use cli/run_ingestion.py or the ZenML pipeline in ingest_multimodal_conda.py instead.
"""
from typing import Any, Dict, List


def build_ingest_multimodal_pipeline():
    """Returns a callable that wires placeholder steps together.

    Replace with `@pipeline` and actual `@step` decorated functions once ZenML
    is installed and the stack is configured.
    """
    from steps.steps.discover_sources.step import discover_sources
    from steps.steps.audio_transcribe.step import audio_transcribe
    from steps.steps.image_ocr.step import image_ocr
    from steps.steps.image_caption.step import image_caption
    from steps.steps.object_detect.step import object_detect
    from steps.steps.face_embed.step import face_embed
    from steps.steps.text_embed.step import text_embed
    from steps.steps.emotion_classify.step import emotion_classify
    from steps.steps.tagger.step import tagger
    from steps.steps.home_assistant_status.step import home_assistant_status
    from steps.steps.system_metrics.step import system_metrics

    def run(config: Dict[str, Any]) -> Dict[str, Any]:
        batch = discover_sources(config)
        results: List[Dict[str, Any]] = []
        for item in batch:
            modality = item.get("modality")
            enriched = dict(item)
            if modality == "audio":
                enriched.update(audio_transcribe(item, config))
            if modality == "image":
                enriched.update(image_ocr(item, config))
                enriched.update(image_caption(item, config))
                enriched.update(object_detect(item, config))
                enriched.update(face_embed(item, config))
            if modality == "text":
                pass  # placeholder: raw text ingestion
            # universal steps
            enriched.update(text_embed(enriched, config))
            enriched.update(emotion_classify(enriched, config))
            enriched.update(tagger(enriched, config))
            results.append(enriched)

        # context providers
        ha = home_assistant_status(config)
        sysm = system_metrics(config)

        return {"items": results, "home_assistant": ha, "system": sysm}

    return run

