from __future__ import annotations

import os
import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

# Ensure import of api.main works by configuring path if needed
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from api.main import app


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_external_deps():
    """Mock network calls and subprocess tasks to prevent hangs or external dependencies during CI."""
    with patch("requests.get") as mock_get, \
         patch("subprocess.run") as mock_sub_run, \
         patch("shutil.which") as mock_which:

        # Default shutil.which mocks: WSL is not available
        mock_which.return_value = None

        # Default requests.get mocks: Raise ConnectionError for health check urls
        def side_effect_get(url, *args, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")

        mock_get.side_effect = side_effect_get

        # Default subprocess.run mock: Raise FileNotFoundError or return error code
        mock_sub_run.side_effect = FileNotFoundError("No such command")

        yield {
            "requests_get": mock_get,
            "subprocess_run": mock_sub_run,
            "shutil_which": mock_which,
        }


def test_api_root_endpoints(api_client, mock_external_deps) -> None:
    # Test GET /
    response_root = api_client.get("/")
    assert response_root.status_code == 200
    assert response_root.json()["status"] == "ok"

    # Test GET /api
    response_api = api_client.get("/api")
    assert response_api.status_code == 200
    assert "endpoints" in response_api.json()


def test_api_health_summary_all_degraded(api_client, mock_external_deps) -> None:
    # Test GET /api/health/summary when services are unresponsive
    response = api_client.get("/api/health/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall"]["status"] == "degraded"
    assert payload["overall"]["healthy"] == 0
    assert payload["vllm"]["status"] == "unhealthy"
    assert payload["ollama"]["status"] == "unhealthy"


def test_api_health_summary_all_healthy(api_client, mock_external_deps) -> None:
    # Set requests.get to return 200 OK for all endpoints
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_external_deps["requests_get"].side_effect = None
    mock_external_deps["requests_get"].return_value = mock_response

    # Test GET /api/health/summary when all services respond 200
    response = api_client.get("/api/health/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall"]["status"] == "healthy"
    assert payload["overall"]["healthy"] == 2
    assert payload["vllm"]["status"] == "healthy"
    assert payload["ollama"]["status"] == "healthy"


def test_api_status_aggregated_health(api_client, mock_external_deps) -> None:
    # Mock requests.get and subprocess.run to simulate active state
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "idle"}
    mock_external_deps["requests_get"].side_effect = None
    mock_external_deps["requests_get"].return_value = mock_response

    # Mock shutil.which to find WSL
    mock_external_deps["shutil_which"].side_effect = lambda cmd: "/usr/bin/wsl" if cmd == "wsl" else None

    # Mock subprocess.run for wsl --status and nvidia-smi
    def mock_run_side_effect(args, *extra_args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        if "wsl" in args:
            res.stdout = "Default Distribution: Ubuntu\nDefault Version: 2\n"
        elif "nvidia-smi" in args:
            res.stdout = "25, 1024, 8192\n"
        else:
            res.stdout = ""
        return res

    mock_external_deps["subprocess_run"].side_effect = mock_run_side_effect

    # Test GET /api/status
    response = api_client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["components"]["api"] == "running"
    assert payload["gpu"]["gpu_utilization"] == 25
    assert payload["gpu"]["gpu_memory_used"] == 1024
    assert payload["wsl"]["available"] is True


def test_api_system_status_degraded(api_client, mock_external_deps) -> None:
    # Test GET /api/system/status when services are degraded
    response = api_client.get("/api/system/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["goodq_core_available"] is False
    assert payload["qdrant_available"] is False
