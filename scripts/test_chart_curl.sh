#!/bin/bash
# Test chart data in SSE stream using curl.
# Run with server up: cd MarginCall && uvicorn server:app --port 8080
# Usage: ./scripts/test_chart_curl.sh

BASE="${BASE:-http://localhost:8080}"
APP="stock_analyst"
USER="Trader"

echo "1. Creating session..."
SESSION=$(curl -s -X POST "$BASE/apps/$APP/users/$USER/sessions" \
  -H "Content-Type: application/json" \
  -d '{}')
SID=$(echo "$SESSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
if [ -z "$SID" ]; then
  echo "ERROR: No session id. Response: $SESSION"
  exit 1
fi
echo "   Session: $SID"

echo "2. Running analysis (SSE stream)..."
OUT="/tmp/margincall_sse_test.txt"
curl -s -N -X POST "$BASE/run_sse" \
  -H "Content-Type: application/json" \
  -d "{\"app_name\":\"$APP\",\"user_id\":\"$USER\",\"session_id\":\"$SID\",\"new_message\":{\"role\":\"user\",\"parts\":[{\"text\":\"tell me about AAPL\"}]},\"streaming\":true}" \
  > "$OUT" 2>/dev/null

echo "3. Searching for fetch_technicals_with_chart..."
if grep -q "fetch_technicals_with_chart" "$OUT"; then
  echo "   FOUND in stream"
  echo ""
  echo "   Checking for image_base64..."
  if grep -q "image_base64" "$OUT"; then
    echo "   FOUND image_base64 in response"
  else
    echo "   NOT FOUND - chart response may be summarized/truncated"
  fi
else
  echo "   NOT FOUND - tool response may not be streamed raw"
fi

echo ""
echo "   Sample of stream (first 500 chars of a data line):"
grep "^data:" "$OUT" | head -1 | cut -c1-500
echo "..."
