# Stage 2: Mechanics

You are performing Stage 2 (Mechanics) of the bug reproduction pipeline.

Based on the bug description and triage output, identify the likely code paths involved
and form root cause hypotheses with supporting evidence. Emit ONLY the following JSON.

## Output Schema

```json
{
  "code_paths": [
    {
      "file": "string",
      "symbol": "string",
      "role": "string"
    }
  ],
  "root_cause_hypotheses": [
    {
      "hypothesis": "string",
      "evidence": "string",
      "confidence": "high | medium | low"
    }
  ]
}
```

## Field Descriptions

- `code_paths`: List of files and symbols likely involved in the bug.
  - `file`: Path relative to repo root (e.g. `src/widget.cpp`). Use "unknown" if uncertain.
  - `symbol`: Function, class, or method name (e.g. `NWidgetHorizontal::SetupSmallestSize`).
  - `role`: What this symbol does in the context of the bug (e.g. "crash site", "root cause", "caller").

- `root_cause_hypotheses`: 2–4 hypotheses explaining what is mechanically wrong.
  - `hypothesis`: A specific, mechanistic claim about what is broken (not just "there is a bug in X").
  - `evidence`: Text from the bug description that supports this hypothesis. Quote directly.
  - `confidence`: Your confidence given that you cannot verify call graphs.
    - `high`: Description contains a stack trace or explicit code reference
    - `medium`: Description implies the mechanism but does not name it
    - `low`: Inference from symptoms only; no direct code evidence

## Important

You do not have access to a code knowledge graph. Do NOT invent file paths or symbol names
that are not derivable from the bug description. Use confidence "low" liberally.
Output ONLY the JSON object.
