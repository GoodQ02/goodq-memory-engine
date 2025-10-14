from __future__ import annotations
import os
from typing import Any, Dict, List

import requests
from goodq4all.steps.common.retry import request_with_retry


def _summarize_entity(entity: Dict[str, Any]) -> str:
    attrs = entity.get('attributes', {})
    name = attrs.get('friendly_name', entity.get('entity_id', 'unknown'))
    state = entity.get('state', 'unknown')
    if entity.get('entity_id', '').startswith('light.'):
        if state == 'on' and 'brightness' in attrs:
            pct = round(int(attrs.get('brightness', 0)) / 255 * 100)
            return f"{name}: ON ({pct}%)"
        return f"{name}: {state.upper()}"
    return f"{name}: {state}"


def home_assistant_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Use HA_TOKEN only (deprecated GOODQ_PIPELINE_HA_API removed per ops guidance)
    token = os.getenv("HA_TOKEN")
    base_url = cfg.get("config", {}).get("ha", {}).get("url", "")
    entities: List[str] = cfg.get("entities", {}).get("list", [])
    if not token or not base_url or not entities:
        return {"status": "unavailable"}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    results: List[Dict[str, Any]] = []
    for ent in entities:
        try:
            r = request_with_retry("GET", f"{base_url}/api/states/{ent}", headers=headers, timeout=3)
            results.append(r.json())
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 35: {str(e)}')
            continue
    summary = "; ".join(_summarize_entity(e) for e in results)
    return {"status": "ok", "results": results, "summary": ("Home: " + summary) if summary else ""}
