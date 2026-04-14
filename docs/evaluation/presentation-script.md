# Presentation Script — Evaluating an AI Agent

---

## Slide 1 — Title

How do you know your AI agent is good?

That's the question we're going to answer today. We built an AI agent that analyzes GitHub pull requests — reads code, identifies risks, generates test plans. But at some point we had to ask ourselves: is it actually doing a good job? And "it looks right to me" isn't an answer you can build on.

---

## Slide 2 — What does the agent do?

Quick context so we're all on the same page.

You give the agent a GitHub pull request URL. It runs through an 8-stage pipeline — reads the PR diff, queries a knowledge graph of the codebase, generates unit tests, and then either produces integration test specs or end-to-end test plans. The whole thing uses human-in-the-loop checkpoints, so a developer can review and approve the unit tests before the agent continues.

The point is: there are a lot of moving parts, and quality can break at any one of them.

---

## Slide 3 — Why "looks good" isn't enough

Four reasons why manual review doesn't scale here.

First, the agent is **non-deterministic** — the same PR can produce different outputs on different runs. So even if it looked good yesterday, you don't know about today.

Second, there's **no ground truth** — there's no single correct test plan for a given PR. Any evaluation approach has to deal with that ambiguity.

Third, it's **multi-step** — a failure in stage 2 of 8 silently poisons everything downstream. You might not even notice until the final output looks wrong.

And fourth, **regressions are silent** — change one prompt and quality quietly drops a week later with no alert.

---

## Slide 4 — Tools we considered

We looked at four options.

LangSmith, Langfuse, Weights & Biases, and Arize AI. The key differentiator for us was LangGraph native integration. Our agent is built on LangGraph, and LangSmith is made by the same team — it integrates without any adapters. The others require manual instrumentation.

---

## Slide 5 — Why LangSmith

Three things made LangSmith the right choice.

Zero-config tracing — one environment variable and every run is automatically recorded. Every tool call, every LLM message, every decision the agent made is visible.

Datasets and evaluators — we store our golden examples in LangSmith and evaluators are just plain Python functions. No new framework to learn.

Experiment comparison — this is the screenshot you see here. Change a prompt, re-run, and see the score difference across every metric side by side. That feedback loop is what makes iteration fast.

---

## Slide 6 — Golden Dataset

To evaluate anything, you need something to evaluate against.

We built a dataset of 8 real pull requests, each with expert-labeled expected outputs — what components should be identified, what risks should be flagged, which tools should be called.

One PR is from our own Qlankr repo, which is fully indexed in our knowledge graph. The other 7 are from external repos — OpenTTD, osu!, Cataclysm-DDA — that the agent has never seen. These cover the full range: small one-file bugfixes, large features touching 80+ files, refactors, and PRs with only new files.

---

## Slide 7 — 3 Evaluator Layers

We have 15 evaluators in total, organized into 3 layers.

The first two layers are **deterministic** — they're just code, no LLM, free to run. They check whether the pipeline completed correctly and whether the agent behaved as expected.

The third layer uses an **LLM as a judge** — we use Claude to score the quality of the output. These answer questions that can't be checked with simple rules, like "did it catch the right risks?" or "are the test specs actually useful?"

---

## Slide 8 — Layer 1: Pipeline Health

Four evaluators that check the basics.

**no_crash** — did the agent finish? Returns 1 if components were produced, 0 if there was an error.

**pipeline_progression** — did it hit all the stages? For the integration path we expect gather, unit tests, and integration tests. Score is how many it reached out of how many it should have.

**output_completeness** — did every component have all 5 required fields? Component name, files changed, impact summary, risks, and confidence level. Averages across all components.

**component_count** — did it find enough components? Each example in our dataset has a minimum threshold set by human review. Score is actual divided by minimum, capped at 1.

---

## Slide 9 — Layer 2: Behaviour

Four evaluators that check how the agent used its tools.

**tool_coverage** — did it call the tools it was supposed to? We check whether the actual tool calls include the ones we expect for that PR. Score is the intersection divided by expected.

**tool_efficiency** — did it waste calls repeating itself? Anything called more than 4 times counts as redundant. Score is 1 minus redundant over total.

**gitnexus_usage** — did it use the knowledge graph when the repo was indexed? Only applies to our own repo. Checks that it called at least 2 of: impact, context, query, cypher.

**confidence_calibration** — is the agent honest about what it knows? For repos without a knowledge graph, all components should be rated "low" confidence. If it's calling things "high" when it has no graph data, that's a problem.

---

## Slide 10 — Layer 3: LLM Judges

Five evaluators where we use Claude to score the output.

**risk_quality** — we give Claude the agent's risks and the ones a human reviewer identified. It checks semantic recall — did the agent find the same underlying concerns, even in different words? It also penalizes missed critical risks.

**component_matching** — "ReAct Agent Core" should match "ReAct Agent." Exact string comparison would fail here, so Claude judges whether the names refer to the same thing.

**groundedness** — are the claims backed by real code? Claude asks: could a human reading the same PR arrive at these conclusions? It flags hallucinated file names, invented risks, fabricated symbols.

**unit_test_quality and integration_test_quality** — are the specs actually useful to a developer? Checks that targets are real symbols, test cases cover meaningful scenarios, mocks are appropriate, and cross-module boundaries are real.

---

## Slide 11 — Results

These are our results from running the integration suite on 7 external GitHub repos.

The top section — green — is pipeline health. All four metrics at 1.0. The pipeline reliably completes, hits all stages, fills all fields, and finds enough components every time.

Tool efficiency and tool coverage are also strong at 0.89 and 0.86.

Then the quality scores — yellow — groundedness at 0.72 and risk quality at 0.66. The agent is finding roughly two thirds of the risks a human would flag, and its claims are mostly grounded.

The red scores are integration tests and confidence calibration. These are the areas that need work.

---

## Slide 12 — Reading the Results

Let's interpret what those scores actually mean.

The pipeline being perfect tells us the infrastructure is solid. We're not fighting crashes or missing output — the agent reliably does something useful every run.

Tool usage being healthy tells us the agent is behaving sensibly — it's not spinning in circles or skipping important tools.

Risk detection at 0.66 is decent for a first version but there's clear room to improve. The agent misses subtle edge cases and sometimes makes claims it can't fully back up.

The integration test scores — 0.29 and 0.18 — are the clearest signal of what to fix next. The agent exhausts its research tool budget without ever submitting results. That's a prompt problem, not an architecture problem. And confidence calibration at 0.18 means the agent is overconfident when it has no knowledge graph to rely on.

---

## Slide 13 — LangSmith in Action

These are actual screenshots from our LangSmith workspace.

On the left you can see a single run traced — every tool call in sequence, and when you click on one you see exactly what arguments were passed and what came back. This is what makes debugging fast. When a score drops, you can open the trace and see precisely where the agent went wrong.

On the right is the evaluation view — all 15 scores for a single example, plus the LLM judge's written reasoning for each score. That reasoning is important: a number alone doesn't tell you why. The reasoning tells you what the judge actually saw.

---

## Slide 14 — The Loop

So how does this actually get used?

You make a change — edit a prompt, adjust the tool budget, swap the model. You run the eval suite. Then you open LangSmith and compare the new experiment against the previous one.

The key is that this loop is fast and cheap. Most of our evaluators are free deterministic checks. The LLM judges add some cost but you're not running them on production traffic — just on 8 golden examples. A full eval run takes minutes.

---

## Slide 15 — Summary

To wrap up.

The problem: AI agents are non-deterministic, multi-step, and silent when they regress. You can't just look at the output and know if it's good.

Our solution: 8 golden PRs as ground truth, 15 evaluators across 3 layers, all wired into LangSmith with a one-command eval runner.

What the results showed us: the pipeline is solid, risk detection is decent, and integration tests plus confidence calibration are the next targets to fix.

The value isn't in any single score — it's in having a baseline you can improve against, and a loop fast enough that you can actually iterate.
