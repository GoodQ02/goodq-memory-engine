from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional

from retrieval.temporal_reasoning import temporal_search
from steps.common.config_loader import load_configs
from steps.common.llm_model_factory import build_llm_models
from lib.llm_client import LLMClient

logger = logging.getLogger(__name__)


def clean_scene_description(summary: str) -> str:
    """
    Extract the core visual description from the structured database summary string
    to prevent structured text parser clutter in the LLM prompt.
    """
    if not summary:
        return ""
    if "Visual:" in summary:
        parts = summary.split("Visual:", 1)
        desc = parts[1].strip()
        for marker in ["Objects:", "Transcript:", "Emotions:", "Sentiment:", "Tags:", "Entities:"]:
            if marker in desc:
                desc = desc.split(marker, 1)[0].strip()
        return desc.rstrip(".;, ")
    return summary


def parse_narrative_segments(raw_text: str, source_scenes: list) -> tuple[str, list[dict]]:
    """
    Parse [Scene X] markers from raw_text, map each text block to the corresponding
    source scene ID and other scene details, strip markers, and return a clean summary
    along with a structured segments list. Supports auto-healing if the first match starts deep.
    """
    if not raw_text:
        return "", []
        
    pattern = re.compile(r'\[(?:Scene|Observation|Segment)\s*#?(\d+)\]', re.IGNORECASE)
    matches = list(pattern.finditer(raw_text))
    
    if not matches:
        return raw_text, []
        
    segments = []
    clean_summary_parts = []
    
    first_start = matches[0].start()
    leading = raw_text[:first_start].strip() if first_start > 0 else ""
    
    # Auto-healing: detect if the first match starts deep (index >= 10 with actual leading content)
    is_deep = (first_start >= 10 and bool(leading))
    shift = 0
    
    if is_deep:
        # Map leading text to Scene 1
        scene_id = None
        source_file = None
        start_time = None
        end_time = None
        if len(source_scenes) > 0:
            scene = source_scenes[0]
            scene_id = scene.get("scene_id")
            source_file = scene.get("source_file")
            start_time = scene.get("start_time")
            end_time = scene.get("end_time")
            
        segments.append({
            "scene_index": 1,
            "scene_id": scene_id,
            "text": leading,
            "source_file": source_file,
            "start_time": start_time,
            "end_time": end_time
        })
        clean_summary_parts.append(leading)
        
        # If the first match scene number is 1, shift subsequent X to X+1
        first_scene_num = int(matches[0].group(1))
        if first_scene_num == 1:
            shift = 1
    elif leading:
        # Standard fallback for short leading text before first marker
        segments.append({
            "scene_index": None,
            "scene_id": None,
            "text": leading,
            "source_file": None,
            "start_time": None,
            "end_time": None
        })
        clean_summary_parts.append(leading)
            
    for i, match in enumerate(matches):
        scene_num = int(match.group(1))
        target_scene_num = scene_num + shift
        
        start_idx = match.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        
        segment_text = raw_text[start_idx:end_idx].strip()
        if not segment_text:
            continue
            
        scene_idx = target_scene_num - 1
        scene_id = None
        source_file = None
        start_time = None
        end_time = None
        
        if 0 <= scene_idx < len(source_scenes):
            scene = source_scenes[scene_idx]
            scene_id = scene.get("scene_id")
            source_file = scene.get("source_file")
            start_time = scene.get("start_time")
            end_time = scene.get("end_time")
            
        segments.append({
            "scene_index": target_scene_num,
            "scene_id": scene_id,
            "text": segment_text,
            "source_file": source_file,
            "start_time": start_time,
            "end_time": end_time
        })
        clean_summary_parts.append(segment_text)
        
    # Reassemble clean summary without the [Scene X] markers
    clean_summary = " ".join(clean_summary_parts)
    return clean_summary, segments


def synthesize_narrative(
    entities: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    time_hint: Optional[str] = None,
    source_file: Optional[str] = None,
    modality: Optional[List[str]] = None,
    max_results: int = 25,
    grouping: str = "semantic_episode",
    summary_style: str = "narrative",
) -> Dict[str, Any]:
    """
    Execute chronological narrative search and synthesize results using a local LLM.
    Enforces the strict no-invention rule and preserves dynamic evidence metrics.
    """
    # 1. Fetch matching scene sequence
    search_res = temporal_search(
        entities=entities,
        start_date=start_date,
        end_date=end_date,
        time_hint=time_hint,
        source_file=source_file,
        modality=modality,
        max_results=max_results,
        grouping=grouping,
    )
    results = search_res.get("results", [])
    total_found = len(results)

    # 2. Dynamic truncation (Cap at 20 scenes initially, then adjust dynamically)
    limit = min(20, total_found)
    truncated = total_found > 20
    sliced_results = []

    # Setup Base System Prompt (No-Invention and Direct Narrative Chronicler)
    base_system_prompt = (
        "You are an authoritative historical archivist and chronicler.\n"
        "Your task is to write a cohesive, synthesized chronological account of real events observed in a sequence of home video clips.\n\n"
        "CRITICAL WRITING STYLE CONSTRAINT (NO META-COMMENTARY):\n"
        "Do NOT write any meta-commentary, introductory explanations, summaries of your own task, or conclusions. "
        "Do NOT mention 'the transcripts', 'the dataset', 'the scenes', 'the recording', or 'the source files'. "
        "Do NOT write 'Based on the provided data', 'This text appears to be', or 'The sequence shows'. "
        "Simply describe the events, actions, people, and timestamps as direct historical facts. "
        "Write as if you are a narrator voiceover describing the actual history as it unfolds. "
        "For example, write 'Joe plays in the kitchen' instead of 'The transcript shows Joe playing'.\n\n"
        "CRITICAL NO-INVENTION CONTRACT:\n"
        "You must ONLY use facts explicitly stated in the provided observations. "
        "Do NOT invent, assume, or infer any emotions, feelings, states of mind, motives, or intentions for any person "
        "(e.g., do NOT say someone felt excited, nervous, angry, sad, glad, or wanted to help unless the source text explicitly states that emotion). "
        "Do NOT invent physical movements, transitions, or actions that are not explicitly documented in the observations "
        "(e.g., do NOT write that someone nodded, left the room, looked around, or walked unless it is explicitly in the description). "
        "If a detail is missing or ambiguous, do NOT try to fill it in; limit your description strictly to the visible facts. "
        "Your report must be completely objective, dry, and clinical, behaving like a careful nurse charting: observe, record, do NOT embellish or dramatize.\n\n"
    )

    if summary_style == "bullets":
        system_prompt = base_system_prompt + (
            "Format your response as a scan-friendly, chronological bulleted list of highlights. "
            "Start the list immediately with the first event. Do not write any intro or outro text."
        )
    elif summary_style == "executive":
        system_prompt = base_system_prompt + (
            "Format your response as a formal, high-level executive briefing. "
            "Summarize the core actions, settings, and historical transitions. Keep it objective, professional, and direct. "
            "Start the briefing immediately with the first event. Do not write any intro or outro text."
        )
    else:  # narrative
        system_prompt = base_system_prompt + (
            "Format your response as a single continuous paragraph of plain text. "
            "Do NOT use markdown, do NOT use bold text, do NOT use bullet points, do NOT list observations or scenes separately. "
            "Connect the facts of each observation chronologically into a single, cohesive, flowing paragraph. "
            "Start writing the paragraph directly. Do not include any headers, titles, or tags.\n\n"
            "CRITICAL SEGMENTATION REQUIREMENT:\n"
            "To map the narrative to source video clips, you MUST prefix each scene's narrative transition with its exact observation index marker in square brackets, like '[Scene X]'. "
            "For example: '[Scene 1] Joe plays in the kitchen. [Scene 2] He then moves to the living room.' "
            "You must write '[Scene X]' (where X is the Observation # number) exactly before you describe the events of Observation #X.\n\n"
            "The very first characters of your output MUST be '[Scene 1]'. Do NOT write any introductory text."
        )

    # Iterative prompt builder to ensure context window compliance
    while limit > 0:
        sliced_results = results[:limit]
        scenes_str = ""
        for i, r in enumerate(sliced_results):
            # Filter out bounding boxes and system voice patterns from entity list
            clean_entities = []
            for ent in r.get("entities", []):
                ent_str = str(ent).strip()
                if not ent_str or ent_str.startswith("{") or "bbox" in ent_str or "voice_pattern" in ent_str:
                    continue
                clean_entities.append(ent_str)

            scenes_str += f"Observation #{i+1}:\n"
            scenes_str += f"  Time: {r['timestamp_label']} ({r['start_time']}s to {r['end_time']}s)\n"
            scenes_str += f"  File: {r['source_file']}\n"
            if clean_entities:
                scenes_str += f"  Entities: {', '.join(clean_entities)}\n"
            
            summary_val = clean_scene_description(r.get("summary", ""))
            if summary_val:
                scenes_str += f"  Description: {summary_val}\n"
            
            transcript = r.get("evidence", {}).get("transcript", "")
            if transcript:
                if len(transcript) > 200:
                    transcript = transcript[:200] + "... [truncated]"
                scenes_str += f"  Audio Heard: \"{transcript}\"\n"
            scenes_str += "\n"

        source_count = len(sliced_results)
        
        if summary_style == "narrative":
            user_prompt = (
                "Write a continuous chronological report of these events. Start the report directly and connect observations smoothly. "
                "Do NOT include introductory remarks, summaries, or conclusions. "
                "Do NOT list events by number. Write a single unified text block. "
                "Enforce the CRITICAL SEGMENTATION REQUIREMENT: prefix each scene's narrative transition with its exact observation index marker in square brackets, like '[Scene X]' where X is the observation index.\n\n"
                "Remember: The very first characters of your output MUST be '[Scene 1]'. Do NOT write any introductory text.\n\n"
                f"{scenes_str}"
            )
        elif summary_style == "bullets":
            user_prompt = (
                "Generate a chronological list of bullet points for these events. Start the list directly. Do not include intro or outro text.\n\n"
                f"{scenes_str}"
            )
        else:  # executive
            user_prompt = (
                "Generate a formal executive briefing of these events. Start the briefing directly. Do not include intro or outro text.\n\n"
                f"{scenes_str}"
            )

        # Estimate input tokens: 1 token is approx 2.8 characters to be safe
        approx_tokens = (len(system_prompt) + len(user_prompt)) // 2.8
        if approx_tokens <= 3300 or limit <= 5:
            # We are within safe limits
            break
        
        # Otherwise, decrease limit by 2 to shrink the prompt
        limit -= 2
        truncated = True

    source_scene_ids = [r["scene_id"] for r in sliced_results]
    source_count = len(sliced_results)

    # 3. Handle empty matching state
    if not sliced_results:
        return {
            "query": {
                "entities": entities or [],
                "time_hint": time_hint,
                "summary_style": summary_style,
            },
            "summary": "No matching scenes were found. Cannot synthesize a narrative summary.",
            "model_used": "none",
            "status": "success",
            "source_scene_ids": [],
            "source_count": 0,
            "truncated": False,
            "warnings": [],
        }

    # 5. Initialize LLM Client with active configs
    cfg = load_configs({})
    try:
        models = build_llm_models(cfg)
        client = LLMClient(
            models=models,
            health_check_interval=60,
            max_retries=2,
            timeout=45,
            cache_ttl=300,
            enable_health_checks=True,
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLMClient: {e}", exc_info=True)
        return {
            "query": {
                "entities": entities or [],
                "time_hint": time_hint,
                "summary_style": summary_style,
            },
            "status": "llm_unavailable",
            "summary": "LLM client configuration is unavailable. Please verify config.yaml.",
            "model_used": "none",
            "source_scene_ids": source_scene_ids,
            "source_count": source_count,
            "truncated": truncated,
            "warnings": ["LLM client config error."],
        }

    if not client.available:
        return {
            "query": {
                "entities": entities or [],
                "time_hint": time_hint,
                "summary_style": summary_style,
            },
            "status": "llm_unavailable",
            "summary": "No local LLM services are running. Please start vLLM on port 38005 or Ollama on port 11434.",
            "model_used": "none",
            "source_scene_ids": source_scene_ids,
            "source_count": source_count,
            "truncated": truncated,
            "warnings": ["vLLM and Ollama are offline."],
        }

    # 6. Execute inference chat request
    try:
        # Prefer speed/low-latency model configs for bullets or executive style
        use_speed = summary_style in ("bullets", "executive")

        # Explicitly target fallback model for narrative style if it is healthy, since it is a larger 3B model
        target_model = None
        if not use_speed:
            health_status = client.check_all_health()
            status = health_status.get("Llama3.2-Ollama")
            if status and status.is_healthy:
                target_model = "Llama3.2-Ollama"
            else:
                reason = "offline" if status else "not found in models registry"
                logger.error(f"Llama3.2-Ollama is {reason}. Narrative style generation is blocked to prevent fictional hallucinations.")
                return {
                    "query": {
                        "entities": entities or [],
                        "time_hint": time_hint,
                        "summary_style": summary_style,
                    },
                    "status": "llm_unavailable",
                    "summary": "The high-quality model (Llama3.2-Ollama) required for narrative synthesis is offline or unavailable. Generation is blocked to prevent fictional hallucinations.",
                    "model_used": "none",
                    "source_scene_ids": source_scene_ids,
                    "source_count": source_count,
                    "truncated": truncated,
                    "warnings": [f"Llama3.2-Ollama is {reason}."],
                }
        
        # Estimate input tokens: 1 token is approx 2.8 characters
        approx_input_tokens = (len(system_prompt) + len(user_prompt)) // 2.8
        # vLLM maximum window is 4096; leave a 150 token safety margin
        max_response_tokens = max(256, min(1024, 4096 - int(approx_input_tokens) - 150))

        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model_name=target_model,
            prefer_speed=use_speed,
            temperature=0.3,  # Keep temperature low for high factual precision
            max_tokens=max_response_tokens,  # Bounded dynamically to fit in context window
        )
        
        summary_text = response["choices"][0]["message"]["content"].strip()
        model_used = client.get_active_model() or "unknown"

        if not use_speed and model_used != "Llama3.2-Ollama":
            logger.error(f"Inference failed or failed over to {model_used} during narrative synthesis. Blocking response to prevent fictional hallucinations.")
            return {
                "query": {
                    "entities": entities or [],
                    "time_hint": time_hint,
                    "summary_style": summary_style,
                },
                "status": "llm_unavailable",
                "summary": "The high-quality model (Llama3.2-Ollama) failed to respond. Narrative synthesis is blocked to prevent fictional hallucinations.",
                "model_used": model_used,
                "source_scene_ids": source_scene_ids,
                "source_count": source_count,
                "truncated": truncated,
                "warnings": [f"Failover from Llama3.2-Ollama to {model_used} occurred."],
            }

        segments = None
        if summary_style == "narrative":
            summary_text, segments = parse_narrative_segments(summary_text, sliced_results)

        warnings_list = []
        if truncated:
            warnings_list.append("Only the top 20 matching scenes were summarized.")

        return {
            "query": {
                "entities": entities or [],
                "time_hint": time_hint,
                "summary_style": summary_style,
            },
            "summary": summary_text,
            "segments": segments,
            "model_used": model_used,
            "status": "success",
            "source_scene_ids": source_scene_ids,
            "source_count": source_count,
            "truncated": truncated,
            "warnings": warnings_list,
        }
    except Exception as e:
        logger.error(f"LLM synthesis invocation failed: {e}", exc_info=True)
        return {
            "query": {
                "entities": entities or [],
                "time_hint": time_hint,
                "summary_style": summary_style,
            },
            "status": "llm_unavailable",
            "summary": f"LLM inference request failed: {str(e)}",
            "model_used": "none",
            "source_scene_ids": source_scene_ids,
            "source_count": source_count,
            "truncated": truncated,
            "warnings": [f"Inference error: {str(e)}"],
        }
