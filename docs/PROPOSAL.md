# Proposal: Qlankr — AI-Assisted QA: Impact Analysis & Bug Reproduction

The deliverable has **two parts**: (1) **Impact analysis** — when QA gets a new PR, show affected components and new risks, with test suggestions (flow: PR → bottlenecks → risks for testing → suggestions: skip or deeper tests). (2) **Bug reproduction** — when QA gets a bug report, facilitate the process (flow: bug → analyze mechanics and components → reproduce by hand → research logs, data, DB, admins → report to dev). Architecture and analysis can draw on GitHub, Jira, Notion/Confluence, Grafana/Kibana, Postman, sniffers.

## Product Hypothesis

**Audience:** QA teams at indie game studios (1–15 person teams) and their QA departments.

**Problem:** Two main pain points: (1) When a new PR lands, QA often doesn’t know what to test — which components are affected and what risks are reintroduced. (2) Bug reproduction is time-consuming and error-prone: reproducing a reported bug and researching logs, DB, admins, and docs is manual and scattered. Inaccurate or incomplete reproduction leads to vague reports, wasted developer time, and critical bugs slipping through. Post-release bugs impact ratings, retention, revenue, and sometimes studio survival.

**Current Behavior:** QA engineers manually assess impact of PRs (or skip it) and manually attempt to reproduce bugs by trial and error across tools (logs, DB, docs). They write bug reports in free text with steps that often miss context. Developers receive reports they cannot act on, request clarification, and the cycle repeats. Communication between QA and dev is a bottleneck.

**Behavioral Change:** With Qlankr, (1) when a PR lands, QA gets impact analysis: affected components, risks, and test suggestions (skip vs. deeper) so they know where to focus. (2) When a bug is reported, the assistant helps analyze mechanics and components, supports research (logs, data, DB, admins), and generates a structured, developer-ready report. QA shifts time from “what do I test?” and reproduction/research to finding new bugs and higher-value testing.

**Value Proposition:** Fewer post-release disasters and faster fixes — clearer test focus on each PR and faster, better bug reproduction and reporting. If we reduce ambiguity on what to test and reduce reproduction/documentation time, we measurably reduce time-to-fix and lower the cost of defects reaching production.

## Assumptions and Risks

| # | Assumption | Risk Level | Validation Method |
|---|------------|------------|--------------------|
| 1 | **Trust (HIGHEST RISK):** Studios are willing to let AI into their QA pipeline and rely on its output for impact analysis and bug reproduction. If the agent misses a critical risk or reproduces incorrectly, it's a disaster — not just an inconvenience. | Critical | Customer interviews (Mom Test): ask about past experiences with QA tools failing them, willingness to adopt new tools. |
| 2 | **Technical Feasibility (HIGH RISK):** Impact analysis requires integrating PR/task/docs/logs; reproduction involves state, logs, DB, and context. Can we consistently deliver useful impact and reproduction support across their stack? If not, it's demo magic that collapses in production. | Critical | Technical proof of concept: impact analysis on sample PRs; reproduction support for 2–3 bug types with logs/docs. |
| 3 | **Problem Severity:** “What do I test on this PR?” and bug reproduction (plus research) are major time sinks in indie QA workflows, and vague reports are a meaningful source of wasted dev time. | High | Customer interviews: "When a new PR lands, how do you decide what to test?" "Walk me through the last critical bug you shipped. How long did reproduction and research take?" |
| 4 | **Adoption Willingness:** Indie studios will integrate a new tool (GitHub, Jira, docs, logs as applicable) without requiring enterprise sales cycles or heavy setup. | High | Validate through self-serve signups and onboarding time metrics with early design partners. |
| 5 | **Willingness to Pay:** Studios at the indie tier ($49–149/month) will pay for impact analysis and reproduction support when their alternative is wasted time and post-release cost. | Medium | Letter of intent or pre-order commitment from at least 5 studios during validation phase. |
| 6 | **Scope Focus:** Delivering impact analysis plus bug reproduction support (not full autonomous exploration) is enough value to acquire and retain paying customers. | Medium | Customer interviews and prototype testing: do these two parts move the needle, or do they need more? |

**Riskiest assumption is trust**, not willingness to pay. QA is high-stakes. The real question isn't whether companies will pay — it's whether they'll let AI into their pipeline and adjust their workflow around it.

**Second riskiest is technical depth.** We must be honest: if we cannot deliver useful impact analysis and reproduction support against their real PRs and bugs, the product doesn't exist.

## Learning Objectives

| # | Objective | How We Validate | Success Criteria |
|---|-----------|-----------------|------------------|
| 1 | Validate that "what do I test on this PR?" and bug reproduction/research are top pain points in indie QA workflows. | 5+ CustDev interviews using Mom Test with QA leads or studio heads at indie studios. | 4 out of 5 interviewees independently describe impact ambiguity and/or reproduction as major pains, with concrete examples. |
| 2 | Validate that studios trust AI-generated impact and bug reports enough to act on them. | Show sample impact analysis and AI-generated bug report to interviewees; ask if they would use them. | 3 out of 5 say they would use directly or with minor edits. |
| 3 | Validate technical feasibility of impact analysis and reproduction support. | Build a proof of concept: impact from a sample PR; reproduction support with logs/docs for 2–3 bug types. | Impact analysis surfaces affected components and risks; reproduction support produces actionable reports. |
| 4 | Validate willingness to pay at the $49–149/month range. | During interviews, ask about current QA spending and present pricing. Aim for letters of intent. | At least 2 studios express concrete willingness (not just "sounds interesting"). |
| 5 | Validate that self-serve onboarding is viable for indie studios. | Prototype a low-friction flow and test with 3 studios. | Average onboarding time under 30 minutes, no engineering support needed. |

## Go-no-go Decision

**Go if:**
- 4/5 interviews confirm impact ambiguity and/or reproduction/research as top-3 pain points with concrete cost/time evidence
- Technical PoC delivers useful impact analysis and reproduction support (as above)
- At least 2 studios express concrete willingness to pay or sign a letter of intent

**No-go if:**
- Interviewees consistently say impact and reproduction are "annoying but manageable" (pain not severe enough)
- Technical PoC fails to deliver useful impact or reproduction support (feasibility gap too large)
- Studios express interest but nobody commits to paying — even hypothetically

**Pivot options if no-go:**
- Pivot to developer-side tooling (e.g. structured reports from crash logs) instead of QA-side
- Narrow to impact analysis only or reproduction only where we can be reliable
- Narrow to a single stack or engine where integrations are tractable

## Market Context

The game QA market is projected to reach $2.5B by 2033. Our serviceable market is ~12,000 indie studios globally with QA budgets. Competitors include AI QA tools (Modl.ai, Nunu.ai, ManaMind) with contact-sales pricing and no self-serve. Traditional QA outsourcing starts at $50K+. Automation frameworks require engineering expertise most indie teams lack.

**Our wedge:** Impact analysis (what to test on each PR) plus bug reproduction support for indie studios, delivered self-serve at indie-friendly pricing ($49–149/month). Not "an AI that does everything" — a tool that clarifies test focus and facilitates reproduction and reporting. Specific, painful, and immediately valuable.

**Target for first 18 months:** 30–50 paying indie studios through product-led growth.
