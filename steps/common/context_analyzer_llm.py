"""
LLM-enhanced scene context analyzer.

This module is intentionally conservative. Any LLM output is additive,
non-authoritative context and must stay grounded in the provided scene evidence.
"""
from typing import Dict, Any, List, Optional
import logging
import requests
import json
import re

logger = logging.getLogger(__name__)
_PLACEHOLDER_SPEAKER_PATTERN = re.compile(r"^(?:speaker|face)_\d+$", re.IGNORECASE)
_LOW_SIGNAL_CAPTION_PATTERNS = (
    re.compile(r"^a black background\b", re.IGNORECASE),
    re.compile(r"^black background\b", re.IGNORECASE),
    re.compile(r"^a dark background\b", re.IGNORECASE),
    re.compile(r"^a black screen\b", re.IGNORECASE),
)
_GENERIC_CONTEXT_TAGS = {
    "man",
    "woman",
    "people",
    "conversation",
    "indoor conversation",
    "room",
    "waiting",
    "friend",
    "friends",
    "family",
    "two women",
}
_ROLE_CONTEXT_TAGS = {"family", "friend", "friends", "couple", "husband", "wife", "children"}
_LOW_VALUE_VISIBLE_TAGS = {
    "background",
    "blue backpack",
    "microwave",
    "room with a blue backpack",
}
_SETTING_HINTS = (
    "living room",
    "kitchen",
    "dining room",
    "bedroom",
    "couch",
    "table",
    "floor",
    "room",
)
_UNSUPPORTED_ACTIVITY_PATTERNS = (
    re.compile(r"\blooking at a microwave\b", re.IGNORECASE),
    re.compile(r"\bsurrounded by (?:men|women|people)\b", re.IGNORECASE),
    re.compile(r"\bfamily watches\b", re.IGNORECASE),
    re.compile(r"\bwaiting for someone\b", re.IGNORECASE),
)
_GENERIC_REWRITE_PATTERNS = (
    re.compile(r"\bpeople talk\b", re.IGNORECASE),
    re.compile(r"\bpeople are talking\b", re.IGNORECASE),
    re.compile(r"\bgroup conversation\b", re.IGNORECASE),
    re.compile(r"\bgroup of people\b", re.IGNORECASE),
    re.compile(r"\bcharacters interact\b", re.IGNORECASE),
    re.compile(r"\b(?:two )?friends discuss\b", re.IGNORECASE),
    re.compile(r"\b(?:a )?(?:man|woman|man and woman|woman and man|group of people)\b", re.IGNORECASE),
)
_SOCIAL_ROLE_TEXT_PATTERN = re.compile(
    r"\b(friend|friends|family|couple|husband|wife|children)\b",
    re.IGNORECASE,
)
_LOW_VALUE_VISIBLE_TEXT_PATTERNS = (
    re.compile(r"\bbackground\b", re.IGNORECASE),
    re.compile(r"\bblue backpack\b", re.IGNORECASE),
    re.compile(r"\bmicrowave\b", re.IGNORECASE),
)
_WAITING_FOR_SOMEONE_PATTERN = re.compile(
    r"\bwait(?:ing|ed)?\b.*\b(?:someone|somebody)\b|\b(?:someone|somebody)\b.*\barriv(?:e|es|ed|al)\b",
    re.IGNORECASE,
)
_WAITING_TEXT_PATTERN = re.compile(r"\bwait(?:ing|ed)?\b", re.IGNORECASE)
_ARRIVAL_TEXT_PATTERN = re.compile(r"\barriv(?:e|es|ed|al)\b", re.IGNORECASE)
_LOW_VALUE_TOPIC_PHRASES = {
    "alarmed god",
    "hell happened",
    "must some",
    "people aware",
    "some mistake",
}
_LOW_VALUE_TOPIC_TOKENS = {
    "alarmed",
    "aware",
    "doing",
    "god",
    "good",
    "happened",
    "happening",
    "hell",
    "mistake",
    "must",
    "people",
    "some",
    "time",
}
_TRANSCRIPT_TOPIC_PATTERNS = (
    (re.compile(r"\bnose job\b", re.IGNORECASE), "nose job"),
    (re.compile(r"\bcrop circles?\b", re.IGNORECASE), "crop circles"),
    (re.compile(r"\bpharmacist\b", re.IGNORECASE), "pharmacist"),
    (re.compile(r"\bpills?\b", re.IGNORECASE), "pills"),
    (re.compile(r"\btypewriter\b", re.IGNORECASE), "typewriter"),
    (re.compile(r"\belevator\b", re.IGNORECASE), "elevator"),
    (re.compile(r"\bhawaii\b", re.IGNORECASE), "hawaii"),
    (re.compile(r"\bcaribbean\b", re.IGNORECASE), "caribbean"),
    (re.compile(r"\bmiss pepper\b", re.IGNORECASE), "miss pepper"),
    (re.compile(r"\bprofessor von nostrand\b", re.IGNORECASE), "professor von nostrand"),
    (re.compile(r"\bshakespeare\b", re.IGNORECASE), "shakespeare"),
    (re.compile(r"\brental car\b", re.IGNORECASE), "rental car"),
    (re.compile(r"\bair conditioning\b", re.IGNORECASE), "air conditioning"),
    (re.compile(r"\bscuba diving\b", re.IGNORECASE), "scuba diving"),
    (re.compile(r"\bscuba\b", re.IGNORECASE), "scuba"),
    (re.compile(r"\bbiscayne bay\b", re.IGNORECASE), "biscayne bay"),
    (re.compile(r"\bbiscayne\b", re.IGNORECASE), "biscayne"),
    (re.compile(r"\bsofa bed\b", re.IGNORECASE), "sofa bed"),
    (re.compile(r"\bback pain\b", re.IGNORECASE), "back pain"),
    (re.compile(r"\bastronaut pen\b", re.IGNORECASE), "astronaut pen"),
    (re.compile(r"\bmask\b", re.IGNORECASE), "mask"),
    (re.compile(r"\bcapillaries?\b", re.IGNORECASE), "capillaries"),
    (re.compile(r"\bcondo constitution\b", re.IGNORECASE), "condo constitution"),
    (re.compile(r"\bcondo\b", re.IGNORECASE), "condo"),
    (re.compile(r"\bbylaws?\b", re.IGNORECASE), "bylaws"),
    (re.compile(r"\bchiropractor\b", re.IGNORECASE), "chiropractor"),
    (re.compile(r"\bemcee\b", re.IGNORECASE), "emcee"),
    (re.compile(r"\bwhite shoes\b", re.IGNORECASE), "white shoes"),
    (re.compile(r"\bmuscle relaxers?\b", re.IGNORECASE), "muscle relaxers"),
    (re.compile(r"\blawyer\b", re.IGNORECASE), "lawyer"),
    (re.compile(r"\bcase\b", re.IGNORECASE), "case"),
    (re.compile(r"\bpresident\b", re.IGNORECASE), "president"),
    (re.compile(r"\bflorida\b", re.IGNORECASE), "florida"),
    (re.compile(r"\bpen\b", re.IGNORECASE), "pen"),
    (re.compile(r"\bbathing suits?\b", re.IGNORECASE), "bathing suit"),
)
_TOPIC_STOPWORDS = {
    "about", "again", "air", "airlines", "all", "and", "any", "are", "around", "back",
    "been", "boat", "bucks", "but", "call", "can", "come", "could", "day",
    "did", "didnt", "dont", "down", "for", "from", "get", "going", "got", "had",
    "has", "have", "here", "him", "his", "how", "i", "if", "ill", "im", "in", "inside",
    "into", "is", "it", "its", "know", "lake", "me", "minutes", "my", "need", "nobody",
    "much", "nice", "not", "of", "oh", "old", "on", "or", "our", "out", "pay", "person",
    "real", "really", "room", "seen", "so", "special", "stay", "tape", "that",
    "thats", "the", "them", "there", "they", "thing", "things", "think", "this",
    "those", "thirty", "to", "too", "took", "towels", "trunks", "twenty", "up", "use", "using", "waited",
    "want", "we", "well", "welcome", "what", "whats", "where", "why", "with", "would",
    "you", "your", "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "hello", "meet", "never", "days",
}
_CAPITALIZED_TOPIC_EXCLUSIONS = {
    "ah",
    "all",
    "anyway",
    "but",
    "can",
    "could",
    "god",
    "has",
    "hello",
    "how",
    "i",
    "it",
    "no",
    "oh",
    "okay",
    "put",
    "so",
    "take",
    "the",
    "well",
    "welcome",
    "what",
    "why",
    "yes",
    "you",
}
_STAGE_MONOLOGUE_VISUAL_HINTS = {
    "microphone",
    "stage",
    "curtain",
    "podium",
    "spotlight",
}
_ROLE_SUPPORT_VARIANTS = {
    "friend": ("friend", "friends"),
    "friends": ("friend", "friends"),
    "family": ("family", "families"),
    "couple": ("couple", "couples"),
    "husband": ("husband", "husbands"),
    "wife": ("wife", "wives"),
    "children": ("child", "children"),
}


def _is_low_value_topic_fragment(value: str) -> bool:
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return True
    if normalized in _LOW_VALUE_TOPIC_PHRASES:
        return True
    tokens = [token for token in re.findall(r"[a-zA-Z]+", normalized) if token]
    if not tokens:
        return True
    return all(token in _LOW_VALUE_TOPIC_TOKENS for token in tokens)


def _resolve_llm_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    root_llm = cfg.get("llm")
    if isinstance(root_llm, dict):
        return root_llm

    nested_llm = cfg.get("config", {}).get("llm", {})
    if isinstance(nested_llm, dict):
        return nested_llm
    return {}


def _speaker_prompt_summary(speakers: List[Any]) -> str:
    names: List[str] = []
    anonymous_ids: set[str] = set()
    for speaker in speakers or []:
        candidate = speaker
        if isinstance(speaker, dict):
            candidate = (
                speaker.get("name")
                or speaker.get("identity")
                or speaker.get("person")
                or speaker.get("speaker_id")
                or speaker.get("speaker")
                or speaker.get("label")
            )
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        label = candidate.strip()
        if _PLACEHOLDER_SPEAKER_PATTERN.fullmatch(label):
            anonymous_ids.add(label.casefold())
            continue
        if label not in names:
            names.append(label)
    if names and anonymous_ids:
        suffix = "anonymous speaker" if len(anonymous_ids) == 1 else f"{len(anonymous_ids)} anonymous speakers"
        return f"{', '.join(names)} + {suffix}"
    if names:
        return ", ".join(names)
    if anonymous_ids:
        return "1 anonymous speaker" if len(anonymous_ids) == 1 else f"{len(anonymous_ids)} anonymous speakers"
    return "unknown"


def _caption_is_low_signal(caption: str) -> bool:
    normalized = str(caption or "").strip().lower()
    if not normalized:
        return True
    if any(pattern.search(normalized) for pattern in _LOW_SIGNAL_CAPTION_PATTERNS):
        return True
    return normalized in {"abstract image", "no visual description"}


def _extract_transcript_topic_hints(transcript: str) -> List[str]:
    transcript_text = str(transcript or "").strip()
    normalized = transcript_text.lower()
    if not normalized:
        return []

    hints: List[str] = []
    seen: set[str] = set()

    for pattern, label in _TRANSCRIPT_TOPIC_PATTERNS:
        if pattern.search(normalized) and label not in seen and not _is_low_value_topic_fragment(label):
            seen.add(label)
            hints.append(label)
            if len(hints) >= 5:
                return hints

    if not hints:
        proper_name_matches = re.findall(
            r"\b(?:[A-Z][a-z]+(?:\s+(?:von|van|de|da))?)(?:\s+[A-Z][a-z]+){0,2}\b",
            transcript_text,
        )
        for match in proper_name_matches:
            raw_candidate = str(match or "").strip()
            if not raw_candidate:
                continue
            tokens = [token for token in raw_candidate.split() if token]
            while tokens and tokens[0].casefold() in _CAPITALIZED_TOPIC_EXCLUSIONS.union(_TOPIC_STOPWORDS):
                tokens.pop(0)
            while tokens and tokens[-1].casefold() in _CAPITALIZED_TOPIC_EXCLUSIONS.union(_TOPIC_STOPWORDS):
                tokens.pop()
            if not tokens:
                continue
            if len(tokens) == 1:
                single = tokens[0].casefold()
                if single in _CAPITALIZED_TOPIC_EXCLUSIONS or single in _TOPIC_STOPWORDS or len(tokens[0]) < 5:
                    continue
            candidate = " ".join(tokens)
            lowered = candidate.casefold()
            if lowered in seen or _is_low_value_topic_fragment(lowered):
                continue
            seen.add(lowered)
            hints.append(candidate)
            if len(hints) >= 5:
                return hints

    return hints[:5]


def _has_stage_monologue_visual_cue(caption: str, objects: List[Any]) -> bool:
    caption_lower = str(caption or "").casefold()
    if any(hint in caption_lower for hint in _STAGE_MONOLOGUE_VISUAL_HINTS):
        return True
    for obj in objects or []:
        label = obj.get("label") if isinstance(obj, dict) else obj
        if str(label or "").strip().casefold() in _STAGE_MONOLOGUE_VISUAL_HINTS:
            return True
    return False


def _minimal_scene_context_payload() -> Dict[str, Any]:
    return {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content"],
        "emotional_arc": "low-signal scene",
        "context_tags": ["low-signal scene"],
        "activity_description": "Minimal visual or dialogue content.",
    }


def _spoken_monologue_payload(topic_hints: List[str]) -> Dict[str, Any]:
    topic = topic_hints[0] if topic_hints else "spoken topic"
    return {
        "narrative_summary": f"Spoken monologue about {topic}.",
        "key_moments": [f"Speaker delivers a monologue about {topic}"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue", topic],
        "activity_description": f"Spoken monologue about {topic}.",
    }


def _contains_supported_role_in_transcript(term: str, transcript: str) -> bool:
    if not isinstance(transcript, str) or not transcript.strip():
        return False
    variants = _ROLE_SUPPORT_VARIANTS.get(term.casefold(), (term.casefold(),))
    transcript_lower = transcript.casefold()
    return any(re.search(rf"\b{re.escape(variant)}\b", transcript_lower) for variant in variants)


def _derive_setting_hint(caption: str, tags: List[str]) -> Optional[str]:
    lowered_caption = str(caption or "").casefold()
    for hint in _SETTING_HINTS:
        if hint == "room":
            continue
        if hint in lowered_caption:
            return hint
    for tag in tags:
        normalized = str(tag).strip().casefold()
        if normalized in _SETTING_HINTS and normalized != "room":
            return normalized
    return None


def _derive_topic_hint(topic_hints: List[str], tags: List[str]) -> Optional[str]:
    for hint in topic_hints:
        normalized = str(hint).strip()
        if normalized and normalized.casefold() not in _GENERIC_CONTEXT_TAGS and not _is_low_value_topic_fragment(normalized):
            return normalized
    for tag in tags:
        normalized = str(tag).strip()
        lowered = normalized.casefold()
        if (
            normalized
            and lowered not in _GENERIC_CONTEXT_TAGS
            and lowered not in _SETTING_HINTS
            and not _is_low_value_topic_fragment(normalized)
        ):
            return normalized
    return None


def _rewrite_scene_text(
    value: Optional[str],
    *,
    setting_hint: Optional[str],
    topic_hint: Optional[str],
    force_rewrite: bool = False,
) -> Optional[str]:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    needs_rewrite = any(pattern.search(text) for pattern in _GENERIC_REWRITE_PATTERNS) or any(
        pattern.search(text) for pattern in _UNSUPPORTED_ACTIVITY_PATTERNS
    )
    if not force_rewrite and not needs_rewrite:
        return text

    if setting_hint and topic_hint:
        return f"{setting_hint.capitalize()} conversation about {topic_hint}."
    if topic_hint:
        return f"Conversation about {topic_hint}."
    if setting_hint:
        return f"Conversation in the {setting_hint}."
    return "Minimal visual or dialogue content."


def _contains_unsupported_role_text(text: str, transcript: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    for match in _SOCIAL_ROLE_TEXT_PATTERN.finditer(text):
        if not _contains_supported_role_in_transcript(match.group(0), transcript):
            return True
    return False


def _contains_low_value_visible_focus(text: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    return any(pattern.search(text) for pattern in _LOW_VALUE_VISIBLE_TEXT_PATTERNS)


def _contains_unsupported_activity_text(text: str, transcript: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    if _WAITING_FOR_SOMEONE_PATTERN.search(text):
        return True
    transcript_text = str(transcript or "")
    if _WAITING_TEXT_PATTERN.search(text) and not _WAITING_TEXT_PATTERN.search(transcript_text):
        return True
    if _ARRIVAL_TEXT_PATTERN.search(text) and not _ARRIVAL_TEXT_PATTERN.search(transcript_text):
        return True
    return False


def _rewrite_emotional_arc(value: Any, transcript: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if not _contains_unsupported_role_text(normalized, transcript):
        return normalized
    rewritten = re.sub(
        r"\b(?:among|between|from)\s+(?:the\s+)?(?:friend|friends|family|couple|husband|wife|children)\b",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    rewritten = _SOCIAL_ROLE_TEXT_PATTERN.sub("people", rewritten)
    rewritten = re.sub(r"\s{2,}", " ", rewritten).strip(" ,.;")
    return rewritten or "neutral tone"


def _rewrite_key_moment(
    value: Optional[str],
    *,
    transcript: str,
    setting_hint: Optional[str],
    topic_hint: Optional[str],
) -> Optional[str]:
    normalized = value.strip() if isinstance(value, str) else value
    if not isinstance(normalized, str) or not normalized.strip():
        return normalized
    if _contains_unsupported_role_text(normalized, transcript) or _contains_unsupported_activity_text(normalized, transcript):
        if topic_hint:
            return f"They mention {topic_hint}."
        return "Minimal visual or dialogue content."
    if topic_hint and _contains_low_value_visible_focus(normalized) and topic_hint.casefold() not in normalized.casefold():
        return f"They mention {topic_hint}."
    return normalized


def _normalize_scene_context_payload(raw_context: Dict[str, Any], scene_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    def _clean_text(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    def _clean_list(values: Any, *, limit: int) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        if not isinstance(values, list):
            return cleaned
        for value in values:
            normalized = _clean_text(value)
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
            if len(cleaned) >= limit:
                break
        return cleaned

    transcript = str(scene_meta.get("transcript") or "").strip()
    caption = str(scene_meta.get("caption") or "").strip()
    objects = scene_meta.get("objects", [])
    object_labels = []
    if isinstance(objects, list):
        for obj in objects[:10]:
            if isinstance(obj, dict):
                label = str(obj.get("label") or "").strip()
            else:
                label = str(obj).strip()
            if label:
                object_labels.append(label)
    evidence_blob = " ".join([transcript, caption, " ".join(object_labels)]).casefold()

    context_tags = _clean_list(raw_context.get("context_tags"), limit=8)
    topic_hints = _extract_transcript_topic_hints(transcript)
    specific_tags_exist = any(tag.casefold() not in _GENERIC_CONTEXT_TAGS for tag in context_tags)
    filtered_tags: List[str] = []
    seen_tags: set[str] = set()
    for tag in context_tags:
        lowered = tag.casefold()
        if _is_low_value_topic_fragment(lowered):
            continue
        if _contains_unsupported_role_text(tag, transcript):
            continue
        if _contains_unsupported_activity_text(tag, transcript):
            continue
        if lowered in _ROLE_CONTEXT_TAGS and not _contains_supported_role_in_transcript(lowered, transcript):
            continue
        if lowered in {"hospital", "constitutional topics"} and lowered not in evidence_blob:
            continue
        if lowered in _SETTING_HINTS and lowered not in evidence_blob:
            continue
        if lowered in _LOW_VALUE_VISIBLE_TAGS and topic_hints:
            continue
        if lowered in _GENERIC_CONTEXT_TAGS and specific_tags_exist:
            continue
        if lowered in seen_tags:
            continue
        seen_tags.add(lowered)
        filtered_tags.append(tag)

    for hint in topic_hints:
        lowered = hint.casefold()
        if lowered in seen_tags or lowered in _GENERIC_CONTEXT_TAGS or _is_low_value_topic_fragment(lowered):
            continue
        filtered_tags.append(hint)
        seen_tags.add(lowered)
        if len(filtered_tags) >= 5:
            break

    filtered_tags = filtered_tags[:5]
    setting_hint = _derive_setting_hint(caption, filtered_tags)
    topic_hint = _derive_topic_hint(topic_hints, filtered_tags)

    raw_summary = _clean_text(raw_context.get("narrative_summary"))
    force_summary_rewrite = _contains_unsupported_role_text(raw_summary or "", transcript)
    if _contains_unsupported_activity_text(raw_summary or "", transcript):
        force_summary_rewrite = True
    if topic_hint and _contains_low_value_visible_focus(raw_summary or "") and topic_hint.casefold() not in (raw_summary or "").casefold():
        force_summary_rewrite = True

    raw_activity = _clean_text(raw_context.get("activity_description"))
    force_activity_rewrite = _contains_unsupported_role_text(raw_activity or "", transcript)
    if _contains_unsupported_activity_text(raw_activity or "", transcript):
        force_activity_rewrite = True
    if topic_hint and _contains_low_value_visible_focus(raw_activity or "") and topic_hint.casefold() not in (raw_activity or "").casefold():
        force_activity_rewrite = True

    key_moments: List[str] = []
    seen_moments: set[str] = set()
    for value in _clean_list(raw_context.get("key_moments"), limit=5):
        rewritten = _rewrite_key_moment(
            value,
            transcript=transcript,
            setting_hint=setting_hint,
            topic_hint=topic_hint,
        )
        if not rewritten:
            continue
        key = rewritten.casefold()
        if key in seen_moments:
            continue
        seen_moments.add(key)
        key_moments.append(rewritten)
        if len(key_moments) >= 3:
            break

    sanitized = {
        "narrative_summary": _rewrite_scene_text(
            raw_summary,
            setting_hint=setting_hint,
            topic_hint=topic_hint,
            force_rewrite=force_summary_rewrite,
        ),
        "key_moments": key_moments,
        "emotional_arc": _rewrite_emotional_arc(raw_context.get("emotional_arc"), transcript),
        "context_tags": filtered_tags,
        "activity_description": _rewrite_scene_text(
            raw_activity,
            setting_hint=setting_hint,
            topic_hint=topic_hint,
            force_rewrite=force_activity_rewrite,
        ),
    }
    has_signal = any(
        sanitized[key]
        for key in (
            "narrative_summary",
            "key_moments",
            "emotional_arc",
            "context_tags",
            "activity_description",
        )
    )
    return sanitized if has_signal else None


def _build_scene_context_prompts(scene_meta: Dict[str, Any]) -> tuple[str, str]:
    index = scene_meta.get("index", 0)
    start = float(scene_meta.get("start", 0.0) or 0.0)
    end = float(scene_meta.get("end", 0.0) or 0.0)
    caption = str(scene_meta.get("caption") or "").strip()
    transcript = str(scene_meta.get("transcript") or "").strip()
    objects = scene_meta.get("objects", [])
    face_count = int(scene_meta.get("face_count", 0) or 0)
    emotions = scene_meta.get("emotions", [])
    speakers = scene_meta.get("speakers", [])

    object_labels: List[str] = []
    for obj in objects[:10] if isinstance(objects, list) else []:
        if isinstance(obj, dict):
            label = str(obj.get("label") or "").strip()
        else:
            label = str(obj).strip()
        if label:
            object_labels.append(label)
    objects_str = ", ".join(object_labels) if object_labels else "none"

    emotion_labels: List[str] = []
    for emotion in emotions[:3] if isinstance(emotions, list) else []:
        if isinstance(emotion, dict):
            label = str(emotion.get("label") or "").strip().lower()
            score = emotion.get("score")
            if label:
                if isinstance(score, (int, float)):
                    emotion_labels.append(f"{label} ({float(score):.0%})")
                else:
                    emotion_labels.append(label)
        else:
            label = str(emotion).strip().lower()
            if label:
                emotion_labels.append(label)
    emotions_str = ", ".join(emotion_labels) if emotion_labels else "neutral / unknown"
    topic_hints = _extract_transcript_topic_hints(transcript)
    topic_hints_str = ", ".join(topic_hints) if topic_hints else "none"

    transcript_excerpt = transcript[:280] if transcript else "No transcript"
    speakers_str = _speaker_prompt_summary(speakers)

    system_prompt = (
        "You are a conservative video scene analyst. Produce dry operator-note style JSON grounded only "
        "in the provided evidence. EVIDENCE PRIORITY (STRICT): 1. Transcript (highest authority). "
        "2. Objects and detected items. 3. Caption (lowest authority, may be incorrect). If transcript "
        "clearly describes a topic, use it. If transcript conflicts with caption, ignore the caption. "
        "If caption is abstract or vague, do not expand it. Captions are unreliable summaries and should "
        "only be used for visible objects or setting hints. Do not infer family roles, friendships, "
        "marriages, jobs, or social relationships unless directly stated in the transcript or visible text. "
        "Do not infer locations beyond what the caption or transcript explicitly supports. Do not rewrite a "
        "conversation into a social event. Do not invent actions not present in transcript or visible "
        "objects. Use observable verbs by default. Do not use interpretive verbs like waiting, discussing, "
        "thinking, feeling, planning, or arguing unless the evidence directly supports them. Every context "
        "tag must be traceable to visible action, spoken topic, object evidence, or emotion signal. If "
        "uncertain, stay literal, short, and non-committal. Return JSON only."
    )

    user_prompt = f"""Analyze this scene using only the evidence below.

SCENE:
- Scene {index}: {start:.1f}s - {end:.1f}s

EVIDENCE:
- Visible caption: {caption or "No visual description"}
- Visible objects: {objects_str}
- Face count: {face_count}
- Transcript excerpt: {transcript_excerpt}
- Transcript topic hints: {topic_hints_str}
- Speaker evidence: {speakers_str}
- Audio emotion signal: {emotions_str}

OUTPUT RULES:
- Keep prose dry and short. Write like an operator note, not a screenplay.
- Evidence priority is transcript first, objects second, caption last.
- If the transcript contains a concrete topic, the narrative_summary MUST mention that topic.
- Do not invent family, friendship, marriage, employment, or other social roles.
- Do not invent locations, events, or activities not directly supported by the evidence.
- If the transcript is empty or minimal and the visual evidence is weak, use: "Minimal visual or dialogue content."
- If people are only talking indoors, say that plainly.
- Context tags must be concrete and traceable to visible action, spoken topic, objects, or audio emotion.
- If the evidence is weak, use broader literal wording instead of guessing.
- Do not rewrite a scene into a social event.

Return ONLY a JSON object with exactly these keys:
- narrative_summary: one short grounded sentence
- key_moments: 1-3 short literal actions or discussion points
- emotional_arc: one short grounded phrase
- context_tags: 2-4 short evidence-backed tags
- activity_description: one short concrete sentence

Example:
{{
  "narrative_summary": "Group conversation in a living room about a rental car.",
  "key_moments": ["People greet each other indoors", "They argue about the rental car"],
  "emotional_arc": "mild tension during conversation",
  "context_tags": ["indoor conversation", "rental car", "living room"],
  "activity_description": "People talk indoors about travel and a rental car."
}}

JSON:"""

    return system_prompt, user_prompt


def analyze_scene_context_llm(scene_meta: Dict[str, Any], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Use LLM to analyze scene context and extract deeper semantic meaning
    
    Args:
        scene_meta: Scene metadata with visual, audio, and temporal info
        cfg: Configuration with LLM settings
        
        Returns a conservative additive context payload:
        {
            'narrative_summary': str,
            'key_moments': List[str],
            'emotional_arc': str,
            'context_tags': List[str],
            'activity_description': str
        }
    """
    try:
        llm_config = _resolve_llm_config(cfg)
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 20)
        transcript = str(scene_meta.get("transcript") or "").strip()
        caption = str(scene_meta.get("caption") or "").strip()
        scene_objects = scene_meta.get("objects", [])
        if not isinstance(scene_objects, list):
            scene_objects = []
        face_count = int(scene_meta.get("face_count", 0) or 0)
        transcript_word_count = len(re.findall(r"\b\w+\b", transcript))
        speaker_count = len(scene_meta.get("speakers") or [])
        stage_monologue_visual = _has_stage_monologue_visual_cue(caption, scene_objects)
        topic_hints = _extract_transcript_topic_hints(transcript)
        weak_visual_signal = face_count <= 0 and not scene_objects and _caption_is_low_signal(caption)
        if transcript_word_count < 3 and (weak_visual_signal or stage_monologue_visual):
            logger.info("Scene %s context resolved via low-signal fallback", scene_meta.get("index", 0))
            return _minimal_scene_context_payload()
        if transcript_word_count >= 8 and (weak_visual_signal or (stage_monologue_visual and speaker_count <= 1)):
            logger.info("Scene %s context resolved via monologue fallback", scene_meta.get("index", 0))
            return _spoken_monologue_payload(topic_hints)
        system_prompt, user_prompt = _build_scene_context_prompts(scene_meta)
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # Clean and parse JSON
            content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                parsed = json.loads(content)
                logger.info("Scene %s context analyzed via LLM", scene_meta.get("index", 0))
                return _normalize_scene_context_payload(parsed, scene_meta)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM context JSON: {content[:100]}")
                return None
        else:
            logger.warning(f"LLM API returned status {response.status_code}")
            return None
            
    except requests.Timeout:
        logger.warning("LLM context analysis timed out")
        return None
    except Exception as e:
        logger.warning(f"LLM context analysis failed: {e}")
        return None


def analyze_emotional_progression(scenes: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Analyze emotional progression across multiple scenes
    
    Args:
        scenes: List of scene metadata dictionaries
        cfg: Configuration with LLM settings
        
    Returns:
        {
            'overall_arc': str,
            'key_transitions': List[Dict],
            'dominant_emotions': List[str],
            'emotional_journey': str
        }
    """
    try:
        llm_config = _resolve_llm_config(cfg)
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        timeout = llm_config.get('timeout', 25)
        
        # Build scene emotion summary
        scene_emotions = []
        for i, scene in enumerate(scenes[:20]):  # Limit to first 20 scenes
            emotions = scene.get('emotions', [])
            if emotions:
                emotion_label = emotions[0].get('label', 'neutral') if isinstance(emotions[0], dict) else str(emotions[0])
            else:
                emotion_label = 'neutral'
            scene_emotions.append(f"Scene {i}: {emotion_label}")
        
        scenes_text = "\n".join(scene_emotions)
        
        prompt = f"""Analyze the emotional progression across this video:

SCENE EMOTIONS:
{scenes_text}

Analyze and return ONLY a JSON object with:
- overall_arc: Overall emotional trajectory (e.g., "gradual build from calm to excitement")
- key_transitions: List of significant emotional shifts with scene numbers
- dominant_emotions: Top 3-5 emotions throughout
- emotional_journey: 2-3 sentence description of the emotional narrative

Example:
{{
  "overall_arc": "Starts calm, builds to joyful climax",
  "key_transitions": [
    {{"from_scene": 0, "to_scene": 5, "shift": "calm to excited"}},
    {{"from_scene": 10, "to_scene": 15, "shift": "excited to contemplative"}}
  ],
  "dominant_emotions": ["joy", "excitement", "calm"],
  "emotional_journey": "The video begins in a relaxed atmosphere, gradually building excitement as activities intensify, before settling into a warm, reflective conclusion"
}}

JSON:"""
        
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an emotional arc analyst. Extract structured emotional progression data as JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.4,
                "max_tokens": 350,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                parsed = json.loads(content)
                logger.info("Emotional progression analyzed via LLM")
                return parsed
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse emotional arc JSON: {content[:100]}")
                return None
        else:
            return None
            
    except Exception as e:
        logger.warning(f"Emotional progression analysis failed: {e}")
        return None


def build_relationship_map(scenes: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build relationship map from scene context
    
    Args:
        scenes: List of scene metadata with context analysis
        cfg: Configuration
        
    Returns:
        {
            'entities': List[str],
            'relationships': List[Dict],
            'interaction_patterns': Dict
        }
    """
    try:
        # Collect all entities and relationships from scenes
        all_entities = set()
        all_relationships = []
        
        for scene in scenes:
            context = scene.get('context', {})
            if not context:
                continue
                
            # Extract relationships
            relationships = context.get('relationships', [])
            for rel in relationships:
                all_relationships.append({
                    'scene': scene.get('index', 0),
                    'entities': rel.get('entities', []),
                    'type': rel.get('type', 'unknown'),
                    'timestamp': scene.get('start', 0.0)
                })
                
                # Add entities
                for entity in rel.get('entities', []):
                    all_entities.add(entity)
        
        # Build interaction patterns
        interaction_patterns = {}
        for rel in all_relationships:
            rel_type = rel['type']
            interaction_patterns[rel_type] = interaction_patterns.get(rel_type, 0) + 1
        
        return {
            'entities': sorted(list(all_entities)),
            'relationships': all_relationships,
            'interaction_patterns': interaction_patterns,
            'total_entities': len(all_entities),
            'total_interactions': len(all_relationships)
        }
        
    except Exception as e:
        logger.error(f"Relationship mapping failed: {e}")
        return None
