# Stage 5: Report

You are performing Stage 5 (Report) of the bug reproduction pipeline.

Synthesise all prior stage outputs into a final structured bug report.
Emit ONLY the following JSON — nothing else before or after.

## Output Schema

```json
{
  "title": "string",
  "severity": "critical | high | medium | low",
  "root_cause": "string",
  "reproduction_steps": [
    {
      "step": 1,
      "action": "string",
      "expected": "string"
    }
  ],
  "affected_components": ["string"],
  "recommendations": ["string"],
  "confidence": "high | medium | low",
  "evidence": {
    "log_entries": [],
    "doc_references": [],
    "related_issues": [],
    "network_traces": []
  }
}
```

## Field Descriptions

- `title`: Short, specific title describing the bug (not generic like "game crashes").
  Name the specific feature and symptom.

- `severity`: Must match the severity from triage unless research contradicts it.

- `root_cause`: 2–4 sentences explaining the underlying mechanism — what is broken and why.
  Name specific code elements if known. Do not just restate the symptom.

- `reproduction_steps`: Condensed, final reproduction steps from Stage 3. Minimum 3 steps.
  Each step has `step` (integer), `action` (concrete), `expected` (observable outcome).

- `affected_components`: List of component/subsystem names affected (e.g. "TimetableWindow",
  "NWidgetHorizontal", "Save/Load System"). Use component names, not file paths.

- `recommendations`: 2–5 actionable fix suggestions. Each must be >= 30 characters.
  Avoid generic advice like "fix the bug". Name specific functions, checks, or invariants.

- `confidence`: Overall confidence in this report.
  - `high`: Stack trace or explicit code reference in description
  - `medium`: Mechanism inferred from symptoms with reasonable certainty
  - `low`: Limited information — multiple plausible causes remain

- `evidence`: Populate only from evidence that exists in the bug description or prior stages.
  Leave lists empty if no evidence of that type was found. Do NOT fabricate entries.

Output ONLY the JSON object.
