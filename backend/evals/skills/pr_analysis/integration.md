# Stage 3a: Integration Tests

You are performing Stage 3a (Integration Tests) of the PR analysis pipeline.

Identify cross-module integration points affected by this PR and generate integration
test specifications for each. Emit ONLY the following JSON — nothing else.

## Output Schema

```json
{
  "integration_tests": [
    {
      "integration_point": "string",
      "modules_involved": ["string"],
      "test_cases": [
        {
          "name": "string",
          "data_setup": "string",
          "trigger": "string",
          "expected_outcome": "string"
        }
      ],
      "risk_level": "CRITICAL | HIGH | MEDIUM | LOW"
    }
  ]
}
```

## Field Descriptions

- `integration_tests`: One entry per cross-module integration point.
  - `integration_point`: A descriptive name for the boundary being tested
    (e.g. "Save/Load System ↔ Order Management").
  - `modules_involved`: Exactly 2 or more module/component names from the gather stage.
  - `test_cases`: 1–3 scenarios that cross this boundary.
    - `name`: Descriptive name for the scenario.
    - `data_setup`: The state that must be established before the trigger.
    - `trigger`: The event or action that crosses the module boundary.
    - `expected_outcome`: What should happen at the receiving end.
  - `risk_level`:
    - `CRITICAL`: Data loss, crashes, or security if this integration breaks
    - `HIGH`: Major user-visible feature broken
    - `MEDIUM`: Feature degraded but application continues
    - `LOW`: Minor or unlikely failure path

## Important

Only include integration points where data or events actually cross module boundaries.
Two files in the same component do not constitute a cross-module integration point.
Output ONLY the JSON object.
