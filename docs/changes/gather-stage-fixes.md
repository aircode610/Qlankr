# Gather Stage Fixes

| Change | Why |
|--------|-----|
| `recursion_limit: 5` → `25` in forced-submit fallback | 5 is too low for even a single tool call in a ReAct graph; caused the "Recursion limit reached" crash every time the main agent hit MAX_SUBMIT_REJECTIONS. |
| `affected_components` made required (no default) | Having `= []` as a default made the JSON schema mark the field optional, so the LLM would call `submit_gather` without populating it at all. |
| Added `pre_model_hook=make_messages_modifier()` to gather agent | Large PRs produce 50KB+ tool output; without truncation the LLM's context filled up and it lost track of the requirement to build components before submitting. |
| Rejection message echoes back the file list | After a rejection the LLM was retrying blind with no new information; showing it the files it already fetched gives it the data to build components immediately. |
| Rewrote `GATHER_PROMPT` — components first, graph calls capped at 5 | The old prompt had component-grouping as Step 4 after per-file graph calls; on an 18-file PR those calls ate the entire 15-call budget before Step 4 was reached. |
