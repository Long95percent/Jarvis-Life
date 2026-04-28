"""Run Jarvis response-time baseline prompts and save repeatable results.

Example:
    python scripts/jarvis_perf/run_baseline.py --base-url http://localhost:8000/v1
    python scripts/jarvis_perf/run_baseline.py --base-url http://localhost:8080/api/v1
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


DEFAULT_PROMPTS = Path(__file__).with_name("baseline_prompts.json")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "perf_baselines"


def _load_prompts(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("baseline prompts must be a JSON array")
    return data


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _session_id(case: dict[str, Any], run_id: str) -> str:
    if case.get("new_session", True):
        return f"perf-{run_id}-{case['id']}-{uuid.uuid4().hex[:8]}"
    return f"perf-{run_id}-shared-{case['category']}"


def _post_chat(client: httpx.Client, base_url: str, case: dict[str, Any], run_id: str) -> dict[str, Any]:
    payload = {
        "agent_id": case["agent_id"],
        "message": case["message"],
        "session_id": _session_id(case, run_id),
    }
    started = time.perf_counter()
    first_byte_ms: float | None = None
    status_code: int | None = None
    response_text = ""
    error = None
    headers: dict[str, str] = {}
    try:
        with client.stream("POST", f"{base_url.rstrip('/')}/jarvis/chat", json=payload) as response:
            status_code = response.status_code
            headers = dict(response.headers)
            chunks: list[bytes] = []
            for chunk in response.iter_bytes():
                if first_byte_ms is None:
                    first_byte_ms = round((time.perf_counter() - started) * 1000, 1)
                chunks.append(chunk)
            response_text = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - baseline runner records failures instead of crashing a whole run.
        error = str(exc)
    total_ms = round((time.perf_counter() - started) * 1000, 1)

    response_json: dict[str, Any] | None = None
    if response_text:
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                response_json = parsed
        except json.JSONDecodeError:
            response_json = None

    timing = {}
    if response_json and isinstance(response_json.get("timing"), dict):
        timing = response_json["timing"]

    content_len = 0
    actions_count = 0
    routed_agent = None
    if response_json:
        content = response_json.get("content")
        content_len = len(content) if isinstance(content, str) else 0
        actions = response_json.get("actions")
        actions_count = len(actions) if isinstance(actions, list) else 0
        routed_agent = response_json.get("agent_id")

    return {
        "case_id": case["id"],
        "category": case["category"],
        "agent_id": case["agent_id"],
        "routed_agent_id": routed_agent,
        "status_code": status_code,
        "ok": bool(status_code and 200 <= status_code < 300),
        "first_byte_ms": first_byte_ms,
        "total_ms": total_ms,
        "server_total_ms": timing.get("total_ms"),
        "llm_ms": _span_ms(timing, "llm_turn"),
        "memory_ms": _span_ms(timing, "memory_context"),
        "consult_ms": _span_ms(timing, "consult"),
        "persist_ms": _span_ms(timing, "persist_final_turns"),
        "actions_count": actions_count,
        "content_len": content_len,
        "error": error,
        "error_code": _extract_error_code(response_json),
        "x_request_id": headers.get("x-request-id"),
    }


def _span_ms(timing: dict[str, Any], name: str) -> float | None:
    spans = timing.get("spans")
    if not isinstance(spans, list):
        return None
    for span in spans:
        if isinstance(span, dict) and span.get("name") == name:
            value = span.get("duration_ms")
            return float(value) if isinstance(value, int | float) else None
    return None


def _extract_error_code(response_json: dict[str, Any] | None) -> str | None:
    if not response_json:
        return None
    detail = response_json.get("detail")
    if isinstance(detail, dict):
        value = detail.get("error_code")
        return str(value) if value else None
    value = response_json.get("error_code")
    return str(value) if value else None


def _write_outputs(results: list[dict[str, Any]], output_dir: Path, run_id: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"jarvis_baseline_{run_id}.json"
    csv_path = output_dir / f"jarvis_baseline_{run_id}.csv"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    fieldnames = list(results[0].keys()) if results else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    return json_path, csv_path


def _print_summary(results: list[dict[str, Any]]) -> None:
    ok_results = [row for row in results if row["ok"]]
    print(f"cases={len(results)} ok={len(ok_results)} failed={len(results) - len(ok_results)}")
    for category in sorted({row["category"] for row in results}):
        rows = [row for row in results if row["category"] == category and row["total_ms"] is not None]
        if not rows:
            continue
        totals = [float(row["total_ms"]) for row in rows]
        print(
            f"{category}: count={len(rows)} "
            f"avg={statistics.mean(totals):.1f}ms "
            f"p50={statistics.median(totals):.1f}ms "
            f"max={max(totals):.1f}ms"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Jarvis fixed prompt latency baseline")
    parser.add_argument("--base-url", default="http://localhost:8000/v1", help="API base URL ending before /jarvis")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--limit", type=int, default=0, help="Run only first N cases when > 0")
    args = parser.parse_args()

    prompts = _load_prompts(args.prompts)
    if args.limit > 0:
        prompts = prompts[: args.limit]
    run_id = _now_stamp()
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=args.timeout) as client:
        for index, case in enumerate(prompts, start=1):
            print(f"[{index}/{len(prompts)}] {case['id']} {case['agent_id']} {case['category']}")
            results.append(_post_chat(client, args.base_url, case, run_id))

    json_path, csv_path = _write_outputs(results, args.output_dir, run_id)
    _print_summary(results)
    print(f"json={json_path}")
    print(f"csv={csv_path}")


if __name__ == "__main__":
    main()

