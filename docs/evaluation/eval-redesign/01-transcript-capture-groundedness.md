# Transcript Capture & Groundedness Redesign

---

## Problem

The current `groundedness` evaluator in `evaluators.py`:

```python
async def groundedness(inputs: dict, outputs: dict) -> dict:
    prompt = f"PR URL: {inputs['pr_url']}\n\nThe agent produced this analysis:\n{formatted}"
```

The judge receives a URL it cannot visit. It scores claims blind. For transitive findings from GitNexus blast tools (`impact`, `context`, `cypher`), a judge reading only the PR diff would incorrectly flag these as hallucinations — they are not in the diff but they are real call-graph dependencies.

---

## Fix 1 — Capture Full Tool Transcripts in `target.py`

### Current state

`_run_full_pipeline` appends tool *names* only:

```python
if etype == "agent_step":
    tool_calls.append(data["tool"])
```

### Change

Append full `{tool, input, output}` dicts to a parallel list:

```python
tool_calls: list[str] = []
tool_transcripts: list[dict] = []

if etype == "agent_step":
    tool_calls.append(data["tool"])
    tool_transcripts.append({
        "tool": data["tool"],
        "input": data.get("input", {}),
        "output": data.get("output", {}),
    })
```

The agent event stream must emit `input` and `output` alongside the tool name. This requires a change to the `agent_step` event emission in `agent.py` — the event currently only emits `tool` (the name). It must also emit `input` (the tool call arguments dict) and `output` (the tool response dict). LangGraph's `ToolMessage` already contains both fields — expose them in the SSE event payload.

### Output dict change

```python
output = {
    "tool_calls": tool_calls,           # existing — names only
    "tool_transcripts": tool_transcripts,  # new — full input+output
    "has_blast_tools": True,            # Qlankr always True
    ...
}
```

Claude Code's target function sets `"has_blast_tools": False` and `"tool_transcripts": []`.

---

## Fix 2 — Split `groundedness` into Two Evaluators

### `surface_groundedness` — both Qlankr and Claude Code

Fetches the real PR diff via GitHub REST API during evaluation:

```
GET https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files
Authorization: Bearer {GITHUB_TOKEN}
```

Parse `pr_url` to extract `owner`, `repo`, `number`. Cache the response per PR URL to avoid redundant fetches when the same PR runs across multiple experiments.

**Judge prompt structure:**

```
PR diff (actual file patches — {N} files changed):
<per-file: filename, additions, deletions, patch hunks>

Agent's component claims (impact summaries and risks):
<formatted_components>

Evaluate: are the claims about DIRECTLY changed code verifiable from this diff?
Do NOT penalize claims about transitive/downstream effects — those are scored separately.

Score 0.0–1.0:
- 1.0 = every claim maps to a real change visible in the diff
- 0.7 = mostly grounded, one or two minor extrapolations
- 0.4 = some claims reference files not in the diff without explanation
- 0.0 = claims contradict the diff or describe unrelated code

Return ONLY: {"score": <float>, "reasoning": "<1-2 sentences>"}
```

**Skip condition:** if the diff fetch fails (rate limit, private repo without token), fall back to `score: None` with comment `"diff unavailable"` rather than scoring blind.

---

### `depth_groundedness` — Qlankr only

Reads GitNexus entries from `tool_transcripts`:

```python
async def depth_groundedness(inputs: dict, outputs: dict) -> dict:
    if not outputs.get("has_blast_tools", False):
        return {"key": "depth_groundedness", "score": None, "comment": "N/A (no blast tools)"}

    blast_tools = {"impact", "context", "cypher", "query", "detect_changes"}
    transcripts = [
        t for t in outputs.get("tool_transcripts", [])
        if t["tool"] in blast_tools
    ]

    if not transcripts:
        return {"key": "depth_groundedness", "score": 0.0, "comment": "No blast tool calls found"}
    ...
```

**Judge prompt structure:**

```
GitNexus tool outputs collected during this run:
  impact("src/auth/tokens.py") →
    { "risk": "HIGH", "affected_processes": ["checkout_flow", "refund_flow"], ... }
  context("refresh_token") →
    { "callers": ["PaymentService.charge", "SessionManager.renew"], ... }

Agent's transitive/downstream claims (claims not directly visible in the diff):
<claims from impact_summary and risks that reference components beyond the changed files>

Evaluate: are these transitive claims consistent with what the GitNexus tools actually returned?
A claim is grounded if the tool output contains the dependency or process the agent describes.
A claim is ungrounded if the agent says X is affected but no tool output mentions X.

Score 0.0–1.0:
- 1.0 = every transitive claim is directly supported by a tool return value
- 0.7 = most claims supported, one extrapolation beyond tool output
- 0.3 = agent made claims about components not present in any tool output
- 0.0 = transitive claims fabricated, contradict tool outputs

Return ONLY: {"score": <float>, "reasoning": "<1-2 sentences>"}
```

---

## Summary of Changes

| Location | Change |
|---|---|
| `agent.py` | Emit `input` + `output` in `agent_step` events |
| `target.py` | Collect `tool_transcripts`; add `has_blast_tools: True` |
| `claude_code_target.py` | Set `has_blast_tools: False`, `tool_transcripts: []` |
| `evaluators.py` | Remove `groundedness`; add `surface_groundedness` + `depth_groundedness` |
| `run_evals.py` | Replace `groundedness` with both new evaluators in `_BASE_EVALUATORS` |
