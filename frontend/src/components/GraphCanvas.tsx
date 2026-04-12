import { useEffect, useCallback, useMemo, useState, forwardRef, useImperativeHandle } from 'react';
import { ZoomIn, ZoomOut, Maximize2, Focus, RotateCcw, Play, Pause } from '@/lib/lucide-icons';
import { useSigma } from '../hooks/useSigma';
import { useAppState } from '../hooks/useAppState';
import { knowledgeGraphToGraphology, filterGraphByDepth, SigmaNodeAttributes, SigmaEdgeAttributes } from '../lib/graph-adapter';
import type { GraphNode } from 'qlankr-shared';
import Graph from 'graphology';

export interface GraphCanvasHandle {
  focusNode: (nodeId: string) => void;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle>((_, ref) => {
  const {
    graph, setSelectedNode, selectedNode: appSelectedNode,
    visibleLabels, visibleEdgeTypes, depthFilter,
    highlightedNodeIds, affectedFileIds,
  } = useAppState();
  const [hoveredNodeName, setHoveredNodeName] = useState<string | null>(null);

  const nodeById = useMemo(() => {
    if (!graph) return new Map<string, GraphNode>();
    return new Map(graph.nodes.map((n) => [n.id, n]));
  }, [graph]);

  const handleNodeClick = useCallback((nodeId: string) => {
    if (!graph) return;
    const node = nodeById.get(nodeId);
    if (node) setSelectedNode(node);
  }, [graph, nodeById, setSelectedNode]);

  const handleNodeHover = useCallback((nodeId: string | null) => {
    if (!nodeId || !graph) { setHoveredNodeName(null); return; }
    const node = nodeById.get(nodeId);
    setHoveredNodeName(node ? node.properties.name : null);
  }, [graph, nodeById]);

  const handleStageClick = useCallback(() => { setSelectedNode(null); }, [setSelectedNode]);

  const {
    containerRef, sigmaRef, setGraph: setSigmaGraph,
    zoomIn, zoomOut, resetZoom, focusNode,
    isLayoutRunning, startLayout, stopLayout,
    selectedNode: sigmaSelectedNode, setSelectedNode: setSigmaSelectedNode,
  } = useSigma({
    onNodeClick: handleNodeClick,
    onNodeHover: handleNodeHover,
    onStageClick: handleStageClick,
    highlightedNodeIds,
    affectedFileIds,
    visibleEdgeTypes,
  });

  useImperativeHandle(ref, () => ({
    focusNode: (nodeId: string) => {
      if (graph) {
        const node = nodeById.get(nodeId);
        if (node) setSelectedNode(node);
      }
      focusNode(nodeId);
    },
  }), [focusNode, graph, nodeById, setSelectedNode]);

  // Update Sigma graph when KnowledgeGraph changes
  useEffect(() => {
    if (!graph) return;
    const communityMemberships = new Map<string, number>();
    graph.relationships.forEach((rel) => {
      if (rel.type === 'MEMBER_OF') {
        const communityNode = nodeById.get(rel.targetId);
        if (communityNode && communityNode.label === 'Community') {
          const numericPart = rel.targetId.replace('comm_', '');
          const communityIdx = /^\d+$/.test(numericPart) ? parseInt(numericPart, 10) : 0;
          communityMemberships.set(rel.sourceId, communityIdx);
        }
      }
    });
    setSigmaGraph(knowledgeGraphToGraphology(graph, communityMemberships));
  }, [graph, nodeById, setSigmaGraph]);

  // Update node visibility when filters change
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const sigmaGraph = sigma.getGraph() as Graph<SigmaNodeAttributes, SigmaEdgeAttributes>;
    if (sigmaGraph.order === 0) return;
    filterGraphByDepth(sigmaGraph, appSelectedNode?.id || null, depthFilter, visibleLabels);
    sigma.refresh();
  }, [visibleLabels, depthFilter, appSelectedNode]);

  // Sync app selected node with sigma
  useEffect(() => {
    setSigmaSelectedNode(appSelectedNode ? appSelectedNode.id : null);
  }, [appSelectedNode, setSigmaSelectedNode]);

  const handleFocusSelected = useCallback(() => {
    if (appSelectedNode) focusNode(appSelectedNode.id);
  }, [appSelectedNode, focusNode]);

  const handleClearSelection = useCallback(() => {
    setSelectedNode(null);
    setSigmaSelectedNode(null);
    resetZoom();
  }, [setSelectedNode, setSigmaSelectedNode, resetZoom]);

  return (
    <div className="relative h-full w-full bg-void">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0" style={{
          background: `radial-gradient(circle at 50% 50%, rgba(124, 58, 237, 0.03) 0%, transparent 70%),
            linear-gradient(to bottom, #06060a, #0a0a10)`,
        }} />
      </div>

      <div ref={containerRef} className="sigma-container h-full w-full cursor-grab active:cursor-grabbing" />

      {hoveredNodeName && !sigmaSelectedNode && (
        <div className="pointer-events-none absolute top-4 left-1/2 z-20 -translate-x-1/2 animate-fade-in rounded-lg border border-border-subtle bg-elevated/95 px-3 py-1.5 backdrop-blur-sm">
          <span className="font-mono text-sm text-text-primary">{hoveredNodeName}</span>
        </div>
      )}

      {sigmaSelectedNode && appSelectedNode && (
        <div className="absolute top-4 left-1/2 z-20 flex -translate-x-1/2 animate-slide-up items-center gap-2 rounded-xl border border-accent/30 bg-accent/20 px-4 py-2 backdrop-blur-sm">
          <div className="h-2 w-2 animate-pulse rounded-full bg-accent" />
          <span className="font-mono text-sm text-text-primary">{appSelectedNode.properties.name}</span>
          <span className="text-xs text-text-muted">({appSelectedNode.label})</span>
          <button onClick={handleClearSelection} className="ml-2 rounded px-2 py-0.5 text-xs text-text-secondary transition-colors hover:bg-white/10 hover:text-text-primary">Clear</button>
        </div>
      )}

      {/* Graph Controls */}
      <div className="absolute right-4 bottom-4 z-10 flex flex-col gap-1">
        <button onClick={zoomIn} className="flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle bg-elevated text-text-secondary transition-colors hover:bg-hover hover:text-text-primary" title="Zoom In"><ZoomIn className="h-4 w-4" /></button>
        <button onClick={zoomOut} className="flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle bg-elevated text-text-secondary transition-colors hover:bg-hover hover:text-text-primary" title="Zoom Out"><ZoomOut className="h-4 w-4" /></button>
        <button onClick={resetZoom} className="flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle bg-elevated text-text-secondary transition-colors hover:bg-hover hover:text-text-primary" title="Fit to Screen"><Maximize2 className="h-4 w-4" /></button>
        <div className="my-1 h-px bg-border-subtle" />
        {appSelectedNode && (
          <button onClick={handleFocusSelected} className="flex h-9 w-9 items-center justify-center rounded-md border border-accent/30 bg-accent/20 text-accent transition-colors hover:bg-accent/30" title="Focus on Selected"><Focus className="h-4 w-4" /></button>
        )}
        {sigmaSelectedNode && (
          <button onClick={handleClearSelection} className="flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle bg-elevated text-text-secondary transition-colors hover:bg-hover hover:text-text-primary" title="Clear Selection"><RotateCcw className="h-4 w-4" /></button>
        )}
        <div className="my-1 h-px bg-border-subtle" />
        <button onClick={isLayoutRunning ? stopLayout : startLayout} className={`flex h-9 w-9 items-center justify-center rounded-md border transition-all ${isLayoutRunning ? 'animate-pulse border-accent bg-accent text-white shadow-glow' : 'border-border-subtle bg-elevated text-text-secondary hover:bg-hover hover:text-text-primary'}`} title={isLayoutRunning ? 'Stop Layout' : 'Run Layout'}>
          {isLayoutRunning ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
      </div>

      {isLayoutRunning && (
        <div className="absolute bottom-4 left-1/2 z-10 flex -translate-x-1/2 animate-fade-in items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/20 px-3 py-1.5 backdrop-blur-sm">
          <div className="h-2 w-2 animate-ping rounded-full bg-emerald-400" />
          <span className="text-xs font-medium text-emerald-400">Layout optimizing...</span>
        </div>
      )}
    </div>
  );
});

GraphCanvas.displayName = 'GraphCanvas';
