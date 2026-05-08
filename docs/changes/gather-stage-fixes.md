# Gather Stage Fixes

| Change | Why |
|--------|-----|
| `recursion_limit: 5` → `25` in forced-submit fallback | 5 is too low for even a single tool call in a ReAct graph; caused the "Recursion limit reached" crash every time the main agent hit MAX_SUBMIT_REJECTIONS. |
| `affected_components` made required (no default) | Having `= []` as a default made the JSON schema mark the field optional, so the LLM would call `submit_gather` without populating it at all. |
| Added `pre_model_hook=make_messages_modifier()` to gather agent | Large PRs produce 50KB+ tool output; without truncation the LLM's context filled up and it lost track of the requirement to build components before submitting. |
| Rejection message echoes back the file list | After a rejection the LLM was retrying blind with no new information; showing it the files it already fetched gives it the data to build components immediately. |
| Rewrote `GATHER_PROMPT` — components first, graph calls capped at 5 | The old prompt had component-grouping as Step 4 after per-file graph calls; on an 18-file PR those calls ate the entire 15-call budget before Step 4 was reached. |

# Forced-Submit Context Bloat Fix

| Change | Why |
|--------|-----|
| `e2e.py` forced-submit — skip accumulated when `process_count == 0` | When no Process nodes exist, accumulated messages are just cypher errors and failed attempts — 100K+ tokens of noise. Passing them to the forced-submit agent caused Anthropic to drop the streaming connection mid-response (`RemoteProtocolError` → `CancelledError`). Now builds a short, self-contained synthesis message from state data (components + files + pr_diff snippet) instead. |
| `e2e.py` forced-submit — trim accumulated to last 30 messages when processes exist | Even with processes, a full 20-call budget can accumulate 100K+ tokens. Trimming to the tail (where synthesis decisions live) keeps context small enough for a reliable Anthropic streaming response. |
| `integration.py` forced-submit — same last-30 trim | Same context-bloat risk: 15 integration tool calls + large `impact`/`context`/`cypher` outputs can hit 100K+ tokens. |

# E2E Process Graph Fixes

| Change | Why |
|--------|-----|
| Removed `list_processes`/`get_process` from `E2E_TOOLS` | `make_process_tools()` already injects these tools with `repo_name` baked in; keeping them in `E2E_TOOLS` too exposed the LLM to two tools with identical names — one requiring `repo=` and one not, causing unreliable calls. |
| `e2e_checkpoint_node` — added `process_count`/`process_note` to interrupt payload | Frontend now receives the process count before the user proceeds to E2E planning, so they can see the warning ("no processes detected") before the agent runs rather than after getting poor results. |
| `e2e.py` — three-way processes clause based on `repo_stats.processes` | When `processes == 0` in graph stats, agent is told not to call `list_processes` (it will fail with "Binder exception") and to derive plans from PR diff instead; when pre-fetch failed but count is non-zero, agent is told to call `list_processes` itself. |

# Submit Tool Empty-Arg Fixes

| Change | Why |
|--------|-----|
| `submit_e2e_plans` — added `= []` default + rejection guard | LLM called with `{}` (no args); `list` with no default is required in Pydantic schema, causing `ValidationError` which LangGraph re-raises (not swallowed as a ToolMessage), crashing the pipeline. The rejection message instructs the LLM to generate plans from PR diff if the process graph is empty. |
| `submit_integration_tests` — same default + rejection guard | Preemptive fix for the identical pattern: an empty call would crash the same way. Rejection message tells the LLM to infer module boundaries from the component list it already has. |
| `E2E_PROMPT` — "no processes found" fallback section | `list_processes` Cypher query throws "Binder exception" when no Process nodes exist in the graph; LLM was submitting empty plans instead of falling back to PR-diff-based plans. Prompt now explicitly instructs the LLM to use the changed file names as process names and generate plans from the diff. |

# E2E Stage Fixes

| Change | Why |
|--------|-----|
| `make_process_tools` — drop context manager, use Cypher directly | `langchain-mcp-adapters 0.1.0` removed async context manager support on `MultiServerMCPClient`; `list_processes` was failing instantly (0.01s) because `async with get_mcp_client()` throws immediately. The Cypher fallback already used the valid `get_tools()` API, so we go straight to it. |
| Batch-aware break (`pending_tools` counter) | Same parallel-batch dangling tool call risk as integration. |
| `fix_dangling_tool_calls` on accumulated messages | Same safety net as integration — raw history passed to forced-synthesis fallback could contain unmatched tool_calls. |
| `recursion_limit: 5` → `25` in forced-synthesis | Same crash risk as gather and integration. |
| Added `pre_model_hook=make_messages_modifier()` | Same context-bloat gap — `get_process` responses can be large. |

# Integration Stage Fixes

| Change | Why |
|--------|-----|
| Batch-aware break (`pending_tools` counter) | Breaking on `on_tool_start` fires mid-parallel-batch, leaving AIMessages with unmatched tool_calls; the counter defers the break until all tools in the current batch have an `on_tool_end`, so the history is always valid. |
| `fix_dangling_tool_calls` on accumulated messages | The forced-synthesis fallback was passing the raw (potentially broken) sub-agent history to Anthropic, which rejects any AIMessage whose tool_calls lack a corresponding ToolMessage. |
| `recursion_limit: 5` → `25` in forced-synthesis | Same crash as gather had — 5 steps isn't enough for the fallback agent to process accumulated context and call one tool. |
| Added `pre_model_hook=make_messages_modifier()` | Same gap as gather — large `impact`/`cypher`/`context` outputs were accumulating unbounded and bloating the context window across rounds. |
