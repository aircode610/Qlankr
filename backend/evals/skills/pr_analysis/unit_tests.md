# Stage 2: Unit Tests

You are performing Stage 2 (Unit Tests) of the PR analysis pipeline.

For each affected component from Stage 1, generate unit test specifications.
Emit ONLY the following JSON — nothing else.

## Output Schema

```json
{
  "unit_tests_by_component": [
    {
      "component": "string",
      "unit_tests": [
        {
          "target": "string",
          "test_cases": [
            {
              "name": "string",
              "setup": "string",
              "action": "string",
              "expected": "string"
            }
          ],
          "mocks_needed": ["string"],
          "priority": "high | medium | low"
        }
      ]
    }
  ]
}
```

## Field Descriptions

- `unit_tests_by_component`: One entry per component from the gather stage.
  - `component`: Must match the component name from Stage 1 exactly.
  - `unit_tests`: 2–4 test specs per component, each targeting a specific symbol.
    - `target`: The specific function, method, or class being tested (e.g. `ScriptCargoClass::GetIncome`).
    - `test_cases`: 2–4 test cases covering happy path, edge cases, and error cases.
      - `name`: Descriptive test name (e.g. "returns 0 when days_in_transit is 0").
      - `setup`: Initial state required (e.g. "cargo object with valid income rate").
      - `action`: The call being tested (e.g. "call GetIncome(days=0, distance=100)").
      - `expected`: The concrete expected outcome (e.g. "returns 0").
    - `mocks_needed`: External dependencies to mock (databases, file systems, network calls).
      Do NOT mock internal logic.
    - `priority`: `high` for critical paths and regression-prone areas; `low` for utilities.

## Important

Test targets must be real symbols derivable from the PR context, not vague descriptions.
Output ONLY the JSON object.
