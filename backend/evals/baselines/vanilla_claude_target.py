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
    max_tokens=4096,
    api_key=(
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY")
    ),
    base_url=os.environ.get("ANTHROPIC_BASE_URL"),
)


_PROMPT = """You are a QA engineer reviewing a GitHub pull request.

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

Analyze the diff and produce a structured QA impact analysis. You have ONLY the
diff above — no access to the rest of the codebase, no call graphs, no docs.
Use your judgment based purely on what the diff shows and what you can infer
from file paths, function names, and standard software engineering knowledge.

Return a JSON object with this exact shape:
{{
  "pr_summary": "<1-2 sentence summary of what this PR does>",
  "affected_components": [
    {{
      "component": "<short human-readable name of an affected area>",
      "files_changed": ["<file path from the diff>", ...],
      "impact_summary": "<1-2 sentences on what this change affects>",
      "risks": ["<specific risk 1>", "<specific risk 2>", ...],
      "confidence": "low"
    }}
  ]
}}

CRITICAL:
- Group related changes into the same component (e.g. all changes to
  `src/auth/*.go` are likely one "Auth" component).
- `risks` must be specific and grounded in the diff — not generic platitudes
  like "could introduce bugs". Each risk should reference what specifically
  could go wrong and why.
- `confidence` is always "low" — you don't have the codebase to verify.
- Return at least 1 component. If the PR is trivial, return one component
  with one risk.

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
    raw_components = parsed.get("affected_components", []) if isinstance(parsed, dict) else []

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
            "unit_tests": [],
            "integration_tests": [],
        })

    output: dict[str, Any] = {
        "affected_components": components,
        "tool_calls": [],
        "stages_seen": [],
        "checkpoints_hit": [],
        "unit_intermediate": [],
        "path_taken": "vanilla",
        "e2e_test_plans": [],
        "agent_steps": 0,
        "pr_title": pr["title"],
        "pr_summary": parsed.get("pr_summary", "") if isinstance(parsed, dict) else "",
    }

    if not components:
        output["error"] = "Claude produced no components"

    return output
