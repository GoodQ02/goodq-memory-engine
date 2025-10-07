from __future__ import annotations
from typing import Any, Dict

import os
import requests
from zenml_project.steps.common.retry import request_with_retry
from zenml_project.steps.common.memory import _connect


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
    llm_cfg = cfg.get("config", {}).get("llm", {})
    api_url = llm_cfg.get("api_url", "http://localhost:1234/v1/chat/completions")
    model_id = llm_cfg.get("model_id", "LM_STUDIO_GOODQ")

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
    except Exception:
      pass
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

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
    }

    prompt_snapshot = {
        "api_url": api_url,
        "model": model_id,
        "messages": messages,
    }

    headers = {}
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and "openai" in api_url:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        r = request_with_retry("POST", api_url, json=payload, headers=headers or None, timeout=60)
        content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"text": content, "prompt_snapshot": prompt_snapshot}
    except Exception as e:
        # Fallback: try Ollama native chat endpoint if OpenAI route not available
        err = str(e)
        try:
            if ("11434" in api_url or "ollama" in api_url) and ("/v1" in api_url or "chat/completions" in api_url):
                # Map to /api/chat
                from urllib.parse import urlparse, urlunparse

                parsed = urlparse(api_url)
                fallback_path = "/api/chat"
                fallback_url = urlunparse((parsed.scheme, parsed.netloc, fallback_path, "", "", ""))
                ollama_payload = {"model": model_id, "messages": messages, "stream": False}
                r2 = request_with_retry("POST", fallback_url, json=ollama_payload, timeout=60)
                j = r2.json() or {}
                content = (
                    (j.get("message") or {}).get("content")
                    or j.get("response")
                    or ""
                )
                if content:
                    return {"text": content, "prompt_snapshot": {**prompt_snapshot, "api_url": fallback_url}}
                # If no content, attempt /api/generate
                gen_url = urlunparse((parsed.scheme, parsed.netloc, "/api/generate", "", "", ""))
                combined_prompt = system_persona + "\n\n" + context_instructions + "\n\n" + user_input
                gen_payload = {"model": model_id, "prompt": combined_prompt, "stream": False}
                r3 = request_with_retry("POST", gen_url, json=gen_payload, timeout=60)
                j2 = r3.json() or {}
                content2 = j2.get("response", "")
                if content2:
                    return {"text": content2, "prompt_snapshot": {**prompt_snapshot, "api_url": gen_url}}
        except Exception:
            pass
        return {"error": err, "prompt_snapshot": prompt_snapshot}
