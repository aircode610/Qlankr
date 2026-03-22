import { useEffect, useMemo, useState } from "react"
import { analyzePR, getGraph, indexRepo, isMockSseEnabled } from "./api"
import RepoInput from "./components/RepoInput"
import PRInput from "./components/PRInput"
import AgentTrace from "./components/AgentTrace"
import ImpactSummary from "./components/ImpactSummary"
import KnowledgeGraph from "./components/KnowledgeGraph"

const MOCK_GRAPH = {
  nodes: [
    { id: "cluster-auth", label: "Auth Cluster", type: "cluster", cluster: "auth" },
    { id: "file-token", label: "src/auth/tokens.py", type: "file", cluster: "auth" },
    { id: "file-middleware", label: "src/auth/middleware.py", type: "file", cluster: "auth" },
    { id: "cluster-game", label: "Game Loop Cluster", type: "cluster", cluster: "game" },
    { id: "file-loop", label: "src/game/loop.py", type: "file", cluster: "game" },
  ],
  edges: [
    { source: "cluster-auth", target: "file-token", type: "CONTAINS" },
    { source: "cluster-auth", target: "file-middleware", type: "CONTAINS" },
    { source: "file-middleware", target: "file-token", type: "CALLS" },
    { source: "cluster-game", target: "file-loop", type: "CONTAINS" },
  ],
  clusters: [
    { id: "auth", label: "Auth Cluster", size: 2 },
    { id: "game", label: "Game Loop Cluster", size: 1 },
  ],
}

function extractOwnerRepo(repoUrl) {
  try {
    const parsed = new URL(repoUrl)
    const parts = parsed.pathname.split("/").filter(Boolean)
    if (parts.length < 2) return null
    return { owner: parts[0], repo: parts[1].replace(".git", "") }
  } catch {
    return null
  }
}

function buildMarkdownReport(result) {
  if (!result) return ""
  const lines = [
    `# PR Impact Analysis`,
    ``,
    `## PR`,
    `- Title: ${result.pr_title}`,
    `- URL: ${result.pr_url}`,
    `- Agent steps: ${result.agent_steps}`,
    ``,
    `## Summary`,
    result.pr_summary || "",
    ``,
    `## Affected Components`,
  ]

  for (const component of result.affected_components || []) {
    lines.push(``, `### ${component.component}`)
    lines.push(`- Confidence: ${component.confidence}`)
    lines.push(`- Files changed:`)
    for (const file of component.files_changed || []) {
      lines.push(`  - ${file}`)
    }
    lines.push(`- Impact summary: ${component.impact_summary}`)
    lines.push(`- Risks:`)
    for (const risk of component.risks || []) {
      lines.push(`  - ${risk}`)
    }
    lines.push(`- Test suggestions`)
    lines.push(`  - Skip:`)
    for (const item of component.test_suggestions?.skip || []) {
      lines.push(`    - ${item}`)
    }
    lines.push(`  - Run:`)
    for (const item of component.test_suggestions?.run || []) {
      lines.push(`    - ${item}`)
    }
    lines.push(`  - Deeper:`)
    for (const item of component.test_suggestions?.deeper || []) {
      lines.push(`    - ${item}`)
    }
  }

  return lines.join("\n")
}

export default function App() {
  // App owns the full page state so each component can stay focused:
  // - Repo indexing flow
  // - Graph state (mock first, real after index)
  // - Analysis streaming flow (trace + final result)
  const [repoUrl, setRepoUrl] = useState("")
  const [indexing, setIndexing] = useState(false)
  const [indexMessages, setIndexMessages] = useState([])
  const [indexedRepo, setIndexedRepo] = useState(null)

  const [graphData, setGraphData] = useState(MOCK_GRAPH)

  const [prUrl, setPrUrl] = useState("")
  const [analyzing, setAnalyzing] = useState(false)
  const [agentSteps, setAgentSteps] = useState([])
  const [analysisResult, setAnalysisResult] = useState(null)

  const [error, setError] = useState("")
  const mockEnabled = isMockSseEnabled()

  const markdownReport = useMemo(
    () => buildMarkdownReport(analysisResult),
    [analysisResult],
  )

  // Session-only cache (browser tab/session):
  // Keeps lightweight data only, so users can refresh while keeping recent context.
  // Heavy repository/index artifacts remain backend responsibility.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("qlankr_ui_session")
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (parsed.repoUrl) setRepoUrl(parsed.repoUrl)
      if (parsed.prUrl) setPrUrl(parsed.prUrl)
      if (parsed.indexedRepo) setIndexedRepo(parsed.indexedRepo)
      if (Array.isArray(parsed.indexMessages)) setIndexMessages(parsed.indexMessages)
      if (parsed.graphData) setGraphData(parsed.graphData)
      if (parsed.analysisResult) setAnalysisResult(parsed.analysisResult)
      if (Array.isArray(parsed.agentSteps)) setAgentSteps(parsed.agentSteps)
    } catch {
      // Ignore broken cache payloads and continue with clean state.
    }
  }, [])

  useEffect(() => {
    const payload = {
      repoUrl,
      prUrl,
      indexedRepo,
      indexMessages: indexMessages.slice(-40),
      graphData,
      analysisResult,
      agentSteps: agentSteps.slice(-80),
      savedAt: new Date().toISOString(),
    }
    try {
      sessionStorage.setItem("qlankr_ui_session", JSON.stringify(payload))
    } catch {
      // Storage can fail in private mode or quota limits; UI still works.
    }
  }, [
    repoUrl,
    prUrl,
    indexedRepo,
    indexMessages,
    graphData,
    analysisResult,
    agentSteps,
  ])

  async function handleIndexRepo() {
    setError("")
    setIndexing(true)
    setIndexMessages([])
    setIndexedRepo(null)
    setGraphData(MOCK_GRAPH)

    try {
      await indexRepo(repoUrl, {
        onIndexStep: (step) => {
          setIndexMessages((prev) => [...prev, step])
        },
        onIndexDone: async (donePayload) => {
          setIndexedRepo(donePayload)
          const ownerRepo = extractOwnerRepo(repoUrl)
          if (!ownerRepo) return
          try {
            const graph = await getGraph(ownerRepo.owner, ownerRepo.repo)
            setGraphData(graph)
          } catch {
            // Keep mock graph when backend graph endpoint is not ready yet.
          }
        },
        onError: (message) => setError(message),
      })
    } catch (err) {
      if (err?.name !== "AbortError") {
        setError(err?.message || "Indexing failed.")
      }
    } finally {
      setIndexing(false)
    }
  }

  async function handleAnalyzePr() {
    setError("")
    setAnalyzing(true)
    setAgentSteps([])
    setAnalysisResult(null)

    try {
      await analyzePR(prUrl, {
        onAgentStep: (step) => {
          setAgentSteps((prev) => [...prev, step])
        },
        onResult: (result) => {
          setAnalysisResult(result)
        },
        onError: (message) => setError(message),
      })
    } catch (err) {
      if (err?.name !== "AbortError") {
        setError(err?.message || "Analysis failed.")
      }
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleCopyMarkdown() {
    if (!markdownReport) return
    try {
      await navigator.clipboard.writeText(markdownReport)
    } catch {
      setError("Could not copy report to clipboard.")
    }
  }

  return (
    <div className="min-h-screen app-bg text-slate-100 relative overflow-hidden">
      <div className="orb orb-one" />
      <div className="orb orb-two" />
      <main className="mx-auto max-w-6xl p-6 space-y-6 relative z-10">
        <header className="space-y-2 glass-panel p-4">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Qlankr - PR Impact Analysis</h1>
            {mockEnabled ? (
              <span className="rounded-full border border-cyan-400/60 bg-cyan-400/10 px-2.5 py-1 text-xs text-cyan-200 pulse-soft">
                Mock SSE mode enabled
              </span>
            ) : null}
          </div>
          <p className="text-sm text-slate-300">
            Step 1: Index repository. Step 2: Analyze a PR with live trace.
          </p>
        </header>

        {error ? (
          <div className="rounded-md border border-red-400/50 bg-red-500/10 p-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <RepoInput
          repoUrl={repoUrl}
          setRepoUrl={setRepoUrl}
          indexing={indexing}
          indexMessages={indexMessages}
          onConnect={handleIndexRepo}
          indexedRepo={indexedRepo}
        />

        <KnowledgeGraph graphData={graphData} />

        <PRInput
          prUrl={prUrl}
          setPrUrl={setPrUrl}
          disabled={analyzing}
          onSubmit={handleAnalyzePr}
        />

        <AgentTrace steps={agentSteps} loading={analyzing} />

        <ImpactSummary
          result={analysisResult}
          onCopyMarkdown={handleCopyMarkdown}
        />
      </main>
    </div>
  )
}
