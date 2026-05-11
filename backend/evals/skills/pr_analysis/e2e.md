# Stage 3b: End-to-End Test Plans

You are performing Stage 3b (E2E Test Plans) of the PR analysis pipeline.

Plan end-to-end test scenarios that cover user-visible workflows affected by this PR.
Emit ONLY the following JSON — nothing else.

## Output Schema

```json
{
  "e2e_test_plans": [
    {
      "process": "string",
      "scenario": "string",
      "steps": [
        {
          "step": 1,
          "action": "string",
          "expected_state": "string"
        }
      ],
      "priority": "CRITICAL | HIGH | MEDIUM | LOW"
    }
  ]
}
```

## Field Descriptions

- `e2e_test_plans`: One entry per distinct user-facing workflow to test.
  - `process`: The name of the business or user process being tested
    (e.g. "Cargo Income Calculation", "Vehicle Timetable Management").
  - `scenario`: A specific scenario within that process
    (e.g. "Income calculation with maximum days_in_transit value").
  - `steps`: 3–7 ordered steps a tester would follow.
    - `step`: Integer starting at 1.
    - `action`: Concrete user action (e.g. "Open a vehicle's timetable window").
    - `expected_state`: Observable application state after this action.
  - `priority`:
    - `CRITICAL`: Core user flow; regression here blocks release
    - `HIGH`: Important feature that users frequently use
    - `MEDIUM`: Secondary feature or edge case
    - `LOW`: Rarely used feature or low-impact edge case

## Important

Each scenario must be testable by a QA engineer without access to the codebase.
Actions must be user-level (UI interactions, API calls) not code-level.
Output ONLY the JSON object.
