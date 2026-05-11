# Stage 1: Gather — Affected Components

You are performing Stage 1 (Gather) of the PR analysis pipeline.

Identify the components affected by this pull request and describe the impact of each.
Emit ONLY the following JSON — nothing else.

## Output Schema

```json
{
  "affected_components": [
    {
      "component": "string",
      "files_changed": ["string"],
      "impact_summary": "string",
      "risks": ["string"],
      "confidence": "high | medium | low"
    }
  ]
}
```

## Field Descriptions

- `affected_components`: One entry per distinct component or subsystem affected.
  Each component must have all fields non-empty.

  - `component`: Human-readable component name (e.g. "Save/Load System", "Order Management").
    Use the component's established name in the codebase, not file names.

  - `files_changed`: List of file paths changed in this component. If you cannot determine
    exact paths from the PR URL alone, list the most likely candidates based on the PR title
    and description.

  - `impact_summary`: 1–2 sentences describing what changed in this component and what it
    means for behaviour. Be specific about the change, not just "this file was modified".

  - `risks`: 2–4 specific risks introduced by this change. Each risk should identify a
    concrete failure mode (not generic "could break things"). Examples:
    - "Integer overflow in calculation with large inputs"
    - "Migration missing — existing saves with this field will have default value silently applied"

  - `confidence`: Your confidence that this component is genuinely affected.
    - `high`: Component is directly named in PR title or description
    - `medium`: Component is implied by changed file names or known relationships
    - `low`: Inferred from transitive dependency you cannot verify without a code graph

## Important

You do not have access to a code knowledge graph. Do NOT claim transitive dependencies
unless explicitly mentioned in the PR. Set confidence "low" for inferred relationships.
Output ONLY the JSON object.
