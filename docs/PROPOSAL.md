# Proposal: Qlankr — AI-Assisted Bug Reproduction for Game QA

## Product Hypothesis

**Audience:** QA teams at indie game studios (1–15 person teams) building Unity-based games with annual budgets under $1M.

**Problem:** Bug reproduction is the most time-consuming and error-prone phase of game QA. When a tester or player reports a bug, reproducing it reliably — capturing the exact game state, inputs, timing, and environment — often takes longer than finding the bug itself. Inaccurate or incomplete reproduction leads to vague bug reports, wasted developer time chasing phantom issues, and critical bugs slipping through to release. Post-release bugs directly impact ratings, retention, revenue, and sometimes studio survival.

**Current Behavior:** QA engineers manually attempt to reproduce bugs by trial and error, often across multiple builds and device configurations. They write bug reports in free text (or semi-structured templates) with screenshots and steps-to-reproduce that frequently miss engine state, RNG seeds, physics context, or version-specific details. Developers receive reports they cannot act on, request clarification, and the cycle repeats. Communication between QA and dev is a bottleneck that compounds with each build.

**Behavioral Change:** With Qlankr, when a QA tester identifies a bug, they feed the bug description to the AI assistant. The assistant traces through the game environment, attempts to reproduce the bug systematically, and generates a structured, developer-ready report including exact reproduction steps, game state snapshots, and environment details. QA engineers shift from spending 60%+ of their time on reproduction and documentation to spending that time finding new bugs. Studios reduce time-to-fix and lower post-release defect risk.

**Value Proposition:** Fewer post-release disasters and faster fixes — not "QA becomes easier." If we reduce bug reproduction and documentation time by 50%, we measurably reduce time-to-fix and lower the cost of defects reaching production.

## Assumptions and Risks

| # | Assumption | Risk Level | Validation Method |
|---|-----------|------------|-------------------|
| 1 | **Trust (HIGHEST RISK):** Studios are willing to let AI into their QA pipeline and rely on its output for bug reproduction. If the agent misses a critical bug or reproduces it incorrectly, it's a disaster — not just an inconvenience. | Critical | Customer interviews (Mom Test): ask about past experiences with QA tools failing them, willingness to adopt new tools in their pipeline. |
| 2 | **Technical Feasibility (HIGH RISK):** Bug reproduction involves world state, physics, RNG, latency, engine versions, and device configs. Can we consistently trace and reproduce bugs across builds for Unity games? If yes, this is our technological wedge. If not, it's demo magic that collapses in production. | Critical | Technical proof of concept: reproduce 3 known bug types (collision, UI, state) in a sample Unity project. Be brutally honest about results. |
| 3 | **Problem Severity:** Bug reproduction (not bug finding) is the single biggest time sink in indie QA workflows, and inaccurate reproduction is a meaningful source of wasted dev time. | High | Customer interviews: "Walk me through the last critical bug you shipped. How long did reproduction take? What went wrong?" |
| 4 | **Adoption Willingness:** Indie studios will integrate a new tool into their workflow without requiring enterprise sales cycles, custom onboarding, or SDK-heavy setup. | High | Validate through self-serve signups and onboarding time metrics with early design partners. |
| 5 | **Willingness to Pay:** Studios at the indie tier ($49–149/month) will pay for a reproduction tool when their alternative is absorbing post-release costs and delays. | Medium | Letter of intent or pre-order commitment from at least 5 studios during validation phase. |
| 6 | **Scope Focus:** Narrowing to bug reproduction only (not autonomous exploration, not full test automation) is enough value to acquire and retain paying customers. | Medium | Customer interviews and prototype testing: does reproduction alone move the needle, or do they need more? |

**Riskiest assumption is trust**, not willingness to pay. Game QA is high-stakes. The real question isn't whether companies will pay — it's whether they'll let AI into their pipeline and adjust their workflow around it.

**Second riskiest is technical depth.** We must be honest: if we cannot reliably reproduce bugs across builds in Unity, the product doesn't exist.

## Learning Objectives

| # | Objective | How We Validate | Success Criteria |
|---|----------|----------------|-----------------|
| 1 | Validate that bug reproduction is the #1 time sink in indie QA workflows. | 5+ CustDev interviews using Mom Test methodology with QA leads or studio heads at indie studios. | 4 out of 5 interviewees independently describe reproduction as a major pain, with concrete examples of time/money lost. |
| 2 | Validate that studios trust AI-generated reproduction reports enough to act on them. | Show a sample AI-generated bug report to interviewees and ask if they would forward it to a developer as-is. | 3 out of 5 say they would use it directly or with minor edits. |
| 3 | Validate technical feasibility of reproducing at least 3 common bug types in Unity. | Build a proof of concept that reproduces collision, UI overlap, and state-related bugs in a sample Unity project. | Successfully reproduces all 3 bug types with accurate steps and state capture in at least 2 out of 3 attempts each. |
| 4 | Validate willingness to pay at the $49–149/month range. | During interviews, ask about current QA spending, and present pricing. Aim for letters of intent. | At least 2 studios express concrete willingness (not just "sounds interesting"). |
| 5 | Validate that self-serve onboarding (no sales call, no SDK) is viable for indie studios. | Prototype a zero-setup flow and test with 3 studios. | Average onboarding time under 30 minutes, no engineering support needed. |

## Go-no-go Decision

**Go if:**
- 4/5 interviews confirm reproduction is a top-3 pain point with concrete cost/time evidence
- Technical PoC successfully reproduces at least 2 of 3 target bug types in Unity
- At least 2 studios express concrete willingness to pay or sign a letter of intent

**No-go if:**
- Interviewees consistently say reproduction is "annoying but manageable" (pain not severe enough)
- Technical PoC fails to reliably reproduce bugs (feasibility gap too large for current scope)
- Studios express interest but nobody commits to paying — even hypothetically

**Pivot options if no-go:**
- Pivot to developer-side tooling (structured bug reports from crash logs) instead of QA-side reproduction
- Pivot to a different engine or game type where reproduction is more tractable
- Narrow further to a single bug category (e.g., only collision bugs) where AI can be reliable

## Market Context

The game QA market is projected to reach $2.5B by 2033. Our serviceable market is ~12,000 indie studios globally with QA budgets. Three funded AI competitors exist (Modl.ai, Nunu.ai, ManaMind), but all use contact-sales pricing with no self-serve option. Traditional QA outsourcing starts at $50K+. Automation frameworks require engineering expertise most indie teams lack.

**Our wedge:** Bug reproduction for Unity-based indie studios, delivered self-serve at indie-friendly pricing ($49–149/month). Not "an AI that plays the game" — a tool that reproduces a bug and generates a perfect developer-ready report. Specific, painful, and immediately valuable.

**Target for first 18 months:** 30–50 paying indie studios through product-led growth. Not a beautiful $18M SOM projection — a realistic count of studios we can onboard and retain.
