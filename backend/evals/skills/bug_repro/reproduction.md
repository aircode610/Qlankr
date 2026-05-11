# Stage 3: Reproduction

You are performing Stage 3 (Reproduction) of the bug reproduction pipeline.

Write a step-by-step reproduction plan that a developer unfamiliar with the codebase
could follow to trigger the bug. Emit ONLY the following JSON.

## Output Schema

```json
{
  "prerequisites": ["string"],
  "steps": [
    {
      "step_number": 1,
      "action": "string",
      "expected_result": "string"
    }
  ]
}
```

## Field Descriptions

- `prerequisites`: Conditions that must be true before the first step.
  Examples: specific OS, game version, save file state, configuration settings, player state.
  Extract these from the bug description — do not omit them.

- `steps`: Ordered list of actions to reproduce the bug. Minimum 3 steps.
  - `step_number`: Integer starting at 1.
  - `action`: Specific, concrete action (e.g. "Open Settings → Interface → Timetable settings
    and disable 'Show arrival and departure date on timetable'"). Avoid vague verbs like
    "interact with the thing".
  - `expected_result`: What the developer should observe after this step (including the
    bug manifestation on the final step).

## Rules

- Include ALL prerequisite conditions mentioned in the description (OS, version, settings,
  game state). Missing even one can make reproduction unreliable.
- For intermittent bugs (race conditions, timing-dependent): describe a stress-test approach
  and explicitly note non-determinism. Do NOT write "Step N: crash occurs" as if it is certain.
- Do not invent steps not implied by the description.

Output ONLY the JSON object.
