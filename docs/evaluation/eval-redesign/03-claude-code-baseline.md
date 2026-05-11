# Claude Code Baseline

Claude Code is invoked as a subprocess (`claude -p`) with structured stage-by-stage skills that mirror Qlankr's pipeline. This ensures the comparison is fair: Claude Code gets the same scaffolding and the same JSON output schema, not a single-shot prompt.

---

## Skill Directory Structure

```
backend/evals/skills/
├── bug_repro/
│   ├── skill.md         ← orchestrator: describes the full pipeline and how stages chain
│   ├── triage.md        ← stage 1 output schema
│   ├── mechanics.md     ← stage 2 output schema
│   ├── reproduction.md  ← stage 3 output schema
│   ├── research.md      ← stage 4 output schema
│   └── report.md        ← stage 5 output schema
└── pr_analysis/
    ├── skill.md         ← orchestrator
    ├── gather.md        ← stage 1: affected components
    ├── unit_tests.md    ← stage 2: unit test specs per component
    ├── integration.md   ← stage 3a: integration test specs
    └── e2e.md           ← stage 3b: e2e test plans
```

---

## Skill Design Principles

Each stage skill:
- Opens with the role and what this stage is responsible for
- Receives: the original bug description / PR URL **plus all prior stage outputs as a JSON block**
- Emits: **only the JSON for its own stage** — nothing else before or after
- Has the full output schema inline with field-level descriptions
- Has a note: "You do not have access to a code knowledge graph. Set confidence to 'low' where applicable."

The orchestrator `skill.md` explains the full pipeline and serves as the top-level prompt context. It is passed to every stage call so Claude Code always knows where it is in the pipeline.

---

## Stage Skill Schemas

### `bug_repro/triage.md` — emits:
```json
{
  "bug_category": "crash | gameplay | networking | UI | data | performance | other",
  "severity": "critical | high | medium | low",
  "keywords": ["string"],
  "initial_hypotheses": ["string"]
}
```

### `bug_repro/mechanics.md` — emits:
```json
{
  "code_paths": [{"file": "string", "symbol": "string", "role": "string"}],
  "root_cause_hypotheses": [{"hypothesis": "string", "evidence": "string", "confidence": "high | medium | low"}]
}
```

### `bug_repro/reproduction.md` — emits:
```json
{
  "prerequisites": ["string"],
  "steps": [{"step_number": 1, "action": "string", "expected_result": "string"}]
}
```

### `bug_repro/research.md` — emits:
```json
{
  "sources_queried": ["string"],
  "sources_with_results": ["string"],
  "code_graph_hits": [],
  "findings": ["string"]
}
```
Note: `code_graph_hits` is always `[]` for Claude Code — it has no knowledge graph.

### `bug_repro/report.md` — emits:
```json
{
  "title": "string",
  "severity": "critical | high | medium | low",
  "root_cause": "string",
  "reproduction_steps": [{"step": 1, "action": "string", "expected": "string"}],
  "affected_components": ["string"],
  "recommendations": ["string"],
  "confidence": "high | medium | low",
  "evidence": {
    "log_entries": [],
    "doc_references": [],
    "related_issues": [],
    "network_traces": []
  }
}
```

---

## `claude_code_target.py`

```python
import asyncio
import json
import re
import subprocess
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

BUG_STAGES = ["triage", "mechanics", "reproduction", "research", "report"]
PR_STAGES  = ["gather", "unit_tests", "integration"]  # or e2e

_OUTPUT_KEYS = {
    "triage":       "triage",
    "mechanics":    "mechanics",
    "reproduction": "reproduction_plan",
    "research":     "research_findings",
    "report":       "bug_report",
    "gather":       "affected_components",
    "unit_tests":   "unit_intermediate",
    "integration":  "integration_tests",
    "e2e":          "e2e_test_plans",
}


def _load_skill(path: str) -> str:
    return (SKILLS_DIR / path).read_text()


def _extract_json(text: str) -> dict:
    """3-strategy JSON extractor (mirrors bug_evaluators._parse_judge_response)."""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            return json.loads(fence.group(1))
    except Exception:
        pass
    try:
        obj = re.search(r"\{.*\}", text, re.DOTALL)
        if obj:
            return json.loads(obj.group(0))
    except Exception:
        pass
    return {}


def _run_stage(skill_path: str, base_context: str, prior: dict) -> dict:
    orchestrator = _load_skill(f"{skill_path.split('/')[0]}/skill.md")
    stage_skill  = _load_skill(skill_path)

    prior_block = ""
    if prior:
        prior_block = "\n\nPrior stage outputs:\n" + json.dumps(prior, indent=2)

    prompt = f"{orchestrator}\n\n---\n\n{stage_skill}\n\n{base_context}{prior_block}"

    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True, text=True, timeout=120,
    )
    return _extract_json(result.stdout)


async def claude_code_target_bug(inputs: dict) -> dict:
    description = inputs.get("description", "")
    environment = inputs.get("environment", "")
    base = f"Bug description:\n{description}\n\nEnvironment: {environment}"

    prior: dict = {}
    output: dict = {"has_blast_tools": False, "tool_transcripts": [], "tool_calls": []}

    for stage in BUG_STAGES:
        parsed = await asyncio.to_thread(_run_stage, f"bug_repro/{stage}.md", base, prior)
        key = _OUTPUT_KEYS[stage]
        output[key] = parsed
        prior[key] = parsed

    return output


async def claude_code_target_pr_integration(inputs: dict) -> dict:
    """Eval target: Claude Code, integration path."""
    return await _claude_code_pr(inputs, path="integration")


async def claude_code_target_pr_e2e(inputs: dict) -> dict:
    """Eval target: Claude Code, e2e path."""
    return await _claude_code_pr(inputs, path="e2e")


async def _claude_code_pr(inputs: dict, path: str) -> dict:
    pr_url = inputs.get("pr_url", "")
    base = f"PR URL: {pr_url}"

    stages = PR_STAGES if path != "e2e" else ["gather", "unit_tests", "e2e"]
    prior: dict = {}
    output: dict = {
        "has_blast_tools": False,
        "tool_transcripts": [],
        "tool_calls": [],
        "path_taken": path,
    }

    for stage in stages:
        parsed = await asyncio.to_thread(_run_stage, f"pr_analysis/{stage}.md", base, prior)
        key = _OUTPUT_KEYS[stage]
        output[key] = parsed
        prior[key] = parsed

    return output
```

---

## LangSmith Experiment Naming

Two experiments run per dataset, side-by-side in LangSmith:

| Dataset | Qlankr experiment | Claude Code experiment |
|---|---|---|
| `qlankr-eval-github` | `qlankr-integration-github` | `claudecode-integration-github` |
| `qlankr-eval-bugs-real` | `qlankr-bugs-real` | `claudecode-bugs-real` |
| `qlankr-eval-bugs-synthetic` | `qlankr-bugs-synthetic` | `claudecode-bugs-synthetic` |

`depth_groundedness` returns `score: None` for Claude Code rows — LangSmith renders this as N/A rather than 0.0, keeping the comparison honest.

---

## Why This Is Fair

- Claude Code gets the same structured pipeline scaffolding (5 stages for bugs, 3 for PR)
- Each stage gets prior outputs as context — same information threading Qlankr's graph does
- Claude Code is not penalized on `depth_groundedness` (skipped entirely)
- Claude Code is not expected to produce `code_graph_hits` — that field is always `[]`
- The only structural difference: Qlankr has access to GitNexus tools; Claude Code has file reading only
