/**
 * Backend-compatible mock graph payload generator.
 *
 * Output shape intentionally matches backend `GET /graph/{owner}/{repo}`:
 * {
 *   nodes: [{ id, label, type, cluster }],
 *   edges: [{ source, target, type }],
 *   clusters: [{ id, label, size }]
 * }
 *
 * This file is data-focused and independent from mock streaming logic.
 */

const GRAPH_BLUEPRINT = [
  {
    cluster: "auth",
    label: "Authentication",
    files: [
      "src/auth/tokens.py",
      "src/auth/middleware.py",
      "src/auth/providers/github.py",
      "src/auth/providers/steam.py",
      "src/auth/policies.py",
      "src/auth/sessions.py",
    ],
  },
  {
    cluster: "api",
    label: "API Gateway",
    files: [
      "src/api/routes.py",
      "src/api/controller.py",
      "src/api/validators.py",
      "src/api/serializers.py",
      "src/api/error_map.py",
      "src/api/rate_limit.py",
    ],
  },
  {
    cluster: "session",
    label: "Session Lifecycle",
    files: [
      "src/session/store.py",
      "src/session/manager.py",
      "src/session/revocation.py",
      "src/session/persistence.py",
      "src/session/cache.py",
      "src/session/audit.py",
    ],
  },
  {
    cluster: "qa",
    label: "QA Analysis Core",
    files: [
      "src/analysis/pr_parser.py",
      "src/analysis/risk_engine.py",
      "src/analysis/component_mapper.py",
      "src/analysis/test_suggestions.py",
      "src/analysis/confidence.py",
      "src/analysis/report_builder.py",
    ],
  },
  {
    cluster: "graph",
    label: "Knowledge Graph",
    files: [
      "src/graph/indexer.py",
      "src/graph/cluster_map.py",
      "src/graph/call_chain.py",
      "src/graph/dependency_edges.py",
      "src/graph/symbols.py",
      "src/graph/query_adapter.py",
    ],
  },
  {
    cluster: "workers",
    label: "Async Workers",
    files: [
      "src/workers/index_jobs.py",
      "src/workers/analyze_jobs.py",
      "src/workers/retry_policy.py",
      "src/workers/event_bus.py",
      "src/workers/heartbeat.py",
      "src/workers/state_tracker.py",
    ],
  },
  {
    cluster: "ui",
    label: "UI Integration",
    files: [
      "src/ui/sse_events.py",
      "src/ui/trace_feed.py",
      "src/ui/summary_mapper.py",
      "src/ui/graph_response.py",
      "src/ui/error_state.py",
      "src/ui/copy_markdown.py",
    ],
  },
  {
    cluster: "data",
    label: "Data Access",
    files: [
      "src/data/repo_clone.py",
      "src/data/repo_cache.py",
      "src/data/git_metadata.py",
      "src/data/path_resolver.py",
      "src/data/snapshot_store.py",
      "src/data/cleanup.py",
    ],
  },
  {
    cluster: "integrations",
    label: "External Integrations",
    files: [
      "src/integrations/github_mcp.py",
      "src/integrations/gitnexus_mcp.py",
      "src/integrations/health.py",
      "src/integrations/token_scope.py",
      "src/integrations/provider_status.py",
      "src/integrations/tool_router.py",
    ],
  },
  {
    cluster: "observability",
    label: "Observability",
    files: [
      "src/obs/logging.py",
      "src/obs/metrics.py",
      "src/obs/tracing.py",
      "src/obs/error_report.py",
      "src/obs/perf_budget.py",
      "src/obs/audit_events.py",
    ],
  },
]

function toNodeId(owner, repo, raw) {
  return `${owner}-${repo}-${raw.replaceAll("/", "_").replaceAll(".", "_")}`
}

export function buildMockGraph(owner, repo) {
  const nodes = []
  const edges = []
  const clusters = []

  for (const clusterSpec of GRAPH_BLUEPRINT) {
    const clusterNodeId = toNodeId(owner, repo, `cluster-${clusterSpec.cluster}`)

    nodes.push({
      id: clusterNodeId,
      label: `${clusterSpec.label} Cluster`,
      type: "cluster",
      cluster: clusterSpec.cluster,
    })

    const fileNodeIds = []

    for (const filePath of clusterSpec.files) {
      const fileNodeId = toNodeId(owner, repo, filePath)
      fileNodeIds.push(fileNodeId)
      nodes.push({
        id: fileNodeId,
        label: filePath,
        type: "file",
        cluster: clusterSpec.cluster,
      })
      edges.push({
        source: clusterNodeId,
        target: fileNodeId,
        type: "CONTAINS",
      })
    }

    for (let i = 1; i < fileNodeIds.length; i += 1) {
      edges.push({
        source: fileNodeIds[i - 1],
        target: fileNodeIds[i],
        type: i % 2 === 0 ? "IMPORTS" : "CALLS",
      })
    }

    clusters.push({
      id: clusterSpec.cluster,
      label: `${clusterSpec.label} Cluster`,
      size: clusterSpec.files.length,
    })
  }

  for (let i = 0; i < GRAPH_BLUEPRINT.length - 1; i += 1) {
    const current = GRAPH_BLUEPRINT[i]
    const next = GRAPH_BLUEPRINT[i + 1]
    const currentEntry = toNodeId(owner, repo, current.files[0])
    const nextEntry = toNodeId(owner, repo, next.files[0])
    edges.push({ source: currentEntry, target: nextEntry, type: "CALLS" })
  }

  return { nodes, edges, clusters }
}
