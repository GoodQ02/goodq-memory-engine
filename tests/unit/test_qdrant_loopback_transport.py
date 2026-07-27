from steps.common.qdrant_client import build_qdrant_session


def test_loopback_qdrant_session_ignores_ambient_proxy() -> None:
    assert build_qdrant_session("http://127.0.0.1:6333").trust_env is False
    assert build_qdrant_session("http://localhost:6333").trust_env is False
    assert build_qdrant_session("http://[::1]:6333").trust_env is False


def test_non_loopback_qdrant_session_keeps_environment_behavior() -> None:
    assert build_qdrant_session("https://qdrant.example.test").trust_env is True
