import { useRef, useEffect, useCallback, useState } from 'react';
import Sigma from 'sigma';
import Graph from 'graphology';
import FA2Layout from 'graphology-layout-forceatlas2/worker';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import noverlap from 'graphology-layout-noverlap';
import EdgeCurveProgram from '@sigma/edge-curve';
import { SigmaNodeAttributes, SigmaEdgeAttributes } from '../lib/graph-adapter';
import type { EdgeType } from '../lib/constants';

const hexToRgb = (hex: string) => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) }
    : { r: 100, g: 100, b: 100 };
};

const rgbToHex = (r: number, g: number, b: number): string =>
  '#' + [r, g, b].map((x) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0')).join('');

const dimColor = (hex: string, amount: number): string => {
  const rgb = hexToRgb(hex);
  const bg = { r: 18, g: 18, b: 28 };
  return rgbToHex(bg.r + (rgb.r - bg.r) * amount, bg.g + (rgb.g - bg.g) * amount, bg.b + (rgb.b - bg.b) * amount);
};

const brightenColor = (hex: string, factor: number): string => {
  const rgb = hexToRgb(hex);
  return rgbToHex(
    rgb.r + ((255 - rgb.r) * (factor - 1)) / factor,
    rgb.g + ((255 - rgb.g) * (factor - 1)) / factor,
    rgb.b + ((255 - rgb.b) * (factor - 1)) / factor,
  );
};

interface UseSigmaOptions {
  onNodeClick?: (nodeId: string) => void;
  onNodeHover?: (nodeId: string | null) => void;
  onStageClick?: () => void;
  highlightedNodeIds?: Set<string>;
  affectedFileIds?: Set<string>;
  visibleEdgeTypes?: EdgeType[];
}

interface UseSigmaReturn {
  containerRef: React.RefObject<HTMLDivElement>;
  sigmaRef: React.RefObject<Sigma | null>;
  setGraph: (graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  resetZoom: () => void;
  focusNode: (nodeId: string) => void;
  isLayoutRunning: boolean;
  startLayout: () => void;
  stopLayout: () => void;
  selectedNode: string | null;
  setSelectedNode: (nodeId: string | null) => void;
}

const NOVERLAP_SETTINGS = { maxIterations: 20, ratio: 1.1, margin: 10, expansion: 1.05 };

const getFA2Settings = (nodeCount: number) => {
  const isSmall = nodeCount < 500;
  const isMedium = nodeCount >= 500 && nodeCount < 2000;
  const isLarge = nodeCount >= 2000 && nodeCount < 10000;
  return {
    gravity: isSmall ? 0.8 : isMedium ? 0.5 : isLarge ? 0.3 : 0.15,
    scalingRatio: isSmall ? 15 : isMedium ? 30 : isLarge ? 60 : 100,
    slowDown: isSmall ? 1 : isMedium ? 2 : isLarge ? 3 : 5,
    barnesHutOptimize: nodeCount > 200,
    barnesHutTheta: isLarge ? 0.8 : 0.6,
    strongGravityMode: false,
    outboundAttractionDistribution: true,
    linLogMode: false,
    adjustSizes: true,
    edgeWeightInfluence: 1,
  };
};

const getLayoutDuration = (nodeCount: number): number => {
  if (nodeCount > 10000) return 45000;
  if (nodeCount > 5000) return 35000;
  if (nodeCount > 2000) return 30000;
  if (nodeCount > 500) return 25000;
  return 20000;
};

export const useSigma = (options: UseSigmaOptions = {}): UseSigmaReturn => {
  const containerRef = useRef<HTMLDivElement>(null!);
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph<SigmaNodeAttributes, SigmaEdgeAttributes> | null>(null);
  const layoutRef = useRef<FA2Layout | null>(null);
  const selectedNodeRef = useRef<string | null>(null);
  const highlightedRef = useRef<Set<string>>(new Set());
  const affectedRef = useRef<Set<string>>(new Set());
  const visibleEdgeTypesRef = useRef<EdgeType[] | null>(null);
  const layoutTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const [selectedNode, setSelectedNodeState] = useState<string | null>(null);

  useEffect(() => {
    highlightedRef.current = options.highlightedNodeIds || new Set();
    affectedRef.current = options.affectedFileIds || new Set();
    visibleEdgeTypesRef.current = options.visibleEdgeTypes || null;
    sigmaRef.current?.refresh();
  }, [options.highlightedNodeIds, options.affectedFileIds, options.visibleEdgeTypes]);

  const setSelectedNode = useCallback((nodeId: string | null) => {
    selectedNodeRef.current = nodeId;
    setSelectedNodeState(nodeId);
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const camera = sigma.getCamera();
    camera.animate({ ratio: camera.ratio * 1.0001 }, { duration: 50 });
    sigma.refresh();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const graph = new Graph<SigmaNodeAttributes, SigmaEdgeAttributes>();
    graphRef.current = graph;

    const sigma = new Sigma(graph, containerRef.current, {
      renderLabels: true,
      labelFont: 'JetBrains Mono, monospace',
      labelSize: 11,
      labelWeight: '500',
      labelColor: { color: '#e4e4ed' },
      labelRenderedSizeThreshold: 8,
      labelDensity: 0.1,
      labelGridCellSize: 70,
      defaultNodeColor: '#6b7280',
      defaultEdgeColor: '#2a2a3a',
      defaultEdgeType: 'curved',
      edgeProgramClasses: { curved: EdgeCurveProgram },
      defaultDrawNodeHover: (context, data, settings) => {
        const label = data.label;
        if (!label) return;
        const size = settings.labelSize || 11;
        const font = settings.labelFont || 'JetBrains Mono, monospace';
        const weight = settings.labelWeight || '500';
        context.font = `${weight} ${size}px ${font}`;
        const textWidth = context.measureText(label).width;
        const nodeSize = data.size || 8;
        const x = data.x;
        const y = data.y - nodeSize - 10;
        const paddingX = 8, paddingY = 5;
        const height = size + paddingY * 2;
        const width = textWidth + paddingX * 2;
        context.fillStyle = '#12121c';
        context.beginPath();
        context.roundRect(x - width / 2, y - height / 2, width, height, 4);
        context.fill();
        context.strokeStyle = data.color || '#6366f1';
        context.lineWidth = 2;
        context.stroke();
        context.fillStyle = '#f5f5f7';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(label, x, y);
        context.beginPath();
        context.arc(data.x, data.y, nodeSize + 4, 0, Math.PI * 2);
        context.strokeStyle = data.color || '#6366f1';
        context.lineWidth = 2;
        context.globalAlpha = 0.5;
        context.stroke();
        context.globalAlpha = 1;
      },
      minCameraRatio: 0.002,
      maxCameraRatio: 50,
      hideEdgesOnMove: true,
      zIndex: true,

      nodeReducer: (node, data) => {
        const res = { ...data };
        if (data.hidden) { res.hidden = true; return res; }

        const currentSelected = selectedNodeRef.current;
        const highlighted = highlightedRef.current;
        const affected = affectedRef.current;
        const hasHighlights = highlighted.size > 0;
        const hasAffected = affected.size > 0;
        const isHighlighted = highlighted.has(node);
        const isAffected = affected.has(node);

        // Affected files from analysis (red/orange glow)
        if (hasAffected && !currentSelected) {
          if (isAffected) {
            res.color = '#ef4444';
            res.size = (data.size || 8) * 1.8;
            res.zIndex = 3;
            res.highlighted = true;
          } else if (isHighlighted) {
            res.color = '#f97316';
            res.size = (data.size || 8) * 1.4;
            res.zIndex = 2;
            res.highlighted = true;
          } else {
            res.color = dimColor(data.color, 0.15);
            res.size = (data.size || 8) * 0.4;
            res.zIndex = 0;
          }
          return res;
        }

        if (hasHighlights && !currentSelected) {
          if (isHighlighted) {
            res.color = '#06b6d4';
            res.size = (data.size || 8) * 1.6;
            res.zIndex = 2;
            res.highlighted = true;
          } else {
            res.color = dimColor(data.color, 0.2);
            res.size = (data.size || 8) * 0.5;
            res.zIndex = 0;
          }
          return res;
        }

        if (currentSelected) {
          const g = graphRef.current;
          if (g) {
            const isSelected = node === currentSelected;
            const isNeighbor = g.hasEdge(node, currentSelected) || g.hasEdge(currentSelected, node);
            if (isSelected) {
              res.size = (data.size || 8) * 1.8;
              res.zIndex = 2;
              res.highlighted = true;
            } else if (isNeighbor) {
              res.size = (data.size || 8) * 1.3;
              res.zIndex = 1;
            } else {
              res.color = dimColor(data.color, 0.25);
              res.size = (data.size || 8) * 0.6;
              res.zIndex = 0;
            }
          }
        }
        return res;
      },

      edgeReducer: (edge, data) => {
        const res = { ...data };
        const visibleTypes = visibleEdgeTypesRef.current;
        if (visibleTypes && data.relationType) {
          if (!visibleTypes.includes(data.relationType as EdgeType)) { res.hidden = true; return res; }
        }

        const currentSelected = selectedNodeRef.current;
        const highlighted = highlightedRef.current;
        const affected = affectedRef.current;
        const hasHighlights = highlighted.size > 0 || affected.size > 0;

        if (hasHighlights && !currentSelected) {
          const g = graphRef.current;
          if (g) {
            const [source, target] = g.extremities(edge);
            const isSourceActive = highlighted.has(source) || affected.has(source);
            const isTargetActive = highlighted.has(target) || affected.has(target);
            if (isSourceActive && isTargetActive) {
              res.color = affected.has(source) && affected.has(target) ? '#ef4444' : '#06b6d4';
              res.size = Math.max(2, (data.size || 1) * 3);
              res.zIndex = 2;
            } else if (isSourceActive || isTargetActive) {
              res.color = dimColor('#06b6d4', 0.4);
              res.size = 1;
              res.zIndex = 1;
            } else {
              res.color = dimColor(data.color, 0.08);
              res.size = 0.2;
              res.zIndex = 0;
            }
          }
          return res;
        }

        if (currentSelected) {
          const g = graphRef.current;
          if (g) {
            const [source, target] = g.extremities(edge);
            if (source === currentSelected || target === currentSelected) {
              res.color = brightenColor(data.color, 1.5);
              res.size = Math.max(3, (data.size || 1) * 4);
              res.zIndex = 2;
            } else {
              res.color = dimColor(data.color, 0.1);
              res.size = 0.3;
              res.zIndex = 0;
            }
          }
        }
        return res;
      },
    });

    sigmaRef.current = sigma;

    sigma.on('clickNode', ({ node }) => { setSelectedNode(node); options.onNodeClick?.(node); });
    sigma.on('clickStage', () => { setSelectedNode(null); options.onStageClick?.(); });
    sigma.on('enterNode', ({ node }) => { options.onNodeHover?.(node); if (containerRef.current) containerRef.current.style.cursor = 'pointer'; });
    sigma.on('leaveNode', () => { options.onNodeHover?.(null); if (containerRef.current) containerRef.current.style.cursor = 'grab'; });

    return () => {
      if (layoutTimeoutRef.current) clearTimeout(layoutTimeoutRef.current);
      layoutRef.current?.kill();
      sigma.kill();
      sigmaRef.current = null;
      graphRef.current = null;
    };
  }, []);

  const runLayout = useCallback((graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>) => {
    const nodeCount = graph.order;
    if (nodeCount === 0) return;
    if (layoutRef.current) { layoutRef.current.kill(); layoutRef.current = null; }
    if (layoutTimeoutRef.current) { clearTimeout(layoutTimeoutRef.current); layoutTimeoutRef.current = null; }

    const inferredSettings = forceAtlas2.inferSettings(graph);
    const customSettings = getFA2Settings(nodeCount);
    const layout = new FA2Layout(graph, { settings: { ...inferredSettings, ...customSettings } });
    layoutRef.current = layout;
    layout.start();
    setIsLayoutRunning(true);

    layoutTimeoutRef.current = setTimeout(() => {
      if (layoutRef.current) {
        layoutRef.current.stop();
        layoutRef.current = null;
        noverlap.assign(graph, NOVERLAP_SETTINGS);
        sigmaRef.current?.refresh();
        setIsLayoutRunning(false);
      }
    }, getLayoutDuration(nodeCount));
  }, []);

  const setGraph = useCallback((newGraph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>) => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    if (layoutRef.current) { layoutRef.current.kill(); layoutRef.current = null; }
    if (layoutTimeoutRef.current) { clearTimeout(layoutTimeoutRef.current); layoutTimeoutRef.current = null; }
    graphRef.current = newGraph;
    sigma.setGraph(newGraph);
    setSelectedNode(null);
    runLayout(newGraph);
    sigma.getCamera().animatedReset({ duration: 500 });
  }, [runLayout, setSelectedNode]);

  const focusNode = useCallback((nodeId: string) => {
    const sigma = sigmaRef.current;
    const graph = graphRef.current;
    if (!sigma || !graph || !graph.hasNode(nodeId)) return;
    const alreadySelected = selectedNodeRef.current === nodeId;
    selectedNodeRef.current = nodeId;
    setSelectedNodeState(nodeId);
    if (!alreadySelected) {
      const attrs = graph.getNodeAttributes(nodeId);
      sigma.getCamera().animate({ x: attrs.x, y: attrs.y, ratio: 0.15 }, { duration: 400 });
    }
    sigma.refresh();
  }, []);

  const zoomIn = useCallback(() => { sigmaRef.current?.getCamera().animatedZoom({ duration: 200 }); }, []);
  const zoomOut = useCallback(() => { sigmaRef.current?.getCamera().animatedUnzoom({ duration: 200 }); }, []);
  const resetZoom = useCallback(() => { sigmaRef.current?.getCamera().animatedReset({ duration: 300 }); setSelectedNode(null); }, [setSelectedNode]);
  const startLayout = useCallback(() => { const g = graphRef.current; if (g && g.order > 0) runLayout(g); }, [runLayout]);
  const stopLayout = useCallback(() => {
    if (layoutTimeoutRef.current) { clearTimeout(layoutTimeoutRef.current); layoutTimeoutRef.current = null; }
    if (layoutRef.current) {
      layoutRef.current.stop(); layoutRef.current = null;
      const g = graphRef.current;
      if (g) { noverlap.assign(g, NOVERLAP_SETTINGS); sigmaRef.current?.refresh(); }
      setIsLayoutRunning(false);
    }
  }, []);

  return {
    containerRef, sigmaRef, setGraph, zoomIn, zoomOut, resetZoom,
    focusNode, isLayoutRunning, startLayout, stopLayout, selectedNode, setSelectedNode,
  };
};
