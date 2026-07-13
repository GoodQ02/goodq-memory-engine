from __future__ import annotations

import builtins
import copy
from dataclasses import FrozenInstanceError
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

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
