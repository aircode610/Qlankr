/**
 * Mock API module for frontend-only demos before backend SSE endpoints exist.
 *
 * How to enable:
 * - Set `VITE_USE_MOCK_SSE=true` in frontend environment
 * - Restart `npm run dev`
 *
 * How to disable:
 * - Remove the var or set it to false
 *
 * This file mirrors real API behavior:
 * - Same exported function names and callback contract
 * - Emits the same event types your components already handle
 * - Simulates latency to mimic live SSE streaming
 */
import { buildMockGraph } from "./mockGraphData"

function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    const id = setTimeout(resolve, ms)
    if (!signal) return
    signal.addEventListener("abort", () => {
      clearTimeout(id)
      reject(new DOMException("Aborted", "AbortError"))
    })
  })
}

function emit(event, data, handlers) {
  handlers.onEvent?.({ event, data })

  if (event === "index_step") handlers.onIndexStep?.(data)
  if (event === "index_done") handlers.onIndexDone?.(data)
  if (event === "agent_step") handlers.onAgentStep?.(data)
  if (event === "result") handlers.onResult?.(data)
  if (event === "error") handlers.onError?.(data?.message || "Mock request failed.")
}

export async function mockIndexRepo(repoUrl, handlers = {}) {
  const repoMatch = repoUrl.match(/github\.com\/([^/]+)\/([^/]+)/i)
  const owner = repoMatch?.[1] || "owner"
  const repo = (repoMatch?.[2] || "repo").replace(".git", "")

  try {
    const steps = [
      { stage: "clone", summary: `Cloning ${owner}/${repo}...` },
      { stage: "analyze", summary: "Building knowledge graph (parsing)..." },
      { stage: "analyze", summary: "Building knowledge graph (clustering)..." },
      { stage: "analyze", summary: "Linking call chains and symbol graph..." },
    ]

    for (const step of steps) {
      await wait(750, handlers.signal)
      emit("index_step", step, handlers)
    }

    const done = { repo: `${owner}/${repo}`, files: 2147, clusters: 16, symbols: 13924 }
    await wait(450, handlers.signal)
    emit("index_done", done, handlers)
    return done
  } catch (error) {
    if (error?.name === "AbortError") throw error
    emit("error", { message: "Mock indexing failed unexpectedly." }, handlers)
    throw error
  }
}

export async function mockAnalyzePR(prUrl, handlers = {}) {
  try {
    const steps = [
      { tool: "get_pull_request", summary: "Reading PR metadata and changed files..." },
      { tool: "get_pull_request_files", summary: "Inspecting diff hunks across touched files..." },
      { tool: "detect_changes", summary: "Mapping diff to changed symbols and likely processes..." },
      { tool: "impact", summary: "Evaluating downstream blast radius for high-impact symbols..." },
      { tool: "context", summary: "Expanding caller and callee chains for changed functions..." },
    ]

    for (const step of steps) {
      await wait(700, handlers.signal)
      emit("agent_step", step, handlers)
    }

    const result = {
      pr_title: "Refactor auth token refresh flow",
      pr_url: prUrl,
      pr_summary:
        "This PR refactors refresh-token validation and middleware wiring. The primary risk is authentication edge-case regressions and session expiry handling under stale token conditions.",
      affected_components: [
        {
          component: "Authentication",
          files_changed: ["src/auth/tokens.py", "src/auth/middleware.py"],
          impact_summary:
            "Token issuance and validation paths were changed, affecting all authenticated endpoints.",
          risks: [
            "Refresh token rotation may reject valid sessions",
            "Middleware order may bypass auth checks in edge paths",
          ],
          test_suggestions: {
            skip: ["Unrelated UI-only smoke tests"],
            run: ["Login/logout regression", "Protected endpoint access rules"],
            deeper: ["Expired token refresh race conditions", "Concurrent session invalidation"],
          },
          confidence: "high",
        },
        {
          component: "Session Management",
          files_changed: ["src/session/store.py"],
          impact_summary:
            "Session invalidation flow now depends on new token parsing behavior.",
          risks: ["Sessions may persist longer than expected for revoked tokens"],
          test_suggestions: {
            skip: ["Map rendering tests"],
            run: ["Manual revoke token checks"],
            deeper: ["High concurrency revoke + refresh test matrix"],
          },
          confidence: "medium",
        },
      ],
      agent_steps: steps.length,
    }

    await wait(600, handlers.signal)
    emit("result", result, handlers)
    return result
  } catch (error) {
    if (error?.name === "AbortError") throw error
    emit("error", { message: "Mock analysis failed unexpectedly." }, handlers)
    throw error
  }
}

export async function mockGetGraph(owner, repo) {
  return buildMockGraph(owner, repo)
}
