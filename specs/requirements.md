# Requirements: Qlankr — AI-Assisted QA: Impact Analysis & Bug Reproduction

The deliverable has **two parts**: (1) **Impact analysis** — PR → affected components (bottlenecks) → risks for testing → suggestions for tests (skip or deeper). (2) **Bug reproduction** — bug → analyze mechanics and components → reproduce by hand → research logs, data, DB, admins → report to dev. **Architecture and analysis sources:** GitHub, Jira (task system), Notion/Confluence (docs), Grafana/Kibana (logs), Postman (API testing), sniffers.

---

## User Roles

- **QA Tester** — the primary user who runs impact analysis on new PRs and finds/reproduces bugs and needs to research and document them
- **Developer** — receives bug reports and needs actionable reproduction steps and context to fix bugs
- **QA Lead / Studio Head** — oversees QA process, cares about throughput, cost, and post-release defect rates

---

## User Stories (Backlog)

Stories are ordered by priority. Stories 1–5 constitute the first version (MVP).

### MVP (First Version)

**1. Impact Analysis on PR**
As a QA tester, I want to run impact analysis when I get a new PR (e.g. by URL or branch), so that I see which components are affected, what risks are introduced or reintroduced, and get suggestions for which tests to run (skip, important, deeper tests).

**2. Bug Report Input**
As a QA tester, I want to describe a bug I found in plain text (what happened, where, what I was doing), so that the AI assistant has enough context to help analyze mechanics and components and guide reproduction.

**3. Analyze Mechanics and Components**
As a QA tester, I want the system to analyze the bug and suggest which mechanics and components are involved, so that I know where to look when reproducing by hand.

**4. Research Support (logs, data, DB, admins)**
As a QA tester, I want to pull in relevant logs, data, DB state, and admin/runbook info (e.g. from Grafana, Kibana, Confluence) in one place, so that I don’t hunt across tools by hand when reproducing and researching a bug.

**5. Structured Developer-Ready Report**
As a developer, I want to receive a structured bug report with reproduction steps, game state/environment details, severity classification, and links to logs/docs, so that I can start fixing the bug immediately without asking QA for clarification.

### Post-MVP (Prioritized Backlog)

**6. Traceability for Impact**
As a QA tester, I want to see how the impact and risks were derived (e.g. from PR, docs, logs), so that I can trust and verify the test suggestions before focusing my testing.

**7. Bug Report Export**
As a QA tester, I want to export the generated bug report in common formats (Markdown, PDF), so that I can share it through our existing communication channels.

**8. Jira / Issue Tracker Integration**
As a QA lead, I want impact analysis and bug reports to link to or push to our issue tracker (Jira, GitHub Issues, Linear), so that reports land in the developer's workflow without copy-pasting.

**9. Reproduction Confidence Score**
As a QA tester, I want to see a confidence score or research-completeness indicator for the bug report, so that I can decide whether to verify manually or trust the report as-is.

**10. Notion / Confluence Integration**
As a QA tester, I want impact analysis and reproduction to use our docs and runbooks (Notion, Confluence), so that suggestions and research are aligned with our internal knowledge.

**11. Grafana / Kibana Integration**
As a QA tester, I want impact and reproduction to reference logs and errors (Grafana, Kibana), so that I can trace issues without switching tools.

**12. Bug Categorization**
As a QA lead, I want the tool to automatically categorize bugs by type, so that I can prioritize and assign them to the right developer.

**13. Discord / Codecks Integration**
As a QA tester at an indie studio, I want to send bug reports directly to our Discord channel or Codecks board, so that bugs reach the team where we actually communicate.

**14. Multi-Build Comparison**
As a developer, I want to know if a bug is present in the current build only or also existed in previous builds, so that I can identify which change introduced the regression.

**15. Screenshot / Video Capture**
As a developer, I want the bug report to include screenshots or short video clips of the reproduction, so that I can see the bug visually without running the game myself.

**16. Custom Report Templates**
As a QA lead, I want to customize the format and fields of generated bug reports to match our studio's internal template, so that reports fit our existing workflow.

**17. Historical Bug Database**
As a QA lead, I want to maintain a searchable history of all reproduced bugs and their reports, so that I can track patterns, avoid duplicates, and reference past issues.

**18. Team Workspace**
As a QA lead, I want multiple team members to access the same project workspace, so that our QA team can collaborate without each person setting up the tool independently.

---

## Functional Requirements

- The system shall accept a PR (e.g. GitHub URL or branch) as input and provide impact analysis: affected components (bottlenecks), risks for testing, and suggestions for which tests to run (skip, important, deeper).
- The system shall accept bug descriptions as free-text input from the QA tester.
- The system shall analyze reported bugs and suggest which mechanics and components are involved.
- The system shall support research by aggregating or linking to logs (e.g. Grafana/Kibana), data, DB, and admin/runbook content (e.g. Notion/Confluence) for reproduction.
- The system shall generate structured bug reports containing: reproduction steps, environment details, severity estimate, and references to logs/docs.
- The system shall display traceability for impact analysis (how impact and risks were derived) and, for bugs, the full trace of reproduction/research where applicable.
- The system shall support exporting reports in Markdown and PDF formats.
- The system shall provide a web-based dashboard for impact analysis, submitting bugs, viewing reproduction status, and accessing reports.
- Where integrated (GitHub, Jira, Notion/Confluence, Grafana/Kibana, Postman, sniffers), the system shall use these sources in a way that is transparent and traceable to the user.

## Non-Functional Requirements

- **Setup / Onboarding:** A QA tester should be able to connect relevant sources and run their first impact analysis or submit their first bug for reproduction within 30 minutes, with minimal setup.
- **Reliability:** The system must not silently skip failures or hide missing data. If impact analysis or reproduction fails or is incomplete, it must clearly report what was tried and what was unavailable — false confidence is worse than no result.
- **Trust / Transparency:** Impact and test suggestions must be traceable to sources (PR, docs, logs). Every generated bug report must include the reasoning and data used. The QA tester must be able to verify any claim against the trace.
- **Security / Privacy:** Game builds, PRs, docs, logs, and bug reports contain proprietary content. All data must be encrypted in transit and at rest. No game assets or code shall be stored beyond the active session unless explicitly opted in.
- **Performance:** Impact analysis for a typical PR should complete within a few minutes. Bug reproduction and research should feel responsive with progress updates; complex cases may take longer with option to cancel.
- **Availability:** The service should maintain 99% uptime during business hours (reliable during work sessions).
- **Cost:** The service must be hostable at a cost that supports $49–149/month pricing. Infrastructure costs per run must stay within target.
- **Compatibility:** Web-based dashboard supporting Chrome, Firefox, and Safari (latest versions). Integrations versioned per provider (e.g. GitHub API, Jira Cloud).

---

## Artifact: Customer Validation Interview Plan

We are conducting CustDev interviews with QA professionals and indie studio leads to validate our core assumptions before building.

### Strategy

We are using the "Mom Test" methodology: no pitching our solution, only asking about their life and past behaviors.

**Target interviewees (5 minimum):**
- QA testers or QA leads at indie studios (1–15 person teams)
- Studio heads / producers at indie studios who manage QA directly
- Former QA professionals who left due to workflow frustrations

**How we find them:**
- The "Student Card" tactic: reach out as university researchers studying QA workflows in indie game development, offering to share findings afterward
- Indie game communities: Reddit (r/gamedev, r/QualityAssurance), Discord servers for indie devs, itch.io forums
- LinkedIn outreach to QA professionals at studios that recently shipped indie titles
- Game jam communities where devs often handle their own QA

### Interview Script (15 minutes, Mom Test rules)

1. "When a new PR or build lands, how do you decide what to test? What's painful about that?"
2. "Tell me about the last critical bug that made it to release. What happened?"
3. "Walk me through how your team handles bug reproduction today. What does a typical day look like?"
4. "What's the most time you've spent trying to reproduce a single bug or researching logs/DB/docs? What made it hard?"
5. "How do you communicate bugs to developers? What does that back-and-forth look like?"
6. "Have you tried any tools to help with QA or impact analysis? What worked? What didn't?"
7. "If you could wave a magic wand and fix one thing about your QA process, what would it be?"
8. "How much does your studio spend on QA currently — in time, people, or money?"

**What we do NOT ask:** "Would you use an AI tool that does impact analysis or reproduces bugs?" (opinion, not fact)

### What We're Validating

| Question | Maps to Assumption |
|----------|-------------------|
| Q1: Deciding what to test on a PR | Problem — is "what do I test?" a real pain? |
| Q2: Last critical bug at release | Problem severity — is post-release defect cost real and painful? |
| Q3–Q4: Reproduction and research workflow | Problem — is reproduction/research the bottleneck? |
| Q5: Bug communication | Problem — is the QA-to-dev handoff a real friction point? |
| Q6: Tools tried | Adoption — are they open to tools, or do they distrust them? |
| Q7: Magic wand | Prioritization — does impact or reproduction come up unprompted? |
| Q8: QA spending | Willingness to pay — what's the budget context? |

### Current Status

Interviews are in progress. We are targeting completion of 5 interviews by March 16. Results will feed directly into the go-no-go decision in the proposal.

### Deliverable

A summary document with anonymized findings, mapped to each assumption, with a clear recommendation on whether to proceed, pivot, or stop.
