from __future__ import annotations

import ast
import builtins
import copy
import ctypes
from dataclasses import FrozenInstanceError
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import pickle
import socket
import subprocess
import sys
from types import SimpleNamespace
import unicodedata

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cli" / "clean_memory.py"
EPOCH_ID = "epoch_2026_07_family"
CONFIGURED_PROTECTED_ROLES = (
    "archive_root",
    "control_root",
    "data_root",
    "failed_media",
    "import_media",
    "model_cache",
    "processed_media",
    "processing_media",
    "qdrant_storage",
    "watchdog_state",
)
UNRESOLVED_PROTECTED_ROLES = (
    "backup_root",
    "download_cache",
    "public_checkout",
    "qdrant_service_logs",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
)


def _load_module():
    assert MODULE_PATH.is_file(), "clean-memory configuration projection has not been implemented"
    return importlib.import_module("cli.clean_memory")


def _join(root: str, *parts: str) -> str:
    prefix = root.rstrip("/\\")
    return f"{prefix}/{'/'.join(parts)}"


def _outer_root(data_root: str) -> str:
    normalized = data_root.replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[0]


def _config(
    *,
    epoch_id: str = EPOCH_ID,
    data_root: str = "/authority/GoodQ_Data",
    qdrant_host: str = "http://127.0.0.1:6333",
    qdrant_port: int | None = None,
) -> dict[str, object]:
    outer = _outer_root(data_root)
    epoch_root = _join(data_root, "epochs", epoch_id)
    paths: dict[str, object] = {
        "data_root": data_root,
        "db_dir": epoch_root,
        "db_path": _join(epoch_root, "memory.db"),
        "knowledge_graph_db": _join(epoch_root, "knowledge_graph.db"),
        "faiss_dir": _join(epoch_root, "faiss"),
        "faiss_index_path": _join(epoch_root, "faiss", "text", "faiss_text.index"),
        "faiss_clip_path": _join(epoch_root, "faiss", "clip", "faiss_clip.index"),
        "faiss_dino_path": _join(epoch_root, "faiss", "dino", "faiss_dino.index"),
        "faiss_audio_path": _join(epoch_root, "faiss", f"goodq_audio_{epoch_id}.index"),
        "clip_id_map_db": _join(epoch_root, "faiss", "clip", "clip_id_map.sqlite"),
        "dino_id_map_db": _join(epoch_root, "faiss", "dino", "dino_id_map.sqlite"),
        "clap_id_map_db": _join(epoch_root, "faiss", "audio", "clap_id_map.sqlite"),
        "import_inbox": _join(data_root, "import_inbox"),
        "processing": _join(epoch_root, "processing"),
        "processed": _join(data_root, "processed"),
        "failed": _join(data_root, "failed"),
        "models_cache": _join(outer, "models"),
        "qdrant_storage": _join(outer, "qdrant_storage"),
        "watchdog_state_file": _join(epoch_root, "logs", "watchdog_state.json"),
        "watchdog_lock_file": _join(epoch_root, "logs", "watchdog.lock"),
        "nas_path": _join(data_root, "archive"),
    }
    collections = {
        "clip": f"goodq_clip_{epoch_id}",
        "dino": f"goodq_dino_{epoch_id}",
        "text": f"goodq_text_{epoch_id}",
        "audio": f"goodq_audio_{epoch_id}",
    }
    qdrant: dict[str, object] = {
        "enabled": True,
        "host": qdrant_host,
        "collections": collections,
        "embedding_dims": {"clip": 768, "dino": 1024, "text": 384, "audio": 512},
    }
    if qdrant_port is not None:
        qdrant["port"] = qdrant_port
    return {
        "host": {"data_root": outer, "profile": "GPU_ENHANCED"},
        "paths": paths,
        "qdrant": qdrant,
        "phase6": {
            "clip_collection": collections["clip"],
            "dino_collection": collections["dino"],
        },
        "api": {"key": "SECRET_API_CANARY"},
        "llm": {"token": "SECRET_LLM_CANARY"},
    }


def _resolve(config: dict[str, object], epoch_id: str = EPOCH_ID):
    module = _load_module()
    return module.resolve_plan_configuration(config, requested_epoch_id=epoch_id)


def _canonical_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_module_import_is_pure(tmp_path: Path) -> None:
    script = r"""
import importlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
config = json.loads(sys.argv[2])
epoch_id = sys.argv[3]
before_env = dict(os.environ)
before_path = list(sys.path)
before_modules = set(sys.modules)
real_environ = os.environ
real_getenv = os.getenv

def forbidden_environment_access(*_args, **_kwargs):
    raise AssertionError("cli.clean_memory read environment state during import")

class ReadFailingEnvironment:
    __getitem__ = forbidden_environment_access
    __setitem__ = forbidden_environment_access
    __delitem__ = forbidden_environment_access
    __iter__ = forbidden_environment_access
    __len__ = forbidden_environment_access
    __contains__ = forbidden_environment_access
    get = forbidden_environment_access
    items = forbidden_environment_access
    keys = forbidden_environment_access
    values = forbidden_environment_access

os.environ = ReadFailingEnvironment()
os.getenv = forbidden_environment_access
try:
    module = importlib.import_module("cli.clean_memory")
    module.resolve_plan_configuration(config, requested_epoch_id=epoch_id)
finally:
    os.environ = real_environ
    os.getenv = real_getenv
new_modules = set(sys.modules) - before_modules
forbidden = {
    "steps.common.config_loader",
    "steps.common.qdrant_client",
    "api.utils.action_jobs",
    "agents.mini_agent_client",
    "requests",
    "socket",
    "subprocess",
}
print(json.dumps({
    "environment_unchanged": dict(os.environ) == before_env,
    "sys_path_unchanged": list(sys.path) == before_path,
    "forbidden_imports": sorted(new_modules & forbidden),
    "tree": sorted(path.relative_to(root).as_posix() for path in root.rglob("*")),
}))
"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), _canonical_text(_config()), EPOCH_ID],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "environment_unchanged": True,
        "sys_path_unchanged": True,
        "forbidden_imports": [],
        "tree": [],
    }


def test_public_api_surface_is_explicit_and_minimal() -> None:
    module = _load_module()
    assert module.__all__ == (
        "CONFIGURATION_SCHEMA",
        "ResolvedPlanConfiguration",
        "resolve_plan_configuration",
    )
    assert not hasattr(module, "PROTECTED_BOUNDARY_ROLES")


def test_private_authenticated_composition_surface_and_closed_error_contract() -> None:
    module = _load_module()

    assert module.__all__ == (
        "CONFIGURATION_SCHEMA",
        "ResolvedPlanConfiguration",
        "resolve_plan_configuration",
    )
    assert "_compose_authenticated_protected_membership" not in module.__all__
    helper = module._compose_authenticated_protected_membership
    error_type = module._ProtectedMembershipCompositionError
    signature = inspect.signature(helper)
    assert tuple(signature.parameters) == ("configuration",)
    assert signature.parameters["configuration"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert str(signature.return_annotation) == "tuple[ProtectedBoundaryEvidence, ...]"

    messages = {
        "invalid_configuration": (
            "Clean-memory authenticated composition configuration is invalid"
        ),
        "invalid_protected_membership": (
            "Clean-memory authenticated protected membership is invalid"
        ),
        "pin_member_overlap": (
            "Clean-memory protected membership overlaps the external pin chain"
        ),
        "observation_raced": (
            "Clean-memory authenticated protected authority changed during composition"
        ),
        "composition_failed": (
            "Clean-memory authenticated protected-membership composition failed"
        ),
    }
    for code, message in messages.items():
        error = error_type(code)
        assert error.code == code
        assert str(error) == message
        assert error.__dict__ == {}
        with pytest.raises(AttributeError):
            error.code = "composition_failed"
        with pytest.raises(AttributeError):
            del error.code
        with pytest.raises(AttributeError):
            error._code = "composition_failed"
        with pytest.raises(AttributeError):
            del error._code
        assert error.code == code
        assert str(error) == message
        assert error.args == (message,)
        with pytest.raises(TypeError):
            error.add_note("SECRET_PATH_CANARY")
        with pytest.raises(TypeError):
            copy.copy(error)
        with pytest.raises(TypeError):
            copy.deepcopy(error)
        with pytest.raises(TypeError):
            pickle.dumps(error)
    with pytest.raises(ValueError):
        error_type("unknown")


def test_module_and_resolver_have_no_passive_or_mutating_capabilities() -> None:
    script = r"""
import collections.abc
import builtins
import dataclasses
import datetime
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import sys
import types
import typing
import unicodedata
import urllib.parse
from pathlib import Path, PurePosixPath

source_path = Path(sys.argv[1])
source = source_path.read_text(encoding="utf-8")
code = compile(source, str(source_path), "exec")
dependency_source_path = Path(sys.argv[2])
dependency_source = dependency_source_path.read_text(encoding="utf-8")
dependency_code = compile(dependency_source, str(dependency_source_path), "exec")
config = json.loads(sys.argv[3])
epoch_id = sys.argv[4]

forbidden_events = {
    "open",
    "os.access",
    "os.chdir",
    "os.chmod",
    "os.chown",
    "os.link",
    "os.listdir",
    "os.mkdir",
    "os.putenv",
    "os.remove",
    "os.rename",
    "os.rmdir",
    "os.scandir",
    "os.symlink",
    "os.stat",
    "os.lstat",
    "os.system",
    "os.truncate",
    "os.unsetenv",
    "os.utime",
    "os.posix_spawn",
    "os.spawn",
    "subprocess.Popen",
    "socket.__new__",
    "socket.connect",
}

def audit(event, _args):
    if event in forbidden_events:
        raise AssertionError(f"forbidden capability used: {event}")

def forbidden_environment_access(*_args, **_kwargs):
    raise AssertionError("environment state was read or changed")

def forbidden_capability(*_args, **_kwargs):
    raise AssertionError("filesystem, process, or network capability was used")

class ReadFailingEnvironment:
    __getitem__ = forbidden_environment_access
    __setitem__ = forbidden_environment_access
    __delitem__ = forbidden_environment_access
    __iter__ = forbidden_environment_access
    __len__ = forbidden_environment_access
    __contains__ = forbidden_environment_access
    get = forbidden_environment_access
    items = forbidden_environment_access
    keys = forbidden_environment_access
    values = forbidden_environment_access

os.environ = ReadFailingEnvironment()
os.getenv = forbidden_environment_access
builtins.open = forbidden_capability
for name in (
    "access",
    "chdir",
    "getcwd",
    "getcwdb",
    "lstat",
    "listdir",
    "link",
    "makedirs",
    "mkdir",
    "popen",
    "putenv",
    "readlink",
    "remove",
    "removedirs",
    "rename",
    "renames",
    "replace",
    "rmdir",
    "scandir",
    "stat",
    "startfile",
    "symlink",
    "system",
    "truncate",
    "unlink",
    "unsetenv",
    "utime",
    "walk",
):
    if hasattr(os, name):
        setattr(os, name, forbidden_capability)
for name in (
    "absolute",
    "cwd",
    "exists",
    "glob",
    "hardlink_to",
    "home",
    "is_dir",
    "is_file",
    "is_symlink",
    "iterdir",
    "lstat",
    "mkdir",
    "open",
    "read_bytes",
    "read_text",
    "readlink",
    "rename",
    "replace",
    "resolve",
    "rglob",
    "rmdir",
    "stat",
    "symlink_to",
    "touch",
    "unlink",
    "write_bytes",
    "write_text",
):
    if hasattr(Path, name):
        setattr(Path, name, forbidden_capability)
for name in ("Popen", "call", "check_call", "check_output", "run"):
    if hasattr(subprocess, name):
        setattr(subprocess, name, forbidden_capability)
socket.socket = forbidden_capability
sys.addaudithook(audit)

for probe, arguments in (
    (os.access, (str(source_path), os.F_OK)),
    (os.mkdir, (str(source_path) + ".forbidden",)),
):
    try:
        probe(*arguments)
    except AssertionError:
        pass
    else:
        raise AssertionError("negative-capability guard did not fire")

for package_name in ("steps", "steps.common", "cli"):
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package

dependency_module = types.ModuleType("steps.common.clean_memory")
dependency_module.__file__ = str(dependency_source_path)
dependency_module.__package__ = "steps.common"
sys.modules["steps.common.clean_memory"] = dependency_module
exec(dependency_code, dependency_module.__dict__)

module = types.ModuleType("cli.clean_memory")
module.__file__ = str(source_path)
module.__package__ = "cli"
sys.modules["cli.clean_memory"] = module
exec(code, module.__dict__)
result = module.resolve_plan_configuration(config, requested_epoch_id=epoch_id)
assert result.projection["epoch"]["epoch_id"] == epoch_id
print("capability-free")
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(MODULE_PATH),
            str(REPO_ROOT / "steps" / "common" / "clean_memory.py"),
            _canonical_text(_config()),
            EPOCH_ID,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    assert completed.stdout.strip() == "capability-free"


def test_projection_is_exact_secret_free_and_immutable() -> None:
    module = _load_module()
    config = _config()
    result = module.resolve_plan_configuration(config, requested_epoch_id=EPOCH_ID)
    projection = result.projection

    assert set(projection) == {
        "schema",
        "path_flavor",
        "epoch",
        "logical_paths",
        "declared_faiss_paths",
        "qdrant",
        "configured_protected_paths",
        "unresolved_protected_roles",
    }
    assert projection["schema"] == "goodq.clean-memory-configuration.v1"
    assert projection["path_flavor"] == "posix"
    assert projection["epoch"] == {
        "epoch_id": EPOCH_ID,
        "root": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}",
    }
    assert projection["logical_paths"] == {
        "storage_root": "/authority",
        "data_root": "/authority/GoodQ_Data",
        "memory_database": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/memory.db",
        "memory_database_wal": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/memory.db-wal",
        "memory_database_shm": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/memory.db-shm",
        "knowledge_graph_database": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/knowledge_graph.db",
        "knowledge_graph_database_wal": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/knowledge_graph.db-wal",
        "knowledge_graph_database_shm": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/knowledge_graph.db-shm",
        "faiss_root": f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/faiss",
        "candidate_evidence_root": "/authority/GoodQ_Data/control/clean_memory",
    }
    assert projection["qdrant"] == {
        "enabled": True,
        "endpoint": "http://127.0.0.1:6333",
        "port": 6333,
        "collections": [
            {"role": "text", "collection_name": f"goodq_text_{EPOCH_ID}"},
            {"role": "clip", "collection_name": f"goodq_clip_{EPOCH_ID}"},
            {"role": "dino", "collection_name": f"goodq_dino_{EPOCH_ID}"},
            {"role": "audio", "collection_name": f"goodq_audio_{EPOCH_ID}"},
        ],
    }
    assert tuple(item["role"] for item in projection["configured_protected_paths"]) == (
        CONFIGURED_PROTECTED_ROLES
    )
    assert tuple(projection["unresolved_protected_roles"]) == UNRESOLVED_PROTECTED_ROLES
    rendered = _canonical_text(projection)
    assert result.configuration_scope_sha256 == hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert "SECRET_API_CANARY" not in rendered
    assert "SECRET_LLM_CANARY" not in rendered

    projection["epoch"]["epoch_id"] = "tampered"
    assert result.projection["epoch"]["epoch_id"] == EPOCH_ID
    with pytest.raises(FrozenInstanceError):
        result.configuration_scope_sha256 = "0" * 64


def test_projection_does_not_mutate_caller_and_is_order_stable() -> None:
    config = _config()
    before = copy.deepcopy(config)
    result = _resolve(config)
    reordered = {
        "llm": copy.deepcopy(config["llm"]),
        "phase6": dict(reversed(list(config["phase6"].items()))),
        "qdrant": dict(reversed(list(config["qdrant"].items()))),
        "paths": dict(reversed(list(config["paths"].items()))),
        "host": copy.deepcopy(config["host"]),
        "api": copy.deepcopy(config["api"]),
    }
    other = _resolve(reordered)

    assert config == before
    assert result.projection == other.projection
    assert result.configuration_scope_sha256 == other.configuration_scope_sha256


def test_unrelated_and_arbitrary_path_injection_cannot_gain_authority() -> None:
    base = _config()
    injected = copy.deepcopy(base)
    injected["clean_memory"] = {
        "evidence_root": "/outside/SECRET_EVIDENCE_CANARY",
        "protected_paths": {"repository": "/outside/SECRET_REPOSITORY_CANARY"},
        "delete_paths": ["/outside/SECRET_DELETE_CANARY"],
    }
    injected["unrelated"] = {"password": "SECRET_PASSWORD_CANARY"}

    expected = _resolve(base)
    actual = _resolve(injected)
    rendered = _canonical_text(actual.projection)

    assert actual.configuration_scope_sha256 == expected.configuration_scope_sha256
    assert actual.projection == expected.projection
    assert "SECRET_" not in rendered
    assert "repository" in actual.projection["unresolved_protected_roles"]


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("host", "profile", "BASELINE"),
        ("paths", "log_dir", "/outside/unrelated-logs"),
        ("qdrant", "embedding_dims", {"text": 9999}),
        ("phase6", "optional_threshold", 0.999),
    ],
)
def test_nested_unrelated_settings_do_not_change_projection_or_digest(
    section: str,
    key: str,
    value: object,
) -> None:
    base = _config()
    changed = copy.deepcopy(base)
    changed[section][key] = value

    expected = _resolve(base)
    actual = _resolve(changed)

    assert actual.projection == expected.projection
    assert actual.configuration_scope_sha256 == expected.configuration_scope_sha256


def test_path_section_rejects_non_text_keys_cleanly() -> None:
    config = _config()
    config["paths"][1] = "/outside/not-authority"
    with pytest.raises(ValueError, match="paths keys"):
        _resolve(config)


def test_absent_and_matching_qdrant_port_have_same_effective_authority() -> None:
    without_override = _resolve(_config())
    with_override = _resolve(_config(qdrant_port=6333))

    assert without_override.projection == with_override.projection
    assert without_override.configuration_scope_sha256 == with_override.configuration_scope_sha256


def test_absent_and_explicit_null_qdrant_port_have_same_effective_authority() -> None:
    without_override = _config()
    explicit_null = _config()
    explicit_null["qdrant"]["port"] = None

    first = _resolve(without_override)
    second = _resolve(explicit_null)

    assert first.projection == second.projection
    assert first.configuration_scope_sha256 == second.configuration_scope_sha256


def test_every_valid_cleanup_authority_change_changes_digest() -> None:
    first = _resolve(_config())
    second_epoch = "epoch_2026_07_family_b"
    second = _resolve(_config(epoch_id=second_epoch), second_epoch)
    alternate_endpoint = _resolve(
        _config(qdrant_host="http://127.0.0.1:6334", qdrant_port=6334)
    )

    assert len(
        {
            first.configuration_scope_sha256,
            second.configuration_scope_sha256,
            alternate_endpoint.configuration_scope_sha256,
        }
    ) == 3


@pytest.mark.parametrize(
    "epoch_id",
    ["", " ", "default", ".", "..", "epoch/escape", r"epoch\\escape", "epoch_${VAR}"],
)
def test_requested_epoch_must_be_one_exact_epoch_identifier(epoch_id: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        _resolve(_config(), epoch_id)


def test_requested_epoch_must_equal_configured_epoch() -> None:
    with pytest.raises(ValueError, match="configured epoch"):
        _resolve(_config(), f"{EPOCH_ID}_other")


@pytest.mark.parametrize("config", [None, [], "config", 1])
def test_projection_requires_a_mapping(config: object) -> None:
    module = _load_module()
    with pytest.raises(TypeError):
        module.resolve_plan_configuration(config, requested_epoch_id=EPOCH_ID)


@pytest.mark.parametrize("section", ["host", "paths", "qdrant", "phase6"])
def test_projection_requires_every_authority_section_as_a_mapping(section: str) -> None:
    config = _config()
    config[section] = None
    with pytest.raises(ValueError, match=section):
        _resolve(config)


@pytest.mark.parametrize(
    "section,key",
    [
        ("host", "data_root"),
        ("paths", "data_root"),
        ("paths", "db_dir"),
        ("paths", "db_path"),
        ("paths", "knowledge_graph_db"),
        ("paths", "faiss_dir"),
        ("paths", "import_inbox"),
        ("paths", "processing"),
        ("paths", "processed"),
        ("paths", "failed"),
        ("paths", "models_cache"),
        ("paths", "qdrant_storage"),
        ("paths", "watchdog_state_file"),
        ("paths", "watchdog_lock_file"),
        ("paths", "nas_path"),
        ("qdrant", "enabled"),
        ("qdrant", "host"),
        ("qdrant", "collections"),
        ("phase6", "clip_collection"),
        ("phase6", "dino_collection"),
    ],
)
def test_projection_rejects_missing_required_authority(section: str, key: str) -> None:
    config = _config()
    del config[section][key]
    with pytest.raises(ValueError, match=key):
        _resolve(config)


@pytest.mark.parametrize(
    "key,replacement",
    [
        ("db_path", f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/alternate.db"),
        (
            "knowledge_graph_db",
            f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/alternate-knowledge.db",
        ),
        ("faiss_dir", f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/vectors"),
        ("import_inbox", "/authority/GoodQ_Data/inbox"),
        ("processed", "/authority/GoodQ_Data/completed"),
        ("failed", "/authority/GoodQ_Data/errors"),
    ],
)
def test_projection_rejects_noncanonical_topology(key: str, replacement: str) -> None:
    config = _config()
    config["paths"][key] = replacement
    with pytest.raises(ValueError, match=key):
        _resolve(config)


def test_supported_protected_path_overrides_are_bound_not_rejected() -> None:
    base = _resolve(_config())
    config = _config()
    config["paths"].update(
        {
            "processing": "/scratch/goodq-processing",
            "models_cache": "/models/goodq",
            "qdrant_storage": "/vectors/qdrant",
            "watchdog_state_file": "/runtime/goodq/watchdog_state.json",
            "watchdog_lock_file": "/runtime/goodq/watchdog.lock",
            "nas_path": "/archive/goodq",
        }
    )

    result = _resolve(config)
    protected = {
        item["role"]: item["paths"]
        for item in result.projection["configured_protected_paths"]
    }

    assert protected["processing_media"] == ["/scratch/goodq-processing"]
    assert protected["model_cache"] == ["/models/goodq"]
    assert protected["qdrant_storage"] == ["/vectors/qdrant"]
    assert protected["watchdog_state"] == [
        "/runtime/goodq/watchdog.lock",
        "/runtime/goodq/watchdog_state.json",
    ]
    assert protected["archive_root"] == ["/archive/goodq"]
    assert result.configuration_scope_sha256 != base.configuration_scope_sha256


@pytest.mark.parametrize(
    "key,replacement",
    [
        ("processing", f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/faiss/work"),
        ("models_cache", f"/authority/GoodQ_Data/epochs/{EPOCH_ID}"),
        ("qdrant_storage", f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/memory.db"),
        ("nas_path", "/authority/GoodQ_Data/control/clean_memory/archive"),
        ("watchdog_state_file", f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/faiss/state.json"),
        ("watchdog_lock_file", f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/faiss/watchdog.lock"),
    ],
)
def test_protected_path_override_cannot_overlap_cleanup_or_evidence_scope(
    key: str,
    replacement: str,
) -> None:
    config = _config()
    config["paths"][key] = replacement
    with pytest.raises(ValueError, match=key):
        _resolve(config)


def test_distinct_protected_roles_cannot_resolve_to_the_same_path() -> None:
    config = _config()
    config["paths"]["models_cache"] = config["paths"]["qdrant_storage"]
    with pytest.raises(ValueError, match="models_cache|qdrant_storage"):
        _resolve(config)


def test_watchdog_state_and_lock_must_resolve_to_distinct_paths() -> None:
    config = _config()
    config["paths"]["watchdog_lock_file"] = config["paths"]["watchdog_state_file"]
    with pytest.raises(ValueError, match="watchdog_lock_file|watchdog_state_file"):
        _resolve(config)


def test_outer_storage_root_must_match_data_and_external_roots() -> None:
    config = _config()
    config["host"]["data_root"] = "/other-authority"
    with pytest.raises(ValueError, match="host.data_root"):
        _resolve(config)


@pytest.mark.parametrize(
    "bad_root",
    [
        "relative/GoodQ_Data",
        "/",
        "/authority/./GoodQ_Data",
        "/authority/../GoodQ_Data",
        "/authority//GoodQ_Data",
        "/authority/GoodQ_Data/",
        " /authority/GoodQ_Data",
        "/authority/${GOODQ_DATA_ROOT}/GoodQ_Data",
        "//server/share/GoodQ_Data",
        "C:relative/GoodQ_Data",
        "C:/",
        r"\\?\C:\authority\GoodQ_Data",
        "C:/authority/NUL/GoodQ_Data",
        "C:/authority/bad?/GoodQ_Data",
        "C:/authority/GoodQ_Data.",
        "/authority/Cafe\u0301/GoodQ_Data",
    ],
)
def test_data_root_rejects_lexical_ambiguity(bad_root: str) -> None:
    config = _config()
    config["paths"]["data_root"] = bad_root
    with pytest.raises(ValueError, match="paths.data_root"):
        _resolve(config)


def test_windows_mixed_separators_are_normalized_without_filesystem_access() -> None:
    config = _config(data_root=r"r:\Authority/GoodQ_Data")
    result = _resolve(config)
    projection = result.projection

    assert projection["path_flavor"] == "windows"
    assert projection["logical_paths"]["storage_root"] == "R:/Authority"
    assert projection["logical_paths"]["data_root"] == "R:/Authority/GoodQ_Data"
    assert projection["epoch"]["root"] == f"R:/Authority/GoodQ_Data/epochs/{EPOCH_ID}"


def test_windows_case_alias_in_configured_child_is_rejected() -> None:
    config = _config(data_root=r"R:\Authority/GoodQ_Data")
    config["paths"]["db_dir"] = f"R:/authority/GoodQ_Data/epochs/{EPOCH_ID}"
    with pytest.raises(ValueError, match="paths.db_dir"):
        _resolve(config)


@pytest.mark.parametrize("enabled", [False, None, 0, 1, "true"])
def test_qdrant_must_be_explicitly_enabled(enabled: object) -> None:
    config = _config()
    config["qdrant"]["enabled"] = enabled
    with pytest.raises(ValueError, match="qdrant.enabled"):
        _resolve(config)


@pytest.mark.parametrize("port", [0, 65536, True, "6333", 6334])
def test_qdrant_port_must_be_an_exact_integer_match(port: object) -> None:
    config = _config()
    config["qdrant"]["port"] = port
    with pytest.raises(ValueError, match="qdrant.port"):
        _resolve(config)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost:6333",
        "https://127.0.0.1:6333",
        "http://user@127.0.0.1:6333",
        "http://127.0.0.1:6333/",
        "http://127.0.0.1:6333/path",
        "http://127.0.0.1:6333?query=1",
        "http://127.0.0.1:6333#fragment",
        "http://127.0.0.1",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
        "http://127.0.0.2:6333",
        "HTTP://127.0.0.1:6333",
    ],
)
def test_qdrant_endpoint_must_be_canonical_loopback_http(endpoint: str) -> None:
    with pytest.raises(ValueError, match="qdrant.host"):
        _resolve(_config(qdrant_host=endpoint))


def test_qdrant_ipv6_loopback_endpoint_is_canonical() -> None:
    result = _resolve(_config(qdrant_host="http://[::1]:6333", qdrant_port=6333))
    assert result.projection["qdrant"]["endpoint"] == "http://[::1]:6333"


@pytest.mark.parametrize("role", ["text", "clip", "dino", "audio"])
def test_collection_name_must_match_exact_role_and_epoch(role: str) -> None:
    config = _config()
    config["qdrant"]["collections"][role] = f"goodq_{role}_{EPOCH_ID}_other"
    with pytest.raises(ValueError, match="qdrant.collections"):
        _resolve(config)


def test_collection_mapping_rejects_missing_extra_and_duplicate_names() -> None:
    missing = _config()
    del missing["qdrant"]["collections"]["audio"]
    with pytest.raises(ValueError, match="qdrant.collections"):
        _resolve(missing)

    extra = _config()
    extra["qdrant"]["collections"]["extra"] = f"goodq_extra_{EPOCH_ID}"
    with pytest.raises(ValueError, match="qdrant.collections"):
        _resolve(extra)

    duplicate = _config()
    duplicate["qdrant"]["collections"]["audio"] = duplicate["qdrant"]["collections"]["text"]
    with pytest.raises(ValueError, match="qdrant.collections"):
        _resolve(duplicate)


def test_phase6_visual_collection_authority_must_match_qdrant() -> None:
    config = _config()
    config["phase6"]["clip_collection"] = f"goodq_clip_{EPOCH_ID}_other"
    with pytest.raises(ValueError, match="phase6.clip_collection"):
        _resolve(config)

    config = _config()
    config["phase6"]["dino_collection"] = f"goodq_dino_{EPOCH_ID}_other"
    with pytest.raises(ValueError, match="phase6.dino_collection"):
        _resolve(config)


@pytest.mark.parametrize(
    "key",
    [
        "faiss_index_path",
        "faiss_clip_path",
        "faiss_dino_path",
        "faiss_audio_path",
        "clip_id_map_db",
        "dino_id_map_db",
        "clap_id_map_db",
    ],
)
def test_declared_faiss_members_must_remain_inside_exact_faiss_root(key: str) -> None:
    config = _config()
    config["paths"][key] = f"/outside/{key}"
    with pytest.raises(ValueError, match=key):
        _resolve(config)


def test_declared_faiss_members_are_bound_deterministically() -> None:
    result = _resolve(_config())
    members = result.projection["declared_faiss_paths"]
    assert list(members) == sorted(members)
    assert all(path.startswith(f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/faiss/") for path in members.values())


@pytest.mark.parametrize(
    "key",
    [
        "faiss_future_path",
        "future_faiss_path",
        "faiss_future_index",
        "clip_index_path",
        "future_id_map_db",
    ],
)
def test_unknown_faiss_path_authority_fails_closed(key: str) -> None:
    config = _config()
    config["paths"][key] = f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/faiss/{key}"
    with pytest.raises(ValueError, match=key):
        _resolve(config)


@pytest.mark.parametrize(
    "key,replacement_key",
    [
        ("faiss_clip_path", "faiss_index_path"),
        ("faiss_clip_path", "faiss_dir"),
    ],
)
def test_declared_faiss_members_cannot_alias_or_contain_each_other(
    key: str,
    replacement_key: str,
) -> None:
    config = _config()
    replacement = config["paths"][replacement_key]
    if replacement_key == "faiss_dir":
        replacement = f"{replacement}/clip"
        config["paths"]["faiss_dino_path"] = f"{replacement}/nested.index"
    config["paths"][key] = replacement
    with pytest.raises(ValueError, match=key):
        _resolve(config)


def test_configured_protected_paths_are_exact_and_watchdog_is_a_pair() -> None:
    projection = _resolve(_config()).projection
    configured = {item["role"]: item["paths"] for item in projection["configured_protected_paths"]}

    assert configured == {
        "archive_root": ["/authority/GoodQ_Data/archive"],
        "control_root": ["/authority/GoodQ_Data/control"],
        "data_root": ["/authority/GoodQ_Data"],
        "failed_media": ["/authority/GoodQ_Data/failed"],
        "import_media": ["/authority/GoodQ_Data/import_inbox"],
        "model_cache": ["/authority/models"],
        "processed_media": ["/authority/GoodQ_Data/processed"],
        "processing_media": [f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/processing"],
        "qdrant_storage": ["/authority/qdrant_storage"],
        "watchdog_state": [
            f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/logs/watchdog.lock",
            f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/logs/watchdog_state.json",
        ],
    }


def test_projection_performs_no_filesystem_network_process_or_directory_operation(monkeypatch) -> None:
    module = _load_module()
    config = _config(data_root="/entirely/nonexistent/GoodQ_Data")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("projection attempted an observation or mutation")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "stat", forbidden)
    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "exists", forbidden)
    monkeypatch.setattr(Path, "is_file", forbidden)
    monkeypatch.setattr(Path, "is_dir", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    result = module.resolve_plan_configuration(config, requested_epoch_id=EPOCH_ID)
    assert result.projection["logical_paths"]["data_root"] == "/entirely/nonexistent/GoodQ_Data"


def _composition_identity(number: int, *, object_kind: str) -> dict[str, str]:
    return {
        "file_id": f"{number:016x}",
        "file_id_kind": "ntfs_file_index_64",
        "object_kind": object_kind,
        "schema": "goodq.windows-file-identity.v1",
        "volume_serial": "0123456789abcdef",
    }


def _composition_manifest_bytes(*, root: str = "S:/Protected") -> bytes:
    return _canonical_text(
        {
            "roles": [
                {
                    "members": [
                        {
                            "absolute_path": f"{root}/{role}",
                            "member_id": "primary",
                            "object_kind": "directory",
                            "presence": "required",
                        }
                    ],
                    "role": role,
                }
                for role in UNRESOLVED_PROTECTED_ROLES
            ],
            "schema": "goodq.clean-memory-protected-authority.v1",
        }
    ).encode("utf-8")


def _composition_inputs(
    *,
    config: dict[str, object] | None = None,
    manifest_root: str = "S:/Protected",
) -> dict[str, object]:
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    membership_module = importlib.import_module("cli.clean_memory_protected_membership")
    common_module = importlib.import_module("steps.common.clean_memory")
    configuration = _resolve(
        config or _config(data_root="R:/Authority/GoodQ_Data")
    )
    manifest_bytes = _composition_manifest_bytes(root=manifest_root)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    pin = external_module.ExternalPinEvidence._from_projection(
        {
            "anchor_identity": _composition_identity(101, object_kind="directory"),
            "dedicated_directory_identities": [
                _composition_identity(number, object_kind="directory")
                for number in range(102, 105)
            ],
            "enrolled_reader_identity_sha256": "1" * 64,
            "manifest_sha256": manifest_sha256,
            "pin_file_identity": _composition_identity(
                105, object_kind="regular_file"
            ),
            "platform": "windows",
            "schema": "goodq.clean-memory-external-pin-evidence.v1",
            "security_policy_sha256": "2" * 64,
            "source_id": "goodq.clean-memory-protected-authority-pin.primary.v1",
            "source_schema": "goodq.clean-memory-external-pin-source.v1",
        }
    )
    manifest = manifest_module.ProtectedManifestEvidence._from_projection(
        manifest_bytes,
        {
            "anchor_identity": _composition_identity(201, object_kind="directory"),
            "configuration_scope_sha256": configuration.configuration_scope_sha256,
            "external_pin_evidence_sha256": pin.external_pin_evidence_sha256,
            "manifest_file_identity": _composition_identity(
                206, object_kind="regular_file"
            ),
            "manifest_sha256": manifest_sha256,
            "platform": "windows",
            "route_directory_identities": [
                _composition_identity(number, object_kind="directory")
                for number in range(202, 206)
            ],
            "schema": "goodq.clean-memory-protected-manifest-evidence.v1",
            "security_policy_sha256": "3" * 64,
        },
        expected_route_count=4,
    )
    membership = membership_module.project_protected_membership(
        configuration,
        manifest_bytes=manifest_bytes,
    )
    membership_digest = membership.protected_membership_scope_sha256
    boundary_id = 300
    boundaries_list = []
    for role_record in membership.projection["protected_roles"]:
        observed_members = []
        for selected in role_record["members"]:
            boundary_id += 1
            parent_identity = _composition_identity(
                boundary_id,
                object_kind="directory",
            )
            boundary_id += 1
            object_identity = _composition_identity(
                boundary_id,
                object_kind=selected["object_kind"],
            )
            child_name = selected["absolute_path"].rsplit("/", 1)[-1]
            child_digest = hashlib.sha256(
                unicodedata.normalize("NFC", child_name)
                .casefold()
                .encode("utf-8")
            ).hexdigest()
            observed_members.append(
                {
                    "absence": None,
                    "child_comparison_sha256": child_digest,
                    "logical_id": (
                        f"protected:{role_record['role']}:{selected['member_id']}"
                    ),
                    "member_id": selected["member_id"],
                    "object_identity": object_identity,
                    "object_kind": selected["object_kind"],
                    "parent_identity": parent_identity,
                    "state": "present",
                }
            )
        role = role_record["role"]
        boundaries_list.append(
            common_module.ProtectedBoundaryEvidence(
                role=role,
                logical_id=f"protected:{role}",
                identity_json=_canonical_text(
                    {
                        "logical_id": f"protected:{role}",
                        "members": observed_members,
                        "protected_membership_scope_sha256": membership_digest,
                        "role": role,
                        "schema": (
                            "goodq.clean-memory-protected-boundary-identity.v1"
                        ),
                    }
                ),
            )
        )
    boundaries = tuple(boundaries_list)
    return {
        "configuration": configuration,
        "manifest_bytes": manifest_bytes,
        "pin": pin,
        "manifest": manifest,
        "membership": membership,
        "boundaries": boundaries,
    }


def _composition_location(
    *,
    drive_root: str = "C:\\",
    program_data_components: tuple[str, ...] = ("ProgramData",),
):
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    instance = object.__new__(locator_module.CleanMemoryWindowsProgramDataLocation)
    object.__setattr__(instance, "_drive_root", drive_root)
    object.__setattr__(instance, "_program_data_components", program_data_components)
    object.__setattr__(
        instance,
        "_fixed_directory_components",
        ("GoodQ", "authority", "clean-memory"),
    )
    object.__setattr__(instance, "_pin_name", "protected-boundaries.sha256")
    return instance


def _composition_equal_value_subclass(
    value: object,
    fields: tuple[str, ...],
) -> object:
    subclass = type(
        f"EqualValue{type(value).__name__}",
        (type(value),),
        {},
    )
    instance = object.__new__(subclass)
    for field in fields:
        object.__setattr__(
            instance,
            field,
            object.__getattribute__(value, field),
        )
    return instance


def _install_composition_world(
    monkeypatch: pytest.MonkeyPatch,
    inputs: dict[str, object],
    *,
    locations: tuple[object, ...] | None = None,
) -> list[object]:
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    membership_module = importlib.import_module("cli.clean_memory_protected_membership")
    boundary_module = importlib.import_module("cli.clean_memory_protected_boundary")
    events: list[object] = []
    shell32 = SimpleNamespace(name="shell32")
    ole32 = SimpleNamespace(name="ole32")
    locator = object.__new__(locator_module.CleanMemoryWindowsProgramDataLocator)
    object.__setattr__(locator, "_known_folder", object())
    object.__setattr__(locator, "_free", object())
    remaining = iter(locations or (_composition_location(),) * 4)
    resolve_count = 0

    def verify_abi() -> None:
        events.append("abi")

    def load_library(name: str, *, use_last_error: bool):
        events.append(("load", name, use_last_error))
        return {"shell32": shell32, "ole32": ole32}[name]

    def bind_locator(*, shell32: object, ole32: object):
        events.append(("bind", shell32 is globals_shell32, ole32 is globals_ole32))
        return locator

    def resolve_location(_self):
        nonlocal resolve_count
        resolve_count += 1
        events.append(("resolve", resolve_count))
        return next(remaining)

    def read_pin():
        events.append("pin")
        return inputs["pin"]

    def read_manifest(configuration, *, external_pin_evidence):
        assert configuration is inputs["configuration"]
        assert external_pin_evidence is inputs["pin"]
        events.append("manifest")
        return inputs["manifest"]

    def project_membership(configuration, *, manifest_bytes):
        assert configuration is inputs["configuration"]
        assert manifest_bytes is inputs["manifest_bytes"]
        events.append("membership")
        return inputs["membership"]

    def observe_boundaries(membership, *, external_pin_evidence):
        assert membership is inputs["membership"]
        assert external_pin_evidence is inputs["pin"]
        events.append("observer")
        return inputs["boundaries"]

    globals_shell32 = shell32
    globals_ole32 = ole32
    monkeypatch.setattr(
        locator_module,
        "verify_clean_memory_windows_program_data_locator_abi",
        verify_abi,
    )
    monkeypatch.setattr(
        locator_module,
        "bind_clean_memory_windows_program_data_locator",
        bind_locator,
    )
    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        resolve_location,
    )
    monkeypatch.setattr(ctypes, "WinDLL", load_library)
    monkeypatch.setattr(external_module, "read_external_pin", read_pin)
    monkeypatch.setattr(manifest_module, "read_protected_manifest", read_manifest)
    monkeypatch.setattr(
        membership_module,
        "project_protected_membership",
        project_membership,
    )
    monkeypatch.setattr(
        boundary_module,
        "observe_protected_boundaries",
        observe_boundaries,
    )
    return events


def test_authenticated_composition_calls_exact_public_chain_and_returns_same_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)

    result = module._compose_authenticated_protected_membership(
        inputs["configuration"]
    )

    assert result is inputs["boundaries"]
    assert events == [
        "abi",
        ("load", "shell32", True),
        ("load", "ole32", True),
        ("bind", True, True),
        ("resolve", 1),
        "pin",
        ("resolve", 2),
        "manifest",
        "membership",
        ("resolve", 3),
        "observer",
        ("resolve", 4),
    ]


def _assert_composition_code(module, code: str, call) -> None:
    with pytest.raises(module._ProtectedMembershipCompositionError) as exc_info:
        call()
    assert exc_info.value.code == code
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


@pytest.mark.parametrize(
    "case",
    [
        "posix",
        "forged_windows_topology",
        "failed_media",
        "import_media",
        "processed_media",
    ],
)
def test_composition_rejects_invalid_configuration_before_capability_import(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    module = _load_module()
    if case == "posix":
        configuration = _resolve(_config())
    elif case == "forged_windows_topology":
        valid = _resolve(_config(data_root="R:/Authority/GoodQ_Data"))
        projection = valid.projection
        projection["logical_paths"]["data_root"] = "R:/Forged/GoodQ_Data"
        configuration = module.ResolvedPlanConfiguration._from_projection(projection)
    else:
        valid = _resolve(_config(data_root="R:/Authority/GoodQ_Data"))
        projection = valid.projection
        record = next(
            item
            for item in projection["configured_protected_paths"]
            if item["role"] == case
        )
        record["paths"] = [f"T:/ForgedAuthority/{case}"]
        configuration = module.ResolvedPlanConfiguration._from_projection(projection)
    real_import = builtins.__import__
    forbidden = {
        "ctypes",
        "cli.clean_memory_external_pin",
        "cli.clean_memory_protected_boundary",
        "cli.clean_memory_protected_manifest",
        "cli.clean_memory_protected_membership",
        "steps.common.clean_memory_windows_program_data_locator",
    }

    def guarded_import(name, *args, **kwargs):
        if name in forbidden:
            raise AssertionError(f"capability import before configuration acceptance: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    _assert_composition_code(
        module,
        "invalid_configuration",
        lambda: module._compose_authenticated_protected_membership(configuration),
    )


@pytest.mark.parametrize(
    ("authority", "expected_code", "terminal_event"),
    [
        ("configuration", "invalid_configuration", None),
        ("locator", "composition_failed", "subclass_locator"),
        ("location", "composition_failed", ("resolve", 1)),
        ("pin", "composition_failed", "pin"),
        ("manifest", "composition_failed", "manifest"),
        ("membership", "invalid_protected_membership", "membership"),
        ("boundary_tuple", "composition_failed", "observer"),
        ("boundary_evidence", "composition_failed", "observer"),
    ],
)
def test_composition_rejects_equal_value_subclasses_of_direct_authorities(
    monkeypatch: pytest.MonkeyPatch,
    authority: str,
    expected_code: str,
    terminal_event: object | None,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()

    if authority == "configuration":
        inputs["configuration"] = _composition_equal_value_subclass(
            inputs["configuration"],
            ("_projection_json", "configuration_scope_sha256"),
        )
        events = _install_composition_world(monkeypatch, inputs)
    elif authority == "locator":
        events = _install_composition_world(monkeypatch, inputs)
        locator = _composition_equal_value_subclass(
            object.__new__(locator_module.CleanMemoryWindowsProgramDataLocator),
            (),
        )

        def bind_subclass_locator(**_kwargs):
            events.append("subclass_locator")
            return locator

        monkeypatch.setattr(
            locator_module,
            "bind_clean_memory_windows_program_data_locator",
            bind_subclass_locator,
        )
    elif authority == "location":
        location = _composition_location()
        location = _composition_equal_value_subclass(
            location,
            (
                "_drive_root",
                "_program_data_components",
                "_fixed_directory_components",
                "_pin_name",
            ),
        )
        events = _install_composition_world(
            monkeypatch,
            inputs,
            locations=(location,),
        )
    else:
        if authority == "pin":
            inputs["pin"] = _composition_equal_value_subclass(
                inputs["pin"],
                ("_projection_bytes", "external_pin_evidence_sha256"),
            )
        elif authority == "manifest":
            inputs["manifest"] = _composition_equal_value_subclass(
                inputs["manifest"],
                (
                    "_manifest_bytes",
                    "_projection_bytes",
                    "protected_manifest_evidence_sha256",
                ),
            )
        elif authority == "membership":
            inputs["membership"] = _composition_equal_value_subclass(
                inputs["membership"],
                ("_projection_json", "protected_membership_scope_sha256"),
            )
        elif authority == "boundary_tuple":
            class EqualValueBoundaryTuple(tuple):
                pass

            inputs["boundaries"] = EqualValueBoundaryTuple(inputs["boundaries"])
        else:
            boundaries = list(inputs["boundaries"])
            boundaries[0] = _composition_equal_value_subclass(
                boundaries[0],
                ("role", "logical_id", "identity_json"),
            )
            inputs["boundaries"] = tuple(boundaries)
        events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        expected_code,
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    if terminal_event is None:
        assert events == []
    else:
        assert events[-1] == terminal_event


@pytest.mark.parametrize(
    ("stage", "expected_code", "forbidden_event"),
    [
        ("pin", "composition_failed", "manifest"),
        ("manifest", "composition_failed", "membership"),
        ("membership", "invalid_protected_membership", "observer"),
        ("boundaries", "composition_failed", ("resolve", 4)),
    ],
)
def test_composition_authenticates_each_direct_return_before_forwarding(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_code: str,
    forbidden_event: object,
) -> None:
    module = _load_module()
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    modules = {
        "pin": importlib.import_module("cli.clean_memory_external_pin"),
        "manifest": importlib.import_module("cli.clean_memory_protected_manifest"),
        "membership": importlib.import_module("cli.clean_memory_protected_membership"),
        "boundaries": importlib.import_module("cli.clean_memory_protected_boundary"),
    }

    if stage == "pin":
        monkeypatch.setattr(modules[stage], "read_external_pin", lambda: object())
    elif stage == "manifest":
        monkeypatch.setattr(
            modules[stage],
            "read_protected_manifest",
            lambda *_args, **_kwargs: object(),
        )
    elif stage == "membership":
        monkeypatch.setattr(
            modules[stage],
            "project_protected_membership",
            lambda *_args, **_kwargs: object(),
        )
    else:
        monkeypatch.setattr(
            modules[stage],
            "observe_protected_boundaries",
            lambda *_args, **_kwargs: tuple(inputs["boundaries"])[:-1],
        )

    _assert_composition_code(
        module,
        expected_code,
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert forbidden_event not in events


def test_composition_rejects_forged_manifest_digest_binding_before_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    inputs = _composition_inputs()
    forged_projection = inputs["manifest"].projection
    forged_projection["configuration_scope_sha256"] = "9" * 64
    forged = manifest_module.ProtectedManifestEvidence._from_projection(
        inputs["manifest_bytes"],
        forged_projection,
        expected_route_count=4,
    )
    events = _install_composition_world(monkeypatch, inputs)

    def read_forged(*_args, **_kwargs):
        events.append("forged_manifest")
        return forged

    monkeypatch.setattr(manifest_module, "read_protected_manifest", read_forged)
    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert "membership" not in events


def test_composition_maps_stable_membership_projection_failure_without_observing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    membership_module = importlib.import_module("cli.clean_memory_protected_membership")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)

    def fail_projection(*_args, **_kwargs):
        events.append("membership_failure")
        raise ValueError("SECRET_MEMBERSHIP_DETAIL")

    monkeypatch.setattr(
        membership_module,
        "project_protected_membership",
        fail_projection,
    )
    _assert_composition_code(
        module,
        "invalid_protected_membership",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert "observer" not in events


@pytest.mark.parametrize("changed_fence", [2, 3, 4])
def test_composition_maps_every_post_baseline_location_change_to_race(
    monkeypatch: pytest.MonkeyPatch,
    changed_fence: int,
) -> None:
    module = _load_module()
    inputs = _composition_inputs()
    baseline = _composition_location()
    changed = _composition_location(program_data_components=("ProgramDataChanged",))
    locations = tuple(
        changed if index == changed_fence else baseline for index in range(1, 5)
    )
    events = _install_composition_world(monkeypatch, inputs, locations=locations)

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    expected_cutoff = {
        2: ("resolve", 2),
        3: ("resolve", 3),
        4: ("resolve", 4),
    }[changed_fence]
    assert events[-1] == expected_cutoff


@pytest.mark.parametrize(
    ("protected_path", "program_data_components", "expected_overlap"),
    [
        ("R:/ProgramData", ("ProgramData",), True),
        ("R:/ProgramData/Child", ("ProgramData",), True),
        ("R:/ProgramData", ("ProgramData", "Child"), True),
        ("R:/PROGRAMDATA/GoodQ", ("ProgramData",), True),
        ("R:/ProgramDataX", ("ProgramData",), False),
        ("S:/ProgramData", ("ProgramData",), False),
    ],
)
def test_composition_uses_component_boundary_casefolded_lexical_exclusion(
    monkeypatch: pytest.MonkeyPatch,
    protected_path: str,
    program_data_components: tuple[str, ...],
    expected_overlap: bool,
) -> None:
    module = _load_module()
    config = _config(data_root="R:/Authority/GoodQ_Data")
    config["paths"]["models_cache"] = protected_path
    inputs = _composition_inputs(config=config)
    location = _composition_location(
        drive_root="R:\\",
        program_data_components=program_data_components,
    )
    events = _install_composition_world(
        monkeypatch,
        inputs,
        locations=(location,) * 4,
    )

    if expected_overlap:
        _assert_composition_code(
            module,
            "pin_member_overlap",
            lambda: module._compose_authenticated_protected_membership(
                inputs["configuration"]
            ),
        )
        assert events[-1] == ("resolve", 3)
        assert "observer" not in events
    else:
        assert (
            module._compose_authenticated_protected_membership(
                inputs["configuration"]
            )
            is inputs["boundaries"]
        )


@pytest.mark.parametrize(
    "protected_path",
    [
        "R:/ProgramData",
        "R:/ProgramData/GoodQ",
        "R:/ProgramData/GoodQ/authority",
        "R:/ProgramData/GoodQ/authority/clean-memory",
        "R:/ProgramData/GoodQ/authority/clean-memory/protected-boundaries.sha256",
    ],
)
def test_composition_rejects_each_pin_chain_prefix(
    monkeypatch: pytest.MonkeyPatch,
    protected_path: str,
) -> None:
    module = _load_module()
    config = _config(data_root="R:/Authority/GoodQ_Data")
    config["paths"]["models_cache"] = protected_path
    inputs = _composition_inputs(config=config)
    location = _composition_location(drive_root="R:\\")
    events = _install_composition_world(
        monkeypatch,
        inputs,
        locations=(location,) * 4,
    )

    _assert_composition_code(
        module,
        "pin_member_overlap",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 3)
    assert "observer" not in events


@pytest.mark.parametrize("lexical_overlap", [False, True])
def test_composition_rechecks_drift_after_normal_lexical_result_before_outcome(
    monkeypatch: pytest.MonkeyPatch,
    lexical_overlap: bool,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    config = _config(data_root="R:/Authority/GoodQ_Data")
    if lexical_overlap:
        config["paths"]["models_cache"] = "C:/ProgramData"
    inputs = _composition_inputs(config=config)
    events = _install_composition_world(monkeypatch, inputs)
    location = _composition_location()
    real_path_parser = module._canonical_absolute_path
    resolve_count = 0
    drifted = False

    def drift_after_normal_parse(*args, **kwargs):
        nonlocal drifted
        parsed = real_path_parser(*args, **kwargs)
        if not drifted:
            drifted = True
            object.__setattr__(
                inputs["pin"],
                "external_pin_evidence_sha256",
                "0" * 64,
            )
        return parsed

    def arm_drift_at_lexical_stage(_self):
        nonlocal resolve_count
        resolve_count += 1
        events.append(("resolve", resolve_count))
        if resolve_count == 3:
            monkeypatch.setattr(
                module,
                "_canonical_absolute_path",
                drift_after_normal_parse,
            )
        return location

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        arm_drift_at_lexical_stage,
    )
    try:
        _assert_composition_code(
            module,
            "observation_raced",
            lambda: module._compose_authenticated_protected_membership(
                inputs["configuration"]
            ),
        )
    finally:
        monkeypatch.setattr(module, "_canonical_absolute_path", real_path_parser)
    assert drifted is True
    assert events[-1] == ("resolve", 3)
    assert "observer" not in events


def test_composition_rechecks_all_inputs_after_fourth_location_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    location = _composition_location()
    resolve_count = 0

    def mutate_on_final_fence(_self):
        nonlocal resolve_count
        resolve_count += 1
        events.append(("resolve", resolve_count))
        if resolve_count == 4:
            object.__setattr__(
                inputs["membership"],
                "protected_membership_scope_sha256",
                "0" * 64,
            )
        return location

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        mutate_on_final_fence,
    )
    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 4)


@pytest.mark.parametrize(
    "stage",
    ["abi", "bind", "baseline", "pin", "manifest", "observer"],
)
def test_composition_propagates_exact_dependency_owned_public_errors(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    boundary_module = importlib.import_module("cli.clean_memory_protected_boundary")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    error_types = {
        "abi": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "bind": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "baseline": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "pin": external_module.ExternalPinReaderError,
        "manifest": manifest_module.ProtectedManifestReaderError,
        "observer": boundary_module.ProtectedBoundaryObservationError,
    }
    owned = error_types[stage]("observation_failed")

    def fail(*_args, **_kwargs):
        events.append(("owned_error", stage))
        raise owned

    if stage == "abi":
        monkeypatch.setattr(
            locator_module,
            "verify_clean_memory_windows_program_data_locator_abi",
            fail,
        )
    elif stage == "bind":
        monkeypatch.setattr(
            locator_module,
            "bind_clean_memory_windows_program_data_locator",
            fail,
        )
    elif stage == "baseline":
        monkeypatch.setattr(
            locator_module.CleanMemoryWindowsProgramDataLocator,
            "resolve",
            fail,
        )
    elif stage == "pin":
        monkeypatch.setattr(external_module, "read_external_pin", fail)
    elif stage == "manifest":
        monkeypatch.setattr(manifest_module, "read_protected_manifest", fail)
    else:
        monkeypatch.setattr(boundary_module, "observe_protected_boundaries", fail)

    with pytest.raises(error_types[stage]) as exc_info:
        module._compose_authenticated_protected_membership(inputs["configuration"])

    assert exc_info.value is owned
    assert events[-1] == ("owned_error", stage)


@pytest.mark.parametrize(
    ("stage", "expected_code"),
    [
        ("shell32", "composition_failed"),
        ("bind", "composition_failed"),
        ("later_location", "observation_raced"),
        ("observer", "composition_failed"),
    ],
)
def test_composition_maps_ordinary_stage_failures_without_raw_links(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_code: str,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    boundary_module = importlib.import_module("cli.clean_memory_protected_boundary")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    secret = "SECRET_COMPOSITION_FAILURE_PATH"

    def fail(*_args, **_kwargs):
        events.append(("ordinary_error", stage))
        raise OSError(secret)

    if stage == "shell32":
        real_loader = ctypes.WinDLL

        def selective_loader(name: str, *, use_last_error: bool):
            if name == "shell32":
                return fail()
            return real_loader(name, use_last_error=use_last_error)

        monkeypatch.setattr(ctypes, "WinDLL", selective_loader)
    elif stage == "bind":
        monkeypatch.setattr(
            locator_module,
            "bind_clean_memory_windows_program_data_locator",
            fail,
        )
    elif stage == "later_location":
        calls = 0
        location = _composition_location()

        def fail_second(_self):
            nonlocal calls
            calls += 1
            if calls == 2:
                return fail()
            events.append(("resolve", calls))
            return location

        monkeypatch.setattr(
            locator_module.CleanMemoryWindowsProgramDataLocator,
            "resolve",
            fail_second,
        )
    else:
        monkeypatch.setattr(boundary_module, "observe_protected_boundaries", fail)

    with pytest.raises(module._ProtectedMembershipCompositionError) as exc_info:
        module._compose_authenticated_protected_membership(inputs["configuration"])

    assert exc_info.value.code == expected_code
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert secret not in repr(exc_info.value)
    assert events[-1] == ("ordinary_error", stage)


def _prime_composition_control(error: BaseException):
    try:
        raise error
    except BaseException as caught:
        assert caught is error
        traceback = caught.__traceback__
    assert traceback is not None
    return traceback


def _assert_composition_traceback_tail(error: BaseException, expected) -> None:
    current = error.__traceback__
    while current is not None:
        if current is expected:
            return
        current = current.tb_next
    raise AssertionError("composition control-flow traceback tail was not preserved")


@pytest.mark.parametrize("control_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_composition_preserves_named_control_identity_traceback_and_closed_links(
    monkeypatch: pytest.MonkeyPatch,
    control_type: type[BaseException],
) -> None:
    module = _load_module()
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    inputs = _composition_inputs()
    _install_composition_world(monkeypatch, inputs)
    primary = control_type()
    original_traceback = _prime_composition_control(primary)
    raw = OSError("SECRET_CONTROL_LINK_PATH")
    primary.__cause__ = raw
    primary.__context__ = raw
    primary.__suppress_context__ = True

    def interrupt():
        raise primary

    monkeypatch.setattr(external_module, "read_external_pin", interrupt)

    with pytest.raises(control_type) as exc_info:
        module._compose_authenticated_protected_membership(inputs["configuration"])

    assert exc_info.value is primary
    _assert_composition_traceback_tail(primary, original_traceback)
    assert type(primary.__cause__) is module._ProtectedMembershipCompositionError
    assert primary.__cause__ is primary.__context__
    assert primary.__cause__.code == "composition_failed"
    assert primary.__suppress_context__ is True
    rendered = " ".join(
        (
            str(primary.__cause__),
            repr(primary.__cause__),
            repr(primary.__cause__.args),
            repr(primary.__cause__.__dict__),
        )
    )
    assert "SECRET_CONTROL_LINK_PATH" not in rendered


def test_composition_closes_unknown_non_exception_without_later_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)

    class UnknownFatal(BaseException):
        pass

    def fail():
        events.append("unknown_fatal")
        raise UnknownFatal("SECRET_FATAL_DETAIL")

    monkeypatch.setattr(external_module, "read_external_pin", fail)

    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "unknown_fatal"
    assert "manifest" not in events


def test_composition_accepts_canonical_public_locator_drive_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    inputs = _composition_inputs()
    location = _composition_location(drive_root="C:\\")
    _install_composition_world(
        monkeypatch,
        inputs,
        locations=(location,) * 4,
    )

    assert (
        module._compose_authenticated_protected_membership(inputs["configuration"])
        is inputs["boundaries"]
    )


def test_composition_rejects_malformed_exact_pin_before_manifest_forwarding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    inputs = _composition_inputs()
    projection = inputs["pin"].projection
    projection["dedicated_directory_identities"][0] = projection["anchor_identity"]
    inputs["pin"] = external_module.ExternalPinEvidence._from_projection(projection)
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert "manifest" not in events


def test_composition_rejects_malformed_exact_manifest_before_membership_forwarding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    inputs = _composition_inputs()
    projection = inputs["manifest"].projection
    projection["route_directory_identities"][1] = projection[
        "route_directory_identities"
    ][0]
    projection_bytes = _canonical_text(projection).encode("utf-8")
    forged = object.__new__(manifest_module.ProtectedManifestEvidence)
    object.__setattr__(forged, "_manifest_bytes", inputs["manifest_bytes"])
    object.__setattr__(forged, "_projection_bytes", projection_bytes)
    object.__setattr__(
        forged,
        "protected_manifest_evidence_sha256",
        hashlib.sha256(projection_bytes).hexdigest(),
    )
    inputs["manifest"] = forged
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert "membership" not in events


def test_composition_rejects_malformed_exact_membership_before_observer_forwarding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    membership_module = importlib.import_module("cli.clean_memory_protected_membership")
    inputs = _composition_inputs()
    projection = inputs["membership"].projection
    projection["protected_roles"][0]["members"][0]["member_id"] = "wrong_id"
    inputs["membership"] = membership_module.ProtectedMembershipProjection._from_projection(
        projection
    )
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "invalid_protected_membership",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert "observer" not in events


def test_composition_rejects_impossible_empty_boundary_members_before_final_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    common_module = importlib.import_module("steps.common.clean_memory")
    inputs = _composition_inputs()
    forged_boundaries = []
    for evidence in inputs["boundaries"]:
        envelope = json.loads(evidence.identity_json)
        envelope["members"] = []
        forged_boundaries.append(
            common_module.ProtectedBoundaryEvidence(
                role=evidence.role,
                logical_id=evidence.logical_id,
                identity_json=_canonical_text(envelope),
            )
        )
    inputs["boundaries"] = tuple(forged_boundaries)
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "observer"
    assert ("resolve", 4) not in events


@pytest.mark.parametrize("control_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_composition_fence_predicates_do_not_swallow_named_controls(
    monkeypatch: pytest.MonkeyPatch,
    control_type: type[BaseException],
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    primary = control_type()
    original_traceback = _prime_composition_control(primary)
    location = _composition_location()
    calls = 0
    armed = False
    pin_type = type(inputs["pin"])
    real_getattribute = pin_type.__getattribute__

    def interrupting_getattribute(self, name: str):
        if self is inputs["pin"] and armed and name == "_projection_bytes":
            raise primary
        return real_getattribute(self, name)

    def mutate_before_pin_fence(_self):
        nonlocal armed, calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 2:
            armed = True
        return location

    monkeypatch.setattr(pin_type, "__getattribute__", interrupting_getattribute)
    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        mutate_before_pin_fence,
    )

    with pytest.raises(control_type) as exc_info:
        module._compose_authenticated_protected_membership(inputs["configuration"])

    assert exc_info.value is primary
    _assert_composition_traceback_tail(primary, original_traceback)
    assert events[-1] == ("resolve", 2)


def test_composition_upstream_drift_precedes_dependency_owned_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    owned = manifest_module.ProtectedManifestReaderError("observation_failed")

    def drift_then_fail(*_args, **_kwargs):
        events.append("manifest_drift_failure")
        object.__setattr__(
            inputs["pin"],
            "external_pin_evidence_sha256",
            "0" * 64,
        )
        raise owned

    monkeypatch.setattr(
        manifest_module,
        "read_protected_manifest",
        drift_then_fail,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "manifest_drift_failure"


def test_composition_wrong_locator_return_honors_configuration_drift_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)

    def drift_then_return_wrong_type(**_kwargs):
        events.append("wrong_locator")
        object.__setattr__(
            inputs["configuration"],
            "configuration_scope_sha256",
            "0" * 64,
        )
        return object()

    monkeypatch.setattr(
        locator_module,
        "bind_clean_memory_windows_program_data_locator",
        drift_then_return_wrong_type,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "wrong_locator"


def test_composition_closes_lexical_failure_without_raw_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    location = _composition_location()
    calls = 0
    real_path_parser = module._canonical_absolute_path

    def fail_lexical(*_args, **_kwargs):
        raise OSError("SECRET_LEXICAL_PATH_DETAIL")

    def arm_failure_at_third_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 3:
            monkeypatch.setattr(module, "_canonical_absolute_path", fail_lexical)
        return location

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        arm_failure_at_third_fence,
    )
    try:
        _assert_composition_code(
            module,
            "composition_failed",
            lambda: module._compose_authenticated_protected_membership(
                inputs["configuration"]
            ),
        )
    finally:
        monkeypatch.setattr(module, "_canonical_absolute_path", real_path_parser)
    assert events[-1] == ("resolve", 3)
    assert "observer" not in events


def test_composition_rejects_manifest_route_cardinality_before_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    inputs = _composition_inputs()
    projection = inputs["manifest"].projection
    projection["route_directory_identities"].pop()
    projection_bytes = _canonical_text(projection).encode("utf-8")
    forged = object.__new__(manifest_module.ProtectedManifestEvidence)
    object.__setattr__(forged, "_manifest_bytes", inputs["manifest_bytes"])
    object.__setattr__(forged, "_projection_bytes", projection_bytes)
    object.__setattr__(
        forged,
        "protected_manifest_evidence_sha256",
        hashlib.sha256(projection_bytes).hexdigest(),
    )
    inputs["manifest"] = forged
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "manifest"
    assert "membership" not in events


def test_composition_rejects_rebound_configured_membership_path_before_observer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    membership_module = importlib.import_module("cli.clean_memory_protected_membership")
    inputs = _composition_inputs()
    projection = inputs["membership"].projection
    roles = {record["role"]: record for record in projection["protected_roles"]}
    roles["model_cache"]["members"][0]["absolute_path"] = (
        "T:/ForgedAuthority/UniqueModelCache"
    )
    forged = membership_module.ProtectedMembershipProjection._from_projection(
        projection
    )
    assert type(forged) is membership_module.ProtectedMembershipProjection
    assert forged._projection_json == _canonical_text(projection)
    assert forged.protected_membership_scope_sha256 == hashlib.sha256(
        forged._projection_json.encode("utf-8")
    ).hexdigest()
    inputs["membership"] = forged
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "invalid_protected_membership",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "membership"
    assert "observer" not in events


@pytest.mark.parametrize("mutation", ["configured_count", "casefold_path_alias"])
def test_composition_rejects_membership_policy_mutants_before_observer(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    module = _load_module()
    membership_module = importlib.import_module("cli.clean_memory_protected_membership")
    inputs = _composition_inputs()
    projection = inputs["membership"].projection
    roles = {record["role"]: record for record in projection["protected_roles"]}
    if mutation == "configured_count":
        roles["watchdog_state"]["members"].pop()
    else:
        first_path = roles["backup_root"]["members"][0]["absolute_path"]
        roles["download_cache"]["members"][0]["absolute_path"] = first_path.swapcase()
    inputs["membership"] = (
        membership_module.ProtectedMembershipProjection._from_projection(projection)
    )
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "invalid_protected_membership",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "membership"
    assert "observer" not in events


@pytest.mark.parametrize(
    "mutation",
    ["membership_digest", "member_id", "child_digest", "parent_volume"],
)
def test_composition_rejects_boundary_envelope_mutants_before_final_fence(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    module = _load_module()
    common_module = importlib.import_module("steps.common.clean_memory")
    inputs = _composition_inputs()
    forged_boundaries = list(inputs["boundaries"])
    original = forged_boundaries[0]
    envelope = json.loads(original.identity_json)
    if mutation == "membership_digest":
        envelope["protected_membership_scope_sha256"] = "0" * 64
    elif mutation == "member_id":
        envelope["members"][0]["member_id"] = "wrong_id"
    elif mutation == "child_digest":
        envelope["members"][0]["child_comparison_sha256"] = "0" * 64
    else:
        envelope["members"][0]["parent_identity"]["volume_serial"] = "f" * 16
    forged_boundaries[0] = common_module.ProtectedBoundaryEvidence(
        role=original.role,
        logical_id=original.logical_id,
        identity_json=_canonical_text(envelope),
    )
    inputs["boundaries"] = tuple(forged_boundaries)
    events = _install_composition_world(monkeypatch, inputs)

    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == "observer"
    assert ("resolve", 4) not in events


def test_composition_detects_boundary_mutation_at_final_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    location = _composition_location()
    calls = 0

    def mutate_on_final_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 4:
            object.__setattr__(
                inputs["boundaries"][0],
                "identity_json",
                _canonical_text({"mutated": True}),
            )
        return location

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        mutate_on_final_fence,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 4)


def test_composition_unicode_casefolds_complete_lexical_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    config = _config(data_root="R:/Authority/GoodQ_Data")
    config["paths"]["models_cache"] = "R:/STRASSE"
    inputs = _composition_inputs(config=config)
    location = _composition_location(
        drive_root="R:\\",
        program_data_components=("Straße",),
    )
    events = _install_composition_world(
        monkeypatch,
        inputs,
        locations=(location,) * 4,
    )

    _assert_composition_code(
        module,
        "pin_member_overlap",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 3)
    assert "observer" not in events


@pytest.mark.parametrize("control_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_composition_preserves_named_controls_from_lexical_stage(
    monkeypatch: pytest.MonkeyPatch,
    control_type: type[BaseException],
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    primary = control_type()
    original_traceback = _prime_composition_control(primary)
    location = _composition_location()
    calls = 0
    real_path_parser = module._canonical_absolute_path

    def interrupt_lexical(*_args, **_kwargs):
        raise primary

    def arm_interrupt_at_third_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 3:
            monkeypatch.setattr(module, "_canonical_absolute_path", interrupt_lexical)
        return location

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        arm_interrupt_at_third_fence,
    )
    try:
        with pytest.raises(control_type) as exc_info:
            module._compose_authenticated_protected_membership(
                inputs["configuration"]
            )
    finally:
        monkeypatch.setattr(module, "_canonical_absolute_path", real_path_parser)

    assert exc_info.value is primary
    _assert_composition_traceback_tail(primary, original_traceback)
    assert events[-1] == ("resolve", 3)


def test_composition_static_dependency_and_capability_allowlist() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_compose_authenticated_protected_membership"
    )
    imports = []
    for node in ast.walk(helper):
        if isinstance(node, ast.Import):
            imports.extend((None, alias.name, alias.asname) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.extend(
                (node.module, alias.name, alias.asname) for alias in node.names
            )
    assert set(imports) == {
        (None, "ctypes", None),
        ("cli.clean_memory_external_pin", "EXTERNAL_PIN_EVIDENCE_SCHEMA", None),
        ("cli.clean_memory_external_pin", "ExternalPinEvidence", None),
        ("cli.clean_memory_external_pin", "ExternalPinReaderError", None),
        ("cli.clean_memory_external_pin", "read_external_pin", None),
        (
            "cli.clean_memory_protected_boundary",
            "PROTECTED_BOUNDARY_IDENTITY_SCHEMA",
            None,
        ),
        (
            "cli.clean_memory_protected_boundary",
            "ProtectedBoundaryObservationError",
            None,
        ),
        (
            "cli.clean_memory_protected_boundary",
            "observe_protected_boundaries",
            None,
        ),
        (
            "cli.clean_memory_protected_manifest",
            "PROTECTED_MANIFEST_EVIDENCE_SCHEMA",
            None,
        ),
        (
            "cli.clean_memory_protected_manifest",
            "ProtectedManifestEvidence",
            None,
        ),
        (
            "cli.clean_memory_protected_manifest",
            "ProtectedManifestReaderError",
            None,
        ),
        (
            "cli.clean_memory_protected_manifest",
            "read_protected_manifest",
            None,
        ),
        (
            "cli.clean_memory_protected_membership",
            "PROTECTED_MEMBERSHIP_SCHEMA",
            None,
        ),
        (
            "cli.clean_memory_protected_membership",
            "ProtectedMembershipProjection",
            None,
        ),
        (
            "cli.clean_memory_protected_membership",
            "project_protected_membership",
            None,
        ),
        ("steps.common.clean_memory", "PROTECTED_BOUNDARY_ROLES", None),
        ("steps.common.clean_memory", "ProtectedBoundaryEvidence", None),
        (
            "steps.common.clean_memory_windows_program_data_locator",
            "CleanMemoryWindowsProgramDataLocation",
            None,
        ),
        (
            "steps.common.clean_memory_windows_program_data_locator",
            "CleanMemoryWindowsProgramDataLocator",
            None,
        ),
        (
            "steps.common.clean_memory_windows_program_data_locator",
            "CleanMemoryWindowsProgramDataLocatorError",
            None,
        ),
        (
            "steps.common.clean_memory_windows_program_data_locator",
            "bind_clean_memory_windows_program_data_locator",
            None,
        ),
        (
            "steps.common.clean_memory_windows_program_data_locator",
            "verify_clean_memory_windows_program_data_locator_abi",
            None,
        ),
    }
    forbidden_names = {
        "Path",
        "ResolvedCleanupScope",
        "__import__",
        "build_candidate_plan",
        "eval",
        "exec",
        "import_module",
        "logging",
        "open",
        "os",
        "print",
        "requests",
        "resolve_plan_configuration",
        "socket",
        "subprocess",
    }
    referenced_names = {
        node.id for node in ast.walk(helper) if isinstance(node, ast.Name)
    }
    assert referenced_names.isdisjoint(forbidden_names)


@pytest.mark.parametrize(
    "target",
    [
        "configuration_json",
        "configuration_digest",
        "location_drive_root",
        "location_program_data_components",
        "location_fixed_directory_components",
        "location_pin_name",
        "pin_bytes",
        "pin_digest",
        "manifest_bytes",
        "manifest_projection_bytes",
        "manifest_digest",
        "membership_json",
        "membership_digest",
        "boundary_role",
        "boundary_logical_id",
        "boundary_identity_json",
    ],
)
def test_composition_final_fence_rejects_different_exact_builtin_values(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    baseline = _composition_location()
    calls = 0

    def mutate_retained_value() -> None:
        if target == "configuration_json":
            owner, field = inputs["configuration"], "_projection_json"
        elif target == "configuration_digest":
            owner, field = inputs["configuration"], "configuration_scope_sha256"
        elif target == "pin_bytes":
            owner, field = inputs["pin"], "_projection_bytes"
        elif target == "pin_digest":
            owner, field = inputs["pin"], "external_pin_evidence_sha256"
        elif target == "manifest_bytes":
            owner, field = inputs["manifest"], "_manifest_bytes"
        elif target == "manifest_projection_bytes":
            owner, field = inputs["manifest"], "_projection_bytes"
        elif target == "manifest_digest":
            owner, field = (
                inputs["manifest"],
                "protected_manifest_evidence_sha256",
            )
        elif target == "membership_json":
            owner, field = inputs["membership"], "_projection_json"
        elif target == "membership_digest":
            owner, field = (
                inputs["membership"],
                "protected_membership_scope_sha256",
            )
        else:
            owner = inputs["boundaries"][0]
            field = {
                "boundary_role": "role",
                "boundary_logical_id": "logical_id",
                "boundary_identity_json": "identity_json",
            }[target]
        current = object.__getattribute__(owner, field)
        if type(current) is bytes:
            replacement = current + b"x"
        else:
            replacement = current + "x"
        assert type(replacement) is type(current)
        assert replacement != current
        object.__setattr__(owner, field, replacement)

    def changed_location():
        location = _composition_location()
        if target == "location_drive_root":
            object.__setattr__(location, "_drive_root", "D:\\")
        elif target == "location_program_data_components":
            object.__setattr__(
                location,
                "_program_data_components",
                ("DifferentProgramData",),
            )
        elif target == "location_fixed_directory_components":
            object.__setattr__(
                location,
                "_fixed_directory_components",
                ("GoodQ", "authority", "different-clean-memory"),
            )
        else:
            object.__setattr__(
                location,
                "_pin_name",
                "different-protected-boundaries.sha256",
            )
        assert type(location) is type(baseline)
        return location

    def mutate_at_final_location_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 4:
            if target.startswith("location_"):
                return changed_location()
            mutate_retained_value()
        return baseline

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        mutate_at_final_location_fence,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 4)


def test_composition_final_fence_requires_same_boundary_evidence_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    common_module = importlib.import_module("steps.common.clean_memory")
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    baseline = _composition_location()
    original = inputs["boundaries"][0]
    replacement = common_module.ProtectedBoundaryEvidence(
        role=original.role,
        logical_id=original.logical_id,
        identity_json=original.identity_json,
    )
    assert type(replacement) is common_module.ProtectedBoundaryEvidence
    assert replacement == original
    assert replacement is not original
    real_zip = builtins.zip
    calls = 0

    def substitute_boundary_identity(*iterables, **kwargs):
        pairs = real_zip(*iterables, **kwargs)
        if len(iterables) == 2 and iterables[0] is inputs["boundaries"]:
            materialized = list(pairs)
            materialized[0] = (replacement, materialized[0][1])
            return iter(materialized)
        return pairs

    def substitute_at_final_location_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 4:
            monkeypatch.setattr(builtins, "zip", substitute_boundary_identity)
        return baseline

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        substitute_at_final_location_fence,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 4)


@pytest.mark.parametrize(
    "target",
    [
        "configuration_json",
        "configuration_digest",
        "location_pin_name",
        "pin_bytes",
        "pin_digest",
        "manifest_bytes",
        "manifest_projection_bytes",
        "manifest_digest",
        "membership_json",
        "membership_digest",
        "boundary_role",
        "boundary_logical_id",
        "boundary_identity_json",
    ],
)
def test_composition_final_fence_rejects_equal_value_type_substitution(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    baseline = _composition_location()
    calls = 0

    class EqualString(str):
        pass

    class EqualBytes(bytes):
        pass

    def substitute_equal_value_type() -> None:
        if target == "configuration_json":
            owner, field, wrapper = (
                inputs["configuration"],
                "_projection_json",
                EqualString,
            )
        elif target == "configuration_digest":
            owner, field, wrapper = (
                inputs["configuration"],
                "configuration_scope_sha256",
                EqualString,
            )
        elif target == "pin_bytes":
            owner, field, wrapper = inputs["pin"], "_projection_bytes", EqualBytes
        elif target == "pin_digest":
            owner, field, wrapper = (
                inputs["pin"],
                "external_pin_evidence_sha256",
                EqualString,
            )
        elif target == "manifest_bytes":
            owner, field, wrapper = (
                inputs["manifest"],
                "_manifest_bytes",
                EqualBytes,
            )
        elif target == "manifest_projection_bytes":
            owner, field, wrapper = (
                inputs["manifest"],
                "_projection_bytes",
                EqualBytes,
            )
        elif target == "manifest_digest":
            owner, field, wrapper = (
                inputs["manifest"],
                "protected_manifest_evidence_sha256",
                EqualString,
            )
        elif target == "membership_json":
            owner, field, wrapper = (
                inputs["membership"],
                "_projection_json",
                EqualString,
            )
        elif target == "membership_digest":
            owner, field, wrapper = (
                inputs["membership"],
                "protected_membership_scope_sha256",
                EqualString,
            )
        else:
            owner = inputs["boundaries"][0]
            field = {
                "boundary_role": "role",
                "boundary_logical_id": "logical_id",
                "boundary_identity_json": "identity_json",
            }[target]
            wrapper = EqualString
        current = object.__getattribute__(owner, field)
        object.__setattr__(owner, field, wrapper(current))

    def mutate_at_final_location_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 4:
            if target == "location_pin_name":
                mutated_location = _composition_location()
                object.__setattr__(
                    mutated_location,
                    "_pin_name",
                    EqualString(mutated_location.pin_name),
                )
                return mutated_location
            substitute_equal_value_type()
        return baseline

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        mutate_at_final_location_fence,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 4)


@pytest.mark.parametrize(
    "component",
    ["ProgramData/GoodQ", "ProgramData\\GoodQ", "Program\x01Data", "Program\x7fData"],
)
def test_composition_rejects_malformed_detached_program_data_component_at_baseline(
    monkeypatch: pytest.MonkeyPatch,
    component: str,
) -> None:
    module = _load_module()
    inputs = _composition_inputs()
    location = _composition_location(program_data_components=(component,))
    events = _install_composition_world(
        monkeypatch,
        inputs,
        locations=(location,) * 4,
    )

    _assert_composition_code(
        module,
        "composition_failed",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 1)
    assert "pin" not in events


@pytest.mark.parametrize("stage", ["pin", "manifest", "membership", "boundaries"])
def test_composition_malformed_direct_return_honors_accepted_upstream_drift(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    module = _load_module()
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    membership_module = importlib.import_module("cli.clean_memory_protected_membership")
    boundary_module = importlib.import_module("cli.clean_memory_protected_boundary")
    common_module = importlib.import_module("steps.common.clean_memory")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)

    if stage == "pin":
        projection = inputs["pin"].projection
        projection["dedicated_directory_identities"][0] = projection["anchor_identity"]
        malformed = external_module.ExternalPinEvidence._from_projection(projection)

        def drift_then_return_malformed():
            events.append(("malformed_drift", stage))
            object.__setattr__(
                inputs["configuration"],
                "configuration_scope_sha256",
                "0" * 64,
            )
            return malformed

        monkeypatch.setattr(
            external_module,
            "read_external_pin",
            drift_then_return_malformed,
        )
    elif stage == "manifest":
        projection = inputs["manifest"].projection
        projection["route_directory_identities"][1] = projection[
            "route_directory_identities"
        ][0]
        projection_bytes = _canonical_text(projection).encode("utf-8")
        malformed = object.__new__(manifest_module.ProtectedManifestEvidence)
        object.__setattr__(malformed, "_manifest_bytes", inputs["manifest_bytes"])
        object.__setattr__(malformed, "_projection_bytes", projection_bytes)
        object.__setattr__(
            malformed,
            "protected_manifest_evidence_sha256",
            hashlib.sha256(projection_bytes).hexdigest(),
        )

        def drift_then_return_malformed(*_args, **_kwargs):
            events.append(("malformed_drift", stage))
            object.__setattr__(
                inputs["pin"],
                "external_pin_evidence_sha256",
                "0" * 64,
            )
            return malformed

        monkeypatch.setattr(
            manifest_module,
            "read_protected_manifest",
            drift_then_return_malformed,
        )
    elif stage == "membership":
        projection = inputs["membership"].projection
        projection["protected_roles"][0]["members"][0]["member_id"] = "wrong_id"
        malformed = membership_module.ProtectedMembershipProjection._from_projection(
            projection
        )

        def drift_then_return_malformed(*_args, **_kwargs):
            events.append(("malformed_drift", stage))
            object.__setattr__(
                inputs["manifest"],
                "protected_manifest_evidence_sha256",
                "0" * 64,
            )
            return malformed

        monkeypatch.setattr(
            membership_module,
            "project_protected_membership",
            drift_then_return_malformed,
        )
    else:
        malformed_boundaries = []
        for evidence in inputs["boundaries"]:
            envelope = json.loads(evidence.identity_json)
            envelope["members"] = []
            malformed_boundaries.append(
                common_module.ProtectedBoundaryEvidence(
                    role=evidence.role,
                    logical_id=evidence.logical_id,
                    identity_json=_canonical_text(envelope),
                )
            )
        malformed = tuple(malformed_boundaries)

        def drift_then_return_malformed(*_args, **_kwargs):
            events.append(("malformed_drift", stage))
            object.__setattr__(
                inputs["membership"],
                "protected_membership_scope_sha256",
                "0" * 64,
            )
            return malformed

        monkeypatch.setattr(
            boundary_module,
            "observe_protected_boundaries",
            drift_then_return_malformed,
        )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("malformed_drift", stage)
    if stage == "pin":
        assert "manifest" not in events
    elif stage == "manifest":
        assert "membership" not in events
    elif stage == "membership":
        assert "observer" not in events
    else:
        assert ("resolve", 4) not in events


def test_composition_final_fence_rejects_distinct_equal_manifest_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    baseline = _composition_location()
    original = inputs["manifest"]._manifest_bytes
    replacement = bytes(bytearray(original))
    assert type(replacement) is bytes
    assert replacement == original
    assert replacement is not original
    calls = 0

    def substitute_at_final_location_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        if calls == 4:
            object.__setattr__(inputs["manifest"], "_manifest_bytes", replacement)
        return baseline

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        substitute_at_final_location_fence,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 4)


@pytest.mark.parametrize(
    "target",
    [
        "drive_root",
        "program_data_tuple",
        "program_data_inner",
        "fixed_tuple",
        "fixed_inner",
    ],
)
def test_composition_final_location_fence_rejects_equal_value_subtypes(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    baseline = _composition_location()
    changed = _composition_location()
    calls = 0

    class EqualString(str):
        pass

    class EqualTuple(tuple):
        pass

    if target == "drive_root":
        object.__setattr__(changed, "_drive_root", EqualString(changed.drive_root))
    elif target == "program_data_tuple":
        object.__setattr__(
            changed,
            "_program_data_components",
            EqualTuple(changed.program_data_components),
        )
    elif target == "program_data_inner":
        object.__setattr__(
            changed,
            "_program_data_components",
            (EqualString(changed.program_data_components[0]),),
        )
    elif target == "fixed_tuple":
        object.__setattr__(
            changed,
            "_fixed_directory_components",
            EqualTuple(changed.fixed_directory_components),
        )
    else:
        object.__setattr__(
            changed,
            "_fixed_directory_components",
            (
                EqualString(changed.fixed_directory_components[0]),
                *changed.fixed_directory_components[1:],
            ),
        )

    def substitute_at_final_location_fence(_self):
        nonlocal calls
        calls += 1
        events.append(("resolve", calls))
        return changed if calls == 4 else baseline

    monkeypatch.setattr(
        locator_module.CleanMemoryWindowsProgramDataLocator,
        "resolve",
        substitute_at_final_location_fence,
    )

    _assert_composition_code(
        module,
        "observation_raced",
        lambda: module._compose_authenticated_protected_membership(
            inputs["configuration"]
        ),
    )
    assert events[-1] == ("resolve", 4)


def test_composition_accepts_fresh_equal_exact_builtin_location_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    inputs = _composition_inputs()
    locations = []
    for _index in range(4):
        location = _composition_location(
            drive_root="".join(("C", ":", "\\")),
            program_data_components=("".join(("Program", "Data")),),
        )
        object.__setattr__(
            location,
            "_fixed_directory_components",
            tuple(
                "".join(parts)
                for parts in (
                    ("Good", "Q"),
                    ("auth", "ority"),
                    ("clean", "-memory"),
                )
            ),
        )
        object.__setattr__(
            location,
            "_pin_name",
            "".join(("protected-boundaries", ".sha256")),
        )
        locations.append(location)
    assert len({id(location) for location in locations}) == 4
    events = _install_composition_world(
        monkeypatch,
        inputs,
        locations=tuple(locations),
    )

    assert (
        module._compose_authenticated_protected_membership(inputs["configuration"])
        is inputs["boundaries"]
    )
    assert events[-1] == ("resolve", 4)


@pytest.mark.parametrize(
    "stage",
    ["abi", "bind", "baseline", "pin", "manifest", "observer"],
)
def test_composition_sanitizes_dependency_owned_public_error_graph(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    boundary_module = importlib.import_module("cli.clean_memory_protected_boundary")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    error_types = {
        "abi": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "bind": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "baseline": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "pin": external_module.ExternalPinReaderError,
        "manifest": manifest_module.ProtectedManifestReaderError,
        "observer": boundary_module.ProtectedBoundaryObservationError,
    }
    owned = error_types[stage]("observation_failed")
    original_code = owned.code
    original_args = owned.args
    original_traceback = _prime_composition_control(owned)
    secret = f"SECRET_DEPENDENCY_ERROR_GRAPH_{stage}"
    object.__setattr__(owned, "args", (secret,))
    raw = OSError(secret)
    object.__setattr__(owned, "__cause__", raw)
    object.__setattr__(owned, "__context__", raw)
    object.__setattr__(owned, "__suppress_context__", False)
    object.__getattribute__(owned, "__dict__").update(
        {"__notes__": [secret], "secret_attribute": secret}
    )

    def fail(*_args, **_kwargs):
        events.append(("owned_graph", stage))
        raise owned

    if stage == "abi":
        monkeypatch.setattr(
            locator_module,
            "verify_clean_memory_windows_program_data_locator_abi",
            fail,
        )
    elif stage == "bind":
        monkeypatch.setattr(
            locator_module,
            "bind_clean_memory_windows_program_data_locator",
            fail,
        )
    elif stage == "baseline":
        monkeypatch.setattr(
            locator_module.CleanMemoryWindowsProgramDataLocator,
            "resolve",
            fail,
        )
    elif stage == "pin":
        monkeypatch.setattr(external_module, "read_external_pin", fail)
    elif stage == "manifest":
        monkeypatch.setattr(manifest_module, "read_protected_manifest", fail)
    else:
        monkeypatch.setattr(boundary_module, "observe_protected_boundaries", fail)

    with pytest.raises(error_types[stage]) as exc_info:
        module._compose_authenticated_protected_membership(inputs["configuration"])

    assert exc_info.value is owned
    assert owned.code == original_code
    assert owned.args == original_args
    _assert_composition_traceback_tail(owned, original_traceback)
    assert type(owned.__cause__) is module._ProtectedMembershipCompositionError
    assert owned.__cause__ is owned.__context__
    assert owned.__cause__.code == "composition_failed"
    assert owned.__suppress_context__ is True
    assert object.__getattribute__(owned, "__dict__") == {}
    rendered = " ".join(
        (
            str(owned),
            repr(owned),
            repr(owned.args),
            repr(owned.__cause__),
            repr(owned.__context__),
            repr(object.__getattribute__(owned, "__dict__")),
        )
    )
    assert secret not in rendered
    assert events[-1] == ("owned_graph", stage)


@pytest.mark.parametrize(
    ("stage", "tamper"),
    [
        ("abi", "unknown"),
        ("bind", "nonstr"),
        ("baseline", "missing"),
        ("pin", "unknown"),
        ("manifest", "nonstr"),
        ("observer", "missing"),
    ],
)
def test_composition_closes_dependency_owned_public_error_with_invalid_code(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    tamper: str,
) -> None:
    module = _load_module()
    locator_module = importlib.import_module(
        "steps.common.clean_memory_windows_program_data_locator"
    )
    external_module = importlib.import_module("cli.clean_memory_external_pin")
    manifest_module = importlib.import_module("cli.clean_memory_protected_manifest")
    boundary_module = importlib.import_module("cli.clean_memory_protected_boundary")
    inputs = _composition_inputs()
    events = _install_composition_world(monkeypatch, inputs)
    error_types = {
        "abi": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "bind": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "baseline": locator_module.CleanMemoryWindowsProgramDataLocatorError,
        "pin": external_module.ExternalPinReaderError,
        "manifest": manifest_module.ProtectedManifestReaderError,
        "observer": boundary_module.ProtectedBoundaryObservationError,
    }
    owned = error_types[stage]("observation_failed")
    secret = f"SECRET_DEPENDENCY_ERROR_CODE_{stage}"
    if tamper == "unknown":
        object.__setattr__(owned, "_code", secret)
    elif tamper == "nonstr":
        object.__setattr__(owned, "_code", object())
    else:
        object.__delattr__(owned, "_code")
    object.__setattr__(owned, "args", (secret,))

    def fail(*_args, **_kwargs):
        events.append(("invalid_owned_code", stage))
        raise owned

    if stage == "abi":
        monkeypatch.setattr(
            locator_module,
            "verify_clean_memory_windows_program_data_locator_abi",
            fail,
        )
    elif stage == "bind":
        monkeypatch.setattr(
            locator_module,
            "bind_clean_memory_windows_program_data_locator",
            fail,
        )
    elif stage == "baseline":
        monkeypatch.setattr(
            locator_module.CleanMemoryWindowsProgramDataLocator,
            "resolve",
            fail,
        )
    elif stage == "pin":
        monkeypatch.setattr(external_module, "read_external_pin", fail)
    elif stage == "manifest":
        monkeypatch.setattr(manifest_module, "read_protected_manifest", fail)
    else:
        monkeypatch.setattr(boundary_module, "observe_protected_boundaries", fail)

    with pytest.raises(module._ProtectedMembershipCompositionError) as exc_info:
        module._compose_authenticated_protected_membership(inputs["configuration"])

    assert exc_info.value.code == "composition_failed"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert secret not in repr(exc_info.value)
    assert events[-1] == ("invalid_owned_code", stage)
