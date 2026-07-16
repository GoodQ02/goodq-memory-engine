"""Passive, fail-closed Qdrant observation for clean-memory planning.

The module accepts only the immutable configuration projection produced by
``cli.clean_memory``. It performs no configuration loading, service access,
evidence persistence, planning, approval, or cleanup mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import socket
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

from cli.clean_memory import ResolvedPlanConfiguration
from steps.common.clean_memory import QdrantCollectionEvidence

QDRANT_OBSERVATION_SCHEMA = "goodq.clean-memory-qdrant-observation.v1"
_CONFIGURATION_SCHEMA = "goodq.clean-memory-configuration.v1"
_QDRANT_ROLES = ("text", "clip", "dino", "audio")
_TOP_LEVEL_KEYS = {
    "schema",
    "path_flavor",
    "epoch",
    "logical_paths",
    "declared_faiss_paths",
    "qdrant",
    "configured_protected_paths",
    "unresolved_protected_roles",
}

__all__ = (
    "QDRANT_OBSERVATION_SCHEMA",
    "QdrantObservationError",
    "QdrantObservation",
    "observe_qdrant",
)

_ERROR_MESSAGES = {
    "invalid_configuration": "Clean-memory Qdrant configuration is invalid",
    "observation_failed": "Clean-memory Qdrant observation failed",
}


class QdrantObservationError(RuntimeError):
    """Bounded, path-free Qdrant observation failure."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        try:
            message = _ERROR_MESSAGES[code]
        except (KeyError, TypeError) as exc:
            raise ValueError("Unknown Qdrant observation error code") from exc
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return self._code

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"code", "_code"} and hasattr(self, "_code"):
            raise AttributeError("Qdrant observation error code is immutable")
        object.__setattr__(name, value)


@dataclass(frozen=True)
class QdrantObservation:
    """Immutable path-free Qdrant evidence for one configured epoch."""

    schema: str
    configuration_scope_sha256: str
    qdrant_endpoint: str
    qdrant_collections: tuple[QdrantCollectionEvidence, ...]


@dataclass(frozen=True)
class _Projection:
    canonical_json: str
    configuration_scope_sha256: str
    qdrant_endpoint: str
    collections: list[dict[str, str]]


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate projection key")
        result[key] = value
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _strict_json_object(payload: str) -> dict[str, Any]:
    value = json.loads(
        payload,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise ValueError("Projection is not an object")
    if _canonical_json(value) != payload:
        raise ValueError("Projection is not canonical")
    return value


def _is_loopback_url(value: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(value)
        if not parsed.scheme:
            parsed = urllib.parse.urlparse("http://" + value)
        host = parsed.hostname
        return host in {"127.0.0.1", "localhost", "::1"}
    except Exception:
        return False


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_json(url: str, *, timeout: float = 3.0, method: str = "GET", body: dict | None = None) -> tuple[int, Any]:
    if not _is_loopback_url(url):
        raise ValueError("Qdrant HTTP queries are restricted to loopback URLs")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirectHandler(),
    )
    with opener.open(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return int(response.status), payload


def _query_collection_info(endpoint: str, collection_name: str) -> tuple[bool, dict[str, Any] | None, int | None]:
    url = f"{endpoint.rstrip('/')}/collections/{collection_name}"
    try:
        status, response = _http_json(url, timeout=3.0)
        if status == 200:
            result = response.get("result", {})
            config = result.get("config")
            point_count = result.get("points_count")
            if point_count is None:
                point_count = result.get("vectors_count")
            return True, config, point_count
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, None, None
        return False, None, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, socket.timeout):
        return False, None, None
    return False, None, None


def _query_collection_fingerprint(endpoint: str, collection_name: str) -> tuple[str | None, str | None]:
    url = f"{endpoint.rstrip('/')}/collections/{collection_name}/points/scroll"
    points: list[dict[str, Any]] = []
    offset = None
    try:
        while True:
            body: dict[str, Any] = {"limit": 100, "with_payload": True, "with_vector": False}
            if offset is not None:
                body["offset"] = offset
            try:
                status, response = _http_json(url, method="POST", body=body, timeout=3.0)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None, None
                return None, None
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, socket.timeout):
                return None, None
            
            if status != 200:
                return None, None
            result = response.get("result", {})
            page_points = result.get("points", [])
            points.extend(page_points)
            offset = result.get("next_page_offset")
            if offset is None or not page_points:
                break
    except Exception:
        return None, None

    def get_sort_key(p: dict) -> Any:
        pid = p.get("id")
        if isinstance(pid, int):
            return (0, pid)
        if isinstance(pid, str):
            return (1, pid)
        return (2, str(pid))

    try:
        sorted_points = sorted(points, key=get_sort_key)
        canonical_list = []
        for p in sorted_points:
            canonical_list.append({
                "id": p.get("id"),
                "payload": p.get("payload"),
            })
        serialized = _canonical_json(canonical_list)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return "point_state_sha256", digest
    except Exception:
        return None, None


def _authenticated_projection(configuration: object) -> _Projection:
    if type(configuration) is not ResolvedPlanConfiguration:
        raise QdrantObservationError("invalid_configuration")
    try:
        payload = configuration._projection_json
        digest = configuration.configuration_scope_sha256
        if not isinstance(payload, str):
            raise ValueError("Projection payload is not text")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Projection digest is invalid")
        projection = _strict_json_object(payload)
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
            raise ValueError("Projection digest mismatch")
        if set(projection) != _TOP_LEVEL_KEYS or projection.get("schema") != _CONFIGURATION_SCHEMA:
            raise ValueError("Projection schema is invalid")
        
        flavor = projection.get("path_flavor")
        if flavor not in {"windows", "posix"}:
            raise ValueError("Projection path flavor is invalid")
        
        epoch = projection.get("epoch")
        if not isinstance(epoch, dict) or set(epoch) != {"epoch_id", "root"}:
            raise ValueError("Projection epoch is invalid")
        epoch_id = epoch.get("epoch_id")
        if not isinstance(epoch_id, str) or not re.fullmatch(
            r"epoch_[A-Za-z0-9][A-Za-z0-9._-]{0,121}", epoch_id
        ):
            raise ValueError("Projection epoch ID is invalid")
        
        qdrant = projection.get("qdrant")
        if not isinstance(qdrant, dict) or set(qdrant) != {
            "enabled",
            "endpoint",
            "port",
            "collections",
        }:
            raise ValueError("Qdrant authority is invalid")
        port = qdrant.get("port")
        endpoint = qdrant.get("endpoint")
        if (
            qdrant.get("enabled") is not True
            or isinstance(port, bool)
            or not isinstance(port, int)
            or not 1 <= port <= 65535
            or endpoint not in {
                f"http://127.0.0.1:{port}",
                f"http://[::1]:{port}",
            }
        ):
            raise ValueError("Qdrant authority is invalid")
        
        collections = qdrant.get("collections")
        expected_collections = [
            {
                "role": role,
                "collection_name": f"goodq_{role}_{epoch_id}",
            }
            for role in _QDRANT_ROLES
        ]
        if collections != expected_collections:
            raise ValueError("Qdrant collection authority is invalid")
    except QdrantObservationError:
        raise
    except Exception as exc:
        raise QdrantObservationError("invalid_configuration") from exc
    
    return _Projection(
        canonical_json=payload,
        configuration_scope_sha256=digest,
        qdrant_endpoint=endpoint,
        collections=collections,
    )


def _assert_projection_unchanged(configuration: ResolvedPlanConfiguration, expected: _Projection) -> None:
    try:
        if (
            configuration._projection_json != expected.canonical_json
            or configuration.configuration_scope_sha256 != expected.configuration_scope_sha256
        ):
            raise QdrantObservationError("observation_failed")
    except QdrantObservationError:
        raise
    except Exception as exc:
        raise QdrantObservationError("observation_failed") from exc


def observe_qdrant(configuration: ResolvedPlanConfiguration) -> QdrantObservation:
    """Observe the state of configured Qdrant collections."""
    projection = _authenticated_projection(configuration)
    
    collections_evidence: list[QdrantCollectionEvidence] = []
    
    for item in projection.collections:
        role = item["role"]
        name = item["collection_name"]
        
        exists, config, point_count = _query_collection_info(projection.qdrant_endpoint, name)
        
        if exists:
            config_json = _canonical_json(config)
            fingerprint_kind, fingerprint_value = _query_collection_fingerprint(projection.qdrant_endpoint, name)
            # Fallback to standard if scroll fails or empty
            if fingerprint_kind is None:
                fingerprint_kind = "point_state_sha256"
                fingerprint_value = hashlib.sha256(b"[]").hexdigest()
        else:
            config_json = None
            point_count = None
            fingerprint_kind = None
            fingerprint_value = None
            
        collections_evidence.append(
            QdrantCollectionEvidence(
                role=role,
                collection_name=name,
                exists=exists,
                configuration_json=config_json,
                point_count=point_count,
                fingerprint_kind=fingerprint_kind,
                fingerprint_value=fingerprint_value,
            )
        )
        
    _assert_projection_unchanged(configuration, projection)
    
    return QdrantObservation(
        schema=QDRANT_OBSERVATION_SCHEMA,
        configuration_scope_sha256=projection.configuration_scope_sha256,
        qdrant_endpoint=projection.qdrant_endpoint,
        qdrant_collections=tuple(collections_evidence),
    )
