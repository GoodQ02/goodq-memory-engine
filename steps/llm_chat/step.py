from __future__ import annotations
# GPU Configuration - Auto-configured on import
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats


from typing import Any, Dict
import os
import logging

from steps.common.memory import _connect
from steps.common.llm_model_factory import build_llm_models
from lib.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _goodq_persona_prompt(cfg: Dict[str, Any]) -> str:
    model = cfg.get("config", {}).get("model", {})
    user = cfg.get("config", {}).get("user", {})
    return (
        "You are GoodQ, witty and precise. User: "
        + user.get("name", "")
        + ". User values: "
        + user.get("values", "")
        + ". GoodQ values: "
        + model.get("goodq_values", "clarity, precision, humor, loyalty")
        + ". Stay concise and helpful."
    )


def _multimodal_context_prompt(context: Dict[str, Any]) -> str:
    transcript = context.get("transcript", "")
    detected_entities = context.get("detected_entities", "")
    emotions = context.get("emotions", "")
    event_type = context.get("event_type", "")
    activities = context.get("activities", "")
    return (
        "Summarize and respond using any provided context.\n"
        f"Transcript: {transcript}\n"
        f"Entities Identified: {detected_entities}\n"
        f"Emotion Tags: {emotions}\n"
        f"Event Type: {event_type}\n"
        f"Activities: {activities}\n"
        "When the user asks a question, answer directly, referencing context when useful."
    )


def llm_chat(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM Chat Step - Thin adapter delegating to LLMClient.
    """
    system_persona = _goodq_persona_prompt(cfg)
    
    # Merge system/home summaries into context for awareness
    context_block = dict(cfg.get("context", {}))
    
    # Inject retrieval hooks from memory bank: last overview + top video advisories
    try:
        dbp = (cfg.get("paths", {}) or {}).get("db_path")
        if dbp:
            con = _connect(dbp)
            cur = con.cursor()
            cur.execute("SELECT content FROM summaries WHERE summary_type='short_term' AND category='overview' ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                import json as _json
                ov = _json.loads(row[0])
                adv = ov.get('video_advisories') or []
                if adv:
                    top_adv = ", ".join([a.get('label','') for a in adv[:3]])
                    prev = context_block.get('activities') or ''
                    context_block['activities'] = (prev + f" Advisories: {top_adv}").strip()
            con.close()
    except Exception as e:
        logger.warning(f"Exception retrieving memory bank short-term overview: {e}")
        
    if context_block:
        sys_sum = context_block.get("system_summary", "")
        home_sum = context_block.get("home_summary", "")
        if sys_sum or home_sum:
            context_block["activities"] = (context_block.get("activities", "") or "") + f" System: {sys_sum}; Home: {home_sum}"
            
    context_instructions = _multimodal_context_prompt(context_block)
    user_input = cfg.get("input", "Hello, GoodQ")

    messages = [
        {"role": "system", "content": system_persona},
        {"role": "system", "content": context_instructions},
        {"role": "user", "content": user_input},
    ]

    client = None
    try:
        models = build_llm_models(cfg)
        llm_cfg = cfg.get("config", {}).get("llm", {}) or {}
        
        client = LLMClient(
            models=models,
            health_check_interval=int(llm_cfg.get("health_check_interval", 60)),
            max_retries=int(llm_cfg.get("max_retries", 3)),
            timeout=int(llm_cfg.get("timeout", 60)),
            cache_ttl=int(llm_cfg.get("cache_ttl", 300)),
            enable_health_checks=bool(llm_cfg.get("enable_health_checks", False))
        )
        
        response = client.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=512,
        )
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        model_used = client.last_model_used
        prompt_snapshot = {
            "api_url": model_used.endpoint if model_used else "unknown",
            "model": model_used.name if model_used else "unknown",
            "messages": messages,
        }
        
        return {"text": content, "prompt_snapshot": prompt_snapshot}
        
    except Exception as e:
        logger.error(f"llm_chat execution via LLMClient failed: {e}", exc_info=True)
        prompt_snapshot = {
            "api_url": "failed",
            "model": "failed",
            "messages": messages,
        }
        return {"error": str(e), "prompt_snapshot": prompt_snapshot}
        
    finally:
        if client:
            try:
                client.close()
            except Exception as close_err:
                logger.warning(f"Failed to close LLMClient in llm_chat step: {close_err}")
