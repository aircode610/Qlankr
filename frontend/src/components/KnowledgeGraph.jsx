/**
 * KnowledgeGraph — force-directed layout (static, runs once on data change).
 *
 * Scope modes:
 * - "all": full graph; selected cluster is emphasized (dim others).
 * - "selected": only nodes/edges belonging to the chosen cluster (if any).
 *
 * Graph viewport: pan (drag), zoom (wheel); selecting a cluster fits the view.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

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

const CLUSTER_PALETTE = [
  { stroke: "rgba(34,211,238,0.45)",  node: "rgba(34,211,238,0.2)",  nodeBorder: "rgba(34,211,238,0.8)",  dot: "rgba(34,211,238,0.85)",  dotBorder: "rgba(165,243,252,0.9)",  text: "rgb(207,250,254)" },
  { stroke: "rgba(167,139,250,0.45)", node: "rgba(167,139,250,0.2)", nodeBorder: "rgba(167,139,250,0.8)", dot: "rgba(167,139,250,0.85)", dotBorder: "rgba(221,214,254,0.9)", text: "rgb(237,233,254)" },
  { stroke: "rgba(52,211,153,0.45)",  node: "rgba(52,211,153,0.2)",  nodeBorder: "rgba(52,211,153,0.8)",  dot: "rgba(52,211,153,0.85)",  dotBorder: "rgba(187,247,208,0.9)",  text: "rgb(209,250,229)" },
  { stroke: "rgba(251,146,60,0.45)",  node: "rgba(251,146,60,0.2)",  nodeBorder: "rgba(251,146,60,0.8)",  dot: "rgba(251,146,60,0.85)",  dotBorder: "rgba(253,211,155,0.9)",  text: "rgb(254,243,199)" },
  { stroke: "rgba(244,114,182,0.45)", node: "rgba(244,114,182,0.2)", nodeBorder: "rgba(244,114,182,0.8)", dot: "rgba(244,114,182,0.85)", dotBorder: "rgba(251,207,232,0.9)", text: "rgb(253,242,248)" },
  { stroke: "rgba(56,189,248,0.45)",  node: "rgba(56,189,248,0.2)",  nodeBorder: "rgba(56,189,248,0.8)",  dot: "rgba(56,189,248,0.85)",  dotBorder: "rgba(186,230,253,0.9)",  text: "rgb(224,242,254)" },
  { stroke: "rgba(234,179,8,0.45)",   node: "rgba(234,179,8,0.2)",   nodeBorder: "rgba(234,179,8,0.8)",   dot: "rgba(234,179,8,0.85)",   dotBorder: "rgba(253,240,138,0.9)",   text: "rgb(254,249,195)" },
]

export default function KnowledgeGraph({ graphData }) {
  const [activeClusterId, setActiveClusterId] = useState(null)
  const [viewMode, setViewMode] = useState("graph")
  const [scopeMode, setScopeMode] = useState("all")
  const [graphDensity, setGraphDensity] = useState("overview")
  const [tooltip, setTooltip] = useState(null)

  const sectionRef        = useRef(null)
  const graphViewportRef  = useRef(null)
  const clusterAnchorRefs = useRef({})
  const viewBoxRef        = useRef({ x: 0, y: 0, w: 1000, h: 380 })
  const dragPanRef        = useRef(null)

  const nodes    = graphData?.nodes    || []
  const edges    = graphData?.edges    || []
  const clusters = (graphData?.clusters || []).filter(c => c.size > 0)

  const filterToClusterOnly = scopeMode === "selected" && activeClusterId

  const visibleNodes = useMemo(() => {
    if (!filterToClusterOnly) return nodes
    return nodes.filter(n => n.cluster === activeClusterId)
  }, [nodes, activeClusterId, filterToClusterOnly])

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map(n => n.id)), [visibleNodes])

  const visibleEdges = useMemo(() => {
    if (!filterToClusterOnly) return edges
    return edges.filter(e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
  }, [edges, visibleNodeIds, filterToClusterOnly])

  const highlightedNodeIds = useMemo(() => {
    if (!activeClusterId || filterToClusterOnly) return new Set()
    const match = clusters.find(c => c.id === activeClusterId)
    if (!match) return new Set()
    return new Set(nodes.filter(n => n.cluster === match.id).map(n => n.id))
  }, [activeClusterId, clusters, nodes, filterToClusterOnly])

  const clusterColorIndex = useMemo(() => {
    const m = new Map()
    clusters.forEach((c, i) => m.set(c.id, i % CLUSTER_PALETTE.length))
    return m
  }, [clusters])

  const isNodeEmphasized = (nodeId, clusterId) => {
    if (!activeClusterId) return true
    if (filterToClusterOnly) return true
    return clusterId === activeClusterId || highlightedNodeIds.has(nodeId)
  }

  const positionedNodes = useMemo(() => {
    const sourceNodes = visibleNodes
    const sourceEdges = visibleEdges

    const filesByCluster = new Map()
    for (const cluster of clusters) filesByCluster.set(cluster.id, [])
    for (const node of sourceNodes) {
      if (node.type === "file" && filesByCluster.has(node.cluster))
        filesByCluster.get(node.cluster).push(node)
    }

    const renderedClusters = filterToClusterOnly
      ? clusters.filter(c => c.id === activeClusterId)
      : clusters

    const totalNodes = visibleNodes.length + renderedClusters.length
    const canvasW = Math.max(2400, totalNodes * 11)
    const canvasH = Math.max(1800, totalNodes * 11)

    const empty = { width: canvasW, height: canvasH, coordinates: [], lineEdges: [], renderedClusters }
    if (!renderedClusters.length) return empty

    const nodeList = []
    for (const cluster of renderedClusters) {
      const fileCount = (filesByCluster.get(cluster.id) || []).length
      nodeList.push({ id: `${cluster.id}__cluster`, type: "cluster", cluster: cluster.id, label: cluster.label, fileCount })
      for (const f of filesByCluster.get(cluster.id) || [])
        nodeList.push({ id: f.id, type: "file", cluster: cluster.id, label: f.label })
    }

    const flatEdges = sourceEdges.map(e => ({ source: e.source, target: e.target }))
    const finalPos  = runForceLayout(nodeList, flatEdges, canvasW, canvasH)

    const coordinates = nodeList.map(n => {
      const p = finalPos.get(n.id) ?? { x: canvasW / 2, y: canvasH / 2 }
      return { id: n.id, x: p.x, y: p.y, label: n.label, type: n.type, cluster: n.cluster }
    })
    const coordMap = new Map(coordinates.map(c => [c.id, c]))

    const lineEdges = sourceEdges
      .map(edge => {
        const source = coordMap.get(edge.source)
          ?? coordMap.get(`${sourceNodes.find(n => n.id === edge.source)?.cluster}__cluster`)
        const target = coordMap.get(edge.target)
          ?? coordMap.get(`${sourceNodes.find(n => n.id === edge.target)?.cluster}__cluster`)
        if (!source || !target) return null
        return { ...edge, source, target }
      })
      .filter(Boolean)

    return { width: canvasW, height: canvasH, coordinates, lineEdges, renderedClusters }
  }, [clusters, visibleNodes, visibleEdges, activeClusterId, filterToClusterOnly])

  const positionedNodesRef = useRef(positionedNodes)
  positionedNodesRef.current = positionedNodes

  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 1000, h: 380 })
  viewBoxRef.current = viewBox

  useEffect(() => {
    setViewBox(vb => ({
      ...vb,
      w: positionedNodes.width,
      h: positionedNodes.height,
      x: Math.min(vb.x, Math.max(0, positionedNodes.width  - vb.w)),
      y: Math.min(vb.y, Math.max(0, positionedNodes.height - vb.h)),
    }))
  }, [positionedNodes.width, positionedNodes.height])

  const fitViewToCluster = useCallback((clusterId) => {
    const pn = positionedNodesRef.current
    if (!clusterId) { setViewBox({ x: 0, y: 0, w: pn.width, h: pn.height }); return }
    const pts = pn.coordinates.filter(n => n.cluster === clusterId)
    if (!pts.length) return
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y)
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
    const pad = 120
    const w = Math.min(pn.width,  Math.max(280, x1 - x0 + pad * 2))
    const h = Math.min(pn.height, Math.max(220, y1 - y0 + pad * 2))
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2
    setViewBox({
      x: Math.max(0, Math.min(cx - w / 2, pn.width  - w)),
      y: Math.max(0, Math.min(cy - h / 2, pn.height - h)),
      w, h,
    })
  }, [])

  const handleClusterClick = (clusterId, toggleOff) => {
    const next = toggleOff ? null : clusterId
    setActiveClusterId(next)
    requestAnimationFrame(() => {
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
      graphViewportRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
      if (viewMode === "text" && next)
        clusterAnchorRefs.current[next]?.scrollIntoView({ behavior: "smooth", block: "nearest" })
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
    setViewBox(vb => {
      const mx = ((e.clientX - rect.left) / rect.width)  * vb.w + vb.x
      const my = ((e.clientY - rect.top)  / rect.height) * vb.h + vb.y
      let nw = Math.min(pn.width,  Math.max(120, vb.w * scale))
      let nh = Math.min(pn.height, Math.max(100, vb.h * scale))
      let nx = Math.max(0, Math.min(mx - (mx - vb.x) * (nw / vb.w), pn.width  - nw))
      let ny = Math.max(0, Math.min(my - (my - vb.y) * (nh / vb.h), pn.height - nh))
      return { x: nx, y: ny, w: nw, h: nh }
    })
  }, [viewMode])

  useEffect(() => {
    const el = graphViewportRef.current
    if (!el) return
    el.addEventListener("wheel", onWheelGraph, { passive: false })
    return () => el.removeEventListener("wheel", onWheelGraph)
  }, [onWheelGraph])

  const onMouseDownPan = e => {
    if (e.button !== 0) return
    const vb = viewBoxRef.current
    dragPanRef.current = { startX: e.clientX, startY: e.clientY, vbX: vb.x, vbY: vb.y, vbW: vb.w, vbH: vb.h }
  }

  useEffect(() => {
    const onMove = e => {
      const drag = dragPanRef.current
      if (!drag) return
      const el = graphViewportRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const pn = positionedNodesRef.current
      let nx = Math.max(0, Math.min(drag.vbX - (e.clientX - drag.startX) * drag.vbW / rect.width,  pn.width  - drag.vbW))
      let ny = Math.max(0, Math.min(drag.vbY - (e.clientY - drag.startY) * drag.vbH / rect.height, pn.height - drag.vbH))
      setViewBox({ x: nx, y: ny, w: drag.vbW, h: drag.vbH })
    }
    const onUp = () => { dragPanRef.current = null }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp) }
  }, [])

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
            Clusters group files; edges show IMPORTS. Pan &amp; zoom inside the canvas; pick a cluster to fit view.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-1">View</span>
          <button type="button" onClick={() => setViewMode("graph")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${viewMode === "graph"
              ? "bg-cyan-500/25 border-cyan-400/60 text-cyan-100 shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"}`}>
            Graphical
          </button>
          <button type="button" onClick={() => setViewMode("text")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${viewMode === "text"
              ? "bg-cyan-500/25 border-cyan-400/60 text-cyan-100 shadow-[0_0_12px_rgba(34,211,238,0.25)]"
              : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"}`}>
            Text
          </button>
          <span className="w-px h-5 bg-slate-600 mx-1 hidden sm:block" aria-hidden />
          <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-1">Scope</span>
          <button type="button" onClick={() => setScopeMode("all")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${scopeMode === "all"
              ? "bg-violet-500/25 border-violet-400/60 text-violet-100"
              : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"}`}>
            All + highlight
          </button>
          <button type="button" onClick={() => setScopeMode("selected")}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${scopeMode === "selected"
              ? "bg-violet-500/25 border-violet-400/60 text-violet-100"
              : "bg-slate-950/50 border-slate-600 text-slate-400 hover:border-slate-500"}`}
            title="Shows only the chosen cluster when one is selected">
            Selected only
          </button>
          {viewMode === "graph" && (<>
            <span className="w-px h-5 bg-slate-600 mx-1 hidden md:block" aria-hidden />
            <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-1">Density</span>
            <button type="button" onClick={() => setGraphDensity("overview")}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${graphDensity === "overview"
                ? "bg-emerald-500/20 border-emerald-400/50 text-emerald-100"
                : "bg-slate-950/50 border-slate-600 text-slate-400"}`}>
              Overview
            </button>
            <button type="button" onClick={() => setGraphDensity("full")}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${graphDensity === "full"
                ? "bg-emerald-500/20 border-emerald-400/50 text-emerald-100"
                : "bg-slate-950/50 border-slate-600 text-slate-400"}`}>
              Full labels
            </button>
          </>)}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {clusters.map(cluster => {
          const active = activeClusterId === cluster.id
          return (
            <button key={cluster.id} type="button"
              onClick={() => handleClusterClick(cluster.id, active)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium border transition ${active
                ? "bg-indigo-500/90 text-white border-indigo-300 shadow-[0_0_14px_rgba(99,102,241,0.45)]"
                : "bg-slate-800/80 border-slate-600 text-slate-200 hover:border-slate-500 hover:bg-slate-800"}`}>
              {cluster.label} <span className="opacity-70">({cluster.size})</span>
            </button>
          )
        })}
      </div>

      {scopeMode === "selected" && !activeClusterId && (
        <p className="text-xs text-amber-300/90 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2">
          Select a cluster above to isolate it, or switch scope to &quot;All + highlight&quot;.
        </p>
      )}

      {viewMode === "graph" ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-500">
            <span>
              Drag to pan · scroll to zoom · click cluster to fit &amp; label its files
              {positionedNodes.lineEdges.length > 0 && (
                <span className="ml-2 text-slate-400">{positionedNodes.lineEdges.length} edges</span>
              )}
            </span>
            <button type="button" onClick={() => fitViewToCluster(activeClusterId)}
              className="rounded border border-slate-600 px-2 py-1 text-slate-300 hover:bg-slate-800">
              Refit selection
            </button>
            <button type="button" onClick={() => fitViewToCluster(null)}
              className="rounded border border-slate-600 px-2 py-1 text-slate-300 hover:bg-slate-800">
              Show all
            </button>
          </div>
          <div
            ref={graphViewportRef}
            className="relative rounded-xl border border-slate-600/60 bg-slate-950/70 shadow-inner cursor-grab active:cursor-grabbing select-none"
            onMouseDown={onMouseDownPan}
            onMouseLeave={() => setTooltip(null)}
          >
            {tooltip && (
              <div
                className="absolute z-20 pointer-events-none rounded-lg border border-slate-500/80 bg-slate-800/95 px-2.5 py-1.5 text-xs text-slate-100 shadow-xl max-w-xs break-all backdrop-blur-sm"
                style={{ left: tooltip.x, top: tooltip.y }}
              >{tooltip.label}</div>
            )}
            <svg
              width="100%"
              height={600}
              style={{ minWidth: "min(100%, 480px)", display: "block" }}
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
                  <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
                <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4"
                  orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L8,4 L0,8 z" fill="rgba(148,163,184,0.55)" />
                </marker>
              </defs>

              <rect x={0} y={0} width={positionedNodes.width} height={positionedNodes.height}
                fill="url(#kg-bg)" rx="12" />

              {positionedNodes.lineEdges.map((edge, idx) => {
                const dx = edge.target.x - edge.source.x
                const dy = edge.target.y - edge.source.y
                const len = Math.hypot(dx, dy) || 1
                const sh  = 14
                const x1 = edge.source.x + (dx / len) * sh, y1 = edge.source.y + (dy / len) * sh
                const x2 = edge.target.x - (dx / len) * sh, y2 = edge.target.y - (dy / len) * sh
                const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - 8
                const emph = !activeClusterId || filterToClusterOnly
                  || edge.source.cluster === activeClusterId || edge.target.cluster === activeClusterId
                const colorIdx = clusterColorIndex.get(edge.source.cluster) ?? 0
                return (
                  <path key={`e${idx}`}
                    d={`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`}
                    fill="none"
                    stroke={emph ? CLUSTER_PALETTE[colorIdx].stroke : "rgba(51,65,85,0.35)"}
                    strokeWidth={emph ? 1.6 : 0.8}
                    markerEnd="url(#arrow)"
                    opacity={emph ? 0.7 : 0.2}
                  />
                )
              })}

              {positionedNodes.coordinates.map(node => {
                const isCluster = node.type === "cluster"
                const emph = isNodeEmphasized(node.id, node.cluster)
                const colorIdx = clusterColorIndex.get(node.cluster) ?? 0
                const color = CLUSTER_PALETTE[colorIdx]
                const labelShort = node.label.length > 42 ? `${node.label.slice(0, 40)}…` : node.label
                const showTip = e => {
                  const rect = graphViewportRef.current?.getBoundingClientRect()
                  if (rect) setTooltip({ x: e.clientX - rect.left + 14, y: e.clientY - rect.top + 14, label: node.label })
                }

                if (isCluster) {
                  const countStr = node.fileCount != null ? ` (${node.fileCount})` : ""
                  return (
                    <g key={node.id} filter={emph ? "url(#kg-glow)" : undefined} opacity={emph ? 1 : 0.35}
                      onMouseEnter={showTip} onMouseLeave={() => setTooltip(null)} style={{ cursor: "default" }}>
                      <rect x={node.x - 82} y={node.y - 28} width={164} height={56} rx={14}
                        fill={emph ? color.node : "rgba(51,65,85,0.3)"}
                        stroke={emph ? color.nodeBorder : "rgba(71,85,105,0.5)"}
                        strokeWidth="1.5" />
                      <text x={node.x} y={node.y + 2} textAnchor="middle"
                        fill={emph ? color.text : "rgb(148,163,184)"}
                        fontSize="11" fontWeight="600">{labelShort}</text>
                      <text x={node.x} y={node.y + 17} textAnchor="middle"
                        fill={emph ? color.stroke : "rgba(100,116,139,0.8)"}
                        fontSize="9">{countStr}</text>
                    </g>
                  )
                }

                // Show labels when: full density, OR this node's cluster is active
                const showLabel = graphDensity === "full" || node.cluster === activeClusterId
                return (
                  <g key={node.id} opacity={emph ? 1 : 0.3}
                    onMouseEnter={showTip} onMouseLeave={() => setTooltip(null)} style={{ cursor: "default" }}>
                    <circle cx={node.x} cy={node.y} r={emph ? (showLabel ? 10 : 8) : 5}
                      fill={emph ? color.dot : "rgba(71,85,105,0.35)"}
                      stroke={emph ? color.dotBorder : "rgba(100,116,139,0.4)"}
                      strokeWidth="1.4" />
                    {showLabel && (
                      <text x={node.x} y={node.y + 22} textAnchor="middle"
                        fill="rgba(226,232,240,0.88)" fontSize="9">{labelShort}</text>
                    )}
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
            {clusters.map(cluster => {
              const list = nodesByCluster.get(cluster.id) || []
              if (!list.length) return null
              return (
                <div key={cluster.id} id={`kg-cluster-${cluster.id}`}
                  ref={el => { if (el) clusterAnchorRefs.current[cluster.id] = el }}
                  className={`rounded-lg border p-3 transition ${activeClusterId === cluster.id
                    ? "border-indigo-400/50 bg-indigo-500/10"
                    : "border-slate-700/80 bg-slate-900/40"}`}>
                  <p className="text-xs font-semibold text-cyan-200/90 mb-2">{cluster.label}</p>
                  <ul className="space-y-1.5 text-xs">
                    {list.map(node => {
                      const highlighted = !filterToClusterOnly && highlightedNodeIds.has(node.id) && activeClusterId
                      return (
                        <li key={node.id}
                          className={`rounded-lg px-2.5 py-1.5 border transition ${highlighted
                            ? "bg-indigo-500/20 text-indigo-100 border-indigo-400/50"
                            : "bg-slate-900/80 text-slate-300 border-slate-700/80"}`}>
                          <span className="font-semibold text-cyan-400/90">[{node.type}]</span>{" "}{node.label}
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
                <li key={`${edge.source}-${edge.target}-${idx}`}
                  className="rounded-lg px-2 py-1 bg-slate-900/60 border border-slate-800/80">
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
