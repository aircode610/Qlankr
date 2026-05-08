"""
Stage 3a: Integration Test Generation

Finds cross-module integration points affected by the PR and generates
IntegrationTestSpec objects. Runs in parallel with e2e.py after the checkpoint.

Writes only to: affected_components[i].integration_tests
Does NOT touch: e2e_test_plans

Budget: 15 tool calls.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BASE_PROMPT, INTEGRATION_PROMPT
from agent.tools import filter_tools, fix_dangling_tool_calls, get_mcp_client, make_budget_warning_hook, make_messages_modifier, safe_tools

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 15


class _IntegrationTestCase(BaseModel):
    name: str
    scenario: str
    expected: str


class _IntegrationTestSpec(BaseModel):
    integration_point: str
    modules_involved: list[str]
    test_cases: list[_IntegrationTestCase]
    data_setup: str = ""
    risk_level: str = "MEDIUM"


class _IntegrationOutput(BaseModel):
    """Container for structured output fallback."""
    integration_tests: list[_IntegrationTestSpec] = Field(min_length=1)


async def run_integration(state: "AnalysisState", llm: Any) -> dict:
    components = state.get("affected_components", [])
    if not components:
        return {}

    client = get_mcp_client()
    all_tools = await client.get_tools()
    stage_tools = safe_tools(filter_tools(all_tools, "integration"))

    integration_results: list[dict] = []

    def submit_integration_tests(integration_tests: list | None = None) -> str:
        if not integration_tests:
            return (
                "REJECTED: integration_tests is empty or missing. "
                "You MUST generate at least one integration test spec. "
                "If graph tools returned no results, generate specs from the affected "
                "components and PR diff you already have — identify the module boundaries "
                "that the changed files cross and describe them. "
                "Each spec needs: integration_point, modules_involved, test_cases "
                "[{name, scenario, expected}], data_setup, risk_level. "
                "Call submit_integration_tests again with a non-empty list."
            )
        integration_results.extend(integration_tests)  # type: ignore[arg-type]
        return "Integration tests recorded."

    submit_tool = StructuredTool.from_function(
        func=submit_integration_tests,
        name="submit_integration_tests",
        description=(
            "Submit all integration test specs when done. "
            "Pass integration_tests as a list of IntegrationTestSpec objects, each with: "
            "integration_point (str), modules_involved (list), "
            "test_cases [{name, scenario, expected}], data_setup (str), "
            "risk_level ('CRITICAL'|'HIGH'|'MEDIUM'|'LOW')."
        ),
    )

    repo_name = state.get("repo_name")
    repo_clause = (
        f'Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No GitNexus repo indexed — integration analysis will be limited."
    )

    # Give the agent the component + file list so it knows what symbols to investigate
    components_block = "\n".join(
        f"- {c.get('component')}: {', '.join(c.get('files_changed', []))}"
        for c in components
    )

    # Include a short diff snippet so the agent knows what changed
    pr_diff = state.get("pr_diff", "")
    diff_section = (
        f"## PR Diff (summary of changes)\n```\n{pr_diff[:4000]}\n```\n"
        if pr_diff
        else ""
    )

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', state.get('pr_url', 'anon'))}-integration-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 40}

    human_message = HumanMessage(content=(
        f"{diff_section}"
        f"Affected components:\n{components_block}\n\n"
        f"{repo_clause}\n\n"
        "Use impact/context/query/cypher to find cross-module integration points. "
        "When done, call submit_integration_tests with all specs at once."
    ))

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{INTEGRATION_PROMPT}"),
        checkpointer=_saver,
        pre_model_hook=make_budget_warning_hook(
            budget=BUDGET,
            base_hook=make_messages_modifier(),
        ),
    )

    tool_call_count = 0
    pending_tools = 0   # tracks how many parallel tool calls are mid-flight
    budget_reached = False
    submit_rejections = 0
    MAX_SUBMIT_REJECTIONS = 3
    RESEARCH_LIMIT = BUDGET - 5

    async for event in agent.astream_events(
        {"messages": [human_message]},
        version="v2",
        config=_stage_config,
    ):
        event_type = event["event"]
        if event_type == "on_tool_start":
            pending_tools += 1
            tool_call_count += 1
            print(f"  [integration {tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_integration_tests" and tool_call_count >= RESEARCH_LIMIT:
                budget_reached = True
        elif event_type == "on_tool_end":
            pending_tools = max(0, pending_tools - 1)
            if event.get("name") == "submit_integration_tests":
                # Only break if submit actually recorded data — rejection
                # returns guidance the agent can use to retry.
                if integration_results:
                    break
                submit_rejections += 1
                print(f"  [integration] submit_integration_tests rejected ({submit_rejections}/{MAX_SUBMIT_REJECTIONS})", flush=True)
                if submit_rejections >= MAX_SUBMIT_REJECTIONS:
                    break
            # Only break once the current parallel batch is fully complete —
            # breaking mid-batch leaves dangling tool_calls with no ToolMessages,
            # which Anthropic's API rejects as invalid chat history.
            elif budget_reached and pending_tools == 0:
                break

    if not integration_results:
        print(f"  [integration] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)

        # Use a direct LLM call with explicit max_tokens and JSON instructions.
        # with_structured_output() loses bind(max_tokens=...) and hits the default
        # 4096 token limit, truncating the response to {}.
        try:
            response = await llm.ainvoke(
                [SystemMessage(content=(
                    "You are a JSON generator. Return ONLY a valid JSON object, no markdown, "
                    "no explanation, no code fences. The object must have a single key "
                    "'integration_tests' containing a non-empty array of test specs."
                ))]
                + [HumanMessage(content=(
                    f"Budget exhausted after {tool_call_count} tool calls.\n\n"
                    f"{diff_section}"
                    f"Affected components:\n{components_block}\n\n"
                    f"{repo_clause}\n\n"
                    "Generate integration test specs as a JSON object: "
                    '{"integration_tests": [{"integration_point": "ModuleA <> ModuleB", '
                    '"modules_involved": ["module_a", "module_b"], '
                    '"test_cases": [{"name": "...", "scenario": "...", "expected": "..."}], '
                    '"data_setup": "...", "risk_level": "MEDIUM"}]}. Return ONLY the JSON.'
                ))],
                max_tokens=16384,
            )
            import json
            data = json.loads(response.content)
            output = _IntegrationOutput.model_validate(data)
            integration_results.extend(
                [spec.model_dump() for spec in output.integration_tests]
            )
        except Exception as e:
            print(f"  [integration] structured output fallback failed: {e}", flush=True)

    # Distribute integration specs back into affected_components.
    # Uses token overlap (splitting on word boundaries) instead of pure substring
    # matching so that "Bug Pipeline" matches module "bug_pipeline" or "pipeline".
    # Any spec that matches no component is attached to ALL components so it is
    # never silently dropped.

    def _tokenize(text: str) -> set[str]:
        return {w for w in text.lower().replace("_", " ").replace("-", " ").split() if len(w) > 1}

    comp_tokens = [_tokenize(c.get("component", "")) for c in components]

    assigned: set[int] = set()  # indices of specs that matched at least one component
    updated = []
    for ci, comp in enumerate(components):
        matched = []
        for si, spec in enumerate(integration_results):
            spec_tokens: set[str] = set()
            for mod in spec.get("modules_involved", []):
                spec_tokens |= _tokenize(mod)
            if spec_tokens & comp_tokens[ci]:
                matched.append(spec)
                assigned.add(si)
        updated.append({**comp, "integration_tests": matched})

    # Attach unmatched specs to every component so nothing is silently lost.
    unmatched = [s for i, s in enumerate(integration_results) if i not in assigned]
    if unmatched:
        print(f"  [integration] {len(unmatched)} spec(s) matched no component — attaching to all", flush=True)
        for comp_dict in updated:
            comp_dict["integration_tests"] = comp_dict["integration_tests"] + unmatched

    return {
        "tool_calls_used": state.get("tool_calls_used", 0) + tool_call_count,
        "affected_components": updated,
    }
