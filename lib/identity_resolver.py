"""
GoodQ4All — Identity Resolver
==============================
Additive retrieval layer that augments normal search with identity-aware
scene pre-selection from the curated roster and active reviewed voice mappings.

Contract:
  - Disabled by config or when both roster and active voice reviews are absent.
  - Augments normal vector search; explicit People mode reads identity evidence only.
  - Thread-safe: roster is loaded once at startup, cached in memory.
  - Reloads changed rosters; reads current graph/review state on each query.

Integration:
  - identity_search.enabled must be true in config to activate.
  - Score boost is additive, not exclusive.
  - Enabled only after Phase 5A promotion and regression test pass.
"""

import logging
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from steps.common.platform_config import PlatformHelper

log = logging.getLogger(__name__)

DEFAULT_ROSTER_NAME   = "family_roster.yaml"


def retired_identity_scene_ids(ucf_path: Path) -> set[str]:
    """Read durable exclusions even while KG projection delivery is pending."""
    if not ucf_path.is_file():
        return set()
    import sqlite3
    from scripts.ucf.ucf_ledger import read_scene_retirements

    with sqlite3.connect(f"{ucf_path.resolve().as_uri()}?mode=ro", uri=True) as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ucf_status_transitions'"
        ).fetchone():
            return set()
        sources = conn.execute(
            "SELECT DISTINCT video_hash FROM ucf_status_transitions WHERE scope LIKE 'scene_retirement:%'"
        ).fetchall()
    return {
        alias
        for (source,) in sources
        for evidence in read_scene_retirements(ucf_path, video_hash=source)
        for alias in evidence["aliases"]
    }


@dataclass
class PersonMatch:
    person_id: str
    display_name: str
    aliases: list[str]
    matched_term: str
    confidence: str = "alias_match"


@dataclass
class _RosterCache:
    identities: list[dict] = field(default_factory=list)
    alias_index: dict[str, str] = field(default_factory=dict)  # alias_lower -> person_id
    mtime: float = 0.0


class IdentityResolver:
    """
    Resolves query terms to curated identities and their associated scene IDs.
    Instantiate once and reuse. Thread-safe.
    """

    def __init__(
        self,
        roster_path: Optional[str] = None,
        kg_db_path: Optional[str] = None,
        enabled: bool = False,
    ) -> None:
        self._enabled = enabled
        configured_roster_path = Path(
            roster_path
            or os.environ.get("GOODQ_IDENTITY_PATH")
            or PlatformHelper.get_data_root() / "GoodQ_Data" / "identity"
        )
        self._roster_path = (
            configured_roster_path
            if configured_roster_path.suffix.lower() in {".yaml", ".yml"}
            else configured_roster_path / DEFAULT_ROSTER_NAME
        )
        self._kg_db_path = kg_db_path
        self._lock = threading.Lock()
        self._cache: _RosterCache = _RosterCache()
        self._scene_cache: dict[str, set[str]] = {}  # person_id -> scene_name set
        self._scene_evidence_cache: dict[str, dict[str, set[str]]] = {}

    def is_enabled(self) -> bool:
        """Require the feature gate and a curated roster or active voice review."""
        if not self._enabled:
            return False
        return self._roster_path.exists() or bool(self._active_voice_mappings())

    def _active_voice_mappings(self) -> list[dict]:
        if not self._kg_db_path:
            return []
        path = Path(self._kg_db_path).parent / "manual_identity_mappings.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [m for m in data.get("mappings", []) if isinstance(m, dict)
                    and m.get("status") == "active" and m.get("source_node_type") == "speaker_pattern"
                    and all(isinstance(m.get(k), str) and m[k].strip() for k in
                            ("mapping_id", "source_node_name", "target_person_name"))]
        except (OSError, ValueError, AttributeError) as exc:
            log.warning("IdentityResolver: reviewed voice mappings unavailable: %s", type(exc).__name__)
            return []

    def _load_roster(self) -> None:
        """Loads (or reloads) the roster if the file has changed."""
        if not self._roster_path.exists():
            self._cache = _RosterCache()
            return
        mtime = self._roster_path.stat().st_mtime
        if mtime == self._cache.mtime:
            return  # No change
        try:
            import yaml
        except ImportError:
            log.warning("PyYAML not available — IdentityResolver cannot load roster.")
            return

        with open(self._roster_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        identities = data.get("identities", [])
        alias_index: dict[str, str] = {}
        for identity in identities:
            person_id = identity.get("id", "")
            display_name = identity.get("display_name", "")
            aliases = identity.get("aliases") or []
            name_keys = identity.get("name_mention_keys") or []
            # Index: display name, all aliases, all mention keys → person_id
            for term in [display_name] + aliases + name_keys:
                if term:
                    alias_index[term.lower()] = person_id

        new_cache = _RosterCache(
            identities=identities,
            alias_index=alias_index,
            mtime=mtime,
        )
        with self._lock:
            self._cache = new_cache
            self._scene_cache.clear()  # invalidate scene cache on roster reload
            self._scene_evidence_cache.clear()
        log.info(
            "IdentityResolver: loaded %d identities, %d alias terms",
            len(identities), len(alias_index),
        )

    def _load_scene_evidence_for_person(
        self,
        person_id: str,
    ) -> dict[str, set[str]]:
        """
        Returns scene names with their exact promoted identity evidence types.
        """
        if not self._kg_db_path:
            return {}
        import sqlite3
        try:
            conn = sqlite3.connect(Path(self._kg_db_path).resolve().as_uri() + "?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT target_n.name, e.edge_type
                FROM edges e
                JOIN nodes source_n ON e.source_id = source_n.id
                JOIN nodes target_n ON e.target_id = target_n.id
                WHERE source_n.node_type = 'Person'
                  AND source_n.name = ?
                  AND e.edge_type IN ('person_appears_in_scene', 'person_mentioned_in_scene')
                  AND target_n.node_type = 'scene'
                """,
                (person_id,),
            )
            evidence: dict[str, set[str]] = {}
            for scene_name, edge_type in cur.fetchall():
                evidence_type = (
                    "appearance"
                    if edge_type == "person_appears_in_scene"
                    else "mention"
                )
                evidence.setdefault(str(scene_name), set()).add(evidence_type)
            # A voice claim requires both an active saved review and its exact
            # materialized manual edge, followed by a scene-local speaker link.
            names = {i.get("display_name") for i in self._cache.identities if i.get("id") == person_id}
            if person_id.startswith("reviewed-voice:"):
                names.add(person_id.removeprefix("reviewed-voice:"))
            for mapping in self._active_voice_mappings():
                if mapping["target_person_name"] not in names:
                    continue
                rows = conn.execute("""
                    SELECT DISTINCT scene.name, review.properties
                    FROM nodes pattern
                    JOIN edges review ON review.source_id=pattern.id AND review.edge_type='identity_evidence'
                    JOIN nodes person ON person.id=review.target_id AND person.node_type='person'
                    JOIN edges voice ON voice.target_id=pattern.id AND voice.edge_type='voice_pattern_match'
                    JOIN nodes speaker ON speaker.id=voice.source_id AND speaker.node_type='speaker'
                    JOIN edges spoken ON spoken.source_id=speaker.id AND spoken.edge_type='speaks_in'
                    JOIN nodes scene ON scene.id=spoken.target_id AND scene.node_type='scene'
                    WHERE pattern.node_type='speaker_pattern' AND pattern.name=? AND person.name=?
                """, (mapping["source_node_name"], mapping["target_person_name"])).fetchall()
                for scene_name, raw_properties in rows:
                    props = json.loads(raw_properties or "{}")
                    if props.get("source") == "operator_manual_override" and props.get("mapping_id") == mapping["mapping_id"]:
                        evidence.setdefault(str(scene_name), set()).add("voice")
            return evidence
        except Exception as e:
            log.warning("IdentityResolver: KG query failed for %s: %s", person_id, e)
            return {}
        finally:
            if 'conn' in locals():
                conn.close()

    def _load_scenes_for_person(self, person_id: str) -> set[str]:
        return set(self._load_scene_evidence_for_person(person_id))

    def resolve_query_entities(self, query_text: str) -> list[PersonMatch]:
        """
        Scans query text for terms matching curated identity aliases.
        Returns a list of PersonMatch objects (may be empty).
        Does not raise — returns [] on any error.
        """
        if not self.is_enabled():
            return []
        try:
            self._load_roster()
        except Exception as e:
            log.warning("IdentityResolver: roster load failed: %s", e)
            return []

        cache = self._cache
        matches = []
        seen_persons: set[str] = set()
        # Check each alias term against the query (word-boundary aware)
        for alias_lower, person_id in cache.alias_index.items():
            if person_id in seen_persons:
                continue
            pattern = re.compile(rf'\b{re.escape(alias_lower)}\b', re.IGNORECASE)
            if pattern.search(query_text):
                identity = next(
                    (i for i in cache.identities if i.get("id") == person_id),
                    {},
                )
                matches.append(PersonMatch(
                    person_id=person_id,
                    display_name=identity.get("display_name", person_id),
                    aliases=identity.get("aliases") or [],
                    matched_term=alias_lower,
                    confidence="curated_alias",
                ))
                seen_persons.add(person_id)

        for name in sorted({m["target_person_name"] for m in self._active_voice_mappings()}):
            # Only an exact unique roster display name bridges to a roster ID.
            # Aliases are query terms, not authority to merge two people.
            curated = [i for i in cache.identities if i.get("display_name") == name]
            if len(curated) > 1:
                continue
            person_id = curated[0]["id"] if curated else "reviewed-voice:" + name
            if person_id not in seen_persons and re.search(rf'\b{re.escape(name)}\b', query_text, re.IGNORECASE):
                matches.append(PersonMatch(person_id, name, [], name, "reviewed_voice"))
                seen_persons.add(person_id)

        if matches:
            log.debug(
                "IdentityResolver: query '%s' matched %d identities: %s",
                query_text[:50], len(matches), [m.person_id for m in matches],
            )
        return matches

    def get_scenes_for_person(self, person_id: str) -> set[str]:
        """
        Returns the set of scene names (KG node names) where this person
        has current identity-linked evidence.
        """
        if not self.is_enabled():
            return set()
        with self._lock:
            self._scene_cache[person_id] = self._load_scenes_for_person(person_id)
        retired = retired_identity_scene_ids(Path(self._kg_db_path).parent / "ucf/ucf_ledger.db") if self._kg_db_path else set()
        return self._scene_cache.get(person_id, set()) - retired

    def get_scene_evidence_for_person(
        self,
        person_id: str,
    ) -> dict[str, set[str]]:
        """Returns typed current evidence; revocation must not survive a cache."""
        if not self.is_enabled():
            return {}
        with self._lock:
            evidence = self._load_scene_evidence_for_person(person_id)
            self._scene_evidence_cache[person_id] = evidence
            self._scene_cache[person_id] = set(evidence)
        retired = retired_identity_scene_ids(Path(self._kg_db_path).parent / "ucf/ucf_ledger.db") if self._kg_db_path else set()
        return {scene: evidence for scene, evidence in self._scene_evidence_cache.get(person_id, {}).items()
                if scene not in retired}

    def get_identity_scene_evidence(
        self,
        query_text: str,
    ) -> dict[str, list[dict]]:
        """Projects query-matched people onto scenes without flattening evidence."""
        result: dict[str, list[dict]] = {}
        for match in self.resolve_query_entities(query_text):
            for scene_id, evidence_types in self.get_scene_evidence_for_person(
                match.person_id
            ).items():
                ordered_types = [
                    evidence_type
                    for evidence_type in ("appearance", "voice", "mention")
                    if evidence_type in evidence_types
                ]
                result.setdefault(scene_id, []).append({
                    "person_id": match.person_id,
                    "display_name": match.display_name,
                    "matched_term": match.matched_term,
                    "evidence_types": ordered_types,
                    "strength": (
                        "appearance"
                        if "appearance" in evidence_types
                        else "voice" if "voice" in evidence_types else "mention"
                    ),
                })
        return result

    def get_identity_scene_ids(self, query_text: str) -> dict[str, set[str]]:
        """
        Convenience method: resolves query → persons → scene IDs.
        Returns {person_id: {scene_name, ...}}.
        """
        result: dict[str, set[str]] = {}
        for match in self.resolve_query_entities(query_text):
            scenes = self.get_scenes_for_person(match.person_id)
            if scenes:
                result[match.person_id] = scenes
        return result


# ── Module-level singleton (lazy, config-driven) ────────────────────────────────

_resolver: Optional[IdentityResolver] = None
_resolver_lock = threading.Lock()


def get_resolver(config: Optional[dict] = None) -> IdentityResolver:
    """
    Returns the module-level IdentityResolver singleton.
    Pass a config dict with identity_search.enabled, roster_path, kg_db_path.
    Safe to call multiple times — returns existing instance if already created.
    """
    global _resolver
    with _resolver_lock:
        if _resolver is None:
            cfg = (config or {}).get("identity_search", {})
            paths = (config or {}).get("paths", {})
            _resolver = IdentityResolver(
                roster_path=cfg.get("roster_path"),
                kg_db_path=(
                    cfg.get("kg_db_path")
                    or paths.get("knowledge_graph_db")
                ),
                enabled=cfg.get("enabled", False),
            )
    return _resolver
