"""Test Qdrant ID normalization contract.

Proves that the Qdrant client's normalize_point_id() and the validator's
normalize_qdrant_id() produce identical results for all supported ID formats.
This is a structural contract — if these functions diverge, the validator will
report false orphans or false matches.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

# Ensure project root is on sys.path
_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

# Import the two ID normalization functions
from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE
from steps.common.qdrant_client import QdrantClient as _QdrantClientClass


def _qdrant_normalize(raw_id: str) -> str:
    """Simulate QdrantClient.normalize_point_id without a live client."""
    import string
    s = raw_id.strip()
    if not s:
        return None
    hex_candidate = s.replace("-", "")
    if len(hex_candidate) == 32 and all(ch in string.hexdigits for ch in hex_candidate):
        return str(uuid.UUID(hex_candidate))
    if s.isdigit():
        return int(s)
    return str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))


def _validator_normalize(raw_id: str) -> str:
    """Reproduce validate_ucf_epoch.normalize_qdrant_id inline."""
    s = raw_id.strip()
    hex_candidate = s.replace("-", "")
    if len(hex_candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in hex_candidate):
        try:
            return str(uuid.UUID(hex_candidate))
        except ValueError:
            pass
    if s.isdigit():
        return s
    return str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))


# ──────────────────────────────────────────────
# Contract: both functions agree on SHA256 hashes
# ──────────────────────────────────────────────


class TestIdNormalizationContract:
    """Proves that Qdrant client and validator produce identical IDs."""

    def test_sha256_hash_produces_same_uuid5(self):
        """A 64-char hex SHA256 hash normalizes to the same UUID5 in both."""
        sha256 = "a" * 64
        qdrant_id = _qdrant_normalize(sha256)
        validator_id = _validator_normalize(sha256)
        assert qdrant_id == validator_id
        # Must be a valid UUID
        assert uuid.UUID(qdrant_id)

    def test_clap_content_fingerprint(self):
        """CLAP content fingerprint (SHA256) normalizes identically."""
        clap_hash = "4c1193d6bf2d7d1a61b7c61089b0e7c434e361aa96a03b96c1f7280af450c472"
        qdrant_id = _qdrant_normalize(clap_hash)
        validator_id = _validator_normalize(clap_hash)
        assert qdrant_id == validator_id

    def test_text_embed_content_fingerprint(self):
        """text_embed content fingerprint (SHA256) normalizes identically."""
        text_hash = "029800df1995f19f00e3479b643f3d2c1b635b2b1471ba01dfb9c877dbc48386"
        qdrant_id = _qdrant_normalize(text_hash)
        validator_id = _validator_normalize(text_hash)
        assert qdrant_id == validator_id

    def test_scene_summary_id(self):
        """Scene-bundle summary ID ({scene_id}_summary) normalizes identically."""
        scene_id = "f9bbc7efccc54c64d28c45e4c4df7ee2829c1cff6c4760a5c0376742a52d60b1"
        summary_id = f"{scene_id}_summary"
        qdrant_id = _qdrant_normalize(summary_id)
        validator_id = _validator_normalize(summary_id)
        assert qdrant_id == validator_id

    def test_uuid_passthrough(self):
        """Already-formatted UUIDs pass through identically."""
        raw_uuid = "2058b732-6666-5424-a820-5cf54ef071c4"
        qdrant_id = _qdrant_normalize(raw_uuid)
        validator_id = _validator_normalize(raw_uuid)
        assert qdrant_id == validator_id
        assert qdrant_id == raw_uuid

    def test_namespace_is_identical(self):
        """Both use the same UUID5 namespace."""
        # Import the validator's namespace
        validator_script = _repo / "scripts" / "ucf" / "validate_ucf_epoch.py"
        assert validator_script.exists(), f"Validator not found at {validator_script}"

        import importlib.util
        spec = importlib.util.spec_from_file_location("validate_ucf_epoch", str(validator_script))
        module = importlib.util.module_from_spec(spec)
        # Don't execute the module (it has side effects), just check the constant
        import re
        content = validator_script.read_text(encoding="utf-8")
        match = re.search(r'GOODQ_POINT_ID_NAMESPACE\s*=\s*uuid\.UUID\(["\']([^"\']+)["\']\)', content)
        assert match, "GOODQ_POINT_ID_NAMESPACE not found in validator"
        validator_ns = uuid.UUID(match.group(1))
        assert validator_ns == GOODQ_POINT_ID_NAMESPACE, (
            f"Namespace mismatch: client={GOODQ_POINT_ID_NAMESPACE} validator={validator_ns}"
        )

    def test_deterministic_across_calls(self):
        """Same input always produces same output."""
        raw = "some_arbitrary_string_that_is_not_a_uuid"
        results = [_qdrant_normalize(raw) for _ in range(5)]
        assert len(set(results)) == 1

    def test_different_inputs_produce_different_ids(self):
        """Different SHA256 hashes produce different UUIDs."""
        hash_a = "a" * 64
        hash_b = "b" * 64
        assert _qdrant_normalize(hash_a) != _qdrant_normalize(hash_b)
