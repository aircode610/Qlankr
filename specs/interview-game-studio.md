# Artifact: CustDev Interview — Game Studio (Team Lead + QA Lead)

**Interviewees:** Team lead and QA lead at a game studio.  
**Purpose:** Validate QA workflow, reproduction pain, communication, and trust in automation.

---

## Questions Asked

1. How QA actually works day-to-day — the full bug lifecycle from discovery to fix, tools used, where time gets wasted
2. Bug reproduction — how it's done, how often it fails, what makes it hard (game state, randomness, unclear steps)
3. QA beyond bug finding — regression testing, triage/prioritization, deduplication, platform testing, severity classification
4. Dev ↔ QA communication — what makes a good vs bad report, how much back-and-forth happens, what "can't reproduce" leads to
5. Indie studio realities — is QA a dedicated role or devs testing their own stuff? Budgets, process maturity, tooling
6. Trust in AI/automation — would QA people trust AI-generated reproduction steps? What proof would they need? Any past experience with automation tools?
7. Technical side — how coupled is reproduction to specific game states? How standardized are engine setups across indie studios?
8. What to build first — if we could only solve one QA pain point, what would actually move the needle?

---

## Summary of Answers

### 1. Bug lifecycle and where time gets wasted

- **Sources of bugs:** Production (reported by users/support or found via metrics/crash reports) or discovered during feature testing. QA also sets priority; critical issues get hotfixes, lower priority go into regular releases.
- **Typical lifecycle:** Analysis and reproduction → fix by dev → verification in test env → release → post-production verification and communication with support (if users need to be notified).
- **Feature-testing path:** Bugs found during feature work are reported and often fixed as part of the feature; low-priority items may become technical debt.
- **Longest stage:** Often **analysis and reproduction**. QA may need to collect logs, check databases, review recent commits, and clarify with support (user behavior, device specs, account data). **Tools:** logging systems, sniffers to recreate specific scenarios.
- Fix is usually fast once root cause is found. **Verification of the fix** is also important and needs risk analysis — complex systems (especially games) have hidden dependencies; project experience and code reading help spot side effects.

### 2. Bug reproduction — how it’s done and what makes it hard

- Critical issues are relatively rare but **investigation can take significant time**.
- **Process:** QA gathers all available info: talk to support, analyze logs for the relevant period, understand what happened on the user’s side, and attempt to reproduce in parallel.
- **Main challenges:** Differences between production and test environments, lack of needed devices, inability to replicate the user’s exact data, device model, or OS version.

### 3. QA beyond bug finding

- **Regression:** Done around major planned updates; smaller releases and bug fixes use smoke testing. Regression can be **time-consuming because impact analysis is sometimes incomplete**, so risks are hard to predict — as a result, some important modules are tested proactively even when not directly touched by the release.
- **Prioritization:** Done in bug review. For new features, QA and product do grooming to decide what must be fixed before first release vs. what can wait.

### 4. Dev ↔ QA communication

- **Good report:** Enough for a developer to start without extra clarification — clear reproduction steps, logs, screenshots, precise expected behavior.
- **Channels:** In smaller teams, a lot of communication still happens in chat rather than only in the task tracker.
- **“Cannot reproduce”:** Treated as a temporary status; QA keeps investigating until there’s enough information to fix the issue.

### 5–8. (Indie realities, trust in AI, technical coupling, what to build first)

*Answers for questions 5–8 were not provided in the input; can be filled in after more interviews or follow-ups.*

---

## Tools Mentioned

| Category        | Tools / practices |
|-----------------|-------------------|
| Discovery       | Product metrics, crash reports, support reports |
| Reproduction    | Logging systems, sniffers (to recreate scenarios) |
| Investigation   | Logs, databases, recent commits, support (user behavior, device specs, account data) |
| Tracking        | Task tracker; chat for smaller teams |
| Verification    | Risk analysis, code reading, test environment |

---

## Mapping to Assumptions (Proposal / Requirements)

| Finding | Maps to |
|--------|--------|
| Analysis and reproduction is one of the longest stages; QA collects logs, DB, commits, support info | **Problem severity** — reproduction + research is a real bottleneck |
| Impact analysis sometimes incomplete → hard to predict risks → proactive testing of modules not directly affected | **Impact analysis** — “what to test?” and incomplete impact are real pains |
| Good report = clear steps, logs, screenshots, expected behavior; “can’t reproduce” is temporary until QA gathers more | **Structured report / communication** — good reports reduce back-and-forth; tooling that helps reproduction and research supports that |
| Logging systems and sniffers used to recreate scenarios | **Architecture** — aligns with Grafana/Kibana, sniffers, logs, DB in our specs |

---

## Status

First interview completed (game studio, team lead + QA lead). Target: 5 interviews total; results feed into go-no-go decision in proposal.
