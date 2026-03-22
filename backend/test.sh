#!/bin/bash
# Backend smoke test
# Usage: ./test.sh [repo_url]

REPO_URL="${1:-https://github.com/luanti-org/luanti}"
BASE="http://localhost:8000"

OWNER_REPO=$(echo "$REPO_URL" | sed 's|https://github.com/||' | sed 's|\.git||')
OWNER=$(echo "$OWNER_REPO" | cut -d'/' -f1)
REPO=$(echo "$OWNER_REPO" | cut -d'/' -f2)

echo "========================================"
echo " Qlankr Backend Smoke Test"
echo " Repo: $REPO_URL"
echo "========================================"
echo ""

# ── 1. Start backend ─────────────────────────────────────────────────────────
echo "--- Starting backend (docker compose up backend) ---"
cd "$(dirname "$0")/.."
docker compose up -d --build backend
if [ $? -ne 0 ]; then
  echo "FAIL: docker compose failed"
  exit 1
fi

echo "Waiting for Uvicorn to be ready..."
for i in $(seq 1 60); do
  if curl -sf "$BASE/health" > /dev/null 2>&1; then
    echo "Backend is up."
    break
  fi
  if [ "$i" = "60" ]; then
    echo "FAIL: backend did not become ready in time"
    docker compose logs backend --tail=30
    exit 1
  fi
  sleep 3
done
echo ""

# ── 2. Health check ───────────────────────────────────────────────────────────
echo "--- 1. GET /health ---"
HEALTH=$(curl -sf "$BASE/health")
echo "PASS: $HEALTH"
echo ""

# ── 3. POST /index ────────────────────────────────────────────────────────────
echo "--- 2. POST /index ($REPO_URL) ---"
echo "Streaming SSE events (may take a few minutes)..."
echo ""

DONE=0
ERROR=0
EVENT_TYPE=""

while IFS= read -r line; do
  if [[ "$line" == event:* ]]; then
    EVENT_TYPE=$(echo "$line" | sed 's/event: //')
    printf "  [%-12s] " "$EVENT_TYPE"
  elif [[ "$line" == data:* ]]; then
    DATA=$(echo "$line" | sed 's/data: //')
    STAGE=$(echo "$DATA"   | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stage',''))"   2>/dev/null)
    SUMMARY=$(echo "$DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',''))" 2>/dev/null)
    MESSAGE=$(echo "$DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',''))" 2>/dev/null)
    FILES=$(echo "$DATA"    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('files',''))"    2>/dev/null)
    CLUSTERS=$(echo "$DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('clusters',''))" 2>/dev/null)
    SYMBOLS=$(echo "$DATA"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('symbols',''))"  2>/dev/null)

    if [ "$EVENT_TYPE" = "index_done" ]; then
      echo "files=$FILES clusters=$CLUSTERS symbols=$SYMBOLS"
      DONE=1
    elif [ "$EVENT_TYPE" = "error" ]; then
      echo "ERROR: $MESSAGE"
      ERROR=1
    else
      [ -n "$STAGE" ] && echo "[$STAGE] $SUMMARY" || echo "$SUMMARY"
    fi
  fi
done < <(curl -sN -X POST "$BASE/index" \
  -H "Content-Type: application/json" \
  -d "{\"repo_url\":\"$REPO_URL\"}")

echo ""
if [ "$ERROR" = "1" ]; then
  echo "FAIL: /index returned an error"
  exit 1
fi
if [ "$DONE" = "0" ]; then
  echo "FAIL: /index never emitted index_done"
  exit 1
fi
echo "PASS: /index completed"
echo ""

# ── 4. GET /graph ─────────────────────────────────────────────────────────────
echo "--- 3. GET /graph/$OWNER/$REPO ---"
GRAPH=$(curl -sf "$BASE/graph/$OWNER/$REPO")
if [ $? -ne 0 ]; then
  echo "FAIL: /graph endpoint error"
  exit 1
fi

NODE_COUNT=$(echo "$GRAPH"    | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('nodes',[])))"    2>/dev/null)
EDGE_COUNT=$(echo "$GRAPH"    | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('edges',[])))"    2>/dev/null)
CLUSTER_COUNT=$(echo "$GRAPH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('clusters',[])))" 2>/dev/null)

echo "PASS: nodes=$NODE_COUNT edges=$EDGE_COUNT clusters=$CLUSTER_COUNT"
echo ""

echo "========================================"
echo " All checks passed."
echo "========================================"
