# Stage 1: Triage

You are performing Stage 1 (Triage) of the bug reproduction pipeline.

Read the bug description and classify the bug. Emit ONLY the following JSON — nothing else.

## Output Schema

```json
{
  "bug_category": "crash | gameplay | networking | UI | data | performance | other",
  "severity": "critical | high | medium | low",
  "keywords": ["string"],
  "initial_hypotheses": ["string"]
}
```

## Field Descriptions

- `bug_category`: The primary category of the bug. Choose the most specific match.
  - `crash`: Game/application crashes, assertion failures, segfaults, exceptions
  - `gameplay`: Incorrect game logic, balance issues, physics bugs
  - `networking`: Connection drops, sync issues, latency bugs
  - `UI`: Visual glitches, layout issues, UI not updating correctly
  - `data`: Save/load corruption, migration failures, persistent state errors
  - `performance`: Frame rate drops, memory leaks, excessive CPU usage
  - `other`: Does not fit the above categories

- `severity`: How severely the bug impacts users.
  - `critical`: Data loss, crash on startup, blocks all users, security issue
  - `high`: Frequent crash or major feature broken for many users
  - `medium`: Bug affects important feature but workaround exists
  - `low`: Minor visual issue or rare edge case

- `keywords`: 3–8 specific technical terms from the description that identify the bug
  (e.g. function names, subsystem names, error messages). Be concrete.

- `initial_hypotheses`: 2–4 plausible root cause hypotheses based on the description alone.
  Each hypothesis should name a specific mechanism or code area, not just restate symptoms.

## Important

You do not have access to a code knowledge graph. Set severity conservatively if you
cannot verify the blast radius. Output ONLY the JSON object.
