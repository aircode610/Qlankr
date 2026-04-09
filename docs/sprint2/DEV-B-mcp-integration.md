# Dev B: GitNexus MCP Integration + Embeddings + Container Runner

**Branch:** `devb/mcp-tools`
**Depends on:** Dev C's models (rebase once merged)
**Files owned:**
- `backend/agent/tools.py` — MCP client setup, all 16 tools, transport config
- `backend/agent/prefetch.py` — NEW: pre-fetch PR data + processes + stats before agent runs
- `backend/agent/prompts.py` — NEW: stage-specific system prompts (co-owned with Dev A)
- `backend/indexer.py` — update: `--embeddings` flag, process-aware indexing
- `backend/runner/Dockerfile.runner` — NEW (Phase 4)
- `backend/runner/run_tests.py` — NEW (Phase 4)

**Shared files (coordinate with):**
- `backend/models.py` — owned by Dev C, you import from it
- `backend/agent/agent.py` — owned by Dev A, they call your `get_mcp_client()` and `prefetch_context()`

---

## Overview

You own the data layer between Qlankr and GitNexus. Your code makes all 16 MCP tools available, enables semantic embeddings, exposes process resources, and pre-fetches context to reduce agent tool calls. In Phase 4, you also build the container-based test runner.

---

## Part 1: MCP Tools Expansion

### Current state (`backend/agent/tools.py`)

```python
# Current: only configures 2 MCP servers via stdio
"gitnexus": {
    "transport": "stdio",
    "command": "gitnexus",
    "args": ["mcp"],
    "env": {**os.environ},
}
```

The agent gets ~6 GitNexus tools: `impact`, `context`, `query`, `cypher`, `detect_changes`, `list_repos`.

### Target state

Expose all 16 GitNexus MCP tools + process resource URIs.

**GitNexus tool inventory (all must be available):**

| Tool | Category | Used by stage |
|------|----------|---------------|
| `query` | Per-repo | gather, integration, e2e |
| `context` | Per-repo | unit, integration |
| `impact` | Per-repo | integration, e2e |
| `detect_changes` | Per-repo | gather |
| `rename` | Per-repo | (available but rarely used) |
| `cypher` | Per-repo | gather, unit, integration |
| `list_repos` | Global | gather |
| `group_list` | Multi-repo | (future: mono-repo support) |
| `group_sync` | Multi-repo | (future) |
| `group_contracts` | Multi-repo | (future) |
| `group_query` | Multi-repo | (future) |
| `group_status` | Multi-repo | (future) |

**Resource URIs (must be accessible as tools or resource reads):**

| URI | Returns | Used by stage |
|-----|---------|---------------|
| `gitnexus://repo/{name}/processes` | List of all execution flows | gather (pre-fetch), e2e |
| `gitnexus://repo/{name}/process/{name}` | Full execution flow detail | e2e |

### Implementation

```python
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

def get_mcp_client() -> MultiServerMCPClient:
    """Returns MCP client with GitHub + GitNexus servers."""
    return MultiServerMCPClient({
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                **os.environ,
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_TOKEN"],
            },
        },
        "gitnexus": {
            "transport": "stdio",
            "command": "gitnexus",
            "args": ["mcp"],
            "env": {**os.environ},
        },
    })
```

**Key change:** Remove any tool filtering. Currently there's no explicit filter, but verify all 16 tools appear when you call `client.get_tools()`. If some are missing, check if `gitnexus mcp` needs flags to expose them all.

### Tool Subsets for Stages

Dev A's stages will filter tools by name. You provide a helper:

```python
# Tool name lists for each stage
GATHER_TOOLS = {
    "get_pull_request", "get_pull_request_files", "get_pull_request_comments",
    "get_file_contents", "list_directory", "search_code", "get_commits",
    "list_repos", "cypher", "detect_changes",
}

UNIT_TOOLS = {
    "context", "cypher", "get_file_contents",
}

INTEGRATION_TOOLS = {
    "impact", "context", "query", "cypher",
}

E2E_TOOLS = {
    "impact", "query", "cypher",
    # + process resource reads (handled separately)
}

def filter_tools(all_tools: list, stage: str) -> list:
    """Return only tools allowed for the given stage."""
    allowed = {
        "gather": GATHER_TOOLS,
        "unit": UNIT_TOOLS,
        "integration": INTEGRATION_TOOLS,
        "e2e": E2E_TOOLS,
    }[stage]
    return [t for t in all_tools if t.name in allowed]
```

---

## Part 2: Process Resource Access

GitNexus exposes process data via MCP resource URIs. These need to be accessible to the agent.

### Option A: Wrap as tools (recommended)

Create wrapper tools that read MCP resources:

```python
from langchain_core.tools import StructuredTool

def make_process_tools(client, repo_name: str) -> list[StructuredTool]:
    """Create tools that read GitNexus process resources."""

    async def list_processes() -> str:
        """List all execution flows (processes) in the indexed repo."""
        result = await client.read_resource(f"gitnexus://repo/{repo_name}/processes")
        return result

    async def get_process(process_name: str) -> str:
        """Get the full execution flow for a specific process."""
        result = await client.read_resource(f"gitnexus://repo/{repo_name}/process/{process_name}")
        return result

    return [
        StructuredTool.from_function(func=list_processes, name="list_processes", ...),
        StructuredTool.from_function(func=get_process, name="get_process", ...),
    ]
```

### Option B: Pre-fetch only

If MCP resource reads aren't supported by `langchain-mcp-adapters`, fetch processes via cypher:

```cypher
MATCH (p:Process) RETURN p.name, p.description LIMIT 100
```

And for individual process steps:

```cypher
MATCH (p:Process {name: '<name>'})<-[r:CodeRelation]-(s)
WHERE r.type='STEP_IN_PROCESS'
RETURN s.name, s.filePath, r.order ORDER BY r.order
```

---

## Part 3: Prefetch Module (`backend/agent/prefetch.py`)

Pre-fetch context before the agent starts to save tool calls and provide richer initial context.

```python
async def prefetch_context(pr_url: str, repo_name: str | None) -> dict:
    """
    Pre-fetch PR data and GitNexus context before agent runs.
    Called by Dev A's run_agent() before building the StateGraph.

    Returns:
        {
            "processes": [...],        # list of process names + descriptions
            "stats": {...},            # repo stats (files, nodes, edges, communities)
            "changed_symbols": [...],  # symbols defined in changed files
        }
    """
    result = {"processes": [], "stats": {}, "changed_symbols": []}

    if not repo_name:
        return result

    async with get_mcp_client() as client:
        tools = await client.get_tools()

        # Fetch repo stats via list_repos
        stats_result = await _call_tool(tools, "list_repos", {})
        result["stats"] = _parse_repo_stats(stats_result, repo_name)

        # Fetch process list
        try:
            processes_result = await client.read_resource(
                f"gitnexus://repo/{repo_name}/processes"
            )
            result["processes"] = _parse_processes(processes_result)
        except Exception:
            # Fallback: cypher query
            cypher_result = await _call_tool(tools, "cypher", {
                "query": "MATCH (p:Process) RETURN p.name LIMIT 100",
                "repo": repo_name,
            })
            result["processes"] = _parse_cypher_processes(cypher_result)

        # Fetch changed symbols (requires PR file list — Dev A passes this)
        # This is called after gather stage, not before

    return result
```

---

## Part 4: Embeddings in Indexer (`backend/indexer.py`)

### Current indexing command

```bash
gitnexus analyze /path/to/repo
```

### Updated command

```bash
gitnexus analyze --embeddings /path/to/repo
```

**Changes to `indexer.py`:**

1. Add `--embeddings` flag to the subprocess command
2. Update the stage detection to recognize embedding-related progress output
3. Add a new `IndexStepEvent` stage: `"embeddings"` between `"search"` and completion
4. Handle the longer indexing time (embeddings are slower — add progress updates)

```python
# In the indexing subprocess call:
cmd = ["gitnexus", "analyze", "--embeddings", repo_path]
```

**New stage in SSE stream:**
```
event: index_step  { stage: "embeddings", summary: "Generating semantic embeddings..." }
```

---

## Part 5: Container Runner (Phase 4)

This is the last step — only start after Phases 1-3 are stable.

### `backend/runner/Dockerfile.runner`

```dockerfile
# Base image with common runtimes
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    git curl python3 python3-pip nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Entry point script
COPY run_tests.py /usr/local/bin/run_tests.py
RUN chmod +x /usr/local/bin/run_tests.py

ENTRYPOINT ["python3", "/usr/local/bin/run_tests.py"]
```

### `backend/runner/run_tests.py`

In-container script that:
1. Receives: repo URL, commit SHA, list of generated test files (as JSON via stdin or env)
2. Clones the repo at the specified commit
3. Detects the project's test framework (look for pytest.ini, package.json scripts, CMakeLists.txt, etc.)
4. Installs dependencies
5. Writes the generated test files to the appropriate locations
6. Runs the test suite
7. Streams results as JSON lines to stdout

```python
#!/usr/bin/env python3
"""In-container test runner. Reads config from stdin, streams results to stdout."""

import json
import subprocess
import sys
import time

def main():
    config = json.load(sys.stdin)
    repo_url = config["repo_url"]
    commit_sha = config["commit_sha"]
    test_files = config["test_files"]  # [{path: str, content: str}, ...]

    # Clone
    subprocess.run(["git", "clone", repo_url, "/workspace/repo"], check=True)
    subprocess.run(["git", "checkout", commit_sha], cwd="/workspace/repo", check=True)

    # Detect framework
    framework = detect_framework("/workspace/repo")

    # Install deps
    install_deps("/workspace/repo", framework)

    # Write test files
    for tf in test_files:
        path = f"/workspace/repo/{tf['path']}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(tf["content"])

    # Run tests and stream results
    for result in run_tests("/workspace/repo", framework):
        print(json.dumps(result), flush=True)
```

### Resource Limits

`executor.py` is owned by Dev C (they own the `/run-tests` endpoint that calls it). Coordinate with Dev C on the container config interface so `executor.py` knows how to read test files from the session.

### Resource Limits

| Limit | Value | Reason |
|-------|-------|--------|
| Memory | 512 MB | Prevent OOM from large test suites |
| CPU | 50% of 1 core | Don't starve the host |
| Timeout | 300 seconds | Kill runaway tests |
| Network | Disabled | Tests shouldn't make external calls |
| Disk | 1 GB | Prevent filling host disk |

---

## Part 5: Stage Prompts (`backend/agent/prompts.py`)

Dev A's stage nodes inject a stage-specific prompt on top of a shared base. You own this file because stage prompts mirror the tool subsets you define — the tools available in a stage dictate what the agent should be told to do.

```python
BASE_PROMPT = """You are Qlankr, an AI QA assistant for game studios.
You have access to a GitNexus knowledge graph of the repository.
[environment, graph schema, tool descriptions — adapt from current prompts.py]
"""

GATHER_PROMPT = """## Current Stage: Context Gathering
Your goal is to pre-fetch all context the downstream stages need.
Retrieve PR metadata, changed files, defined symbols, and process list.
Budget: 10 tool calls. Do not analyse — only collect.
"""

UNIT_PROMPT = """## Current Stage: Unit Test Generation
For each affected component, generate UnitTestSpec objects.
Identify the function signature, 2-5 test cases (happy path, edge cases, errors),
and which dependencies to mock. Output must conform to UnitTestSpec schema.
Budget: 15 tool calls.
"""

INTEGRATION_PROMPT = """## Current Stage: Integration Test Generation
Identify cross-module integration points via impact and context tools.
For each module pair, generate IntegrationTestSpec objects.
Rate risk based on blast radius. Do not guess module boundaries.
Budget: 15 tool calls.
"""

E2E_PROMPT = """## Current Stage: E2E Test Planning
Convert affected execution flows (processes) into user-facing test scenarios.
Write clear preconditions, numbered steps, and expected outcomes.
If user_context is provided, create a targeted regression test for that scenario.
Budget: 20 tool calls.
"""
```

Dev A imports these constants and passes them to the sub-agent for each stage. If you need to update a prompt, coordinate with Dev A so the stage logic stays consistent.

---

## Acceptance Criteria

### Phase 1-3 (MCP + Embeddings + Prefetch)
- [ ] `client.get_tools()` returns all 16 GitNexus tools
- [ ] `filter_tools()` correctly subsets tools per stage
- [ ] Process resource URIs are accessible (as tools or cypher fallback)
- [ ] `prefetch_context()` returns processes, stats for an indexed repo
- [ ] `prefetch_context()` returns empty dicts gracefully for non-indexed repos
- [ ] `POST /index` runs with `--embeddings` flag
- [ ] `query` tool returns semantically ranked results after embedding-enabled indexing
- [ ] Indexing SSE stream includes `"embeddings"` stage
- [ ] Tool call count in agent traces drops after prefetch is enabled

### Phase 4 (Container Runner)
- [ ] Runner container builds and starts
- [ ] Container clones repo at correct commit
- [ ] Framework detection works for pytest, jest, and gtest
- [ ] Generated test files are written to correct paths
- [ ] Test results stream as JSON lines
- [ ] Memory/CPU/timeout limits enforced (enforced by Dev C's executor, configured here)
- [ ] Network disabled in container

### Phase 1 (Prompts)
- [ ] `prompts.py` exports `BASE_PROMPT`, `GATHER_PROMPT`, `UNIT_PROMPT`, `INTEGRATION_PROMPT`, `E2E_PROMPT`
- [ ] Stage prompts reference only tools available in that stage's tool subset
- [ ] Dev A can import and use prompts without modification

---

## Testing

Add to `backend/tests/`:

**`test_tools.py`** (new):
- Test that `get_mcp_client()` configures both servers
- Test `filter_tools()` for each stage returns correct subset
- Test that no stage gets access to `submit_analysis` or unexpected tools

**`test_prefetch.py`** (new):
- Mock MCP client, test `prefetch_context()` returns correct structure
- Test fallback when resource URIs aren't available
- Test graceful handling of non-indexed repos

**`test_indexer_async.py`** (update):
- Test that `--embeddings` flag is passed to subprocess
- Test `"embeddings"` stage appears in SSE events

**`test_prompts.py`** (new):
- Test that all 5 prompt constants are exported and non-empty
- Test that each stage prompt only references tools in its allowed subset
