/**
 * KnowledgeGraph — mock-friendly renderer with optional Sigma.js upgrade path.
 *
 * Scope modes:
 * - "all": full graph; selected cluster is emphasized (dim others).
 * - "selected": only nodes/edges belonging to the chosen cluster (if any).
 *
 * Graph viewport: pan (drag), zoom (wheel), scroll container; selecting a cluster
 * fits/zooms the view to that group. See specs for intended node/edge types.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

export default function KnowledgeGraph({ graphData }) {
  const [activeClusterId, setActiveClusterId] = useState(null)
  const [viewMode, setViewMode] = useState("graph")
  /** "all" = show everything + highlight selection; "selected" = filter to active cluster when set */
  const [scopeMode, setScopeMode] = useState("all")
  /** "overview" = cluster labels + file dots (less clutter); "full" = file labels on canvas */
  const [graphDensity, setGraphDensity] = useState("overview")

  const sectionRef = useRef(null)
  const graphViewportRef = useRef(null)
  const clusterAnchorRefs = useRef({})
  const viewBoxRef = useRef({ x: 0, y: 0, w: 1000, h: 380 })
  const dragPanRef = useRef(null)

  const nodes = graphData?.nodes || []
  const edges = graphData?.edges || []
  const clusters = graphData?.clusters || []

  const filterToClusterOnly = scopeMode === "selected" && activeClusterId

  const visibleNodes = useMemo(() => {
    if (!filterToClusterOnly) return nodes
    return nodes.filter((node) => node.cluster === activeClusterId)
  }, [nodes, activeClusterId, filterToClusterOnly])

  const visibleNodeIds = useMemo(() => {
    return new Set(visibleNodes.map((node) => node.id))
  }, [visibleNodes])

  const visibleEdges = useMemo(() => {
    if (!filterToClusterOnly) return edges
    return edges.filter(
      (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target),
    )
  }, [edges, visibleNodeIds, filterToClusterOnly])

  const highlightedNodeIds = useMemo(() => {
    if (!activeClusterId || filterToClusterOnly) return new Set()
    const match = clusters.find((c) => c.id === activeClusterId)
    if (!match) return new Set()
    return new Set(
      nodes.filter((node) => node.cluster === match.id).map((node) => node.id),
    )
  }, [activeClusterId, clusters, nodes, filterToClusterOnly])

  const isNodeEmphasized = (nodeId, clusterId) => {
    if (!activeClusterId) return true
    if (filterToClusterOnly) return true
    return clusterId === activeClusterId || highlightedNodeIds.has(nodeId)
  }

  const positionedNodes = useMemo(() => {
    const width = 1000
    const height = scopeMode === "selected" && activeClusterId ? 340 : 380
    const sourceNodes = visibleNodes
    const sourceEdges = visibleEdges

    const filesByCluster = new Map()
    for (const cluster of clusters) filesByCluster.set(cluster.id, [])
    for (const node of sourceNodes) {
      if (node.type === "file" && filesByCluster.has(node.cluster)) {
        filesByCluster.get(node.cluster).push(node)
      }
    }

    const renderedClusters = filterToClusterOnly
      ? clusters.filter((c) => c.id === activeClusterId)
      : clusters

    const clusterPositions = new Map()
    const total = Math.max(1, renderedClusters.length)
    renderedClusters.forEach((cluster, i) => {
      const cx = ((i + 1) * width) / (total + 1)
      clusterPositions.set(cluster.id, { x: cx, y: 100, node: cluster })
    })

    const coordinates = new Map()
    for (const cluster of renderedClusters) {
      const cp = clusterPositions.get(cluster.id)
      coordinates.set(`${cluster.id}__cluster`, {
        id: `${cluster.id}__cluster`,
        x: cp.x,
        y: cp.y,
        label: cluster.label,
        type: "cluster",
        cluster: cluster.id,
      })
      const files = filesByCluster.get(cluster.id) || []
      files.forEach((fileNode, idx) => {
        const spread = Math.max(1, files.length - 1)
        const offsetX = ((idx - spread / 2) * 110) / Math.max(1, spread)
        coordinates.set(fileNode.id, {
          id: fileNode.id,
          x: cp.x + offsetX,
          y: 240,
          label: fileNode.label,
          type: "file",
          cluster: cluster.id,
        })
      })
    }

    const lineEdges = sourceEdges
      .map((edge) => {
        const source =
          coordinates.get(edge.source) ||
          coordinates.get(`${sourceNodes.find((n) => n.id === edge.source)?.cluster}__cluster`)
        const target =
          coordinates.get(edge.target) ||
          coordinates.get(`${sourceNodes.find((n) => n.id === edge.target)?.cluster}__cluster`)
        if (!source || !target) return null
        return { ...edge, source, target }
      })
      .filter(Boolean)

    return { width, height, coordinates: Array.from(coordinates.values()), lineEdges }
  }, [clusters, visibleNodes, visibleEdges, activeClusterId, filterToClusterOnly, scopeMode])

  const positionedNodesRef = useRef(positionedNodes)
  positionedNodesRef.current = positionedNodes

  const [viewBox, setViewBox] = useState(() => ({
    x: 0,
    y: 0,
    w: 1000,
    h: 380,
  }))
  viewBoxRef.current = viewBox

  useEffect(() => {
    setViewBox((vb) => ({
      ...vb,
      w: positionedNodes.width,
      h: positionedNodes.height,
      x: Math.min(vb.x, Math.max(0, positionedNodes.width - vb.w)),
      y: Math.min(vb.y, Math.max(0, positionedNodes.height - vb.h)),
    }))
  }, [positionedNodes.width, positionedNodes.height])

  const fitViewToCluster = useCallback((clusterId) => {
    const pn = positionedNodesRef.current
    if (!clusterId) {
      setViewBox({
        x: 0,
        y: 0,
        w: pn.width,
        h: pn.height,
      })
      return
    }
    const pts = pn.coordinates.filter((n) => n.cluster === clusterId)
    if (!pts.length) return
    const xs = pts.map((p) => p.x)
    const ys = pts.map((p) => p.y)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const pad = 120
    const w = Math.min(pn.width, Math.max(280, maxX - minX + pad * 2))
    const h = Math.min(pn.height, Math.max(220, maxY - minY + pad * 2))
    const cx = (minX + maxX) / 2
    const cy = (minY + maxY) / 2
    let nx = cx - w / 2
    let ny = cy - h / 2
    nx = Math.max(0, Math.min(nx, pn.width - w))
    ny = Math.max(0, Math.min(ny, pn.height - h))
    setViewBox({ x: nx, y: ny, w, h })
  }, [])

  const handleClusterClick = (clusterId, toggleOff) => {
    const next = toggleOff ? null : clusterId
    setActiveClusterId(next)
    requestAnimationFrame(() => {
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
      graphViewportRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
      if (viewMode === "text" && next) {
        clusterAnchorRefs.current[next]?.scrollIntoView({ behavior: "smooth", block: "nearest" })
      }
    })
  }

  useEffect(() => {
    if (viewMode !== "graph") return
    if (activeClusterId) fitViewToCluster(activeClusterId)
    else fitViewToCluster(null)
  }, [activeClusterId, viewMode, fitViewToCluster])

  const onWheelGraph = useCallback((e) => {
    if (viewMode !== "graph") return
    e.preventDefault()
    const el = graphViewportRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const pn = positionedNodesRef.current
    const scale = e.deltaY > 0 ? 1.08 : 1 / 1.08
    setViewBox((vb) => {
      const mx = ((e.clientX - rect.left) / rect.width) * vb.w + vb.x
      const my = ((e.clientY - rect.top) / rect.height) * vb.h + vb.y
      let nw = Math.min(pn.width, Math.max(120, vb.w * scale))
      let nh = Math.min(pn.height, Math.max(100, vb.h * scale))
      let nx = mx - (mx - vb.x) * (nw / vb.w)
      let ny = my - (my - vb.y) * (nh / vb.h)
      nx = Math.max(0, Math.min(nx, pn.width - nw))
      ny = Math.max(0, Math.min(ny, pn.height - nh))
      return { x: nx, y: ny, w: nw, h: nh }
    })
  }, [viewMode])

  useEffect(() => {
    const el = graphViewportRef.current
    if (!el) return
    const handler = (e) => onWheelGraph(e)
    el.addEventListener("wheel", handler, { passive: false })
    return () => el.removeEventListener("wheel", handler)
  }, [onWheelGraph])

  const onMouseDownPan = (e) => {
    if (e.button !== 0) return
    const vb = viewBoxRef.current
    dragPanRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      vbX: vb.x,
      vbY: vb.y,
      vbW: vb.w,
      vbH: vb.h,
    }
  }

  useEffect(() => {
    const onMove = (e) => {
      const drag = dragPanRef.current
      if (!drag) return
      const el = graphViewportRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const dx = e.clientX - drag.startX
      const dy = e.clientY - drag.startY
      const scaleX = drag.vbW / rect.width
      const scaleY = drag.vbH / rect.height
      let nx = drag.vbX - dx * scaleX
      let ny = drag.vbY - dy * scaleY
      nx = Math.max(0, Math.min(nx, positionedNodes.width - drag.vbW))
      ny = Math.max(0, Math.min(ny, positionedNodes.height - drag.vbH))
      setViewBox({ x: nx, y: ny, w: drag.vbW, h: drag.vbH })
    }
    const onUp = () => {
      dragPanRef.current = null
    }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
    return () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
    }
  }, [positionedNodes.width, positionedNodes.height])

  const nodesByCluster = useMemo(() => {
    const m = new Map()
    for (const c of clusters) m.set(c.id, [])
    for (const n of visibleNodes) {
      if (!m.has(n.cluster)) m.set(n.cluster, [])
      m.get(n.cluster).push(n)
    }
    return m
  }, [visibleNodes, clusters])

  return (
    <section
      ref={sectionRef}
      className="rounded-xl border border-slate-600/80 bg-gradient-to-br from-slate-900/90 via-slate-900/70 to-slate-950/90 p-5 space-y-4 shadow-2xl backdrop-blur"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-slate-50">Knowledge graph</h2>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Clusters group files; edges show CONTAINS / CALLS / IMPORTS. Pan & zoom inside the
            canvas; pick a cluster to scroll/fit to that group.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-1">View</span>
          <button
            type="button"
            onClick={() => setViewMode("graph")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              viewMode === "graph"
                ? "bg-cyan-500/25 border-cyan-400/60 text-cyan-100 shadow-[0_0_12px_rgba(34,211,238,0.25)]"
                : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"
            }`}
          >
            Graphical
          </button>
          <button
            type="button"
            onClick={() => setViewMode("text")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              viewMode === "text"
                ? "bg-cyan-500/25 border-cyan-400/60 text-cyan-100 shadow-[0_0_12px_rgba(34,211,238,0.25)]"
                : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"
            }`}
          >
            Text
          </button>
          <span className="w-px h-5 bg-slate-600 mx-1 hidden sm:block" aria-hidden />
          <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-1">Scope</span>
          <button
            type="button"
            onClick={() => setScopeMode("all")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              scopeMode === "all"
                ? "bg-violet-500/25 border-violet-400/60 text-violet-100"
                : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"
            }`}
          >
            All + highlight
          </button>
          <button
            type="button"
            onClick={() => setScopeMode("selected")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              scopeMode === "selected"
                ? "bg-violet-500/25 border-violet-400/60 text-violet-100"
                : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"
            }`}
            title="Shows only the chosen cluster when one is selected"
          >
            Selected only
          </button>
          {viewMode === "graph" ? (
            <>
              <span className="w-px h-5 bg-slate-600 mx-1 hidden md:block" aria-hidden />
              <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-1">Density</span>
              <button
                type="button"
                onClick={() => setGraphDensity("overview")}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                  graphDensity === "overview"
                    ? "bg-emerald-500/20 border-emerald-400/50 text-emerald-100"
                    : "bg-slate-950/50 border-slate-600 text-slate-400"
                }`}
              >
                Overview
              </button>
              <button
                type="button"
                onClick={() => setGraphDensity("full")}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                  graphDensity === "full"
                    ? "bg-emerald-500/20 border-emerald-400/50 text-emerald-100"
                    : "bg-slate-950/50 border-slate-600 text-slate-400"
                }`}
              >
                Full labels
              </button>
            </>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {clusters.map((cluster) => {
          const active = activeClusterId === cluster.id
          return (
            <button
              key={cluster.id}
              type="button"
              onClick={() => handleClusterClick(cluster.id, active)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium border transition ${
                active
                  ? "bg-indigo-500/90 text-white border-indigo-300 shadow-[0_0_14px_rgba(99,102,241,0.45)]"
                  : "bg-slate-800/80 border-slate-600 text-slate-200 hover:border-slate-500 hover:bg-slate-800"
              }`}
            >
              {cluster.label}{" "}
              <span className="opacity-70">({cluster.size})</span>
            </button>
          )
        })}
      </div>

      {scopeMode === "selected" && !activeClusterId ? (
        <p className="text-xs text-amber-300/90 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2">
          Select a cluster above to isolate it, or switch scope to &quot;All + highlight&quot;.
        </p>
      ) : null}

      {viewMode === "graph" ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-500">
            <span>
              Drag to pan · wheel to zoom · cluster click fits view
            </span>
            <button
              type="button"
              onClick={() => fitViewToCluster(activeClusterId)}
              className="rounded border border-slate-600 px-2 py-1 text-slate-300 hover:bg-slate-800"
            >
              Refit selection
            </button>
            <button
              type="button"
              onClick={() => fitViewToCluster(null)}
              className="rounded border border-slate-600 px-2 py-1 text-slate-300 hover:bg-slate-800"
            >
              Show all
            </button>
          </div>
          <div
            ref={graphViewportRef}
            className="relative rounded-xl border border-slate-600/60 bg-slate-950/70 overflow-auto max-h-[min(65vh,520px)] shadow-inner cursor-grab active:cursor-grabbing select-none"
            onMouseDown={onMouseDownPan}
          >
            <svg
              width="100%"
              height={positionedNodes.height}
              style={{ minWidth: "min(100%, 480px)" }}
              viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
              preserveAspectRatio="xMidYMid meet"
              role="img"
              aria-label="Knowledge graph visualization"
            >
              <defs>
                <linearGradient id="kg-bg" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#0f172a" />
                  <stop offset="50%" stopColor="#0c1222" />
                  <stop offset="100%" stopColor="#020617" />
                </linearGradient>
                <filter id="kg-glow" x="-40%" y="-40%" width="180%" height="180%">
                  <feGaussianBlur stdDeviation="3" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <marker
                  id="arrow"
                  markerWidth="8"
                  markerHeight="8"
                  refX="6"
                  refY="4"
                  orient="auto"
                  markerUnits="strokeWidth"
                >
                  <path d="M0,0 L8,4 L0,8 z" fill="rgba(148,163,184,0.55)" />
                </marker>
              </defs>
              <rect
                x={0}
                y={0}
                width={positionedNodes.width}
                height={positionedNodes.height}
                fill="url(#kg-bg)"
                rx="12"
              />

              {positionedNodes.lineEdges.map((edge, idx) => {
                const dx = edge.target.x - edge.source.x
                const dy = edge.target.y - edge.source.y
                const len = Math.hypot(dx, dy) || 1
                const shorten = 14
                const x1 = edge.source.x + (dx / len) * shorten
                const y1 = edge.source.y + (dy / len) * shorten
                const x2 = edge.target.x - (dx / len) * shorten
                const y2 = edge.target.y - (dy / len) * shorten
                const midX = (x1 + x2) / 2
                const midY = (y1 + y2) / 2 - 8
                const inSel = (coord) =>
                  !activeClusterId || coord.cluster === activeClusterId
                const emphasized =
                  !activeClusterId ||
                  filterToClusterOnly ||
                  (inSel(edge.source) && inSel(edge.target))
                return (
                  <g key={`${edge.source.id}-${edge.target.id}-${idx}`}>
                    <path
                      d={`M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`}
                      fill="none"
                      stroke={emphasized ? "rgba(94,234,212,0.35)" : "rgba(51,65,85,0.45)"}
                      strokeWidth={emphasized ? 1.8 : 1}
                      markerEnd="url(#arrow)"
                      opacity={emphasized ? 1 : graphDensity === "overview" ? 0.25 : 0.35}
                    />
                  </g>
                )
              })}

              {positionedNodes.coordinates.map((node) => {
                const isCluster = node.type === "cluster"
                const emphasized = isNodeEmphasized(node.id, node.cluster)
                const labelShort =
                  node.label.length > 42 ? `${node.label.slice(0, 40)}…` : node.label
                if (isCluster) {
                  return (
                    <g
                      key={node.id}
                      filter={emphasized ? "url(#kg-glow)" : undefined}
                      opacity={emphasized ? 1 : 0.45}
                    >
                      <rect
                        x={node.x - 72}
                        y={node.y - 22}
                        width={144}
                        height={44}
                        rx={12}
                        fill={emphasized ? "rgba(34,211,238,0.18)" : "rgba(51,65,85,0.35)"}
                        stroke={emphasized ? "rgba(34,211,238,0.75)" : "rgba(71,85,105,0.6)"}
                        strokeWidth="1.5"
                      />
                      <text
                        x={node.x}
                        y={node.y + 4}
                        textAnchor="middle"
                        fill={emphasized ? "rgb(207,250,254)" : "rgb(148,163,184)"}
                        fontSize="11"
                        fontWeight="600"
                      >
                        {labelShort}
                      </text>
                    </g>
                  )
                }
                const showFileLabel = graphDensity === "full"
                return (
                  <g key={node.id} opacity={emphasized ? 1 : 0.35}>
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={emphasized ? (showFileLabel ? 9 : 6) : 5}
                      fill={
                        emphasized ? "rgba(129,140,248,0.85)" : "rgba(71,85,105,0.55)"
                      }
                      stroke={emphasized ? "rgba(196,181,253,0.9)" : "rgba(100,116,139,0.6)"}
                      strokeWidth="1.2"
                    />
                    {showFileLabel ? (
                      <text
                        x={node.x}
                        y={node.y + 22}
                        textAnchor="middle"
                        fill="rgba(226,232,240,0.88)"
                        fontSize="9"
                      >
                        {labelShort}
                      </text>
                    ) : null}
                  </g>
                )
              })}
            </svg>
          </div>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-slate-600/60 bg-slate-950/50 p-3 md:col-span-2 space-y-4 max-h-[min(65vh,520px)] overflow-y-auto">
            <p className="text-sm font-medium text-slate-200">Nodes by cluster</p>
            {clusters.map((cluster) => {
              const list = nodesByCluster.get(cluster.id) || []
              if (!list.length) return null
              return (
                <div
                  key={cluster.id}
                  id={`kg-cluster-${cluster.id}`}
                  ref={(el) => {
                    if (el) clusterAnchorRefs.current[cluster.id] = el
                  }}
                  className={`rounded-lg border p-3 transition ${
                    activeClusterId === cluster.id
                      ? "border-indigo-400/50 bg-indigo-500/10"
                      : "border-slate-700/80 bg-slate-900/40"
                  }`}
                >
                  <p className="text-xs font-semibold text-cyan-200/90 mb-2">{cluster.label}</p>
                  <ul className="space-y-1.5 text-xs">
                    {list.map((node) => {
                      const highlighted =
                        !filterToClusterOnly &&
                        highlightedNodeIds.has(node.id) &&
                        activeClusterId
                      return (
                        <li
                          key={node.id}
                          className={`rounded-lg px-2.5 py-1.5 border transition ${
                            highlighted
                              ? "bg-indigo-500/20 text-indigo-100 border-indigo-400/50"
                              : "bg-slate-900/80 text-slate-300 border-slate-700/80"
                          }`}
                        >
                          <span className="font-semibold text-cyan-400/90">[{node.type}]</span>{" "}
                          {node.label}
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )
            })}
          </div>

          <div className="rounded-xl border border-slate-600/60 bg-slate-950/50 p-3 md:col-span-2">
            <p className="text-sm font-medium mb-2 text-slate-200">Edges</p>
            <ul className="space-y-1.5 text-xs max-h-40 overflow-y-auto font-mono text-slate-400 pr-1">
              {visibleEdges.map((edge, idx) => (
                <li
                  key={`${edge.source}-${edge.target}-${idx}`}
                  className="rounded-lg px-2 py-1 bg-slate-900/60 border border-slate-800/80"
                >
                  <span className="text-emerald-400/80">{edge.source}</span>{" "}
                  <span className="text-slate-500">[{edge.type}]</span> →{" "}
                  <span className="text-sky-400/80">{edge.target}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  )
}
