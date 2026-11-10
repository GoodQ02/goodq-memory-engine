"""
LLM-enhanced scene context analyzer.

This module is intentionally conservative. Any LLM output is additive,
non-authoritative context and must stay grounded in the provided scene evidence.
"""
from typing import Dict, Any, List, Optional, TYPE_CHECKING
import logging
import requests
import json
import re

if TYPE_CHECKING:
    from lib.llm_client import LLMClient

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
    "man and woman",
    "man sitting on couch",
    "woman",
    "men",
    "person",
    "people",
    "conversation",
    "indoor conversation",
    "room",
    "waiting",
    "friend",
    "friends",
    "family",
    "two women",
    "men sitting",
    "men in a store",
    "woman in a suit",
    "spoken topic",
}
_ROLE_CONTEXT_TAGS = {"family", "friend", "friends", "couple", "husband", "wife", "children"}
_LOW_VALUE_VISIBLE_TAGS = {
    "background", "person", "people", "man", "men", "woman", "women", "spoken topic", "sitting",
}
_SETTING_HINTS = (
    "living room",
    "kitchen",
    "dining room",
    "bedroom",
    "bathroom",
    "restaurant",
    "store",
    "couch",
    "table",
    "floor",
    "room",
)
_STRUCTURAL_SETTING_HINTS = {"table", "room"}
_STRUCTURAL_CONTEXT_TAGS = {"conversation", "indoor conversation", "waiting", "low-signal scene", "spoken monologue"}
_UNSUPPORTED_ACTIVITY_PATTERNS = (
    re.compile(r"\bsurrounded by (?:men|women|people)\b", re.IGNORECASE),
    re.compile(r"\bfamily watches\b", re.IGNORECASE),
    re.compile(r"\bwaiting for someone\b", re.IGNORECASE),
)
_GENERIC_REWRITE_PATTERNS = (
    re.compile(r"\bpeople talk\b", re.IGNORECASE),
    re.compile(r"\bpeople are talking\b", re.IGNORECASE),
    re.compile(r"\bgroup conversation\b", re.IGNORECASE),
    re.compile(r"\bgroup of people\b", re.IGNORECASE),
    re.compile(r"\bgroup of coworkers\b", re.IGNORECASE),
    re.compile(r"\bcoworkers?\b", re.IGNORECASE),
    re.compile(r"\bcharacters interact\b", re.IGNORECASE),
    re.compile(r"\b(?:two )?friends discuss\b", re.IGNORECASE),
    re.compile(r"\bplans?\s+for\s+the\s+day\b", re.IGNORECASE),
    re.compile(r"\bday'?s\s+tasks?\b", re.IGNORECASE),
    re.compile(r"\b(?:a )?(?:man|woman|man and woman|woman and man|group of people)\b", re.IGNORECASE),
)
_SOCIAL_ROLE_TEXT_PATTERN = re.compile(
    r"\b(friend|friends|family|couple|husband|wife|children)\b",
    re.IGNORECASE,
)
_LOW_VALUE_VISIBLE_TEXT_PATTERNS = (
    re.compile(r"\bbackground\b", re.IGNORECASE),
    re.compile(r"\bman and woman\b", re.IGNORECASE),
    re.compile(r"\b(?:the\s+)?man and (?:the\s+)?woman\b", re.IGNORECASE),
    re.compile(r"\b(?:the\s+)?woman and (?:the\s+)?man\b", re.IGNORECASE),
    re.compile(r"\b(?:man|woman)\s+in\s+(?:(?:a|an)\s+)?(?:[a-z]+\s+){0,2}(?:robe|suit|jacket|dress|coat|shirt|tie)\b", re.IGNORECASE),
    re.compile(r"\bman sitting on couch\b", re.IGNORECASE),
    re.compile(r"\bwoman sitting on couch\b", re.IGNORECASE),
    re.compile(r"\bspoken topic\b", re.IGNORECASE),
    re.compile(r"\bperson\b", re.IGNORECASE),
    re.compile(r"\b(?:one|two|three|four)\s+(?:man|men|woman|women)\b", re.IGNORECASE),
    re.compile(r"\bmen(?:\s+sitting|\s+in\s+a\s+store)?\b", re.IGNORECASE),
)
_LOW_VALUE_VISUAL_KEY_MOMENT_PATTERNS = (
    re.compile(
        r"^(?:the|a|an|one|two|three|four)(?:\s+other)?\s+(?:man|men|woman|women|person)\b.*\b(?:sit|sits|sitting|stand|stands|standing|nod|nods|look|looks|looking|walk|walks|walking|enter|enters|leave|leaves|holding|holds|ask|asks)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:the|a|an)\s+(?:first|second|third|other)\s+(?:man|men|woman|women|person)\b.*\b(?:say|says|said|respond|responds|recognize|recognizes|remember|remembers|recall|recalls|confus(?:e|es|ed)|ask|asks)\b",
        re.IGNORECASE,
    ),
)
_INTERPRETIVE_REACTION_KEY_MOMENT_PATTERNS = (
    re.compile(r"\blooks?\s+confused\b", re.IGNORECASE),
    re.compile(r"\basks?\s+why\b", re.IGNORECASE),
    re.compile(r"\basks?\s+if\s+he\s+is\s+there\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+speaker\s+mentions?\b", re.IGNORECASE),
)
_CAPTION_SHAPED_VISUAL_NARRATION_PATTERNS = (
    re.compile(r"\bis\s+displayed\s+as\b", re.IGNORECASE),
    re.compile(r"\bare\s+seen\s+nearby\b", re.IGNORECASE),
)
_INTERPRETIVE_SUMMARY_PATTERNS = (
    re.compile(r"^\s*the\s+group\s+discuss(?:es|ing)?\b", re.IGNORECASE),
    re.compile(r"^\s*they\s+discuss(?:es|ing)?\b", re.IGNORECASE),
    re.compile(r"\bimpact\s+on\s+humanity\b", re.IGNORECASE),
    re.compile(r"\bcurrent\s+situation\b", re.IGNORECASE),
)
_GENERIC_KEY_MOMENT_TOKENS = {
    "a",
    "an",
    "and",
    "another",
    "answer",
    "answers",
    "are",
    "ask",
    "asked",
    "asking",
    "asks",
    "at",
    "character",
    "characters",
    "conversation",
    "converse",
    "conversing",
    "describe",
    "describes",
    "describing",
    "discuss",
    "discusses",
    "discussing",
    "explain",
    "explaining",
    "explains",
    "female",
    "he",
    "her",
    "him",
    "his",
    "identifies",
    "identify",
    "in",
    "individual",
    "individuals",
    "indoors",
    "indoor",
    "is",
    "it",
    "male",
    "man",
    "men",
    "mention",
    "mentions",
    "note",
    "notes",
    "noting",
    "one",
    "other",
    "people",
    "person",
    "present",
    "presents",
    "replies",
    "reply",
    "restaurant",
    "say",
    "says",
    "scene",
    "setting",
    "she",
    "sit",
    "sits",
    "sitting",
    "speak",
    "speaker",
    "speakers",
    "speaking",
    "speaks",
    "stand",
    "standing",
    "state",
    "states",
    "stating",
    "store",
    "table",
    "talk",
    "talking",
    "talks",
    "the",
    "their",
    "they",
    "this",
    "those",
    "to",
    "two",
    "up",
    "someone",
    "somebody",
    "else",
    "while",
    "woman",
    "women",
}
_WAITING_FOR_SOMEONE_PATTERN = re.compile(
    r"\bwait(?:ing|ed)?\b.*\b(?:someone|somebody)\b|\b(?:someone|somebody)\b.*\barriv(?:e|es|ed|al)\b",
    re.IGNORECASE,
)
_WAITING_TEXT_PATTERN = re.compile(r"\bwait(?:ing|ed)?\b", re.IGNORECASE)
_ARRIVAL_TEXT_PATTERN = re.compile(r"\barriv(?:e|es|ed|al)\b", re.IGNORECASE)

# Discourse fillers are not topics. Content words must not be corpus-blacklisted.
_LOW_VALUE_TOPIC_TOKENS = {"ah", "uh", "um", "oh", "okay", "ok", "yeah", "yep", "nope"}



# Generic stopwords delimit extractive hints; no names or plot vocabulary.
_TOPIC_STOPWORDS = {
    "a", "about", "again", "all", "an", "and", "any", "are", "around", "as", "at", "back",
    "been", "but", "call", "can", "come", "could", "day",
    "did", "didnt", "dont", "down", "for", "from", "get", "going", "got", "had",
    "has", "have", "here", "him", "his", "how", "i", "if", "ill", "im", "in", "inside",
    "into", "is", "it", "its", "know", "m", "me", "minutes", "my", "need", "nobody",
    "much", "nice", "not", "of", "oh", "on", "or", "our", "out", "pay", "person",
    "real", "really", "room", "seen", "so", "special", "stay", "that",
    "s", "thats", "the", "them", "there", "they", "thing", "things", "think", "this",
    "those", "thirty", "to", "too", "took", "twenty", "up", "use", "using", "waited",
    "want", "we", "well", "welcome", "what", "whats", "where", "why", "with", "would",
    "you", "your", "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "hello", "meet", "never", "days",
    "am", "be", "being", "was", "were", "yes", "yeah", "yep", "no", "nope",
    "ah", "uh", "um", "when", "while", "away", "pretty", "very", "keep", "own", "moment",
}



# Curtains also occur in ordinary rooms; they do not establish a stage.
_STAGE_MONOLOGUE_VISUAL_HINTS = {
    "microphone",
    "stage",
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
    tokens = re.findall(r"[^\W\d_]+", str(value or "").casefold())
    return (not tokens or tokens[-1] in {"a", "an", "the", "and", "or", "but", "is", "was", "were", "he", "she", "they", "to", "of", "in"}
            or all(token in _TOPIC_STOPWORDS or token in _LOW_VALUE_TOPIC_TOKENS for token in tokens))


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


def _prompt_evidence_values(value: Any, *, limit: int = 8) -> List[str]:
    values: List[str] = []

    def _append(raw: Any) -> None:
        if raw is None or len(values) >= limit:
            return
        text = str(raw).strip()
        if not text:
            return
        if text not in values:
            values.append(text)

    def _walk(raw: Any) -> None:
        if len(values) >= limit:
            return
        if isinstance(raw, dict):
            for key in ("label", "event", "context", "text", "value", "name"):
                _append(raw.get(key))
            for key in ("explicit_dates", "times", "weekdays", "months", "relative_phrases"):
                _walk(raw.get(key))
            return
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                _walk(item)
                if len(values) >= limit:
                    break
            return
        _append(raw)

    _walk(value)
    return values[:limit]


def _select_scene_object_labels(objects: Any, *, limit: int = 10) -> List[str]:
    labels: List[str] = []
    seen: set[str] = set()
    if not isinstance(objects, list) or limit <= 0:
        return labels
    for obj in objects:
        raw_label: Any = None
        if isinstance(obj, dict):
            for key in ("label", "name", "class"):
                candidate = obj.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    raw_label = candidate
                    break
        elif isinstance(obj, str):
            raw_label = obj
        if not isinstance(raw_label, str):
            continue
        label = raw_label.strip()
        if not label:
            continue
        normalized_key = label.casefold()
        if normalized_key in seen:
            continue
        seen.add(normalized_key)
        labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def _caption_is_low_signal(caption: str) -> bool:
    normalized = str(caption or "").strip().lower()
    if not normalized:
        return True
    if any(pattern.search(normalized) for pattern in _LOW_SIGNAL_CAPTION_PATTERNS):
        return True
    return normalized in {"abstract image", "no visual description"}


def _extract_transcript_topic_hints(transcript: str) -> List[str]:
    """Extract literal names/noun-like spans without corpus vocabulary or aliases.

    Hints are incomplete lexical aids, not a semantic topic classifier. Exact
    model-supplied topics are grounded separately; no match does not prove absence.
    """
    transcript_text = str(transcript or "").strip()
    normalized = transcript_text.lower()
    if not normalized:
        return []

    hints: List[str] = []
    seen: set[str] = set()

    if not hints:
        proper_name_matches = re.finditer(
            r"\b(?:[A-Z][a-z]+(?:\s+(?:von|van|de|da))?)(?:\s+[A-Z][a-z]+){0,2}\b",
            transcript_text,
        )
        for match in proper_name_matches:
            raw_candidate = str(match.group(0) or "").strip()
            if not raw_candidate:
                continue
            if transcript_text[match.end() : match.end() + 1] == "-":
                continue
            tokens = [token for token in raw_candidate.split() if token]
            while tokens and tokens[0].casefold() in _TOPIC_STOPWORDS:
                tokens.pop(0)
            while tokens and tokens[-1].casefold() in _TOPIC_STOPWORDS:
                tokens.pop()
            if not tokens:
                continue
            if len(tokens) == 1:
                continue
            candidate = " ".join(tokens)
            lowered = candidate.casefold()
            if lowered in seen or _is_low_value_topic_fragment(lowered):
                continue
            seen.add(lowered)
            hints.append(candidate)
            if len(hints) >= 5:
                return hints

    if not hints:
        clauses = [re.findall(r"[a-zA-Z]+", clause) for clause in re.split(r"[.!?,;:\n]+", normalized)]
        for window_size in (3, 2):
            for words in clauses:
                for index in range(0, len(words) - window_size + 1):
                    phrase_tokens = words[index : index + window_size]
                    while phrase_tokens and phrase_tokens[0] in _TOPIC_STOPWORDS:
                        phrase_tokens = phrase_tokens[1:]
                    while phrase_tokens and phrase_tokens[-1] in _TOPIC_STOPWORDS:
                        phrase_tokens = phrase_tokens[:-1]
                    if len(phrase_tokens) < 2:
                        continue
                    if any(token in _TOPIC_STOPWORDS or token in _LOW_VALUE_TOPIC_TOKENS for token in phrase_tokens):
                        continue
                    if phrase_tokens[0].endswith("ly") or phrase_tokens[0].endswith("ed"):
                        continue
                    head = phrase_tokens[-1]
                    if head.endswith("ing"):
                        continue
                    has_noun_suffix = head.endswith(("ment", "tion", "sion", "ness", "ship", "ist", "ity")) and not (
                        head.endswith("ist") and len(head) < 6
                    )
                    if not has_noun_suffix:
                        continue
                    candidate = " ".join(phrase_tokens)
                    if (candidate in seen or _is_low_value_topic_fragment(candidate)
                            or not _is_evidence_grounded_topic_candidate(candidate, transcript_text)):
                        continue
                    seen.add(candidate)
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
        "primary_tags": [],
        "contextual_tags": [],
        "structural_tags": ["low-signal scene"],
        "activity_description": "Minimal visual or dialogue content.",
    }


def _transcription_coverage_warning_regions(coverage: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [row for row in coverage.get("regions", []) if isinstance(row, dict)
            and (row.get("outcome") != "text_returned" or row.get("quality_flags")
                 or row.get("unplaced_segments") or row.get("timing_retry") == "error")]


def _transcription_coverage_is_uncertain(scene_meta: Dict[str, Any]) -> bool:
    coverage = scene_meta.get("transcription_coverage") or {}
    return bool(coverage) and (coverage.get("status") not in ("completed", "not_applicable_no_detected_speech")
                              or bool(_transcription_coverage_warning_regions(coverage)))


_TRANSCRIPTION_TIMING_ONLY_FLAGS = {"invalid_word_timing", "word_alignment_unavailable"}


def _recording_scene_meta(scene_meta):
    """Versioned evidence is the only transcript authority on the candidate path."""
    projection = scene_meta.get('audio_evidence')
    if projection is None:
        return scene_meta
    from wsl2_audio.scene_projection import legacy_audio
    from steps.audio.recording_ingestion import bound_text_fields
    audio = legacy_audio(projection)
    context = audio['transcript_meta'].get('transcription_context')
    return {**scene_meta, 'transcript': audio['transcript'],
            'speaker_transcript': audio['speaker_transcript'], 'speakers': audio['speakers'],
            'sound_events': audio['sound_events'], 'emotion_segments': audio['emotion_segments'],
            'emotion_input': audio['emotion_input'], 'emotions': [],
            # Old text-derived channels have no binding to this recording's
            # admitted words. Their integration needs explicit input provenance.
            'sentiment': audio['sentiment'], 'sentiment_meta': audio['sentiment_meta'],
            'text_emotion_ranking': [], 'music_events': [], 'time_hints': {},
            # Unused roster names are recognizer settings, not scene evidence.
            # Retain hinting provenance without seeding a summary with names.
            'transcription_context': ({'basis': context['basis'], 'vocabulary_supplied': True,
                                       'identity_claim': False} if context else None),
            'transcription_coverage': {}, **bound_text_fields(scene_meta)}


def _transcription_has_supported_absence(scene_meta: Dict[str, Any]) -> bool:
    if scene_meta.get('audio_evidence') is not None:
        return scene_meta['audio_evidence']['source'].get('audio_track') == 'absent'
    return (not str(scene_meta.get("transcript") or "").strip()
            and (scene_meta.get("transcription_coverage") or {}).get("status")
            == "not_applicable_no_detected_speech")


def _transcription_text_is_restricted(scene_meta: Dict[str, Any]) -> bool:
    """Alignment failure cannot invalidate words; unknown recognition evidence can."""
    if scene_meta.get('audio_evidence') is not None:
        from wsl2_audio.scene_projection import validate_scene_audio
        projection = validate_scene_audio(scene_meta['audio_evidence'])
        return not any(u['eligibility']['transcript']['status'] == 'eligible' for u in projection['utterances'])
    coverage = scene_meta.get("transcription_coverage") or {}
    if not coverage:
        return False  # Historical transcripts retain their existing interpretation.
    status = coverage.get("status")
    if status == "not_applicable_no_detected_speech":
        return bool(str(scene_meta.get("transcript") or "").strip())
    if status != "completed":
        return True
    regions = coverage.get("regions")
    if not isinstance(regions, list) or not regions:
        return bool(str(scene_meta.get("transcript") or "").strip())
    for row in regions:
        if not isinstance(row, dict):
            return True
        flags = row.get("quality_flags") or []
        if (row.get("outcome") != "text_returned" or not isinstance(flags, list)
                or any(flag not in _TRANSCRIPTION_TIMING_ONLY_FLAGS for flag in flags)
                or row.get("unplaced_segments") or row.get("unplaced_segment_count")
                or row.get("timing_retry") == "error"):
            return True
    return False


def _transcription_evidence_details(scene_meta: Dict[str, Any]) -> Dict[str, Any]:
    if scene_meta.get('audio_evidence') is not None:
        projection = scene_meta['audio_evidence']
        admitted = [u for u in projection['utterances'] if u['eligibility']['transcript']['status'] == 'eligible']
        return {'text_status': 'available_model_estimate' if admitted else 'withheld_recognition_uncertainty'
                    if projection['utterances'] else 'no_text',
                'recognition_accuracy': projection['quality_qualification'],
                'coverage_status': projection['stages'].get('recognition', {}).get('status', 'not_run'),
                'timing_status': 'source_phrase_spans_word_times_separate', 'timing_warnings': [],
                'retained_utterance_ids': [u['id'] for u in admitted],
                'withheld_utterance_count': len(projection['utterances'])-len(admitted),
                'evidence_sha256': projection['content_sha256']}
    coverage = scene_meta.get("transcription_coverage") or {}
    timing_flags = sorted({flag for row in coverage.get("regions", []) if isinstance(row, dict)
        for flag in (row.get("quality_flags") or []) if flag in _TRANSCRIPTION_TIMING_ONLY_FLAGS})
    return {
        "text_status": ("withheld_recognition_uncertainty" if _transcription_text_is_restricted(scene_meta)
                        else "available_model_estimate" if str(scene_meta.get("transcript") or "").strip()
                        else "no_text"),
        "recognition_accuracy": "unverified",
        "coverage_status": coverage.get("status", "not_reported"),
        "timing_status": "unresolved" if timing_flags else "not_qualified_by_summary",
        "timing_warnings": timing_flags,
    }


_AUDIO_ANALYSIS_CHANNELS = (
    "audio_evidence",
    "transcription_coverage", "emotion_input", "emotion_segments", "sound_events",
    "text_emotion_ranking", "sentiment", "sentiment_meta",
)


def _has_audio_evidence(scene_meta: Dict[str, Any]) -> bool:
    return any(scene_meta.get(key) for key in (*_AUDIO_ANALYSIS_CHANNELS, "emotions"))


def _qualify_scene_audio_result(payload: Dict[str, Any], scene_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Attach qualifications after generation/heuristics, without changing source evidence."""
    result = dict(payload)
    coverage = scene_meta.get("transcription_coverage") or {}
    if coverage or scene_meta.get('audio_evidence') is not None:
        details = _transcription_evidence_details(scene_meta)
        result["transcription_evidence"] = details
        restricted = details["text_status"] == "withheld_recognition_uncertainty"
        if (details["text_status"] == "available_model_estimate"
                and result.get("narrative_summary") == "Minimal visual or dialogue content."):
            # Rejected/generated prose cannot turn retained words into an
            # assertion that dialogue is absent.
            result.update(narrative_summary="Spoken or dialogue evidence present.", key_moments=[],
                          activity_description="Spoken or dialogue evidence present.")
            provenance = {"source": "scene_context_evidence", "depends_on": ["transcribe"],
                "qualification": "unverified_model_transcript", "establishes_visible_presence": False}
            result.setdefault("claim_provenance", {}).update(
                narrative_summary=dict(provenance), activity_description=dict(provenance))
        warning = ("Speech recognition is uncertain; review the source audio." if restricted else
                   "Speech timing is uncertain; transcript wording remains an unverified model estimate."
                   if details["timing_warnings"] else None)
        if _transcription_coverage_is_uncertain(scene_meta) or restricted:
            result["transcription_coverage_uncertain"] = True
        if warning:
            summary = result.get("narrative_summary")
            if not summary or summary == "Minimal visual or dialogue content.":
                result.update(narrative_summary=warning, key_moments=[],
                    activity_description="Speech recognition requires source review." if restricted else warning)
            elif warning not in summary:
                result["narrative_summary"] = summary + " " + warning
    if _has_audio_evidence(scene_meta):
        # Individual vocal estimates, text sentiment and missing scores cannot
        # qualify the mood of the entire scene, regardless of ASR timing status.
        result["emotional_arc"] = "unqualified"
        result["emotion_qualification"] = {"status": "unqualified", "scope": "whole_scene",
            "reason": "individual_audio_estimates_do_not_establish_scene_mood"}
    return result


def _scene_context_failure_fallback_payload(
    scene_meta: Dict[str, Any], *, reason: str = "llm_failure",
) -> Dict[str, Any]:
    """Return a conservative, evidence-grounded payload when the LLM path fails."""
    scene_meta = _recording_scene_meta(scene_meta)
    def observed_fallback(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **_qualify_scene_audio_result(payload, scene_meta), "status": "fallback", "reason": reason,
            "source": "scene_context_fallback",
        }

    transcript = str(scene_meta.get("transcript") or "").strip()
    transcript_word_count = len(re.findall(r"\b\w+\b", transcript))
    caption = str(scene_meta.get("caption") or "").strip()
    objects = scene_meta.get("objects", [])
    object_labels = _select_scene_object_labels(objects, limit=10)

    if _transcription_text_is_restricted(scene_meta) or _transcription_has_supported_absence(scene_meta):
        # Failure of one modality is not evidence that the others are empty.
        visual = caption if caption and not _caption_is_low_signal(caption) else ""
        normalized = _normalize_scene_context_payload({
            "narrative_summary": visual, "activity_description": visual,
            "key_moments": [visual] if visual else [], "emotional_arc": "unqualified",
            "context_tags": [],
        }, scene_meta)
        return observed_fallback(normalized or _minimal_scene_context_payload())

    topic_hints = _extract_transcript_topic_hints(transcript)
    setting_hint = _derive_setting_hint(caption, object_labels)
    emotion_label = None
    emotions = scene_meta.get("emotions")
    if isinstance(emotions, list):
        for item in emotions:
            if isinstance(item, dict):
                label = str(item.get("label") or "").strip().lower()
            else:
                label = str(item).strip().lower()
            if label:
                emotion_label = label
                break
    emotional_arc = f"{emotion_label} audio emotion signal" if emotion_label else "unqualified"

    if topic_hints:
        topic = topic_hints[0]
        tags = [topic]
        if setting_hint:
            tags.append(setting_hint)
        raw_payload = {
            "narrative_summary": (
                f"{setting_hint.capitalize()} conversation about {topic}."
                if setting_hint
                else f"Conversation about {topic}."
            ),
            "key_moments": [f"They mention {topic}."],
            "emotional_arc": emotional_arc,
            "context_tags": tags,
            "activity_description": (
                f"{setting_hint.capitalize()} conversation about {topic}."
                if setting_hint
                else f"Conversation about {topic}."
            ),
        }
        return observed_fallback(
            _normalize_scene_context_payload(raw_payload, scene_meta) or _minimal_scene_context_payload()
        )

    if transcript_word_count >= 3:
        tags = [setting_hint] if setting_hint else ["conversation"]
        summary = f"{setting_hint.capitalize()} conversation." if setting_hint else "Spoken or dialogue evidence present."
        raw_payload = {
            "narrative_summary": summary,
            "key_moments": [summary],
            "emotional_arc": emotional_arc,
            "context_tags": tags,
            "activity_description": summary,
        }
        normalized = _normalize_scene_context_payload(raw_payload, scene_meta) or _minimal_scene_context_payload()
        if normalized["narrative_summary"] == "Minimal visual or dialogue content.":
            # The topic filter may reject generic prose, but an unavailable LLM
            # must not turn present dialogue into an assertion of absent signal.
            normalized["narrative_summary"] = summary
            normalized["activity_description"] = summary
            normalized["key_moments"] = [summary]
        return observed_fallback(normalized)

    return observed_fallback(_minimal_scene_context_payload())


def _spoken_monologue_payload(topic_hints: List[str]) -> Dict[str, Any]:
    topic = topic_hints[0] if topic_hints else None
    if not topic:
        return {
            "narrative_summary": "Spoken monologue.",
            "key_moments": ["Speaker delivers a monologue"],
            "emotional_arc": "spoken performance",
            "context_tags": ["spoken monologue"],
            "primary_tags": [],
            "contextual_tags": [],
            "structural_tags": ["spoken monologue"],
            "activity_description": "Spoken monologue.",
        }
    return {
        "narrative_summary": f"Spoken monologue about {topic}.",
        "key_moments": [f"Speaker delivers a monologue about {topic}"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue", topic],
        "primary_tags": [topic],
        "contextual_tags": [],
        "structural_tags": ["spoken monologue"],
        "activity_description": f"Spoken monologue about {topic}.",
    }


def _contains_supported_role_in_transcript(term: str, transcript: str) -> bool:
    if not isinstance(transcript, str) or not transcript.strip():
        return False
    variants = _ROLE_SUPPORT_VARIANTS.get(term.casefold(), (term.casefold(),))
    transcript_lower = transcript.casefold()
    return any(re.search(rf"\b{re.escape(variant)}\b", transcript_lower) for variant in variants)


def _derive_setting_hint(caption: str, tags: List[str]) -> Optional[str]:
    from steps.video.entity_extractor import is_hedged_mention

    lowered_caption = str(caption or "").casefold()
    for hint in _SETTING_HINTS:
        if hint == "room":
            continue
        # A hedged caption guess ("possibly a living room") is not a setting.
        if any(not is_hedged_mention(lowered_caption, match.start())
               for match in re.finditer(re.escape(hint), lowered_caption)):
            return hint
    for tag in tags:
        normalized = str(tag).strip().casefold()
        if normalized in _SETTING_HINTS and normalized != "room":
            return normalized
    return None


def _is_evidence_grounded_topic_candidate(candidate: str, evidence_blob: str) -> bool:
    normalized = str(candidate or "").strip()
    if not normalized or _is_low_value_topic_fragment(normalized):
        return False
    # Contiguous, token-bounded source support: "pen" is not in "open", and
    # separated first/surnames do not authorize a fabricated combined identity.
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in normalized.split()) + r"(?!\w)"
    return re.search(pattern, str(evidence_blob or ""), re.IGNORECASE) is not None


def _is_transcript_grounded_topic_candidate(candidate: str, transcript: str) -> bool:
    return _is_evidence_grounded_topic_candidate(candidate, transcript)


def _extract_declared_topic_phrase(text: str) -> Optional[str]:
    if not isinstance(text, str) or not text.strip():
        return None
    patterns = (
        re.compile(r"\b(?:conversation|monologue)\s+about\s+(.+?)[.!?]*$", re.IGNORECASE),
        re.compile(r"\bthey\s+mention\s+(.+?)[.!?]*$", re.IGNORECASE),
        re.compile(r"\bspeaker\s+delivers\s+a\s+monologue\s+about\s+(.+?)[.!?]*$", re.IGNORECASE),
    )
    for pattern in patterns:
        match = pattern.search(text.strip())
        if not match:
            continue
        candidate = re.sub(r"\s{2,}", " ", match.group(1).strip(" .!?,'\""))
        return candidate or None
    return None


def _contains_low_value_declared_topic(text: str) -> bool:
    candidate = _extract_declared_topic_phrase(text)
    return bool(candidate and _is_low_value_topic_fragment(candidate))


def _derive_topic_hint(
    topic_hints: List[str],
    tags: List[str],
    evidence_blob: str,
    *,
    transcript: str = "",
    allow_visual_fallback: bool = True,
) -> Optional[str]:
    for hint in topic_hints:
        normalized = str(hint).strip()
        if (
            normalized
            and normalized.casefold() not in _GENERIC_CONTEXT_TAGS
            and _is_transcript_grounded_topic_candidate(normalized, transcript)
        ):
            return normalized
    if not allow_visual_fallback:
        return None
    for tag in tags:
        normalized = str(tag).strip()
        lowered = normalized.casefold()
        if (
            normalized
            and lowered not in _GENERIC_CONTEXT_TAGS
            and lowered not in _SETTING_HINTS
            and _is_evidence_grounded_topic_candidate(normalized, evidence_blob)
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
    setting_conversation_only = bool(
        topic_hint
        and topic_hint.casefold() not in text.casefold()
        and (
            text == "Minimal visual or dialogue content."
            or re.fullmatch(r"(?:[A-Za-z ]+ )?conversation\.?", text, flags=re.IGNORECASE)
        )
    )
    needs_rewrite = any(pattern.search(text) for pattern in _GENERIC_REWRITE_PATTERNS) or any(
        pattern.search(text) for pattern in _UNSUPPORTED_ACTIVITY_PATTERNS
    )
    if not force_rewrite and not needs_rewrite and not setting_conversation_only:
        return text

    if setting_hint and topic_hint:
        return f"{setting_hint.capitalize()} conversation about {topic_hint}."
    if topic_hint:
        return f"Conversation about {topic_hint}."
    if setting_hint:
        return f"{setting_hint.capitalize()} conversation."
    return "Minimal visual or dialogue content."


def _append_unique(values: List[str], candidate: str) -> None:
    normalized = str(candidate or "").strip()
    if not normalized:
        return
    lowered = normalized.casefold()
    if any(str(existing).casefold() == lowered for existing in values):
        return
    values.append(normalized)


def _classify_context_tags(
    tags: List[str],
    *,
    transcript: str,
    evidence_blob: str,
    topic_hint: Optional[str],
    narrative_summary: Optional[str],
) -> Dict[str, List[str]]:
    primary_tags: List[str] = []
    contextual_tags: List[str] = []
    structural_tags: List[str] = []
    minimal_scene = str(narrative_summary or "").strip() == "Minimal visual or dialogue content."
    normalized_topic_hint = str(topic_hint or "").strip().casefold()

    for tag in tags:
        lowered = str(tag or "").strip().casefold()
        if not lowered:
            continue
        if (
            lowered in _STRUCTURAL_CONTEXT_TAGS
            or lowered in _GENERIC_CONTEXT_TAGS
            or lowered in _LOW_VALUE_VISIBLE_TAGS
            or _contains_low_value_visible_focus(tag)
        ):
            _append_unique(structural_tags, tag)
            continue
        if lowered in _SETTING_HINTS:
            target = structural_tags if lowered in _STRUCTURAL_SETTING_HINTS else contextual_tags
            _append_unique(target, tag)
            continue
        if normalized_topic_hint and lowered == normalized_topic_hint:
            _append_unique(primary_tags, tag)
            continue
        if _is_transcript_grounded_topic_candidate(tag, transcript):
            if minimal_scene or (normalized_topic_hint and lowered != normalized_topic_hint):
                _append_unique(contextual_tags, tag)
            else:
                _append_unique(primary_tags, tag)
            continue
        if _is_evidence_grounded_topic_candidate(tag, evidence_blob):
            _append_unique(contextual_tags, tag)
            continue
        _append_unique(structural_tags, tag)

    context_tags: List[str] = []
    for group in (primary_tags, contextual_tags):
        for tag in group:
            _append_unique(context_tags, tag)
    for tag in structural_tags:
        if tag.casefold() in _STRUCTURAL_CONTEXT_TAGS:
            _append_unique(context_tags, tag)
    return {
        "primary_tags": primary_tags[:5],
        "contextual_tags": contextual_tags[:5],
        "structural_tags": structural_tags[:5],
        "context_tags": context_tags[:5],
    }


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


def _contains_mojibake_artifact(text: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    return any(char in text for char in ("\ufffd", "\u201a"))


def _looks_like_low_value_visual_key_moment(text: str) -> bool:
    if _contains_low_value_visible_focus(text) or _contains_mojibake_artifact(text):
        return True
    return any(
        pattern.search(text)
        for pattern in (_LOW_VALUE_VISUAL_KEY_MOMENT_PATTERNS + _CAPTION_SHAPED_VISUAL_NARRATION_PATTERNS)
    )


def _has_excess_ungrounded_content(
    text: str,
    *,
    evidence_blob: str,
    topic_hint: Optional[str],
    setting_hint: Optional[str],
) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    stems = _content_token_stems(text)
    if not stems:
        return False
    supported = set(_content_token_stems(evidence_blob))
    if topic_hint:
        supported.update(_content_token_stems(topic_hint))
    if setting_hint:
        supported.update(_content_token_stems(setting_hint))
    missing = [stem for stem in stems if stem not in supported]
    # Even a short claim is unsupported when none of its content occurs in the
    # evidence. The previous two-missing-token allowance admitted lone invented
    # topics such as "vacation" in otherwise generic conversation prose.
    return stems.isdisjoint(supported) or (len(missing) >= 2 and len(missing) >= max(2, len(stems) // 2))


def _normalize_key_moment_identity(value: str) -> str:
    normalized = re.sub(r"[.!?]+$", "", str(value or "").strip().casefold())
    normalized = re.sub(r"\s{2,}", " ", normalized)
    return normalized


def _content_token_stems(text: str) -> set[str]:
    tokens = [
        token
        for token in re.findall(r"[a-zA-Z]+", str(text or "").casefold())
        if token
        and token not in _TOPIC_STOPWORDS
        and token not in _LOW_VALUE_TOPIC_TOKENS
        and token not in _GENERIC_KEY_MOMENT_TOKENS
    ]
    stems: set[str] = set()
    for token in tokens:
        if len(token) <= 3:
            stems.add(token)
        else:
            stems.add(token[:3])
    return stems


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
    if _contains_low_value_visible_focus(normalized):
        return "neutral tone"
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


def _text_contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = str(text or "").strip().casefold()
    normalized_phrase = str(phrase or "").strip().casefold()
    if not normalized_text or not normalized_phrase:
        return False
    return bool(re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized_text))


def _rewrite_key_moment(
    value: Optional[str],
    *,
    transcript: str,
    evidence_blob: str,
    setting_hint: Optional[str],
    topic_hint: Optional[str],
    detector_only_labels: Optional[List[str]] = None,
) -> Optional[str]:
    normalized = value.strip() if isinstance(value, str) else value
    if not isinstance(normalized, str) or not normalized.strip():
        return normalized
    if detector_only_labels and any(
        _text_contains_phrase(normalized.casefold(), label) for label in detector_only_labels
    ):
        if topic_hint:
            return f"They mention {topic_hint}."
        if setting_hint:
            return f"{setting_hint.capitalize()} conversation."
        return None
    if any(pattern.search(normalized) for pattern in _CAPTION_SHAPED_VISUAL_NARRATION_PATTERNS):
        if topic_hint:
            return f"They mention {topic_hint}."
        if setting_hint:
            return f"{setting_hint.capitalize()} conversation."
        return None
    if _contains_unsupported_role_text(normalized, transcript) or _contains_unsupported_activity_text(normalized, transcript):
        if topic_hint:
            return f"They mention {topic_hint}."
        if setting_hint:
            return f"{setting_hint.capitalize()} conversation."
        return "Minimal visual or dialogue content."
    if _contains_low_value_declared_topic(normalized):
        if topic_hint:
            return f"They mention {topic_hint}."
        if setting_hint:
            return f"{setting_hint.capitalize()} conversation."
        return None
    if re.fullmatch(r"(?:they|people)\s+(?:talk|are talking)\.?", normalized, flags=re.IGNORECASE):
        if topic_hint:
            return f"They mention {topic_hint}."
        if setting_hint:
            return f"{setting_hint.capitalize()} conversation."
        return "Minimal visual or dialogue content."
    visual_staging = _looks_like_low_value_visual_key_moment(normalized)
    if visual_staging:
        if topic_hint:
            if topic_hint.casefold() not in normalized.casefold():
                return f"They mention {topic_hint}."
            return normalized
        if setting_hint:
            return f"{setting_hint.capitalize()} conversation."
        return None
    if topic_hint:
        moment_stems = _content_token_stems(normalized)
        transcript_stems = _content_token_stems(transcript)
        evidence_stems = _content_token_stems(evidence_blob)
        topic_in_moment = topic_hint.casefold() in normalized.casefold()
        if visual_staging and moment_stems and transcript_stems and transcript_stems.isdisjoint(moment_stems):
            return f"They mention {topic_hint}."
        if (
            not topic_in_moment
            and moment_stems
            and evidence_stems
            and evidence_stems.isdisjoint(moment_stems)
        ):
            return f"They mention {topic_hint}."
        if not topic_in_moment and any(
            pattern.search(normalized) for pattern in _INTERPRETIVE_REACTION_KEY_MOMENT_PATTERNS
        ):
            return f"They mention {topic_hint}."
        if _has_excess_ungrounded_content(
            normalized,
            evidence_blob=evidence_blob,
            topic_hint=topic_hint,
            setting_hint=setting_hint,
        ):
            return f"They mention {topic_hint}."
    if not topic_hint:
        moment_stems = _content_token_stems(normalized)
        evidence_stems = _content_token_stems(evidence_blob)
        if not moment_stems:
            if setting_hint:
                return f"{setting_hint.capitalize()} conversation."
            return None
        if moment_stems and evidence_stems.isdisjoint(moment_stems):
            if setting_hint:
                return f"{setting_hint.capitalize()} conversation."
            return None
    return normalized


def _normalize_scene_context_payload(raw_context: Dict[str, Any], scene_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    scene_meta = _recording_scene_meta(scene_meta)
    recognition_restricted = _transcription_text_is_restricted(scene_meta)
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

    # Do not let topic synthesis turn incomplete/warned ASR into factual claims.
    # Other modalities remain available to this normalizer; the original audio
    # evidence remains in the prompt and Inspector with its source coordinates.
    transcript = "" if recognition_restricted else str(scene_meta.get("transcript") or "").strip()
    caption = str(scene_meta.get("caption") or "").strip()
    visible_text_values = _prompt_evidence_values(
        scene_meta.get("ocr_text") or scene_meta.get("visible_text"),
        limit=4,
    )
    if recognition_restricted or _transcription_has_supported_absence(scene_meta):
        # Withhold spoken claims from warned recognition or supported absence.
        # Copy independent observations with their modality instead of treating lexical similarity
        # as proof of arbitrary model prose (e.g. vacuum/vacation, 1988/1999).
        evidence = {}
        observations = []
        if caption and not _caption_is_low_signal(caption):
            evidence["image_caption"] = caption.casefold()
            observations.append(caption)
        if visible_text_values:
            evidence["image_ocr"] = " ".join(visible_text_values).casefold()
            observations.extend(f'Visible text: "{value}".' for value in visible_text_values)
        tag_sources = {}
        for tag in _clean_list(raw_context.get("context_tags"), limit=5):
            sources = [source for source, text in evidence.items() if _text_contains_phrase(text, tag.casefold())]
            if sources and tag.casefold() not in _GENERIC_CONTEXT_TAGS:
                tag_sources[tag] = {"sources": sources,
                    "scope": "written_text" if "image_ocr" in sources else "qualified_visual_observation",
                    "establishes_visible_presence": False}
        summary = " ".join(observations) or "Minimal visual or dialogue content."
        provenance = {"source": "scene_context_evidence", "depends_on": list(evidence),
            "qualification": "unverified_independent_observation" if evidence else "low_signal_fallback",
            "establishes_visible_presence": False}
        return _qualify_scene_audio_result({
            "narrative_summary": summary, "key_moments": observations[:3],
            "emotional_arc": "unqualified", "activity_description": summary,
            "context_tags": list(tag_sources), "primary_tags": [],
            "contextual_tags": list(tag_sources), "structural_tags": [],
            "claim_provenance": {"narrative_summary": dict(provenance),
                "activity_description": dict(provenance), "tag_sources": tag_sources},
        }, scene_meta)
    music_event_values = _prompt_evidence_values(scene_meta.get("music_events"), limit=8)
    time_hint_values = _prompt_evidence_values(scene_meta.get("time_hints"), limit=8)
    metadata_time_hint_values = _prompt_evidence_values(scene_meta.get("metadata_time_hints"), limit=8)
    objects = scene_meta.get("objects", [])
    object_labels = _select_scene_object_labels(objects, limit=10)
    non_detector_evidence_blob = " ".join(
        [
            transcript,
            caption,
            " ".join(visible_text_values),
            " ".join(music_event_values),
            " ".join(time_hint_values),
            " ".join(metadata_time_hint_values),
        ]
    ).casefold()
    evidence_blob = " ".join(
        [
            non_detector_evidence_blob,
            " ".join(object_labels),
        ]
    ).casefold()
    detector_only_labels = [
        label.casefold()
        for label in object_labels
        if label.casefold() not in _GENERIC_CONTEXT_TAGS
        and label.casefold() not in _SETTING_HINTS
        and not _text_contains_phrase(non_detector_evidence_blob, label.casefold())
    ]

    def _contains_detector_only_label(text: Optional[str]) -> bool:
        normalized_text = str(text or "").strip().casefold()
        if not normalized_text or not detector_only_labels:
            return False
        return any(_text_contains_phrase(normalized_text, label) for label in detector_only_labels)

    context_tags = _clean_list(raw_context.get("context_tags"), limit=8)
    topic_hints = _extract_transcript_topic_hints(transcript)
    # Prefer a model-selected literal source phrase; heuristic hints cannot
    # displace an explicitly grounded topic just because it is absent from a list.
    grounded_topics = [tag for tag in context_tags
                       if _is_transcript_grounded_topic_candidate(tag, transcript)
                       and tag.casefold() not in {cue.casefold() for cue in music_event_values}]
    topic_hint = _derive_topic_hint(
        [candidate for candidate in [_extract_declared_topic_phrase(str(raw_context.get("narrative_summary") or ""))]
         if candidate and _is_transcript_grounded_topic_candidate(candidate, transcript)] + grounded_topics + topic_hints,
        [],
        non_detector_evidence_blob,
        transcript=transcript,
        allow_visual_fallback=False,
    )
    specific_tags_exist = any(tag.casefold() not in _GENERIC_CONTEXT_TAGS for tag in context_tags)
    filtered_tags: List[str] = []
    seen_tags: set[str] = set()
    for tag in context_tags:
        lowered = tag.casefold()
        if _is_low_value_topic_fragment(lowered) or _contains_mojibake_artifact(tag):
            continue
        if _contains_unsupported_role_text(tag, transcript):
            continue
        if _contains_unsupported_activity_text(tag, transcript):
            continue
        if _looks_like_low_value_visual_key_moment(tag):
            continue
        if _contains_low_value_visible_focus(tag):
            continue
        if lowered in _ROLE_CONTEXT_TAGS and not _contains_supported_role_in_transcript(lowered, transcript):
            continue
        if lowered in _SETTING_HINTS and lowered not in evidence_blob:
            continue
        # Topic selection must not veto complementary evidence. The classifier
        # below keeps detector-only tags structural, never confirmed presence.
        if (
            lowered not in _GENERIC_CONTEXT_TAGS
            and lowered not in _SETTING_HINTS
            and not _contains_low_value_visible_focus(tag)
            and not _is_evidence_grounded_topic_candidate(tag, evidence_blob)
        ):
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

    if any(tag.casefold() not in _GENERIC_CONTEXT_TAGS for tag in filtered_tags):
        filtered_tags = [tag for tag in filtered_tags if tag.casefold() not in _GENERIC_CONTEXT_TAGS]

    filtered_tags = filtered_tags[:5]
    setting_hint = _derive_setting_hint(caption, filtered_tags)

    transcript_stems = _content_token_stems(transcript)
    caption_specific_stems = (
        _content_token_stems(caption)
        - _content_token_stems(" ".join(_SETTING_HINTS))
        - _content_token_stems(" ".join(_LOW_VALUE_VISIBLE_TAGS))
    )

    def _is_transcript_grounded_without_topic(text: Optional[str]) -> bool:
        normalized_text = str(text or "").strip()
        # A supported multi-topic summary must not lose detail just because
        # a single tag was selected as the fallback topic.
        if (not normalized_text or not transcript_stems
                or (topic_hint is not None and sum(
                    _is_evidence_grounded_topic_candidate(tag, normalized_text)
                    for tag in grounded_topics if tag.casefold() not in _SETTING_HINTS) < 2)):
            return False
        if normalized_text == "Minimal visual or dialogue content." or re.fullmatch(
            r"(?:[A-Za-z ]+ )?conversation\.?",
            normalized_text,
            flags=re.IGNORECASE,
        ):
            return False
        if _contains_unsupported_role_text(normalized_text, transcript):
            return False
        if _contains_unsupported_activity_text(normalized_text, transcript):
            return False
        if _contains_low_value_declared_topic(normalized_text):
            return False
        if _contains_detector_only_label(normalized_text):
            return False
        text_stems = _content_token_stems(normalized_text)
        if not text_stems or text_stems.isdisjoint(transcript_stems):
            return False
        framing_stripped = re.sub(
            r"\b(?:involve|involved|involves|involving|scenario)\b",
            " ",
            normalized_text,
            flags=re.IGNORECASE,
        )
        if _has_excess_ungrounded_content(
            framing_stripped,
            evidence_blob=non_detector_evidence_blob,
            topic_hint=topic_hint,
            setting_hint=setting_hint,
        ):
            return False
        return True

    def _is_caption_grounded_visual_only(text: Optional[str]) -> bool:
        normalized_text = str(text or "").strip()
        if not normalized_text or topic_hint is not None or transcript_stems:
            return False
        if _caption_is_low_signal(caption) or not caption_specific_stems:
            return False
        if normalized_text == "Minimal visual or dialogue content." or re.fullmatch(
            r"(?:[A-Za-z ]+ )?conversation\.?",
            normalized_text,
            flags=re.IGNORECASE,
        ):
            return False
        if _contains_unsupported_role_text(normalized_text, transcript):
            return False
        if _contains_unsupported_activity_text(normalized_text, transcript):
            return False
        if _contains_low_value_declared_topic(normalized_text):
            return False
        if _contains_mojibake_artifact(normalized_text):
            return False
        if _contains_detector_only_label(normalized_text):
            return False
        text_stems = _content_token_stems(normalized_text)
        if not text_stems or text_stems.isdisjoint(caption_specific_stems):
            return False
        if _has_excess_ungrounded_content(
            normalized_text,
            evidence_blob=caption,
            topic_hint=None,
            setting_hint=setting_hint,
        ):
            return False
        return True

    raw_summary = _clean_text(raw_context.get("narrative_summary"))
    summary_grounded_without_topic = (
        _is_transcript_grounded_without_topic(raw_summary)
        or _is_caption_grounded_visual_only(raw_summary)
    )
    force_summary_rewrite = _contains_unsupported_role_text(raw_summary or "", transcript)
    if _contains_unsupported_activity_text(raw_summary or "", transcript):
        force_summary_rewrite = True
    if _contains_detector_only_label(raw_summary):
        force_summary_rewrite = True
    if _contains_low_value_visible_focus(raw_summary or "") and not summary_grounded_without_topic:
        force_summary_rewrite = True
    if _contains_low_value_declared_topic(raw_summary or ""):
        force_summary_rewrite = True
    if any(pattern.search(raw_summary or "") for pattern in _INTERPRETIVE_SUMMARY_PATTERNS) and not summary_grounded_without_topic:
        force_summary_rewrite = True
    if _has_excess_ungrounded_content(
        raw_summary or "",
        evidence_blob=non_detector_evidence_blob,
        topic_hint=topic_hint,
        setting_hint=setting_hint,
    ):
        force_summary_rewrite = True

    raw_activity = _clean_text(raw_context.get("activity_description"))
    activity_grounded_without_topic = (
        _is_transcript_grounded_without_topic(raw_activity)
        or _is_caption_grounded_visual_only(raw_activity)
    )
    force_activity_rewrite = _contains_unsupported_role_text(raw_activity or "", transcript)
    if _contains_unsupported_activity_text(raw_activity or "", transcript):
        force_activity_rewrite = True
    if _contains_detector_only_label(raw_activity):
        force_activity_rewrite = True
    if _contains_low_value_visible_focus(raw_activity or "") and not activity_grounded_without_topic:
        force_activity_rewrite = True
    if _contains_low_value_declared_topic(raw_activity or ""):
        force_activity_rewrite = True
    if any(pattern.search(raw_activity or "") for pattern in _INTERPRETIVE_SUMMARY_PATTERNS) and not activity_grounded_without_topic:
        force_activity_rewrite = True
    if _has_excess_ungrounded_content(
        raw_activity or "",
        evidence_blob=non_detector_evidence_blob,
        topic_hint=topic_hint,
        setting_hint=setting_hint,
    ):
        force_activity_rewrite = True

    key_moments: List[str] = []
    seen_moments: set[str] = set()
    for value in _clean_list(raw_context.get("key_moments"), limit=5):
        if _is_caption_grounded_visual_only(value):
            rewritten = value.strip()
        else:
            rewritten = _rewrite_key_moment(
                value,
                transcript=transcript,
                evidence_blob=non_detector_evidence_blob,
                setting_hint=setting_hint,
                topic_hint=topic_hint,
                detector_only_labels=detector_only_labels,
            )
        if not rewritten:
            continue
        key = _normalize_key_moment_identity(rewritten)
        if key in seen_moments:
            continue
        seen_moments.add(key)
        key_moments.append(rewritten)
        if len(key_moments) >= 3:
            break

    specific_moments = [
        moment
        for moment in key_moments
        if moment != "Minimal visual or dialogue content."
        and not re.fullmatch(r"(?:[A-Za-z ]+ )?conversation\.?", moment, flags=re.IGNORECASE)
    ]
    if specific_moments:
        key_moments = specific_moments

    narrative_summary = (
        raw_summary
        if summary_grounded_without_topic and not force_summary_rewrite
        else _rewrite_scene_text(
            raw_summary,
            setting_hint=setting_hint,
            topic_hint=topic_hint,
            force_rewrite=force_summary_rewrite,
        )
    )
    candidate_tags = filtered_tags
    if narrative_summary == "Minimal visual or dialogue content.":
        candidate_tags = [
            tag
            for tag in filtered_tags
            if _is_transcript_grounded_topic_candidate(tag, transcript) or tag.casefold() in _STRUCTURAL_CONTEXT_TAGS
        ]
    tag_payload = _classify_context_tags(
        candidate_tags,
        transcript=transcript,
        evidence_blob=non_detector_evidence_blob,
        topic_hint=topic_hint,
        narrative_summary=narrative_summary,
    )

    activity_description = (
        raw_activity
        if activity_grounded_without_topic and not force_activity_rewrite
        else _rewrite_scene_text(
            raw_activity,
            setting_hint=setting_hint,
            topic_hint=topic_hint,
            force_rewrite=force_activity_rewrite,
        )
    )
    promoted_activity_summary = False
    if (
        narrative_summary == "Minimal visual or dialogue content."
        and activity_description != "Minimal visual or dialogue content."
        and not _has_excess_ungrounded_content(
            activity_description,
            evidence_blob=non_detector_evidence_blob,
            topic_hint=topic_hint,
            setting_hint=setting_hint,
        )
    ):
        narrative_summary = activity_description
        promoted_activity_summary = True
    if (
        topic_hint is None
        and transcript_stems
        and (
            narrative_summary == "Minimal visual or dialogue content."
            or re.fullmatch(r"(?:[A-Za-z ]+ )?conversation\.?", str(narrative_summary or ""), flags=re.IGNORECASE)
        )
    ):
        for moment in key_moments:
            if _is_transcript_grounded_without_topic(moment):
                promoted_moment = moment if moment.endswith((".", "!", "?")) else f"{moment}."
                narrative_summary = promoted_moment
                if (
                    activity_description == "Minimal visual or dialogue content."
                    or re.fullmatch(
                        r"(?:[A-Za-z ]+ )?conversation\.?",
                        str(activity_description or ""),
                        flags=re.IGNORECASE,
                    )
                ):
                    activity_description = promoted_moment
                break
    if promoted_activity_summary and not key_moments:
        key_moments = [activity_description]

    def _claim_dependencies(text: Optional[str]) -> Dict[str, Any]:
        normalized_claim = str(text or "").strip()
        if not normalized_claim or normalized_claim == "Minimal visual or dialogue content.":
            return {
                "source": "scene_context_llm",
                "depends_on": [],
                "qualification": "low_signal_fallback",
                "establishes_visible_presence": False,
            }
        depends_on: List[str] = []
        claim_stems = _content_token_stems(normalized_claim)
        if transcript_stems and (
            (topic_hint and topic_hint.casefold() in normalized_claim.casefold())
            or not claim_stems.isdisjoint(transcript_stems)
        ):
            depends_on.append("transcribe")
        if visible_text_values and not claim_stems.isdisjoint(_content_token_stems(" ".join(visible_text_values))):
            depends_on.append("image_ocr")
        if caption and not _caption_is_low_signal(caption) and (
            (setting_hint and setting_hint in normalized_claim.casefold() and setting_hint in caption.casefold())
            or not claim_stems.isdisjoint(_content_token_stems(caption))
        ):
            depends_on.append("image_caption")
        qualification = (
            "qualified_visual_observation"
            if depends_on == ["image_caption"]
            else "unverified_model_summary"
        )
        return {
            "source": "scene_context_llm",
            "depends_on": depends_on,
            "qualification": qualification,
            "establishes_visible_presence": False,
        }

    tag_sources: Dict[str, Dict[str, Any]] = {}
    visible_text_blob = " ".join(visible_text_values).casefold()
    caption_blob = caption.casefold()
    object_blob = " ".join(object_labels).casefold()
    for tag in (
        tag_payload["primary_tags"]
        + tag_payload["contextual_tags"]
        + tag_payload["structural_tags"]
    ):
        if tag in tag_sources:
            continue
        tag_key = tag.casefold()
        sources: List[str] = []
        if transcript and (
            (topic_hint and tag_key == topic_hint.casefold())
            or _is_transcript_grounded_topic_candidate(tag, transcript)
        ):
            sources.append("transcribe")
        if visible_text_blob and _is_evidence_grounded_topic_candidate(tag, visible_text_blob):
            sources.append("image_ocr")
        if caption_blob and (
            (tag_key in _SETTING_HINTS and tag_key in caption_blob)
            or _is_evidence_grounded_topic_candidate(tag, caption_blob)
        ):
            sources.append("image_caption")
        if object_blob and (
            any(lbl.casefold() == tag_key for lbl in object_labels)
            or _is_evidence_grounded_topic_candidate(tag, object_blob)
        ):
            sources.append("object_detect")
        if not sources:
            sources.append("scene_context_llm")
        if "transcribe" in sources:
            scope = "spoken_mention"
        elif "image_ocr" in sources:
            scope = "written_text"
        elif "image_caption" in sources:
            scope = "qualified_visual_observation"
        elif "object_detect" in sources:
            scope = "candidate_detection"
        else:
            scope = "model_context"
        tag_sources[tag] = {
            "sources": sources,
            "scope": scope,
            "establishes_visible_presence": False,
        }

    if (narrative_summary == "Minimal visual or dialogue content." and transcript
            # Provider failures own their existing generic presence fallback.
            and raw_summary != "Spoken or dialogue evidence present."
            and not _transcription_coverage_is_uncertain(scene_meta)):
        excerpt = re.split(r"(?<=[.!?])\s+", transcript)[0].strip()
        if excerpt and len(excerpt.split()) <= 80:
            narrative_summary = f'Transcript: "{excerpt}"'
            key_moments = [narrative_summary]
            if activity_description == "Minimal visual or dialogue content.":
                activity_description = narrative_summary

    sanitized = {
        "narrative_summary": narrative_summary,
        "key_moments": key_moments,
        "emotional_arc": _rewrite_emotional_arc(raw_context.get("emotional_arc"), transcript),
        "context_tags": tag_payload["context_tags"],
        "primary_tags": tag_payload["primary_tags"],
        "contextual_tags": tag_payload["contextual_tags"],
        "structural_tags": tag_payload["structural_tags"],
        "activity_description": activity_description,
        "claim_provenance": {
            "narrative_summary": _claim_dependencies(narrative_summary),
            "activity_description": _claim_dependencies(activity_description),
            "tag_sources": tag_sources,
        },
    }
    if sanitized["narrative_summary"] == "Minimal visual or dialogue content.":
        sanitized["key_moments"] = ["Minimal visual or dialogue content."]
    if scene_meta.get("audio_evidence") is not None and not _transcription_text_is_restricted(scene_meta):
        # A model can return a literal command, question, age or date without
        # attribution. Preserve it as quoted recognized speech, never as an
        # observed action, a confirmed identity or the recording date. Only exact
        # excerpts qualify here; do not invent a supporting quote for a paraphrase.
        transcript_only = (_caption_is_low_signal(caption) and not object_labels
                           and not visible_text_values and not scene_meta.get("face_count"))
        def attribute_excerpt(value):
            if not isinstance(value, str) or not value.strip():
                return value
            match = re.search(r"(?<!\w)" + re.escape(value.strip()) + r"(?!\w)", transcript, re.IGNORECASE)
            if match:
                return f'Transcript: "{match.group(0)}"'
            if not transcript_only or value == "Minimal visual or dialogue content.":
                return value
            stems = _content_token_stems(value)
            # Lexical overlap selects a quote; it never validates an inferred
            # action, even with speech framing and matching vocabulary. Word
            # sets cannot prove negation or who did what to whom. Preserve source
            # wording, negation and modality verbatim.
            candidates = [part.strip() for part in re.findall(r'[^.!?]+(?:[.!?]+|$)', transcript)
                          if part.strip() and len(part.split()) <= 80]
            quote = max(candidates, key=lambda part: len(stems & _content_token_stems(part)), default="")
            if quote and stems & _content_token_stems(quote):
                return f'Transcript: "{quote}"'
            return "Spoken or dialogue evidence present."

        for key in ("narrative_summary", "activity_description"):
            sanitized[key] = attribute_excerpt(sanitized[key])
            if isinstance(sanitized[key], str) and sanitized[key].startswith('Transcript: "'):
                sanitized["claim_provenance"][key] = {
                    "source": "scene_context_evidence", "depends_on": ["transcribe"],
                    "qualification": "unverified_model_transcript", "establishes_visible_presence": False,
                }
        sanitized["key_moments"] = list(dict.fromkeys(attribute_excerpt(value) for value in sanitized["key_moments"]))
    sanitized = _qualify_scene_audio_result(sanitized, scene_meta)
    has_signal = any(
        sanitized[key]
        for key in (
            "narrative_summary",
            "key_moments",
            "emotional_arc",
            "context_tags",
            "primary_tags",
            "contextual_tags",
            "structural_tags",
            "activity_description",
        )
    )
    return sanitized if has_signal else None


def _build_scene_context_prompts(scene_meta: Dict[str, Any]) -> tuple[str, str]:
    scene_meta = _recording_scene_meta(scene_meta)
    index = scene_meta.get("index", 0)
    start = float(scene_meta.get("start", 0.0) or 0.0)
    end = float(scene_meta.get("end", 0.0) or 0.0)
    caption = str(scene_meta.get("caption") or "").strip()
    transcript = str(scene_meta.get("transcript") or "").strip()
    visible_text_values = _prompt_evidence_values(
        scene_meta.get("ocr_text") or scene_meta.get("visible_text"),
        limit=4,
    )
    music_event_values = _prompt_evidence_values(scene_meta.get("music_events"), limit=8)
    time_hint_values = _prompt_evidence_values(scene_meta.get("time_hints"), limit=8)
    metadata_time_hint_values = _prompt_evidence_values(scene_meta.get("metadata_time_hints"), limit=8)
    objects = scene_meta.get("objects", [])
    face_count = int(scene_meta.get("face_count", 0) or 0)
    emotions = scene_meta.get("emotions", [])
    speakers = scene_meta.get("speakers", [])

    object_labels = _select_scene_object_labels(objects, limit=10)
    objects_str = ", ".join(object_labels) if object_labels else "none"
    visible_text_str = ", ".join(visible_text_values) if visible_text_values else "none"
    music_events_str = ", ".join(music_event_values) if music_event_values else "none"
    all_time_hint_values = time_hint_values + [
        value for value in metadata_time_hint_values if value not in time_hint_values
    ]
    time_hints_str = ", ".join(all_time_hint_values) if all_time_hint_values else "none"

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
    emotions_str = ", ".join(emotion_labels) if emotion_labels else "not available (not evidence of neutral mood)"
    topic_hints = [] if _transcription_text_is_restricted(scene_meta) else _extract_transcript_topic_hints(transcript)
    topic_hints_str = ", ".join(topic_hints) if topic_hints else "none"

    transcript_excerpt = transcript[:12000] if transcript else "No transcript"
    def evidence_rows(key, fields, limit):
        rows = scene_meta.get(key) or []
        return {"total": len(rows), "shown": [
            {field: row.get(field) for field in fields} for row in rows[:limit] if isinstance(row, dict)]}
    admission = scene_meta.get("emotion_input") or {}
    overlap = (admission.get("speaker_purity") or {}).get("local_overlap") or {}
    additional_overlap = (admission.get("speaker_purity") or {}).get("additional_overlap") or {}
    coverage = scene_meta.get("transcription_coverage") or {}
    coverage_warnings = _transcription_coverage_warning_regions(coverage)
    analysis_evidence = json.dumps({
        'recording_audio': ({'schema': scene_meta['audio_evidence']['schema'],
            'recording_id': scene_meta['audio_evidence']['recording_id'],
            'uncertainty': _transcription_evidence_details(scene_meta),
            'overlap': [{key: row.get(key) for key in ('span', 'channel', 'status')}
                        for row in scene_meta['audio_evidence']['overlap']],
            'interpretation': 'Retained words are model estimates. Unclear background words are withheld. '
                'Speaker tracks are not named identities. Spoken dates are utterances, not recording dates. '
                'Sound events and individual vocal estimates do not establish whole-scene mood.'}
            if scene_meta.get('audio_evidence') is not None else None),
        "text_emotion_ranking": evidence_rows("text_emotion_ranking", ("label", "score"), 3),
        "sentiment": scene_meta.get("sentiment"), "sentiment_meta": scene_meta.get("sentiment_meta"),
        "sound_events": evidence_rows("sound_events", ("label", "start", "end", "status", "boundary_precision"), 24),
        "emotion_segments": evidence_rows("emotion_segments", ("start", "end", "speaker", "text", "label", "scores",
            "review_status", "interpretation_status", "uncertainty_reasons", "boundary_status", "model_qualification"), 24),
        "transcription_context": scene_meta.get("transcription_context"),
        "transcription_evidence": _transcription_evidence_details(scene_meta),
        "transcription_coverage": {**{key: coverage.get(key) for key in (
            "policy", "status", "detected_region_count", "completed_region_count",
            "regions_without_text", "recognition_accuracy")},
            "warning_region_count": len(coverage_warnings),
            "shown_warning_regions": [{key: row.get(key) for key in (
                "start", "end", "outcome", "quality_flags", "unplaced_segment_count", "timing_retry")}
                                       for row in coverage_warnings[:24]]},
        "emotion_input": {key: admission.get(key) for key in ("status", "policy", "selected_seconds")},
        "overlap_detection": {**{key: overlap.get(key) for key in
            ("status", "policy", "timebase", "review_status", "identity_claim", "qualification")},
            "intervals": (overlap.get("intervals") or [])[:24]},
        "additional_overlap_detection": {**{key: additional_overlap.get(key) for key in
            ("status", "policy", "model", "revision", "timebase", "review_status", "identity_claim", "qualification")},
            "intervals": (additional_overlap.get("intervals") or [])[:24]},
        "emotion_phrase_selection": {**{key: (admission.get("phrase_selection") or {}).get(key)
            for key in ("status", "policy", "selected_seconds", "boundary_qualification")},
            "rejected": (admission.get("phrase_selection") or {}).get("rejected", [])[:24]},
        "speaker_transcript": evidence_rows("speaker_transcript", ("start", "end", "text", "speaker", "speaker_candidates",
            "attribution_status", "attribution_reason", "overlap_intervals", "timing_scope"), 48),
    }, ensure_ascii=False)
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
- Visible text: {visible_text_str}
- Audio/music events: {music_events_str}
- Time hints: {time_hints_str}
- Face count: {face_count}
- Transcript excerpt: {transcript_excerpt}
- Transcript topic hints: {topic_hints_str}
- Speaker evidence: {speakers_str}
- Audio emotion signal: {emotions_str}
- Separate analysis evidence (model estimates, not verified scene facts): {analysis_evidence}

OUTPUT RULES:
- Keep prose dry and short. Write like an operator note, not a screenplay.
- Distinguish spoken meaning, vocal delivery and non-speech sounds. Crying or laughter by one source does not establish the whole scene's mood.
- Consider text emotion, sentiment and speaker-specific vocal estimates separately; retain disagreement. Missing or withheld estimates do not mean neutral.
- Vocal scores are uncalibrated model rankings, not probabilities of someone's feelings. A close or spread-out ranking does not establish the winning emotion as fact.
- Uncertain vocal estimates and withheld/incomplete phrases do not establish an emotion. Preserve that uncertainty; do not promote a candidate label to a person's feelings or a scene mood. Missing complete supported phrases does not mean no audible speech.
- Vocabulary hints may influence recognized names; a hinted name does not establish who is present or speaking.
- Processing every detected speech region does not prove that every word was recognized. Preserve missing-text, failed-region, repetition and timing warnings. Do not invent missing words or treat warning-marked text as verified speech.
- Timing-only warnings constrain word/phrase locations, not the availability of recognized wording. Use available_model_estimate text with its unverified status; never infer missing timestamps. When text_status is withheld_recognition_uncertainty, do not derive factual topics from that transcript; use independently supported visual evidence instead.
- Transcript-derived music/event and time cues inherit the transcript's recognition limits. They are not independent corroboration; file metadata and visible text retain their own provenance.
- Sound-event times are approximate candidates; speaker labels and identities are unreviewed unless explicitly stated otherwise.
- Spelling hints are recognizer configuration, not observations or evidence of identity.
- Overlapping voices with unresolved attribution are group evidence. Preserve their words without assigning them, their vocal emotion or a voice identity to an individual. Speaker candidates are not confirmed people.
- Evidence priority is transcript with its stated quality limits first, objects second, caption last.
- Topic hints are incomplete literal excerpts, not mandatory topics or additional evidence. Preserve a supported model-selected topic even when no hint matches it.
- Do not invent family, friendship, marriage, employment, or other social roles.
- Do not invent locations, events, or activities not directly supported by the evidence.
- Transcript-only evidence establishes what was said, not what happened on screen. Frame each transcript-derived claim as something said, asked, mentioned or requested. Commands and questions do not prove that the requested action occurred; preserve negation and uncertainty.
- When visual evidence is absent, narrative_summary, key_moments and activity_description must describe the speech content only. Do not convert spoken instructions into observed actions or infer kinship, ownership, visible presence or the recording date from spoken names, ages, pronouns or dates.
- If the transcript is empty or minimal and the visual evidence is weak, use: "Minimal visual or dialogue content."
- If people are only talking indoors, say that plainly.
- Context tags must be concrete and traceable to visible action, spoken topic, objects, or audio emotion.
- If the evidence is weak, use broader literal wording instead of guessing.
- Do not rewrite a scene into a social event.

Return ONLY a JSON object with exactly these keys. Do not add a preamble,
Markdown fences, comments or an explanation after the object. Output instructions
describe the format; they are not additional scene evidence.
- narrative_summary: one short grounded sentence
- key_moments: an array of 0-3 short literal actions or discussion points; use [] when unsupported
- emotional_arc: one short grounded phrase, or "unqualified" when scene mood is not established
- context_tags: an array of 0-4 short evidence-backed tags; use [] when unsupported
- activity_description: one short concrete sentence

JSON:"""

    return system_prompt, user_prompt


def analyze_scene_context_llm(
    scene_meta: Dict[str, Any], cfg: Dict[str, Any], *, llm_client: Optional["LLMClient"] = None,
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to analyze scene context and extract deeper semantic meaning
    
    Args:
        scene_meta: Scene metadata with visual, audio, and temporal info
        cfg: Configuration with LLM settings
        llm_client: Runtime-owned client with explicit models and execution policy
        
        Returns a conservative additive context payload:
        {
            'narrative_summary': str,
            'key_moments': List[str],
            'emotional_arc': str,
            'context_tags': List[str],
            'primary_tags': List[str],
            'contextual_tags': List[str],
            'structural_tags': List[str],
            'activity_description': str
        }
    """
    scene_meta = _recording_scene_meta(scene_meta)
    try:
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
        # Legacy flat emotion estimates do not change the narrative shortcut;
        # they still receive the same scene-mood qualification below.
        has_audio_analysis = any(scene_meta.get(key) for key in _AUDIO_ANALYSIS_CHANNELS)
        if transcript_word_count < 3 and not has_audio_analysis and (weak_visual_signal or stage_monologue_visual):
            logger.info("Scene %s context resolved via low-signal fallback", scene_meta.get("index", 0))
            return _qualify_scene_audio_result({
                **_minimal_scene_context_payload(), "status": "not_applicable",
                "reason": "low_signal", "source": "scene_context_heuristic",
            }, scene_meta)
        if transcript_word_count >= 8 and not has_audio_analysis and (weak_visual_signal or (stage_monologue_visual and speaker_count <= 1)):
            logger.info("Scene %s context resolved via monologue fallback", scene_meta.get("index", 0))
            return _qualify_scene_audio_result({
                **_spoken_monologue_payload(topic_hints), "status": "ok",
                "reason": "spoken_monologue", "source": "scene_context_heuristic",
            }, scene_meta)
        system_prompt, user_prompt = _build_scene_context_prompts(scene_meta)
        
        if llm_client is None:
            return _scene_context_failure_fallback_payload(scene_meta, reason="llm_client_unavailable")
        result = llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        choice = result.get('choices', [{}])[0]
        if choice.get("finish_reason") == "length":
            logger.warning("LLM context response exhausted its token budget; using grounded fallback")
            return _scene_context_failure_fallback_payload(scene_meta, reason="llm_output_truncated")
        content = (choice.get('message', {}).get('content') or '').strip()
        content = content.replace('```json', '').replace('```', '').strip()
        try:
            parsed = json.loads(content)
            normalized = _normalize_scene_context_payload(parsed, scene_meta)
            if normalized:
                model = llm_client.last_model_used
                logger.info("Scene %s context analyzed via LLM", scene_meta.get("index", 0))
                return {
                    **normalized, "status": "ok", "reason": "model_output",
                    "source": "scene_context_llm",
                    "model_id": model.model_id if model else None,
                    "api_url": model.endpoint if model else None,
                    "provider": llm_client.last_provider_used,
                }
            logger.warning("LLM context normalized to empty payload; using grounded fallback")
            return _scene_context_failure_fallback_payload(scene_meta, reason="llm_empty_context")
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM context JSON: %s", content[:100])
            return _scene_context_failure_fallback_payload(scene_meta, reason="llm_invalid_json")
            
    except requests.Timeout:
        logger.warning("LLM context analysis timed out")
        return _scene_context_failure_fallback_payload(scene_meta, reason="llm_timeout")
    except Exception as e:
        logger.warning(f"LLM context analysis failed: {e}")
        return _scene_context_failure_fallback_payload(scene_meta, reason=f"llm_error:{type(e).__name__}")


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
