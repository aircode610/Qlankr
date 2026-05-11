"""
Claude Code eval target — drives `claude -p` stage-by-stage for fair comparison.

Each stage is invoked as a subprocess with the orchestrator skill + stage skill
concatenated into a single prompt. Prior stage outputs are threaded through as
a JSON block so Claude Code has the same information-threading Qlankr's graph does.

Two task families:
  - Bug reproduction: 5 stages (triage, mechanics, reproduction, research, report)
  - PR analysis: 3 stages (gather, unit_tests, integration | e2e)

Output keys match Qlankr target.py exactly so all evaluators run unchanged.
has_blast_tools is always False — depth_groundedness returns N/A, not 0.0.
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

BUG_STAGES = ["triage", "mechanics", "reproduction", "research", "report"]
PR_STAGES = ["gather", "unit_tests", "integration"]

_OUTPUT_KEYS = {
    "triage": "triage",
    "mechanics": "mechanics",
    "reproduction": "reproduction_plan",
    "research": "research_findings",
    "report": "bug_report",
    "gather": "affected_components",
    "unit_tests": "unit_intermediate",
    "integration": "integration_tests",
    "e2e": "e2e_test_plans",
}


def _load_skill(path: str) -> str:
    return (SKILLS_DIR / path).read_text()


def _extract_json(text: str) -> dict:
    """3-strategy JSON extractor."""
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
    stage_skill = _load_skill(skill_path)

    prior_block = ""
    if prior:
        prior_block = "\n\nPrior stage outputs:\n" + json.dumps(prior, indent=2)

    prompt = f"{orchestrator}\n\n---\n\n{stage_skill}\n\n{base_context}{prior_block}"

    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return _extract_json(result.stdout)


async def claude_code_target_bug(inputs: dict) -> dict:
    """Eval target: Claude Code, bug reproduction pipeline."""
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
    """Eval target: Claude Code, PR analysis — integration path."""
    return await _claude_code_pr(inputs, path="integration")


async def claude_code_target_pr_e2e(inputs: dict) -> dict:
    """Eval target: Claude Code, PR analysis — e2e path."""
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
