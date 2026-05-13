from __future__ import annotations

from steps.common.config_redaction import REDACTION_MARKER, redact_config


def test_redacts_exact_and_suspicious_secret_keys() -> None:
    cfg = {
        "token": "plain-value",
        "api_key": "api-key-value",
        "secret": "secret-value",
        "password": "password-value",
        "authorization": "Bearer value",
        "credential": "credential-value",
        "use_auth_token": "auth-value",
        "bearer": "bearer-value",
        "cookie": "cookie-value",
        "session": "session-value",
        "client_secret": "client-secret-value",
        "private_key": "private-key-value",
    }

    redacted = redact_config(cfg)

    assert all(value == REDACTION_MARKER for value in redacted.values())


def test_redacts_suffix_keys_and_nested_values_without_mutating_source() -> None:
    cfg = {
        "home_assistant": {"HA_TOKEN": "ha_sentinel_value"},
        "models": [{"hf_token": "hf_sentinel_value"}, {"name": "public-model"}],
    }
    original = {
        "home_assistant": {"HA_TOKEN": "ha_sentinel_value"},
        "models": [{"hf_token": "hf_sentinel_value"}, {"name": "public-model"}],
    }

    redacted = redact_config(cfg)

    assert redacted["home_assistant"]["HA_TOKEN"] == REDACTION_MARKER
    assert redacted["models"][0]["hf_token"] == REDACTION_MARKER
    assert redacted["models"][1]["name"] == "public-model"
    assert cfg == original


def test_redacts_token_like_values() -> None:
    jwt_value = ".".join(("a" * 12, "b" * 12, "c" * 12))
    openai_key = "sk-" + ("a" * 30)
    huggingface_token = "hf_" + ("a" * 30)
    cfg = {
        "jwt": jwt_value,
        "openai": openai_key,
        "huggingface": huggingface_token,
        "safe": "goodq_core",
    }

    redacted = redact_config(cfg)

    assert redacted["jwt"] == REDACTION_MARKER
    assert redacted["openai"] == REDACTION_MARKER
    assert redacted["huggingface"] == REDACTION_MARKER
    assert redacted["safe"] == "goodq_core"


def test_tokenizes_local_paths_when_local_values_are_excluded() -> None:
    cfg = {
        "repo_file": "X:/GOODQ/projects/goodq4all/configs/config.yaml",
        "data_file": "Y:/DATA_ROOT/GoodQ_Data/epochs/demo/memory.db",
        "user_file": "Z:/Users/example/.cache/goodq/item.json",
    }

    redacted = redact_config(
        cfg,
        include_local_values=False,
        repo_root="X:/GOODQ/projects/goodq4all",
        data_root="Y:/DATA_ROOT",
        user_root="Z:/Users/example",
    )

    assert redacted["repo_file"] == "<PROJECT_ROOT>/configs/config.yaml"
    assert redacted["data_file"] == "<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/demo/memory.db"
    assert redacted["user_file"] == "<USER_ROOT>/.cache/goodq/item.json"


def test_preserves_local_paths_when_local_values_are_included() -> None:
    cfg = {"repo_file": "X:/GOODQ/projects/goodq4all/configs/config.yaml"}

    redacted = redact_config(
        cfg,
        include_local_values=True,
        repo_root="X:/GOODQ/projects/goodq4all",
    )

    assert redacted["repo_file"] == "X:/GOODQ/projects/goodq4all/configs/config.yaml"
