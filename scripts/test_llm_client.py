#!/usr/bin/env python3
"""
GoodQ4All LLM client integration test.

Validates the current injected vLLM primary + Ollama fallback contract from the
active config surface.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.llm_client import LLMClient
from steps.common.config_loader import load_configs
from steps.common.llm_model_factory import build_llm_models


def build_client() -> LLMClient:
    cfg = load_configs({})
    models = build_llm_models(cfg)
    return LLMClient(
        models=models,
        health_check_interval=60,
        max_retries=3,
        timeout=30,
        cache_ttl=300,
        enable_health_checks=False,
    )


def main() -> int:
    print("=" * 80)
    print("[LAUNCH] GoodQ4All LLM Client Integration Test")
    print("=" * 80)
    print()

    print("[LOG] Initializing injected LLM client from active config...")
    try:
        client = build_client()
    except Exception as exc:
        print(f"[FAIL] Client initialization failed: {exc}")
        return 1

    print(f"[OK] Client initialized with {len(client.models)} configured models")
    print("   Configured models:")
    for model in client.models:
        print(f"     - {model.name:25} @ {model.endpoint}")
    print()

    print("-" * 80)
    print("TEST 1: Health Check All Endpoints")
    print("-" * 80)
    health = client.check_all_health(force=True)

    for model_name, status in health.items():
        icon = "[OK]" if status.is_healthy else "[FAIL]"
        print(
            f"{icon} {model_name:25} - "
            f"{'HEALTHY' if status.is_healthy else 'UNHEALTHY':10} "
            f"({status.response_time_ms:.0f}ms)"
        )
        if status.last_error:
            print(f"   Error: {status.last_error}")

    healthy_count = sum(1 for status in health.values() if status.is_healthy)
    print(f"\n[STATS] {healthy_count}/{len(health)} models healthy")
    print()

    print("-" * 80)
    print("TEST 2: Simple Chat Completion")
    print("-" * 80)
    test_message = "Hello! Please respond with a brief greeting."
    print(f"[LOG] Sending: {test_message}")

    try:
        response = client.chat(
            messages=[{"role": "user", "content": test_message}],
            max_tokens=30,
        )
        print("[OK] Response received:")
        print(f"   Model: {response.get('model', 'unknown')}")
        if "choices" in response and response["choices"]:
            message = response["choices"][0]["message"]["content"]
            print(f"   Message: {message[:200]}")
        print(f"   Tokens: {response.get('usage', {})}")
    except Exception as exc:
        print(f"[FAIL] Error: {exc}")
    print()

    print("-" * 80)
    print("TEST 3: Multi-turn Conversation")
    print("-" * 80)
    conversation = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "And if we multiply that by 3?"},
    ]

    try:
        response = client.chat(conversation)
        print("[OK] Multi-turn response:")
        if "choices" in response and response["choices"]:
            message = response["choices"][0]["message"]["content"]
            print(f"   Message: {message}")
    except Exception as exc:
        print(f"[FAIL] Error: {exc}")
    print()

    print("-" * 80)
    print("TEST 4: Streaming Response")
    print("-" * 80)
    print("[LOG] Requesting stream...")

    try:
        response = client.chat(
            [{"role": "user", "content": "Count from 1 to 5"}],
            stream=True,
        )
        print("[OK] Stream:")
        print("   ", end="")
        for line in response.iter_lines():
            if not line:
                continue
            line_text = line.decode("utf-8")
            if not line_text.startswith("data: "):
                continue
            data = line_text[6:]
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "choices" in chunk and chunk["choices"]:
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    print(content, end="", flush=True)
        print()
        print("[OK] Stream complete")
    except Exception as exc:
        print(f"[FAIL] Error: {exc}")
    print()

    print("-" * 80)
    print("TEST 5: Model Selection Strategies")
    print("-" * 80)

    try:
        print("Testing prefer_speed...")
        response = client.chat(
            [{"role": "user", "content": "Hi"}],
            prefer_speed=True,
            max_tokens=10,
        )
        print(f"[OK] Speed-preferred model: {response.get('model', 'unknown')}")

        print("Testing prefer_quality...")
        response = client.chat(
            [{"role": "user", "content": "Hi"}],
            prefer_quality=True,
            max_tokens=10,
        )
        print(f"[OK] Quality-preferred model: {response.get('model', 'unknown')}")
    except Exception as exc:
        print(f"[FAIL] Error: {exc}")
    print()

    print("=" * 80)
    print("[STATS] TEST SUMMARY")
    print("=" * 80)
    status = client.get_status()
    print(f"[OK] Total Models: {status['models_total']}")
    print(f"[OK] Healthy Models: {status['models_healthy']}")
    print(f"[FAIL] Unhealthy Models: {status['models_unhealthy']}")
    print(
        f"[OK] Fallback Chain: "
        f"{'OPERATIONAL' if status['models_healthy'] > 1 else 'LIMITED'}"
    )
    print()
    print("[TARGET] Integration test complete!")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
