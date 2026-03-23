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

export function extractOwnerRepo(repoUrl) {
  try {
    const parsed = new URL(repoUrl)
    const parts = parsed.pathname.split("/").filter(Boolean)
    if (parts.length < 2) return null
    return { owner: parts[0], repo: parts[1].replace(".git", "") }
  } catch {
    return null
  }
}

export function buildMarkdownReport(result) {
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
  const [repoUrl, setRepoUrl] = useState("")
  const [indexing, setIndexing] = useState(false)
  const [indexMessages, setIndexMessages] = useState([])
  const [indexedRepo, setIndexedRepo] = useState(null)

  const [graphData, setGraphData] = useState(MOCK_GRAPH)

  const [prUrl, setPrUrl] = useState("")
  const [analyzing, setAnalyzing] = useState(false)
  const [agentSteps, setAgentSteps] = useState([])
  const [analysisResult, setAnalysisResult] = useState(null)

  const [focusedFiles, setFocusedFiles] = useState(null)

  const [error, setError] = useState("")
  const mockEnabled = isMockSseEnabled()

  const markdownReport = useMemo(
    () => buildMarkdownReport(analysisResult),
    [analysisResult],
  )

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
      // ignore broken cache
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
      // quota or private mode
    }
  }, [repoUrl, prUrl, indexedRepo, indexMessages, graphData, analysisResult, agentSteps])

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
            // keep mock graph
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
    <div className="min-h-screen bg-void text-text-primary font-sans">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border-subtle bg-deep/80 backdrop-blur-md px-6 py-3 flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-accent animate-breathe" />
          <span className="font-semibold tracking-tight">Qlankr</span>
        </div>
        <span className="text-text-muted text-sm hidden sm:block">/ PR Impact Analysis</span>
        {mockEnabled && (
          <span className="ml-auto text-xs text-accent border border-accent/30 bg-accent/10 rounded-full px-2.5 py-0.5 pulse-soft">
            Mock SSE
          </span>
        )}
      </header>

      {/* Main */}
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-4">
        {error && (
          <div className="animate-slide-up rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <RepoInput
          repoUrl={repoUrl}
          setRepoUrl={setRepoUrl}
          indexing={indexing}
          indexMessages={indexMessages}
          onConnect={handleIndexRepo}
          indexedRepo={indexedRepo}
        />

        <KnowledgeGraph graphData={graphData} focusedFiles={focusedFiles} />

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
          focusedFiles={focusedFiles}
          onFocusFiles={(files) => setFocusedFiles(prev =>
            prev && prev.length === files.length && prev.every((f, i) => f === files[i]) ? null : files
          )}
        />
      </main>
    </div>
  )
}
