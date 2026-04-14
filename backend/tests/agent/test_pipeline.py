"""
End-to-end pipeline test.

Drives the full graph through all checkpoints automatically:
  gather → unit_tests → checkpoint_unit → choice → integration_tests → submit

Usage:
  # Start the backend first (in another terminal):
  #   cd backend && uvicorn main:app --reload --port 8000
  #
  # Then run:
  #   python3 tests/agent/test_pipeline.py [PR_URL] [--choice integration|e2e]

Env vars required:
  GITHUB_TOKEN      — GitHub personal access token
  ANTHROPIC_API_KEY — or ANTHROPIC_AUTH_TOKEN
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"

DEFAULT_PR = "https://github.com/minetest/minetest/pull/15600"


def parse_sse_line(line: str) -> dict | None:
    """Parse a single SSE data line into a dict."""
    if line.startswith("data:"):
        try:
            return json.loads(line[5:].strip())
        except json.JSONDecodeError:
            return None
    return None


def stream_events(url: str, payload: dict | None = None) -> list[dict]:
    """POST to url, stream SSE events, return list of parsed event dicts."""
    events = []
    method = "POST"
    print(f"\n{'='*60}")
    print(f"→ {method} {url}")
    if payload:
        print(f"  body: {json.dumps(payload)}")
    print()

    with httpx.Client(timeout=300.0) as client:
        with client.stream(method, url, json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                event = parse_sse_line(line)
                if event is None:
                    continue

                event_type = event.get("type", "?")
                events.append(event)

                if event_type == "stage_change":
                    print(f"  [stage]      {event.get('stage')} — {event.get('summary')}")
                elif event_type == "agent_step":
                    print(f"  [tool]       {event.get('tool')}: {event.get('summary')}")
                elif event_type == "checkpoint":
                    print(f"  [CHECKPOINT] type={event.get('interrupt_type')}  session={event.get('session_id')}")
                    payload_text = event.get("payload", {}).get("prompt", "")
                    if payload_text:
                        print(f"               {payload_text[:120]}")
                elif event_type == "result":
                    print(f"  [RESULT]     {event.get('pr_title')}")
                    comps = event.get("affected_components", [])
                    print(f"               {len(comps)} components, {event.get('agent_steps')} tool calls")
                elif event_type == "error":
                    print(f"  [ERROR]      {event.get('message')}")
                else:
                    print(f"  [{event_type}]  {str(event)[:80]}")

    return events


def find_checkpoint(events: list[dict]) -> dict | None:
    for e in events:
        if e.get("type") == "checkpoint":
            return e
    return None


def find_result(events: list[dict]) -> dict | None:
    for e in events:
        if e.get("type") == "result":
            return e
    return None


def find_error(events: list[dict]) -> dict | None:
    for e in events:
        if e.get("type") == "error":
            return e
    return None


def ask(prompt: str) -> str:
    """Read a line from stdin, stripping whitespace."""
    return input(f"\n{prompt}\n> ").strip()


def handle_checkpoint(cp: dict) -> dict:
    """Show checkpoint to human and collect their response."""
    interrupt_type = cp["interrupt_type"]
    payload = cp.get("payload", {})

    print("\n" + "="*60)
    print(f"CHECKPOINT — {interrupt_type}")
    print("="*60)

    if interrupt_type == "checkpoint":
        # Show unit test results
        intermediate = payload.get("intermediate_result", {})
        components = intermediate.get("affected_components", [])
        print(f"\nUnit tests generated for {len(components)} component(s):\n")
        for comp in components:
            tests = comp.get("unit_tests", [])
            print(f"  {comp.get('component')} — {len(tests)} unit test spec(s)")
            for t in tests[:2]:  # show first 2
                print(f"    • {t.get('target', '?')} [{t.get('priority', '?')}]")
                for tc in t.get("test_cases", [])[:2]:
                    print(f"      - {tc.get('name', '?')}")
            if len(tests) > 2:
                print(f"    ... and {len(tests) - 2} more")

        print(f"\n{payload.get('prompt', '')}")
        action = ask("Your choice [approve / refine]:") or "approve"

        if action == "refine":
            feedback = ask("What should be improved?")
            return {"action": "refine", "feedback": feedback}
        return {"action": "approve"}

    elif interrupt_type == "choice":
        print(f"\n{payload.get('prompt', '')}")
        choice = ask("Your choice [integration / e2e]:") or "integration"
        return {"choice": choice}

    elif interrupt_type == "e2e_context":
        print(f"\n{payload.get('prompt', '')}")
        context = ask("Your context (or press Enter to skip):")
        return {"context": context}

    elif interrupt_type == "question":
        question = payload.get("question", "?")
        print(f"\nThe agent is asking:\n  {question}")
        answer = ask("Your answer:")
        return {"answer": answer}

    else:
        print(f"Unknown interrupt type: {interrupt_type!r}")
        sys.exit(1)


def run_pipeline(pr_url: str, auto: bool = False, stage_choice: str = "integration"):
    print(f"\nPipeline test — PR: {pr_url}")
    print(f"Mode: {'auto' if auto else 'interactive (human-in-the-loop)'}")

    # ── Step 1: Start analysis ────────────────────────────────────────────────
    events = stream_events(f"{BASE_URL}/analyze", {"pr_url": pr_url})

    err = find_error(events)
    if err:
        print(f"\nFAILED at start: {err['message']}")
        sys.exit(1)

    result = find_result(events)
    if result:
        print("\nCompleted without checkpoints")
        _print_result(result)
        return

    cp = find_checkpoint(events)
    if not cp:
        print("\nFAILED: no checkpoint or result received")
        sys.exit(1)

    session_id = cp["session_id"]
    print(f"\n  session_id = {session_id}")

    # ── Step 2: Drive through checkpoints ────────────────────────────────────
    max_steps = 10
    for step in range(max_steps):
        interrupt_type = cp["interrupt_type"]

        if auto:
            # Auto mode — no human input
            if interrupt_type == "checkpoint":
                resume = {"action": "approve"}
                print(f"\n[auto] Approving unit checkpoint")
            elif interrupt_type == "choice":
                resume = {"choice": stage_choice}
                print(f"\n[auto] Choosing: {stage_choice}")
            elif interrupt_type == "e2e_context":
                resume = {"context": ""}
                print(f"\n[auto] Skipping e2e context")
            elif interrupt_type == "question":
                resume = {"answer": "Please determine from the PR context."}
                print(f"\n[auto] Answering agent question")
            else:
                print(f"\nUnknown interrupt: {interrupt_type}")
                sys.exit(1)
        else:
            # Interactive mode — ask the human
            resume = handle_checkpoint(cp)

        events = stream_events(
            f"{BASE_URL}/analyze/{session_id}/continue",
            resume,
        )

        err = find_error(events)
        if err:
            print(f"\nFAILED at step {step + 1}: {err['message']}")
            sys.exit(1)

        result = find_result(events)
        if result:
            print("\n" + "="*60)
            print("PIPELINE COMPLETE")
            _print_result(result)
            return

        cp = find_checkpoint(events)
        if not cp:
            print(f"\nFAILED at step {step + 1}: no checkpoint or result")
            sys.exit(1)

    print(f"\nFAILED: exceeded {max_steps} checkpoint steps")
    sys.exit(1)


def _print_result(result: dict):
    print(f"\nPR:      {result.get('pr_title')}")
    print(f"URL:     {result.get('pr_url')}")
    print(f"Summary: {result.get('pr_summary', '')[:200]}")
    print(f"Steps:   {result.get('agent_steps')}")
    print(f"\nAffected components ({len(result.get('affected_components', []))}):")
    for comp in result.get("affected_components", []):
        name = comp.get("component", "?")
        unit = comp.get("unit_tests", [])
        integ = comp.get("integration_tests", [])
        print(f"  - {name}  (unit={len(unit)}, integration={len(integ)})")

    e2e = result.get("e2e_test_plans", [])
    if e2e:
        print(f"\nE2E plans ({len(e2e)}):")
        for plan in e2e:
            print(f"  - [{plan.get('priority')}] {plan.get('scenario')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="End-to-end pipeline test")
    parser.add_argument("pr_url", nargs="?", default=DEFAULT_PR, help="GitHub PR URL")
    parser.add_argument(
        "--auto", action="store_true",
        help="Auto-approve all checkpoints (no human input)"
    )
    parser.add_argument(
        "--choice", default="integration", choices=["integration", "e2e"],
        help="Stage to pick in auto mode (default: integration)"
    )
    args = parser.parse_args()

    run_pipeline(args.pr_url, auto=args.auto, stage_choice=args.choice)
