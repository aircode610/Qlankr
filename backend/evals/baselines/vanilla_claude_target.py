"""
Vanilla Claude baseline — Claude reading just the PR diff, no tools, no graph.

This is the honest baseline that answers: "How much value does Qlankr's
pipeline (GitNexus knowledge graph, multi-stage agents, MCP tools) add on top
of what Claude can do with just the diff?"

The target fetches the PR diff via the GitHub REST API and sends it to Claude
Sonnet 4.6 (same model the Qlankr agent uses) with a prompt asking for the
same `affected_components` schema Qlankr produces. No tool calls, no
knowledge graph, no checkpoints.
"""

import json
import os
import re
from typing import Any

import httpx
from langchain_anthropic import ChatAnthropic


_llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=16384,  # full analysis with unit + integration + e2e fills 4-7k easily
    api_key=(
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY")
    ),
    base_url=os.environ.get("ANTHROPIC_BASE_URL"),
)


_PROMPT = """You are a QA engineer reviewing a GitHub pull request and producing a full test plan.

PR URL: {pr_url}
PR title: {pr_title}
PR description:
{pr_body}

Changed files:
{files_list}

Full diff:
```
{pr_diff}
```

Analyze the diff and produce a structured QA analysis with unit tests,
integration tests, AND end-to-end test plans. You have ONLY the diff above —
no access to the rest of the codebase, no call graphs, no docs. Use your
judgment based purely on what the diff shows and what you can infer from file
paths, function names, and standard software engineering knowledge.

Return a JSON object with this EXACT shape — every field must be present:
{{
  "pr_summary": "<1-2 sentence summary of what this PR does>",
  "affected_components": [
    {{
      "component": "<short human-readable name of an affected area>",
      "files_changed": ["<file path from the diff>", ...],
      "impact_summary": "<1-2 sentences on what this change affects>",
      "risks": ["<specific risk 1>", "<specific risk 2>", ...],
      "confidence": "low",
      "unit_tests": [
        {{
          "target": "<specific function/class/symbol to test, e.g. ParseTimetable>",
          "test_cases": [
            {{"name": "<short test name>", "expected": "<concrete expected outcome>"}},
            ...
          ],
          "priority": "high|medium|low",
          "mocks_needed": ["<external dep to mock if any>", ...]
        }}
      ],
      "integration_tests": [
        {{
          "integration_point": "<the cross-module boundary being tested>",
          "modules_involved": ["<module A>", "<module B>"],
          "test_cases": [
            {{"name": "<short test name>", "expected": "<concrete expected outcome>"}},
            ...
          ],
          "data_setup": "<specific fixtures/state needed to reproduce the scenario>",
          "risk_level": "CRITICAL|HIGH|MEDIUM|LOW"
        }}
      ]
    }}
  ],
  "e2e_test_plans": [
    {{
      "process": "<the user-facing process being exercised, e.g. 'Vehicle order editing'>",
      "scenario": "<specific scenario this plan covers>",
      "steps": [
        "<step 1>",
        "<step 2>",
        ...
      ],
      "priority": "CRITICAL|HIGH|MEDIUM|LOW"
    }}
  ]
}}

CRITICAL RULES:
- Group related changes into one component (e.g. all changes under `src/auth/*`
  belong to one "Auth" component).
- `risks` must be specific, grounded in the diff — not "could introduce bugs".
- `unit_tests[].target` must name a specific symbol from the diff (not "the
  function"). `test_cases[].expected` must be concrete and verifiable.
- `integration_tests[].modules_involved` must contain at least 2 distinct modules.
- `integration_tests[].risk_level` uses UPPERCASE (CRITICAL/HIGH/MEDIUM/LOW).
  `unit_tests[].priority` uses lowercase (high/medium/low).
- `e2e_test_plans` covers user-facing flows the PR touches. Even bugfixes
  should have at least one E2E plan describing how a tester would verify the
  fix end-to-end.
- `confidence` is always "low" — you don't have the codebase to verify.
- Return at least 1 component, at least 1 unit test per component, and at
  least 1 e2e plan total.

Return ONLY the JSON object, no prose, no markdown fences."""


_PR_URL_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")


async def _fetch_pr(pr_url: str) -> dict:
    """Fetch PR metadata + diff + files list via GitHub REST API."""
    m = _PR_URL_RE.search(pr_url)
    if not m:
        raise ValueError(f"Could not parse PR URL: {pr_url}")
    owner, repo, num = m.groups()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN (or GH_TOKEN) must be set to fetch PR data")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"https://api.github.com/repos/{owner}/{repo}/pulls/{num}"

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        meta_resp = await client.get(base)
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        diff_resp = await client.get(
            base,
            headers={**headers, "Accept": "application/vnd.github.v3.diff"},
        )
        diff_resp.raise_for_status()
        diff = diff_resp.text

        files_resp = await client.get(f"{base}/files", params={"per_page": 100})
        files_resp.raise_for_status()
        files = [f["filename"] for f in files_resp.json()]

    return {
        "title": meta.get("title", ""),
        "body": meta.get("body") or "",
        "diff": diff,
        "files": files,
    }


def _parse_response(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {}


# GitHub diffs can be huge for large PRs. Cap at ~80k chars (~20k tokens) so we
# don't blow the context window. The prompt + schema still fits comfortably.
_MAX_DIFF_CHARS = 80_000


async def vanilla_claude_target(inputs: dict) -> dict:
    """Run Claude on just the PR diff with no tools. Return Qlankr-shape dict."""
    pr_url = inputs["pr_url"]

    try:
        pr = await _fetch_pr(pr_url)
    except Exception as e:
        return {
            "error": f"Failed to fetch PR: {e}",
            "tool_calls": [],
            "stages_seen": [],
            "path_taken": "vanilla",
        }

    diff = pr["diff"]
    if len(diff) > _MAX_DIFF_CHARS:
        diff = diff[:_MAX_DIFF_CHARS] + f"\n\n... [diff truncated — {len(pr['diff']) - _MAX_DIFF_CHARS} chars omitted]"

    prompt = _PROMPT.format(
        pr_url=pr_url,
        pr_title=pr["title"],
        pr_body=pr["body"][:2000] if pr["body"] else "(no description)",
        files_list="\n".join(f"  - {f}" for f in pr["files"]) or "(none)",
        pr_diff=diff,
    )

    try:
        response = await _llm.ainvoke([{"role": "user", "content": prompt}])
    except Exception as e:
        return {
            "error": f"LLM call failed: {e}",
            "tool_calls": [],
            "stages_seen": [],
            "path_taken": "vanilla",
        }

    parsed = _parse_response(response.content)
    if not isinstance(parsed, dict):
        parsed = {}

    raw_components = parsed.get("affected_components", []) or []
    raw_e2e_plans = parsed.get("e2e_test_plans", []) or []

    components: list[dict] = []
    for c in raw_components:
        if not isinstance(c, dict):
            continue
        components.append({
            "component": c.get("component", "Unknown"),
            "files_changed": c.get("files_changed", []) or [],
            "impact_summary": c.get("impact_summary", ""),
            "risks": c.get("risks", []) or [],
            "confidence": "low",
            "unit_tests": c.get("unit_tests", []) or [],
            "integration_tests": c.get("integration_tests", []) or [],
        })

    e2e_plans: list[dict] = []
    for p in raw_e2e_plans:
        if not isinstance(p, dict):
            continue
        e2e_plans.append({
            "process": p.get("process", ""),
            "scenario": p.get("scenario", ""),
            "steps": p.get("steps", []) or [],
            "priority": p.get("priority", "LOW"),
        })

    output: dict[str, Any] = {
        "affected_components": components,
        "tool_calls": [],
        "stages_seen": [],
        "checkpoints_hit": [],
        "unit_intermediate": [],
        "path_taken": "vanilla",
        "e2e_test_plans": e2e_plans,
        "agent_steps": 0,
        "pr_title": pr["title"],
        "pr_summary": parsed.get("pr_summary", ""),
    }

    if not components:
        output["error"] = "Claude produced no components"

    return output
