#report #sprint_1

Qlankr — Sprint 1 Report

🔹 Context
Qlankr is an AI QA tool for indie game studios. Sprint 1 focused on the full impact analysis pipeline: index a GitHub repo into a knowledge graph and run an AI agent on a PR to produce a structured QA report.

🔹 Planned / Done
- FastAPI backend + SSE streaming (index, analyze, graph endpoints) [done]
- Repo indexer: clone → gitnexus analyze → graph data via MCP [done]
- LangGraph ReAct agent with GitHub + GitNexus MCP tools [done]
- System prompt v1.3 (environment-orientation approach) [done]
- Frontend: Sigma.js knowledge graph + live agent trace + result cards [done]
- Docker Compose full stack [done]

🔹 Demo
(attach screenshot or recording)

🔹 Key Decisions
- Backend: in-memory registry only (no DB) for Sprint 1 — keeps the stack simple; repos are lost on restart but acceptable for demo scope.
- Agent: `submit_analysis` structured tool as the only return path instead of parsing JSON from the agent's final message — eliminates the output parser and makes validation deterministic.
- Agent prompt: environment-orientation over mandatory phases — prescribing steps caused the agent to call tools in a fixed order regardless of the PR; describing resources + goal lets it adapt.
- Frontend: client-side ForceAtlas2 layout (Graphology) instead of server-side — graph renders in the browser with no extra backend step and stays interactive after load.

🔹 Problems & Next Steps
- GitNexus MCP response format required reverse-engineering (prose footer, 2-hop community queries, symbol-only `impact` tool) → all fixed and documented in AGENTS.md
- Next sprint focus: evaluate agent output quality on calibration repos (Cataclysm-DDA, OpenTTD, osu!, Luanti) and tune prompt + confidence scoring on real PRs
