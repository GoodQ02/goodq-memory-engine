"""
ZenML pipeline definition (scaffold) for multimodal ingestion.

This file intentionally avoids importing zenml at import-time to keep the
scaffold runnable without ZenML installed. Replace placeholders when ZenML is
set up and registered with a conda step operator.
"""
from typing import Any, Dict, List


def build_ingest_multimodal_pipeline():
    """Returns a callable that wires placeholder steps together.

    Replace with `@pipeline` and actual `@step` decorated functions once ZenML
    is installed and the stack is configured.
    """
    from zenml_project.steps.discover_sources.step import discover_sources
    from zenml_project.steps.audio_transcribe.step import audio_transcribe
    from zenml_project.steps.image_ocr.step import image_ocr
    from zenml_project.steps.image_caption.step import image_caption
    from zenml_project.steps.object_detect.step import object_detect
    from zenml_project.steps.face_embed.step import face_embed
    from zenml_project.steps.text_embed.step import text_embed
    from zenml_project.steps.emotion_classify.step import emotion_classify
    from zenml_project.steps.tagger.step import tagger
    from zenml_project.steps.home_assistant_status.step import home_assistant_status
    from zenml_project.steps.system_metrics.step import system_metrics

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

