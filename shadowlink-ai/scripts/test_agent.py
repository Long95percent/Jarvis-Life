#!/usr/bin/env python3
"""Smoke test for the Agent module — tests all 4 strategies via HTTP API.

Usage:
    # Start the service first:
    #   cd shadowlink-ai && python -m uvicorn app.main:app --port 9100
    #
    # Then run this script:
    #   python scripts/test_agent.py [--base-url http://localhost:9100]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:9100"

# ── Test Cases ──

TESTS = [
    {
        "name": "DIRECT — simple greeting",
        "payload": {
            "session_id": "test-direct",
            "message": "Hello! What can you help me with?",
            "strategy": "direct",
            "stream": False,
        },
    },
    {
        "name": "REACT — tool use (current time)",
        "payload": {
            "session_id": "test-react",
            "message": "What is the current time?",
            "strategy": "react",
            "stream": False,
        },
    },
    {
        "name": "PLAN_EXECUTE — multi-step task",
        "payload": {
            "session_id": "test-plan",
            "message": "Calculate 17 * 23, then tell me the result and whether it's a prime number.",
            "strategy": "plan_execute",
            "stream": False,
        },
    },
    {
        "name": "SUPERVISOR — multi-domain delegation",
        "payload": {
            "session_id": "test-supervisor",
            "message": "Write a short Python function that calculates fibonacci numbers and explain how it works.",
            "strategy": "supervisor",
            "stream": False,
        },
    },
    {
        "name": "AUTO-ROUTE — let complexity router decide",
        "payload": {
            "session_id": "test-auto",
            "message": "Explain the concept of recursion in programming.",
            "stream": False,
        },
    },
]


def test_health(client: httpx.Client, base_url: str) -> bool:
    """Test the health endpoint."""
    print("\n── Health Check ──")
    try:
        resp = client.get(f"{base_url}/health")
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  Body: {resp.json()}")
            return True
        else:
            print(f"  FAIL: {resp.text}")
            return False
    except httpx.ConnectError:
        print(f"  FAIL: Cannot connect to {base_url}")
        print("  Make sure the service is running:")
        print("    cd shadowlink-ai && python -m uvicorn app.main:app --port 9100")
        return False


def test_chat(client: httpx.Client, base_url: str, test: dict) -> bool:
    """Test a non-streaming chat request."""
    name = test["name"]
    payload = test["payload"]
    print(f"\n── {name} ──")
    print(f"  Message: {payload['message'][:80]}")

    try:
        start = time.perf_counter()
        resp = client.post(
            f"{base_url}/v1/agent/chat",
            json=payload,
            timeout=120.0,
        )
        elapsed = time.perf_counter() - start
        print(f"  Status: {resp.status_code} ({elapsed:.1f}s)")

        if resp.status_code == 200:
            data = resp.json()
            result = data.get("data", data)
            answer = result.get("answer", "")[:200]
            strategy = result.get("strategy", "unknown")
            steps = result.get("steps", [])
            latency = result.get("total_latency_ms", 0)
            print(f"  Strategy: {strategy}")
            print(f"  Steps: {len(steps)}")
            print(f"  Latency: {latency:.0f}ms")
            print(f"  Answer: {answer}...")
            return True
        else:
            print(f"  FAIL: {resp.text[:300]}")
            return False
    except httpx.ReadTimeout:
        print("  FAIL: Request timed out (120s)")
        return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_stream(client: httpx.Client, base_url: str) -> bool:
    """Test SSE streaming endpoint."""
    print("\n── SSE Streaming Test ──")
    payload = {
        "session_id": "test-stream",
        "message": "Count from 1 to 5.",
        "strategy": "direct",
        "stream": True,
    }
    print(f"  Message: {payload['message']}")

    try:
        event_types: dict[str, int] = {}
        token_content = []

        with client.stream(
            "POST",
            f"{base_url}/v1/agent/chat/stream",
            json=payload,
            timeout=60.0,
        ) as resp:
            print(f"  Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"  FAIL: {resp.read().decode()[:200]}")
                return False

            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                etype = event.get("event", "unknown")
                event_types[etype] = event_types.get(etype, 0) + 1

                if etype == "token":
                    content = event.get("data", {}).get("content", "")
                    token_content.append(content)

        print(f"  Event types: {event_types}")
        full_text = "".join(token_content)
        print(f"  Streamed text: {full_text[:200]}...")
        has_tokens = event_types.get("token", 0) > 0
        has_done = event_types.get("done", 0) > 0
        print(f"  Has tokens: {has_tokens}, Has done: {has_done}")
        return has_tokens

    except httpx.ReadTimeout:
        print("  FAIL: Stream timed out (60s)")
        return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="ShadowLink Agent smoke test")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Service base URL")
    parser.add_argument("--strategy", choices=["direct", "react", "plan_execute", "supervisor", "auto", "all"], default="all")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"ShadowLink Agent Smoke Test")
    print(f"Base URL: {base_url}")

    client = httpx.Client()
    results: list[tuple[str, bool]] = []

    # Health check first
    if not test_health(client, base_url):
        sys.exit(1)

    # Non-streaming tests
    for test in TESTS:
        strategy = test["payload"].get("strategy", "auto")
        if args.strategy != "all" and strategy != args.strategy:
            continue
        ok = test_chat(client, base_url, test)
        results.append((test["name"], ok))

    # Streaming test
    if args.strategy in ("all", "direct"):
        ok = test_stream(client, base_url)
        results.append(("SSE Streaming", ok))

    # Summary
    print("\n" + "=" * 50)
    print("RESULTS:")
    passed = 0
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if ok:
            passed += 1

    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
