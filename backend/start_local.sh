#!/bin/zsh
# Local dev startup — sets all required env vars and starts uvicorn

ENV_FILE="/Users/danila/PycharmProjects/Qlankr/.env"

# Parse .env, strip inline comments
while IFS= read -r line; do
    line="${line%%#*}"          # strip inline comments
    line="${line//[[:space:]]/}" # strip spaces
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" != *=* ]] && continue
    export "$line"
done < "$ENV_FILE"

# LangChain needs LANGCHAIN_* prefixed vars (not LANGSMITH_*)
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY="$LANGSMITH_API_KEY"
export LANGCHAIN_ENDPOINT="$LANGSMITH_ENDPOINT"
export LANGCHAIN_PROJECT="${LANGSMITH_PROJECT:-Qlankr}"

echo "GITHUB_TOKEN:    ${GITHUB_TOKEN:0:10}..."
echo "ANTHROPIC_KEY:   ${ANTHROPIC_API_KEY:0:10}..."
echo "LANGCHAIN_PROJECT: $LANGCHAIN_PROJECT"
echo ""

cd /Users/danila/PycharmProjects/Qlankr/backend
uvicorn main:app --reload --port 8000
