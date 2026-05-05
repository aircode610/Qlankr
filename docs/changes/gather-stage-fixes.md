# Gather Stage Fixes

| Change | Why |
|--------|-----|
| `recursion_limit: 5` → `25` in forced-submit fallback | 5 is too low for even a single tool call in a ReAct graph; caused the "Recursion limit reached" crash every time the main agent hit MAX_SUBMIT_REJECTIONS. |
| `affected_components` made required (no default) | Having `= []` as a default made the JSON schema mark the field optional, so the LLM would call `submit_gather` without populating it at all. |
| Added `pre_model_hook=make_messages_modifier()` to gather agent | Large PRs produce 50KB+ tool output; without truncation the LLM's context filled up and it lost track of the requirement to build components before submitting. |
| Rejection message echoes back the file list | After a rejection the LLM was retrying blind with no new information; showing it the files it already fetched gives it the data to build components immediately. |
| Rewrote `GATHER_PROMPT` — components first, graph calls capped at 5 | The old prompt had component-grouping as Step 4 after per-file graph calls; on an 18-file PR those calls ate the entire 15-call budget before Step 4 was reached. |

# Integration Stage Fixes

| Change | Why |
|--------|-----|
| Batch-aware break (`pending_tools` counter) | Breaking on `on_tool_start` fires mid-parallel-batch, leaving AIMessages with unmatched tool_calls; the counter defers the break until all tools in the current batch have an `on_tool_end`, so the history is always valid. |
| `fix_dangling_tool_calls` on accumulated messages | The forced-synthesis fallback was passing the raw (potentially broken) sub-agent history to Anthropic, which rejects any AIMessage whose tool_calls lack a corresponding ToolMessage. |
| `recursion_limit: 5` → `25` in forced-synthesis | Same crash as gather had — 5 steps isn't enough for the fallback agent to process accumulated context and call one tool. |
| Added `pre_model_hook=make_messages_modifier()` | Same gap as gather — large `impact`/`cypher`/`context` outputs were accumulating unbounded and bloating the context window across rounds. |
