# Stage 4: Research

You are performing Stage 4 (Research) of the bug reproduction pipeline.

Summarise what external evidence sources you would query and what you found.
Since you are operating without live tool access, reason about what sources are
relevant and what they would likely contain. Emit ONLY the following JSON.

## Output Schema

```json
{
  "sources_queried": ["string"],
  "sources_with_results": ["string"],
  "code_graph_hits": [],
  "findings": ["string"]
}
```

## Field Descriptions

- `sources_queried`: List of source types you attempted to query.
  Examples: "issue tracker", "git log", "documentation", "stack trace", "forum posts".

- `sources_with_results`: Subset of `sources_queried` that would likely return relevant data
  given the bug description. Be honest — if no external source is obviously relevant, say so.

- `code_graph_hits`: Always `[]` for Claude Code — you have no knowledge graph access.

- `findings`: 2–5 concrete findings derived from the bug description and prior stages.
  Each finding should be a specific technical observation, not a restatement of symptoms.
  Examples:
  - "Stack trace directly names crash site: NWidgetHorizontal::SetupSmallestSize() at widget.cpp:1578"
  - "Bug is 100% reproducible — deterministic, not intermittent"
  - "Setting toggle (not game data) triggers the crash — suggests UI widget layout recalculation"

## Important

`code_graph_hits` must always be `[]`. Output ONLY the JSON object.
