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
    "background",
    "blue backpack",
    "blue shirt",
    "man and woman",
    "man sitting on couch",
    "microwave",
    "potted plant",
    "room with a blue backpack",
    "person",
    "men",
    "men sitting",
    "men in a store",
    "sitting",
    "vibrant woman",
    "wine glass",
    "woman in a suit",
    "woman sitting on couch",
    "spoken topic",
}
_SETTING_HINTS = (
    "living room",
    "kitchen",
    "dining room",
    "bedroom",
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
    re.compile(r"\bblue backpack\b", re.IGNORECASE),
    re.compile(r"\bblue shirt\b", re.IGNORECASE),
    re.compile(r"\bfianc[^\s]*", re.IGNORECASE),
    re.compile(r"\bman and woman\b", re.IGNORECASE),
    re.compile(r"\b(?:the\s+)?man and (?:the\s+)?woman\b", re.IGNORECASE),
    re.compile(r"\b(?:the\s+)?woman and (?:the\s+)?man\b", re.IGNORECASE),
    re.compile(r"\b(?:man|woman)\s+in\s+(?:(?:a|an)\s+)?(?:[a-z]+\s+){0,2}(?:robe|suit|jacket|dress|coat|shirt|tie)\b", re.IGNORECASE),
    re.compile(r"\bman sitting on couch\b", re.IGNORECASE),
    re.compile(r"\bwoman sitting on couch\b", re.IGNORECASE),
    re.compile(r"\bmicrowave\b", re.IGNORECASE),
    re.compile(r"\bspoken topic\b", re.IGNORECASE),
    re.compile(r"\bperson\b", re.IGNORECASE),
    re.compile(r"\b(?:one|two|three|four)\s+(?:man|men|woman|women)\b", re.IGNORECASE),
    re.compile(r"\bmen(?:\s+sitting|\s+in\s+a\s+store)?\b", re.IGNORECASE),
    re.compile(r"\bman with a limp\b", re.IGNORECASE),
    re.compile(r"\bvibrant woman\b", re.IGNORECASE),
    re.compile(r"\bwoman in a suit\b", re.IGNORECASE),
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
    re.compile(r"\bread(?:s|ing)\s+(?:a\s+)?(?:manuscript|newspaper)\b", re.IGNORECASE),
    re.compile(r"\bdriv(?:es|ing)\s+(?:a\s+)?car\b", re.IGNORECASE),
    re.compile(r"\beat(?:s|ing)\s+(?:lunch|pretzels?)\b", re.IGNORECASE),
    re.compile(r"\bdrink(?:s|ing)\s+coffee\b", re.IGNORECASE),
    re.compile(r"\bl(?:ie|y)(?:s|ing)\s+(?:down\s+)?on\s+(?:the\s+)?couch\b", re.IGNORECASE),
    re.compile(r"\bsit(?:s|ting)\s+on\s+(?:the\s+)?floor\b", re.IGNORECASE),
    re.compile(r"\bgiv(?:es|ing)\s+a\s+bottle\b", re.IGNORECASE),
    re.compile(r"\bis\s+displayed\s+as\b", re.IGNORECASE),
    re.compile(r"\bare\s+seen\s+nearby\b", re.IGNORECASE),
    re.compile(r"\bturns?\s+to\b", re.IGNORECASE),
    re.compile(r"\bspeaks?\s+to\s+(?:the\s+)?(?:man|woman|person)\b", re.IGNORECASE),
    re.compile(r"\bdiscuss(?:es|ing)?\s+(?:their|the)\b", re.IGNORECASE),
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
    "are",
    "asks",
    "at",
    "conversation",
    "converse",
    "conversing",
    "discuss",
    "discusses",
    "discussing",
    "he",
    "her",
    "him",
    "his",
    "in",
    "indoors",
    "indoor",
    "is",
    "it",
    "man",
    "men",
    "mention",
    "mentions",
    "one",
    "other",
    "people",
    "person",
    "restaurant",
    "say",
    "says",
    "setting",
    "sit",
    "sits",
    "sitting",
    "speak",
    "speaking",
    "speaks",
    "stand",
    "standing",
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
_LOW_VALUE_TOPIC_PHRASES = {
    "a question",
    "a question sure",
    "alarmed god",
    "always encouraged experimentation",
    "apartment yep",
    "apartment yep just",
    "attention yeah",
    "ask mark",
    "business no",
    "business no no",
    "business listen",
    "cable station lov",
    "cable station lough",
    "certain pain",
    "clean apartment",
    "clean apartment yep",
    "compartment wait",
    "compartment wait hold",
    "different interpretation",
    "encouraged experimentation",
    "ever mention",
    "fianc‚",
    "go off oppression",
    "glove compartment",
    "glove compartment wait",
    "hell happened",
    "jimmy shar",
    "jerry baby",
    "lasting impression",
    "like a car",
    "lunch",
    "m meeting",
    "made a reservation",
    "men sitting at a table",
    "move cars",
    "must some",
    "no job",
    "operation yeah",
    "operation yeah yeah",
    "pocketing cars",
    "people aware",
    "position he was",
    "question do",
    "restitution because",
    "restitution restitution",
    "relationship respirator",
    "relationship respirator keeping",
    "s a community",
    "sing songy quality",
    "songy quality",
    "some mistake",
    "station lov",
    "st street apartment",
    "show business listen",
    "off oppression wild",
    "off oppression",
    "other business",
    "business elsewhere",
    "business end",
    "business end take",
    "business leave",
    "other business no",
    "negotiating negotiation",
    "oppression don",
    "oppression don t",
    "oppression wild",
    "oppression wild oppression",
    "transition phase",
    "transition phase right",
    "vibrant woman",
    "wild oppression",
    "wild oppression don",
    "woody yells action",
    "yells action",
}
_LOW_VALUE_TOPIC_TOKENS = {
    "alarmed",
    "ask",
    "aware",
    "baby",
    "block",
    "cable",
    "cars",
    "do",
    "doing",
    "different",
    "ever",
    "fianc",
    "god",
    "good",
    "happened",
    "happening",
    "hell",
    "interpretation",
    "job",
    "like",
    "listen",
    "lough",
    "lov",
    "lunch",
    "made",
    "mention",
    "mistake",
    "must",
    "parks",
    "people",
    "pocketing",
    "some",
    "station",
    "sure",
    "time",
    "whole",
    "shirt",
    "vibrant",
    "wearing",
    "yells",
}
_LOWERCASE_TOPIC_HEADS = {
    "appointment",
    "bed",
    "bills",
    "bylaws",
    "car",
    "case",
    "chiropractor",
    "collar",
    "constitution",
    "directions",
    "drive",
    "drugstore",
    "elevator",
    "emcee",
    "expressway",
    "job",
    "lawyer",
    "mask",
    "medication",
    "meeting",
    "medicine",
    "pain",
    "pen",
    "pharmacist",
    "pills",
    "president",
    "project",
    "relaxers",
    "schedule",
    "scuba",
    "shakespeare",
    "shoes",
    "sofa",
    "typewriter",
}
_TOPIC_NOUN_SUFFIXES = ("ment", "tion", "sion", "ness", "ship", "ist", "ity", "ware")
_TRANSCRIPT_TOPIC_PATTERNS = (
    (re.compile(r"\bcold medication\b", re.IGNORECASE), "cold medication"),
    (re.compile(r"\bdentist appointment\b", re.IGNORECASE), "dentist appointment"),
    (re.compile(r"\bdrug company\b", re.IGNORECASE), "drug company"),
    (re.compile(r"\bdrugstore\b", re.IGNORECASE), "drugstore"),
    (re.compile(r"\bmedicine\b", re.IGNORECASE), "medicine"),
    (re.compile(r"\b(?:mr\.?\s+)?poc[ao]tillo\b", re.IGNORECASE), "Steve Pocatillo"),
    (re.compile(r"\b(?:stay here steve|letting us stay here steve)\b", re.IGNORECASE), "Steve"),
    (re.compile(r"\blong island expressway\b", re.IGNORECASE), "Long Island Expressway"),
    (re.compile(r"\blong island\b", re.IGNORECASE), "Long Island"),
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
    (re.compile(r"\brent(?:-| )a(?:-| )car\b", re.IGNORECASE), "rental car"),
    (re.compile(r"\bair conditioning\b", re.IGNORECASE), "air conditioning"),
    (
        re.compile(
            r"\bmoves?\s+(?:them\s+)?from one side of the street to the other\b",
            re.IGNORECASE,
        ),
        "alternate side",
    ),
    (re.compile(r"\balternate side(?: parking)?\b", re.IGNORECASE), "alternate side"),
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
    (re.compile(r"\bpeanut(?:\s+brittle|\s+butter|\s+oil)?\b", re.IGNORECASE), "peanut"),
    (re.compile(r"\bpretzel(?:s|\s+guy)?\b", re.IGNORECASE), "pretzel"),
    (re.compile(r"\bpresident\b", re.IGNORECASE), "president"),
    (re.compile(r"\breservation\b", re.IGNORECASE), "reservation"),
    (re.compile(r"\brestitution\b", re.IGNORECASE), "restitution"),
    (re.compile(r"\b(?:counter offer|whole deal)\b", re.IGNORECASE), "business deal"),
    (re.compile(r"\b(?:deformed position|nothing but a claw|a claw)\b", re.IGNORECASE), "deformed hand"),
    (re.compile(r"\bflorida\b", re.IGNORECASE), "florida"),
    (re.compile(r"\bpen\b", re.IGNORECASE), "pen"),
    (re.compile(r"\bbathing suits?\b", re.IGNORECASE), "bathing suit"),
)
_TOPIC_STOPWORDS = {
    "a", "about", "again", "air", "airlines", "all", "an", "and", "any", "are", "around", "as", "at", "back",
    "been", "boat", "bucks", "but", "call", "can", "come", "could", "day",
    "did", "didnt", "dont", "down", "for", "from", "get", "going", "got", "had",
    "has", "have", "here", "him", "his", "how", "i", "if", "ill", "im", "in", "inside",
    "into", "is", "it", "its", "know", "lake", "m", "me", "minutes", "my", "need", "nobody",
    "much", "nice", "not", "of", "oh", "old", "on", "or", "our", "out", "pay", "person",
    "real", "really", "room", "seen", "so", "special", "stay", "tape", "that",
    "s", "thats", "the", "them", "there", "they", "thing", "things", "think", "this",
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
    "first",
    "no",
    "oh",
    "okay",
    "put",
    "so",
    "take",
    "the",
    "thanks",
    "well",
    "welcome",
    "what",
    "why",
    "yes",
    "you",
    "ask",
    "goodbye",
    "maybe",
}
_TOPIC_FRAGMENT_EDGE_TOKENS = {
    "always",
    "he",
    "i",
    "just",
    "no",
    "other",
    "she",
    "they",
    "we",
    "yeah",
    "yep",
    "you",
}
_TOPIC_GERUND_HEAD_ALLOWLIST = {"meeting"}
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
            while tokens and tokens[0].casefold() in _CAPITALIZED_TOPIC_EXCLUSIONS.union(_TOPIC_STOPWORDS):
                tokens.pop(0)
            while tokens and tokens[-1].casefold() in _CAPITALIZED_TOPIC_EXCLUSIONS.union(_TOPIC_STOPWORDS):
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
        words = re.findall(r"[a-zA-Z]+", normalized)
        for window_size in (3, 2):
            for index in range(0, len(words) - window_size + 1):
                phrase_tokens = words[index : index + window_size]
                while phrase_tokens and phrase_tokens[0] in _TOPIC_FRAGMENT_EDGE_TOKENS:
                    phrase_tokens = phrase_tokens[1:]
                while phrase_tokens and phrase_tokens[-1] in _TOPIC_FRAGMENT_EDGE_TOKENS:
                    phrase_tokens = phrase_tokens[:-1]
                if len(phrase_tokens) < 2:
                    continue
                if any(token in _TOPIC_STOPWORDS or token in _LOW_VALUE_TOPIC_TOKENS for token in phrase_tokens):
                    continue
                if phrase_tokens[0].endswith("ly") or phrase_tokens[0].endswith("ed"):
                    continue
                head = phrase_tokens[-1]
                if head.endswith("ing") and head not in _TOPIC_GERUND_HEAD_ALLOWLIST:
                    continue
                singular_head = head[:-1] if head.endswith("s") and len(head) > 3 else head
                if singular_head not in _LOWERCASE_TOPIC_HEADS and not any(
                    token.endswith(_TOPIC_NOUN_SUFFIXES) for token in phrase_tokens
                ):
                    continue
                candidate = " ".join(phrase_tokens)
                if candidate in seen or _is_low_value_topic_fragment(candidate):
                    continue
                seen.add(candidate)
                hints.append(candidate)
                if len(hints) >= 5:
                    return hints

    return hints[:5]


def _matches_explicit_transcript_topic_pattern(candidate: str, transcript: str) -> bool:
    normalized_candidate = str(candidate or "").strip().casefold()
    normalized_transcript = str(transcript or "").strip().casefold()
    if not normalized_candidate or not normalized_transcript:
        return False
    for pattern, label in _TRANSCRIPT_TOPIC_PATTERNS:
        if label.casefold() == normalized_candidate and pattern.search(normalized_transcript):
            return True
    return False


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


def _scene_context_failure_fallback_payload(scene_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return a conservative, evidence-grounded payload when the LLM path fails."""
    transcript = str(scene_meta.get("transcript") or "").strip()
    transcript_word_count = len(re.findall(r"\b\w+\b", transcript))
    caption = str(scene_meta.get("caption") or "").strip()
    objects = scene_meta.get("objects", [])
    object_labels: List[str] = []
    if isinstance(objects, list):
        for obj in objects[:10]:
            if isinstance(obj, dict):
                label = str(obj.get("label") or "").strip()
            else:
                label = str(obj).strip()
            if label:
                object_labels.append(label)

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
    emotional_arc = f"{emotion_label} audio emotion signal" if emotion_label else "neutral tone"

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
        return _normalize_scene_context_payload(raw_payload, scene_meta) or _minimal_scene_context_payload()

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
        return _normalize_scene_context_payload(raw_payload, scene_meta) or _minimal_scene_context_payload()

    return _minimal_scene_context_payload()


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


def _is_evidence_grounded_topic_candidate(candidate: str, evidence_blob: str) -> bool:
    normalized = str(candidate or "").strip().casefold()
    if not normalized or _is_low_value_topic_fragment(normalized):
        return False
    if normalized.endswith(" conversation"):
        return False
    tokens = [
        token
        for token in re.findall(r"[a-zA-Z]+", normalized)
        if token not in _TOPIC_STOPWORDS and token not in _LOW_VALUE_TOPIC_TOKENS
    ]
    if not tokens:
        return False
    return all(token in evidence_blob for token in tokens)


def _is_transcript_grounded_topic_candidate(candidate: str, transcript: str) -> bool:
    return _matches_explicit_transcript_topic_pattern(candidate, transcript) or _is_evidence_grounded_topic_candidate(
        candidate,
        str(transcript or "").casefold(),
    )


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
    return len(missing) >= 2 and len(missing) >= max(2, len(stems) // 2)


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


def _rewrite_key_moment(
    value: Optional[str],
    *,
    transcript: str,
    evidence_blob: str,
    setting_hint: Optional[str],
    topic_hint: Optional[str],
) -> Optional[str]:
    normalized = value.strip() if isinstance(value, str) else value
    if not isinstance(normalized, str) or not normalized.strip():
        return normalized
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
    visible_text_values = _prompt_evidence_values(
        scene_meta.get("ocr_text") or scene_meta.get("visible_text"),
        limit=4,
    )
    music_event_values = _prompt_evidence_values(scene_meta.get("music_events"), limit=8)
    time_hint_values = _prompt_evidence_values(scene_meta.get("time_hints"), limit=8)
    metadata_time_hint_values = _prompt_evidence_values(scene_meta.get("metadata_time_hints"), limit=8)
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
    evidence_blob = " ".join(
        [
            transcript,
            caption,
            " ".join(object_labels),
            " ".join(visible_text_values),
            " ".join(music_event_values),
            " ".join(time_hint_values),
            " ".join(metadata_time_hint_values),
        ]
    ).casefold()

    context_tags = _clean_list(raw_context.get("context_tags"), limit=8)
    topic_hints = _extract_transcript_topic_hints(transcript)
    topic_hint = _derive_topic_hint(
        topic_hints,
        [],
        evidence_blob,
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
        if lowered in {"hospital", "constitutional topics"} and lowered not in evidence_blob:
            continue
        if lowered in _SETTING_HINTS and lowered not in evidence_blob:
            continue
        if (
            topic_hint
            and lowered not in _SETTING_HINTS
            and lowered != topic_hint.casefold()
            and not _is_transcript_grounded_topic_candidate(tag, transcript)
        ):
            continue
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

    raw_summary = _clean_text(raw_context.get("narrative_summary"))
    force_summary_rewrite = _contains_unsupported_role_text(raw_summary or "", transcript)
    if _contains_unsupported_activity_text(raw_summary or "", transcript):
        force_summary_rewrite = True
    if _contains_low_value_visible_focus(raw_summary or ""):
        force_summary_rewrite = True
    if _contains_low_value_declared_topic(raw_summary or ""):
        force_summary_rewrite = True
    if any(pattern.search(raw_summary or "") for pattern in _INTERPRETIVE_SUMMARY_PATTERNS):
        force_summary_rewrite = True
    if _has_excess_ungrounded_content(
        raw_summary or "",
        evidence_blob=evidence_blob,
        topic_hint=topic_hint,
        setting_hint=setting_hint,
    ):
        force_summary_rewrite = True

    raw_activity = _clean_text(raw_context.get("activity_description"))
    force_activity_rewrite = _contains_unsupported_role_text(raw_activity or "", transcript)
    if _contains_unsupported_activity_text(raw_activity or "", transcript):
        force_activity_rewrite = True
    if _contains_low_value_visible_focus(raw_activity or ""):
        force_activity_rewrite = True
    if _contains_low_value_declared_topic(raw_activity or ""):
        force_activity_rewrite = True
    if any(pattern.search(raw_activity or "") for pattern in _INTERPRETIVE_SUMMARY_PATTERNS):
        force_activity_rewrite = True
    if _has_excess_ungrounded_content(
        raw_activity or "",
        evidence_blob=evidence_blob,
        topic_hint=topic_hint,
        setting_hint=setting_hint,
    ):
        force_activity_rewrite = True

    key_moments: List[str] = []
    seen_moments: set[str] = set()
    for value in _clean_list(raw_context.get("key_moments"), limit=5):
        rewritten = _rewrite_key_moment(
            value,
            transcript=transcript,
            evidence_blob=evidence_blob,
            setting_hint=setting_hint,
            topic_hint=topic_hint,
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

    narrative_summary = _rewrite_scene_text(
        raw_summary,
        setting_hint=setting_hint,
        topic_hint=topic_hint,
        force_rewrite=force_summary_rewrite,
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
        evidence_blob=evidence_blob,
        topic_hint=topic_hint,
        narrative_summary=narrative_summary,
    )

    activity_description = _rewrite_scene_text(
        raw_activity,
        setting_hint=setting_hint,
        topic_hint=topic_hint,
        force_rewrite=force_activity_rewrite,
    )
    promoted_activity_summary = False
    if (
        narrative_summary == "Minimal visual or dialogue content."
        and activity_description != "Minimal visual or dialogue content."
        and not _has_excess_ungrounded_content(
            activity_description,
            evidence_blob=evidence_blob,
            topic_hint=topic_hint,
            setting_hint=setting_hint,
        )
    ):
        narrative_summary = activity_description
        promoted_activity_summary = True
    if promoted_activity_summary and not key_moments:
        key_moments = [activity_description]

    sanitized = {
        "narrative_summary": narrative_summary,
        "key_moments": key_moments,
        "emotional_arc": _rewrite_emotional_arc(raw_context.get("emotional_arc"), transcript),
        "context_tags": tag_payload["context_tags"],
        "primary_tags": tag_payload["primary_tags"],
        "contextual_tags": tag_payload["contextual_tags"],
        "structural_tags": tag_payload["structural_tags"],
        "activity_description": activity_description,
    }
    if sanitized["narrative_summary"] == "Minimal visual or dialogue content.":
        sanitized["key_moments"] = ["Minimal visual or dialogue content."]
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

    object_labels: List[str] = []
    for obj in objects[:10] if isinstance(objects, list) else []:
        if isinstance(obj, dict):
            label = str(obj.get("label") or "").strip()
        else:
            label = str(obj).strip()
        if label:
            object_labels.append(label)
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
- Visible text: {visible_text_str}
- Audio/music events: {music_events_str}
- Time hints: {time_hints_str}
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
            'primary_tags': List[str],
            'contextual_tags': List[str],
            'structural_tags': List[str],
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
                normalized = _normalize_scene_context_payload(parsed, scene_meta)
                if normalized:
                    return normalized
                logger.warning("LLM context normalized to empty payload; using grounded fallback")
                return _scene_context_failure_fallback_payload(scene_meta)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM context JSON: {content[:100]}")
                return _scene_context_failure_fallback_payload(scene_meta)
        else:
            logger.warning(f"LLM API returned status {response.status_code}")
            return _scene_context_failure_fallback_payload(scene_meta)
            
    except requests.Timeout:
        logger.warning("LLM context analysis timed out")
        return _scene_context_failure_fallback_payload(scene_meta)
    except Exception as e:
        logger.warning(f"LLM context analysis failed: {e}")
        return _scene_context_failure_fallback_payload(scene_meta)


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
