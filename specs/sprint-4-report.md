#report #sprint_4

Qlankr — Sprint 4 Report

🔹 Context
Sprint 4 productionized Qlankr: persistent storage, multi-tenant user workspaces, a redesigned evaluation framework covering both pipelines, and UI polish across the full product.

🔹 Planned / Done
- Database: Supabase schema + migrations, multi-tenant RLS, automatic user profile trigger [done]
- Auth: JWT/JWKS (ES256) verification, `get_current_user` dependency, Supabase auth flow in React [done]
- Projects API: named projects, CRUD endpoints + tests, legacy registry migration script [done]
- User credentials: server-side GitHub/Jira/Notion/Confluence token storage via Supabase [done]
- Eval redesign: 5 LangSmith datasets (25 examples), transcript capture, split groundedness, PR diff fetcher, diff-aware evaluators [done]
- LLM-as-judge for bug reproduction: 3 LLM judges (root cause quality, report coherence, reproduction step clarity) + 10 deterministic evaluators [done]
- Vanilla Claude + Claude Code baselines: structured QA plans, benchmark comparison target for PR analysis evals [done]
- Indexer: persistent repo clones, symbol-level graph nodes and edges [done]
- UI: projects list/detail, history view, PR analysis and bug report replay views, GraphCanvas component, light mode, loading state for indexing [done]
- Bug repro fix: zero-score issue in reproduction stage resolved before demo [done]

🔹 Key Decisions
- Supabase over custom DB — row-level security handles multi-tenancy at query time; user-scoped isolation requires no custom middleware.
- LLM judges for bug evals — deterministic checks (field presence, step count) cannot measure semantic root-cause alignment; rubric-anchored judges fill that gap.
- 5-dataset eval structure — separates real bugs (OpenTTD, osu!, Luanti, Cataclysm-DDA) from adversarial synthetic examples so regressions are localized by failure mode.
- Claude Code as eval baseline — fairer comparison than vanilla Claude; runs full skill prompts without pipeline overhead so scores reflect prompt quality, not infrastructure.

🔹 Problems & Next Steps
- Done ig UwU
- We will probably improve the eval though
