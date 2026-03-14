# Requirements: Qlankr — AI-Assisted Bug Reproduction for Game QA

## User Roles

- **QA Tester** — the primary user who finds bugs and needs to reproduce/document them
- **Developer** — receives bug reports and needs actionable reproduction steps to fix bugs
- **QA Lead / Studio Head** — oversees QA process, cares about throughput, cost, and post-release defect rates

---

## User Stories (Backlog)

Stories are ordered by priority. Stories 0–5 constitute the first version (MVP).

### MVP (First Version)
**0. As a QA tester, I want to perform regression testing automatically by providing AI all testing data and context information.

**1. Bug Report Input**
As a QA tester, I want to describe a bug I found in plain text (what happened, where, what I was doing), so that the AI assistant has enough context to attempt reproduction.

**2. Automated Bug Reproduction**
As a QA tester, I want the AI assistant to attempt to reproduce a reported bug in a Unity game environment, so that I don't have to spend hours manually trying to trigger the same issue across builds.

**3. Structured Developer-Ready Report**
As a developer, I want to receive a structured bug report with exact reproduction steps, game state details, environment info, and severity classification, so that I can start fixing the bug immediately without asking QA for clarification.

**4. Reproduction Trace Visibility**
As a QA tester, I want to see the full trace of what the AI assistant tried during reproduction (steps attempted, states observed, what succeeded and failed), so that I can trust the output and verify correctness before forwarding to developers.

**5. Unity Project Connection**
As a QA tester, I want to connect the tool to my Unity project with minimal setup (no SDK integration, no code changes), so that I can start using it without needing engineering help.

### Post-MVP (Prioritized Backlog)

**6. Bug Report Export**
As a QA tester, I want to export the generated bug report in common formats (Markdown, PDF), so that I can share it through our existing communication channels.

**7. Jira / Issue Tracker Integration**
As a QA lead, I want generated bug reports to be pushed directly to our issue tracker (Jira, GitHub Issues, Linear), so that the report lands in the developer's workflow without copy-pasting.

**8. Reproduction Confidence Score**
As a QA tester, I want to see a confidence score indicating how reliably the AI was able to reproduce the bug, so that I can decide whether to verify manually or trust the report as-is.

**9. Bug Categorization**
As a QA lead, I want the tool to automatically categorize bugs by type (collision, UI, state, performance, visual), so that I can prioritize and assign them to the right developer.

**10. Discord / Codecks Integration**
As a QA tester at an indie studio, I want to send bug reports directly to our Discord channel or Codecks board, so that bugs reach the team where we actually communicate (not enterprise tools we don't use).


**11. Multi-Build Comparison**
As a developer, I want to know if a bug is present in the current build only or also existed in previous builds, so that I can identify which change introduced the regression.

**12. Screenshot / Video Capture**
As a developer, I want the bug report to include screenshots or short video clips of the reproduction, so that I can see the bug visually without running the game myself.

**13. Custom Report Templates**
As a QA lead, I want to customize the format and fields of generated bug reports to match our studio's internal template, so that reports fit our existing workflow.

**14. Historical Bug Database**
As a QA lead, I want to maintain a searchable history of all reproduced bugs and their reports, so that I can track patterns, avoid duplicates, and reference past issues.

**15. Team Workspace**
As a QA lead, I want multiple team members to access the same project workspace, so that our QA team can collaborate without each person setting up the tool independently.

**16. Batch Bug Processing**
As a QA lead, I want to submit multiple bug reports at once and have the tool process them in queue, so that overnight or during breaks, reproduction work continues without manual input.

**17. Godot Engine Support**
As a QA tester at a studio using Godot, I want the tool to support Godot projects, so that I can use it regardless of our engine choice.

**18. Performance Bug Detection**
As a QA tester, I want the tool to flag performance anomalies (frame drops, memory spikes) observed during reproduction, so that performance bugs are documented alongside functional bugs.

---

## Functional Requirements

- The system shall allow the AI assistant to retain contextual information about targeted fixes or new features during regression testing and use this context to evaluate whether the intended issues were resolved and whether any new regressions were introduced.
- The system shall accept bug descriptions as free-text input from the QA tester.
- The system shall connect to a Unity project build and interact with the game environment to attempt bug reproduction.
- The system shall generate structured bug reports containing: reproduction steps, game state at time of bug, environment details (engine version, OS, device config), severity estimate, and reproduction success/failure status.
- The system should execute automated tests in a controlled and repeatable environment so that identical builds and test conditions produce consistent results across multiple runs.
- Each regression test execution shall run in an isolated environment where game state, save data, and configuration are reset between tests.
- The system shall display a full trace of reproduction attempts to the QA tester for verification.
- The system shall support exporting reports in Markdown and PDF formats.
- The system shall provide a web-based dashboard for submitting bugs, viewing reproduction status, and accessing reports.
- The system shall support testing across multiple game builds and maintain clear version tracking for all test executions and reports.
- The system should break down each change or feature into individual, testable modules, starting with unit-level components and progressively integrating them. This approach ensures we can precisely identify which modules are working correctly and which are failing, enabling faster debugging and more reliable validation of the overall functionality
- The system shall integrate with Unity via the MCP(https://github.com/mcp/coplaydev/unity-mcp) to enable the AI assistant to access game context and interact with Unity tools for automated testing and bug reproduction without requiring modifications to the Unity project.

## Non-Functional Requirements

- **Setup / Onboarding:** A QA tester should be able to connect a Unity project and submit their first bug for reproduction within 30 minutes, with no SDK integration or code changes required.
- **Reliability:** The system must not silently skip reproduction failures. If reproduction fails, it must clearly report what was tried and why it failed — false confidence is worse than no result.
- **Trust / Transparency:** Every generated report must include the full reproduction trace. The QA tester must be able to verify any claim in the report against the trace.
- **Security / Privacy:** Game builds and bug reports contain proprietary content. All data must be encrypted in transit and at rest. No game assets or code shall be stored beyond the active reproduction session unless explicitly opted in.
- **Performance:** Bug reproduction attempts should complete within 15 minutes for typical bugs. Complex reproduction may take longer, but the system must provide progress updates and allow cancellation.
- **Availability:** The service should maintain 99% uptime during business hours (the tool is not needed 24/7 for indie studios, but must be reliable during work sessions).
- **Cost:** The service must be hostable at a cost that supports $49–149/month pricing. Infrastructure costs per reproduction attempt must stay under $0.50.
- **Compatibility:** Initial support for Unity 2021 LTS and later. Windows and macOS build targets. Web-based dashboard supporting Chrome, Firefox, and Safari (latest versions).

---

## Artifact: Customer Validation Interview Plan

As our third artifact, we are conducting CustDev interviews with QA professionals and indie studio leads to validate our core assumptions before building.

### Strategy

We are using the "Mom Test" methodology: no pitching our solution, only asking about their life and past behaviors.

**Target interviewees (5 minimum):**
- QA testers or QA leads at indie studios (1–15 person teams)
- Studio heads / producers at indie studios who manage QA directly
- Former QA professionals who left due to workflow frustrations

**How we find them:**
- The "Student Card" tactic: reach out as university researchers studying QA workflows in indie game development, offering to share findings afterward
- Indie game communities: Reddit (r/gamedev, r/QualityAssurance), Discord servers for indie devs, itch.io forums
- LinkedIn outreach to QA professionals at studios that recently shipped Unity-based indie titles
- Game jam communities where devs often handle their own QA

### Interview Script (15 minutes, Mom Test rules)

1. "Tell me about the last critical bug that made it to release. What happened?"
2. "Walk me through how your team handles bug reproduction today. What does a typical day look like?"
3. "What's the most time you've spent trying to reproduce a single bug? What made it hard?"
4. "How do you communicate bugs to developers? What does that back-and-forth look like?"
5. "Have you tried any tools to help with QA? What worked? What didn't?"
6. "If you could wave a magic wand and fix one thing about your QA process, what would it be?"
7. "How much does your studio spend on QA currently — in time, people, or money?"

**What we do NOT ask:** "Would you use an AI tool that reproduces bugs?" (opinion, not fact)

### What We're Validating

| Question | Maps to Assumption |
|----------|-------------------|
| Q1: Last critical bug at release | Problem severity — is post-release defect cost real and painful? |
| Q2–Q3: Reproduction workflow | Problem — is reproduction actually the bottleneck, or is it something else? |
| Q4: Bug communication | Problem — is the QA-to-dev handoff a real friction point? |
| Q5: Tools tried | Adoption — are they open to tools, or do they distrust them? |
| Q6: Magic wand | Prioritization — does reproduction come up unprompted? |
| Q7: QA spending | Willingness to pay — what's the budget context? |

### Current Status

Interviews are in progress. We are targeting completion of 5 interviews by March 16. Results will feed directly into the go-no-go decision in the proposal.

### Deliverable

A summary document with anonymized findings, mapped to each assumption, with a clear recommendation on whether to proceed, pivot, or stop.
