/**
 * KnowledgeGraph — Sigma.js WebGL renderer with ForceAtlas2 layout.
 *
 * Inspired by GitNexus's GraphCanvas design:
 * - Dark void background
 * - Purple accent for cluster nodes
 * - Per-cluster color coding for file nodes
 * - Interactive: click cluster pills to filter, zoom controls, hover tooltips
 * - ForceAtlas2 physics layout for natural cluster grouping
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Graph from "graphology"
import Sigma from "sigma"
import forceAtlas2 from "graphology-layout-forceatlas2"
import { circular } from "graphology-layout"
import { ZoomIn, ZoomOut, Maximize2, RotateCcw } from "lucide-react"

// Color palette for clusters (file nodes inherit their cluster's color)
const CLUSTER_NODE_COLOR = "#7c3aed"  // accent purple for cluster hub nodes
const CLUSTER_PALETTE = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ec4899", // pink
  "#14b8a6", // teal
  "#6366f1", // indigo
  "#ef4444", // red
  "#8b5cf6", // violet
  "#f97316", // orange
  "#06b6d4", // cyan
]

function dimHex(hex, alpha = 0.2) {
  return hex + Math.round(alpha * 255).toString(16).padStart(2, "0")
}

function hashInt(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) h = (Math.imul(31, h) + str.charCodeAt(i)) | 0
  return Math.abs(h)
}

/**
 * Force-directed layout — runs synchronously, fast enough for ~300–500 nodes.
 * Cross-cluster repulsion is much stronger than same-cluster to carve out
 * distinct territories in 2D space.
 */
function runForceLayout(nodeList, edgeList, width, height) {
  const ITER        = 180
  const REP_FF_SAME =  4000   // file ↔ file, same cluster
  const REP_FF_DIFF = 35000   // file ↔ file, different cluster — primary driver of separation
  const REP_CC      = 80000   // cluster label ↔ cluster label
  const REP_CF      = 40000   // cluster label ↔ any file
  const K_EDGE      =  0.018  // edge spring attraction
  const K_COHESION  =  0.10   // file → its cluster label (keep clusters tight)
  const DAMP        =  0.74

  const pos = new Map()

  const clusterNodes = nodeList.filter(n => n.type === "cluster")
  const NC = Math.max(1, clusterNodes.length)
  clusterNodes.forEach((n, i) => {
    const angle = (i / NC) * 2 * Math.PI - Math.PI / 2
    const r = Math.min(width, height) * 0.36
    pos.set(n.id, {
      x: width / 2 + (NC > 1 ? r * Math.cos(angle) : 0),
      y: height / 2 + (NC > 1 ? r * Math.sin(angle) : 0),
      vx: 0, vy: 0,
    })
  })

  nodeList.filter(n => n.type === "file").forEach(n => {
    const cp = pos.get(`${n.cluster}__cluster`) ?? { x: width / 2, y: height / 2 }
    const h = hashInt(n.id)
    const angle = (h % 10000) / 10000 * 2 * Math.PI
    const r = 30 + (h % 110)
    pos.set(n.id, { x: cp.x + r * Math.cos(angle), y: cp.y + r * Math.sin(angle), vx: 0, vy: 0 })
  })

  const arr = nodeList.filter(n => pos.has(n.id))

  for (let iter = 0; iter < ITER; iter++) {
    const cool = Math.max(0.04, 1 - iter / ITER)

    for (let i = 0; i < arr.length; i++) {
      const a = pos.get(arr[i].id)
      for (let j = i + 1; j < arr.length; j++) {
        const b = pos.get(arr[j].id)
        const dx = b.x - a.x || 0.1
        const dy = b.y - a.y || 0.1
        const d2 = Math.max(100, dx * dx + dy * dy)
        const d  = Math.sqrt(d2)
        const ti = arr[i].type, tj = arr[j].type
        const sameCluster = arr[i].cluster === arr[j].cluster
        const rep = ti === "cluster" && tj === "cluster" ? REP_CC
          : ti === "cluster" || tj === "cluster" ? REP_CF
          : sameCluster ? REP_FF_SAME : REP_FF_DIFF
        const f = rep / d2
        const fx = (dx / d) * f, fy = (dy / d) * f
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy
      }
    }

    for (const e of edgeList) {
      const a = pos.get(e.source), b = pos.get(e.target)
      if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const f = d * K_EDGE
      const fx = (dx / d) * f, fy = (dy / d) * f
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy
    }

    for (const n of arr) {
      if (n.type !== "file") continue
      const a = pos.get(n.id), b = pos.get(`${n.cluster}__cluster`)
      if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const f = d * K_COHESION
      a.vx += (dx / d) * f; a.vy += (dy / d) * f
    }

    for (const n of arr) {
      const p = pos.get(n.id)
      p.x += p.vx * cool; p.y += p.vy * cool
      p.vx *= DAMP; p.vy *= DAMP
    }
  }

  const PAD = 100
  const xs = arr.map(n => pos.get(n.id).x), ys = arr.map(n => pos.get(n.id).y)
  const x0 = Math.min(...xs), x1 = Math.max(...xs)
  const y0 = Math.min(...ys), y1 = Math.max(...ys)
  const sx = (width - PAD * 2) / Math.max(1, x1 - x0)
  const sy = (height - PAD * 2) / Math.max(1, y1 - y0)
  const sc = Math.min(sx, sy)
  const ox = (width  - (x1 - x0) * sc) / 2
  const oy = (height - (y1 - y0) * sc) / 2
  for (const n of arr) {
    const p = pos.get(n.id)
    p.x = ox + (p.x - x0) * sc
    p.y = oy + (p.y - y0) * sc
  }

  return pos
}

export default function KnowledgeGraph({ graphData }) {
  const containerRef = useRef(null)
  const sigmaRef = useRef(null)
  const graphRef = useRef(null)
  const activeClusterRef = useRef(null)

  const [activeCluster, setActiveCluster] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null) // { label, x, y }
  const [stats, setStats] = useState({ nodes: 0, edges: 0, clusters: 0 })
  const [viewMode, setViewMode] = useState("graph") // "graph" | "list"

  const nodes    = graphData?.nodes    || []
  const edges    = graphData?.edges    || []
  const clusters = (graphData?.clusters || []).filter(c => c.size > 0)

  // Stable color map: cluster id → color
  const clusterColorMap = useMemo(() => {
    const map = {}
    clusters.forEach((c, i) => {
      map[c.id] = CLUSTER_PALETTE[i % CLUSTER_PALETTE.length]
    })
    return map
  }, [clusters])

  // Build and render graph whenever data changes
  useEffect(() => {
    const container = containerRef.current
    if (!container || viewMode !== "graph") return

    // Destroy previous instance
    if (sigmaRef.current) {
      sigmaRef.current.kill()
      sigmaRef.current = null
    }

    if (!nodes.length) return

    const graph = new Graph({ multi: false, type: "directed" })
    graphRef.current = graph

    // Add nodes
    for (const node of nodes) {
      const isCluster = node.type === "cluster"
      const color = isCluster
        ? CLUSTER_NODE_COLOR
        : (clusterColorMap[node.cluster] || CLUSTER_PALETTE[0])
      graph.addNode(node.id, {
        label: node.label,
        size: isCluster ? 16 : 5,
        color,
        borderColor: isCluster ? "#a78bfa" : color,
        nodeType: node.type,
        cluster: node.cluster,
        x: Math.random() * 100,
        y: Math.random() * 100,
      })
    }

    // Add edges (skip duplicates and self-loops)
    for (const edge of edges) {
      if (edge.source === edge.target) continue
      if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) continue
      try {
        graph.addEdge(edge.source, edge.target, {
          size: 1.2,
          color: "rgba(124,58,237,0.22)",
          edgeType: edge.type,
        })
      } catch {
        // skip duplicate edges
      }
    }

    // Layout: circular seed then ForceAtlas2
    circular.assign(graph)
    forceAtlas2.assign(graph, {
      iterations: 150,
      settings: {
        gravity: 1.5,
        scalingRatio: 8,
        strongGravityMode: false,
        barnesHutOptimize: graph.order > 100,
        barnesHutTheta: 0.5,
        adjustSizes: true,
      },
    })
    setStats({
      nodes: graph.order,
      edges: graph.size,
      clusters: clusters.length,
    })

    // Create Sigma renderer
    const renderer = new Sigma(graph, container, {
      renderEdgeLabels: false,
      defaultEdgeColor: "rgba(124,58,237,0.22)",
      defaultNodeColor: CLUSTER_NODE_COLOR,
      labelColor: { color: "#e4e4ed" },
      labelSize: 11,
      labelWeight: "500",
      labelFont: "Outfit, system-ui, sans-serif",
      labelDensity: 0.07,
      labelGridCellSize: 120,
      allowInvalidContainer: true,
      nodeReducer: (node, data) => {
        const cluster = activeClusterRef.current
        if (!cluster) return { ...data, highlighted: false }
        if (data.cluster === cluster || (data.nodeType === "cluster" && data.cluster === cluster)) {
          return { ...data, highlighted: true, size: data.size * 1.3 }
        }
        return {
          ...data,
          color: "rgba(42,42,58,0.55)",
          borderColor: "rgba(42,42,58,0.3)",
          size: data.size * 0.6,
          label: "",
        }
      },
      edgeReducer: (edge, data) => {
        const cluster = activeClusterRef.current
        if (!cluster) return { ...data }
        const src = graph.getNodeAttribute(graph.source(edge), "cluster")
        const tgt = graph.getNodeAttribute(graph.target(edge), "cluster")
        if (src === cluster && tgt === cluster) {
          return { ...data, color: "rgba(124,58,237,0.55)", size: 2 }
        }
        return { ...data, color: "rgba(42,42,58,0.15)", size: 0.5 }
      },
    })

    sigmaRef.current = renderer

    // Hover events
    renderer.on("enterNode", ({ node, event }) => {
      const attrs = graph.getNodeAttributes(node)
      const pos = renderer.graphToViewport({ x: attrs.x, y: attrs.y })
      const rect = container.getBoundingClientRect()
      setHoveredNode({
        label: attrs.label,
        x: pos.x,
        y: pos.y,
        containerRect: rect,
      })
      container.style.cursor = "pointer"
    })
    renderer.on("leaveNode", () => {
      setHoveredNode(null)
      container.style.cursor = "default"
    })

    // Click on empty canvas clears selection
    renderer.on("clickStage", () => {
      setActiveCluster(null)
      activeClusterRef.current = null
      renderer.refresh()
    })
    return () => {
      renderer.kill()
      sigmaRef.current = null
    }
  }, [nodes, edges, clusters, clusterColorMap, viewMode])

  // Update reducers when activeCluster changes without rebuilding
  useEffect(() => {
    activeClusterRef.current = activeCluster
    if (sigmaRef.current) {
      sigmaRef.current.refresh()
    }
  }, [activeCluster])

  const handleClusterClick = useCallback((clusterId) => {
    const next = activeCluster === clusterId ? null : clusterId
    setActiveCluster(next)
    activeClusterRef.current = next
    if (sigmaRef.current) sigmaRef.current.refresh()
  }, [activeCluster])

  const handleZoomIn = useCallback(() => {
    const camera = sigmaRef.current?.getCamera()
    if (!camera) return
    camera.animate({ ratio: camera.ratio / 1.4 }, { duration: 200 })
  }, [])

  const handleZoomOut = useCallback(() => {
    const camera = sigmaRef.current?.getCamera()
    if (!camera) return
    camera.animate({ ratio: camera.ratio * 1.4 }, { duration: 200 })
  }, [])

  const handleReset = useCallback(() => {
    sigmaRef.current?.getCamera().animate({ x: 0.5, y: 0.5, ratio: 1, angle: 0 }, { duration: 300 })
  }, [])

  const handleFitGraph = useCallback(() => {
    const renderer = sigmaRef.current
    if (!renderer) return
    renderer.getCamera().animatedReset({ duration: 400 })
  }, [])

  // Nodes grouped by cluster for list view
  const nodesByCluster = useMemo(() => {
    const map = new Map()
    for (const c of clusters) map.set(c.id, [])
    for (const n of nodes) {
      if (n.type === "file") {
        if (!map.has(n.cluster)) map.set(n.cluster, [])
        map.get(n.cluster).push(n)
      }
    }
    return map
  }, [nodes, clusters])

  return (
    <section className="rounded-xl border border-border-default bg-surface overflow-hidden">
      {/* Panel header */}
      <div className="px-5 py-3.5 border-b border-border-subtle flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-text-primary">Knowledge Graph</h2>
          <div className="flex items-center gap-2 text-[11px] text-text-muted font-mono">
            <span className="px-1.5 py-0.5 rounded bg-elevated border border-border-subtle">
              {stats.nodes} nodes
            </span>
            <span className="px-1.5 py-0.5 rounded bg-elevated border border-border-subtle">
              {stats.edges} edges
            </span>
            <span className="px-1.5 py-0.5 rounded bg-elevated border border-border-subtle">
              {stats.clusters} clusters
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setViewMode("graph")}
            className={`px-3 py-1 rounded text-xs font-medium transition-all ${
              viewMode === "graph"
                ? "bg-accent/20 text-accent border border-accent/40"
                : "text-text-secondary border border-transparent hover:border-border-default hover:text-text-primary"
            }`}
          >
            Graph
          </button>
          <button
            type="button"
            onClick={() => setViewMode("list")}
            className={`px-3 py-1 rounded text-xs font-medium transition-all ${
              viewMode === "list"
                ? "bg-accent/20 text-accent border border-accent/40"
                : "text-text-secondary border border-transparent hover:border-border-default hover:text-text-primary"
            }`}
          >
            List
          </button>
        </div>
      </div>

      {/* Cluster filter pills */}
      {clusters.length > 0 && (
        <div className="px-5 py-2.5 border-b border-border-subtle flex flex-wrap gap-2">
          {clusters.map((cluster) => {
            const color = clusterColorMap[cluster.id] || CLUSTER_PALETTE[0]
            const isActive = activeCluster === cluster.id
            return (
              <button
                key={cluster.id}
                type="button"
                onClick={() => handleClusterClick(cluster.id)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-all ${
                  isActive
                    ? "border-current bg-current/15 shadow-glow"
                    : "border-border-default bg-elevated text-text-secondary hover:border-current hover:text-text-primary"
                }`}
                style={{ color: isActive ? color : undefined, borderColor: isActive ? color : undefined }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: color }}
                />
                {cluster.label}
                <span className="opacity-60 font-mono">({cluster.size})</span>
              </button>
            )
          })}
          {activeCluster && (
            <button
              type="button"
              onClick={() => handleClusterClick(null)}
              className="px-3 py-1 rounded-full text-xs border border-border-default text-text-muted hover:border-border-default hover:text-text-secondary transition-all"
            >
              Clear filter ×
            </button>
          )}
        </div>
      )}

      {viewMode === "graph" ? (
        <div className="relative bg-deep" style={{ height: "480px" }}>
          {/* Sigma canvas container */}
          <div ref={containerRef} className="sigma-container" />

          {/* Hover tooltip */}
          {hoveredNode && (
            <div
              className="pointer-events-none absolute z-20 px-2.5 py-1.5 rounded-lg bg-elevated border border-border-default text-xs text-text-primary shadow-glow-soft whitespace-nowrap animate-fade-in"
              style={{
                left: Math.min(hoveredNode.x + 14, (hoveredNode.containerRect?.width || 480) - 200),
                top: Math.max(hoveredNode.y - 28, 4),
              }}
            >
              {hoveredNode.label}
            </div>
          )}

          {/* Zoom controls */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-1 z-10">
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-1.5 rounded-lg bg-elevated border border-border-default text-text-secondary hover:text-text-primary hover:border-border-default transition-all"
              title="Zoom in"
            >
              <ZoomIn size={14} />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-1.5 rounded-lg bg-elevated border border-border-default text-text-secondary hover:text-text-primary hover:border-border-default transition-all"
              title="Zoom out"
            >
              <ZoomOut size={14} />
            </button>
            <button
              type="button"
              onClick={handleFitGraph}
              className="p-1.5 rounded-lg bg-elevated border border-border-default text-text-secondary hover:text-text-primary hover:border-border-default transition-all"
              title="Fit to screen"
            >
              <Maximize2 size={14} />
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="p-1.5 rounded-lg bg-elevated border border-border-default text-text-secondary hover:text-text-primary hover:border-border-default transition-all"
              title="Reset camera"
            >
              <RotateCcw size={14} />
            </button>
          </div>

          {/* Legend */}
          <div className="absolute bottom-4 left-4 flex flex-col gap-1.5 z-10">
            <div className="flex items-center gap-2 text-[10px] text-text-muted">
              <span className="w-3 h-3 rounded-full bg-accent flex-shrink-0" />
              Cluster hub
            </div>
            {clusters.slice(0, 4).map((c) => (
              <div key={c.id} className="flex items-center gap-2 text-[10px] text-text-muted">
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: clusterColorMap[c.id] }}
                />
                {c.label}
              </div>
            ))}
            {clusters.length > 4 && (
              <div className="text-[10px] text-text-muted opacity-60">
                +{clusters.length - 4} more
              </div>
            )}
          </div>

          {/* Hint */}
          <div className="absolute top-3 left-1/2 -translate-x-1/2 text-[10px] text-text-muted pointer-events-none">
            Scroll to zoom · Drag to pan · Click pill to filter
          </div>
        </div>
      ) : (
        /* List view */
        <div className="p-5 space-y-3 max-h-[480px] overflow-y-auto scrollbar-thin">
          {clusters.map((cluster) => {
            const fileNodes = nodesByCluster.get(cluster.id) || []
            const color = clusterColorMap[cluster.id] || CLUSTER_PALETTE[0]
            const isActive = activeCluster === cluster.id
            return (
              <div
                key={cluster.id}
                className={`rounded-lg border p-3 transition-all ${
                  isActive
                    ? "border-current bg-current/5"
                    : "border-border-default bg-elevated"
                }`}
                style={{ borderColor: isActive ? color : undefined }}
              >
                <div className="flex items-center gap-2 mb-2.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                  <p className="text-xs font-semibold" style={{ color }}>{cluster.label}</p>
                  <span className="ml-auto text-[10px] font-mono text-text-muted">{fileNodes.length} files</span>
                </div>
                <ul className="space-y-1">
                  {fileNodes.map((node) => (
                    <li
                      key={node.id}
                      className="text-xs text-text-secondary font-mono px-2 py-1 rounded bg-deep border border-border-subtle truncate"
                      title={node.label}
                    >
                      {node.label}
                    </li>
                  ))}
                  {fileNodes.length === 0 && (
                    <li className="text-xs text-text-muted italic">No file nodes</li>
                  )}
                </ul>
              </div>
            )
          })}

          {/* Edges section */}
          {edges.length > 0 && (
            <div className="rounded-lg border border-border-default bg-elevated p-3">
              <p className="text-xs font-semibold text-text-secondary mb-2">Edges ({edges.length})</p>
              <ul className="space-y-1 max-h-36 overflow-y-auto scrollbar-thin">
                {edges.map((edge, idx) => (
                  <li
                    key={`${edge.source}-${edge.target}-${idx}`}
                    className="text-[11px] font-mono text-text-muted px-2 py-0.5 rounded bg-deep border border-border-subtle"
                  >
                    <span className="text-blue-400/80">{edge.source}</span>
                    {" "}
                    <span className="text-text-muted opacity-60">[{edge.type}]</span>
                    {" → "}
                    <span className="text-emerald-400/80">{edge.target}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
