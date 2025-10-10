"""
FUTURE FEATURE: GoodQ chat pipeline for conversational interface.

This is a placeholder for future chat/conversation functionality.
Current focus is on ingestion pipeline (ingest_multimodal_conda.py).

Status: NOT IMPLEMENTED
Priority: LOW - Implement after core ingestion is stable
"""
from typing import Any, Dict


def build_goodq_chat_pipeline():
    from steps.steps.common.config_loader import load_configs
    from steps.steps.llm_chat.step import llm_chat
    from steps.steps.tts.step import tts_speak
    from steps.steps.system_metrics.step import system_metrics
    from steps.steps.home_assistant_status.step import home_assistant_status

    def run(config_overrides: Dict[str, Any]) -> Dict[str, Any]:
        cfg = load_configs(config_overrides)
        # enrich context with system and home summaries
        sysm = system_metrics(cfg)
        ham = home_assistant_status(cfg)
        cfg["context"] = {
            "system_summary": sysm.get("summary", ""),
            "home_summary": ham.get("summary", ""),
        }
        chat = llm_chat(cfg)
        tts = tts_speak(chat, cfg)
        return {"chat": chat, "tts": tts}

    return run
