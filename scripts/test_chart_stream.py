#!/usr/bin/env python3
"""
Test script: Run a stock analysis and inspect SSE events for chart data.
Run with server already up: cd MarginCall && uvicorn server:app --port 8080
Usage: python3 scripts/test_chart_stream.py
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8080"
APP_NAME = "stock_analyst"
USER_ID = "Trader"


def main():
    # 1. Create session
    req = urllib.request.Request(
        f"{BASE}/apps/{APP_NAME}/users/{USER_ID}/sessions",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            session = json.loads(r.read().decode())
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot connect to {BASE}. Is the server running?")
        print(f"  {e}")
        sys.exit(1)

    session_id = session.get("id")
    if not session_id:
        print("ERROR: No session id in response:", session)
        sys.exit(1)
    print(f"Session: {session_id}")

    # 2. Run analysis (SSE stream)
    print("Running analysis (tell me about AAPL)...")
    body = json.dumps({
        "app_name": APP_NAME,
        "user_id": USER_ID,
        "session_id": session_id,
        "new_message": {"role": "user", "parts": [{"text": "tell me about AAPL"}]},
        "streaming": True,
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/run_sse",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    chart_found = False
    event_count = 0
    fn_resp_count = 0
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            for line in r:
                line = line.decode().strip()
                if not line or not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:].strip())
                except json.JSONDecodeError:
                    continue
                event_count += 1

                parts = (ev.get("content") or {}).get("parts") or []
                author = ev.get("author", "?")
                for i, part in enumerate(parts):
                    part_keys = list(part.keys()) if isinstance(part, dict) else []
                    # Log part types (skip verbose text)
                    if "text" in part and part.get("text"):
                        pass  # skip text noise
                    elif "function_call" in part or "functionCall" in part:
                        fc = part.get("function_call") or part.get("functionCall") or {}
                        print(f"  [Event] author={author} part[{i}] function_call: {fc.get('name', '?')}")
                    elif "function_response" in part or "functionResponse" in part:
                        fn_resp_count += 1
                        fn_resp = part.get("function_response") or part.get("functionResponse")
                        name = (fn_resp or {}).get("name", "?")
                        resp = (fn_resp or {}).get("response")
                        has_charts = isinstance(resp, dict) and "charts" in resp
                        rk = list(resp.keys()) if isinstance(resp, dict) else []
                        print(f"  [Tool] {name}: has_charts={has_charts} response_keys={rk}")
                        if name == "fetch_technicals_with_chart":
                            chart_found = True
                            resp = fn_resp.get("response") or {}
                            print("\n--- Found fetch_technicals_with_chart response ---")
                            print(f"Keys: {list(resp.keys())}")
                            charts = resp.get("charts") or {}
                            print(f"charts keys: {list(charts.keys())}")
                            for k, v in charts.items():
                                if isinstance(v, dict):
                                    has_b64 = "image_base64" in v and bool(v.get("image_base64"))
                                    b64_len = len(v.get("image_base64") or "")
                                    print(f"  {k}: label={v.get('label')!r}, has image_base64={has_b64}, len={b64_len}")
                                else:
                                    print(f"  {k}: {type(v).__name__}")
    except urllib.error.URLError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"\nTotal events: {event_count}, function_response parts: {fn_resp_count}")
    if not chart_found:
        print("\n*** NO fetch_technicals_with_chart response found in stream ***")
        if fn_resp_count == 0:
            print("No tool responses - only pipeline-level events are streamed.")
        else:
            print("Tool response may be summarized/truncated, or tool name differs.")

    print("\n--- Verifying charts API (cache populated by pipeline) ---")
    if session_id:
        ticker = "AAPL"
        try:
            req2 = urllib.request.Request(
                f"{BASE}/api/charts?ticker={ticker}",
                method="GET",
            )
            with urllib.request.urlopen(req2, timeout=5) as r2:
                data = json.loads(r2.read().decode())
            charts = data.get("charts", {})
            has_imgs = sum(1 for v in charts.values() if isinstance(v, dict) and v.get("image_base64"))
            print(f"GET /api/charts?ticker={ticker}: {len(charts)} charts, {has_imgs} with image_base64")
        except Exception as e:
            print(f"Charts API error: {e}")


if __name__ == "__main__":
    main()
