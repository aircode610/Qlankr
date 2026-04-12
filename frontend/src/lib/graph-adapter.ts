import Graph from 'graphology';
import type { NodeLabel } from 'qlankr-shared';
import type { KnowledgeGraph } from '../core/graph/types';
import { NODE_COLORS, NODE_SIZES, getCommunityColor } from './constants';

export interface SigmaNodeAttributes {
  x: number;
  y: number;
  size: number;
  color: string;
  label: string;
  nodeType: NodeLabel;
  filePath: string;
  startLine?: number;
  endLine?: number;
  hidden?: boolean;
  zIndex?: number;
  highlighted?: boolean;
  mass?: number;
  community?: number;
  communityColor?: string;
}

export interface SigmaEdgeAttributes {
  size: number;
  color: string;
  relationType: string;
  type?: string;
  curvature?: number;
  zIndex?: number;
}

const getScaledNodeSize = (baseSize: number, nodeCount: number): number => {
  if (nodeCount > 50000) return Math.max(1, baseSize * 0.4);
  if (nodeCount > 20000) return Math.max(1.5, baseSize * 0.5);
  if (nodeCount > 5000) return Math.max(2, baseSize * 0.65);
  if (nodeCount > 1000) return Math.max(2.5, baseSize * 0.8);
  return baseSize;
};

const getNodeMass = (nodeType: NodeLabel, nodeCount: number): number => {
  const baseMassMultiplier = nodeCount > 5000 ? 2 : nodeCount > 1000 ? 1.5 : 1;
  switch (nodeType) {
    case 'Project': return 50 * baseMassMultiplier;
    case 'Package': return 30 * baseMassMultiplier;
    case 'Module': return 20 * baseMassMultiplier;
    case 'Folder': return 15 * baseMassMultiplier;
    case 'File': return 3 * baseMassMultiplier;
    case 'Class': case 'Interface': return 5 * baseMassMultiplier;
    case 'Function': case 'Method': return 2 * baseMassMultiplier;
    default: return 1;
  }
};

export const knowledgeGraphToGraphology = (
  knowledgeGraph: KnowledgeGraph,
  communityMemberships?: Map<string, number>,
): Graph<SigmaNodeAttributes, SigmaEdgeAttributes> => {
  const graph = new Graph<SigmaNodeAttributes, SigmaEdgeAttributes>();
  const nodeCount = knowledgeGraph.nodes.length;

  const parentToChildren = new Map<string, string[]>();
  const childToParent = new Map<string, string>();
  const hierarchyRelations = new Set(['CONTAINS', 'DEFINES', 'IMPORTS']);

  knowledgeGraph.relationships.forEach((rel) => {
    if (hierarchyRelations.has(rel.type)) {
      if (!parentToChildren.has(rel.sourceId)) parentToChildren.set(rel.sourceId, []);
      parentToChildren.get(rel.sourceId)!.push(rel.targetId);
      childToParent.set(rel.targetId, rel.sourceId);
    }
  });

  const nodeMap = new Map(knowledgeGraph.nodes.map((n) => [n.id, n]));
  const structuralTypes = new Set(['Project', 'Package', 'Module', 'Folder']);
  const structuralNodes = knowledgeGraph.nodes.filter((n) => structuralTypes.has(n.label));

  const structuralSpread = Math.sqrt(nodeCount) * 40;
  const childJitter = Math.sqrt(nodeCount) * 3;

  const clusterCenters = new Map<number, { x: number; y: number }>();
  if (communityMemberships && communityMemberships.size > 0) {
    const communities = new Set(communityMemberships.values());
    const communityCount = communities.size;
    const clusterSpread = structuralSpread * 0.8;
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    let idx = 0;
    communities.forEach((communityId) => {
      const angle = idx * goldenAngle;
      const radius = clusterSpread * Math.sqrt((idx + 1) / communityCount);
      clusterCenters.set(communityId, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
      idx++;
    });
  }
  const clusterJitter = Math.sqrt(nodeCount) * 1.5;
  const nodePositions = new Map<string, { x: number; y: number }>();

  structuralNodes.forEach((node, index) => {
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    const angle = index * goldenAngle;
    const radius = structuralSpread * Math.sqrt((index + 1) / Math.max(structuralNodes.length, 1));
    const jitter = structuralSpread * 0.15;
    const x = radius * Math.cos(angle) + (Math.random() - 0.5) * jitter;
    const y = radius * Math.sin(angle) + (Math.random() - 0.5) * jitter;
    nodePositions.set(node.id, { x, y });

    graph.addNode(node.id, {
      x, y,
      size: getScaledNodeSize(NODE_SIZES[node.label] || 8, nodeCount),
      color: NODE_COLORS[node.label] || '#9ca3af',
      label: node.properties.name,
      nodeType: node.label,
      filePath: node.properties.filePath,
      startLine: node.properties.startLine,
      endLine: node.properties.endLine,
      hidden: false,
      mass: getNodeMass(node.label, nodeCount),
    });
  });

  const addNodeWithPosition = (nodeId: string) => {
    if (graph.hasNode(nodeId)) return;
    const node = nodeMap.get(nodeId);
    if (!node) return;

    let x: number, y: number;
    const communityIndex = communityMemberships?.get(nodeId);
    const symbolTypes = new Set(['Function', 'Class', 'Method', 'Interface']);
    const clusterCenter = communityIndex !== undefined ? clusterCenters.get(communityIndex) : null;

    if (clusterCenter && symbolTypes.has(node.label)) {
      x = clusterCenter.x + (Math.random() - 0.5) * clusterJitter;
      y = clusterCenter.y + (Math.random() - 0.5) * clusterJitter;
    } else {
      const parentId = childToParent.get(nodeId);
      const parentPos = parentId ? nodePositions.get(parentId) : null;
      if (parentPos) {
        x = parentPos.x + (Math.random() - 0.5) * childJitter;
        y = parentPos.y + (Math.random() - 0.5) * childJitter;
      } else {
        x = (Math.random() - 0.5) * structuralSpread * 0.5;
        y = (Math.random() - 0.5) * structuralSpread * 0.5;
      }
    }

    nodePositions.set(nodeId, { x, y });
    const hasCommunity = communityIndex !== undefined;
    const usesCommunityColor = hasCommunity && symbolTypes.has(node.label);
    const nodeColor = usesCommunityColor ? getCommunityColor(communityIndex!) : NODE_COLORS[node.label] || '#9ca3af';

    graph.addNode(nodeId, {
      x, y,
      size: getScaledNodeSize(NODE_SIZES[node.label] || 8, nodeCount),
      color: nodeColor,
      label: node.properties.name,
      nodeType: node.label,
      filePath: node.properties.filePath,
      startLine: node.properties.startLine,
      endLine: node.properties.endLine,
      hidden: false,
      mass: getNodeMass(node.label, nodeCount),
      community: communityIndex,
      communityColor: hasCommunity ? getCommunityColor(communityIndex!) : undefined,
    });
  };

  const queue: string[] = [...structuralNodes.map((n) => n.id)];
  const visited = new Set<string>(queue);
  while (queue.length > 0) {
    const currentId = queue.shift()!;
    const children = parentToChildren.get(currentId) || [];
    for (const childId of children) {
      if (!visited.has(childId)) {
        visited.add(childId);
        addNodeWithPosition(childId);
        queue.push(childId);
      }
    }
  }

  knowledgeGraph.nodes.forEach((node) => {
    if (!graph.hasNode(node.id)) addNodeWithPosition(node.id);
  });

  const edgeBaseSize = nodeCount > 20000 ? 0.4 : nodeCount > 5000 ? 0.6 : 1.0;
  const EDGE_STYLES: Record<string, { color: string; sizeMultiplier: number }> = {
    CONTAINS: { color: '#2d5a3d', sizeMultiplier: 0.4 },
    DEFINES: { color: '#0e7490', sizeMultiplier: 0.5 },
    IMPORTS: { color: '#1d4ed8', sizeMultiplier: 0.6 },
    CALLS: { color: '#7c3aed', sizeMultiplier: 0.8 },
    EXTENDS: { color: '#c2410c', sizeMultiplier: 1.0 },
    IMPLEMENTS: { color: '#be185d', sizeMultiplier: 0.9 },
  };

  knowledgeGraph.relationships.forEach((rel) => {
    if (graph.hasNode(rel.sourceId) && graph.hasNode(rel.targetId)) {
      if (!graph.hasEdge(rel.sourceId, rel.targetId)) {
        const style = EDGE_STYLES[rel.type] || { color: '#4a4a5a', sizeMultiplier: 0.5 };
        graph.addEdge(rel.sourceId, rel.targetId, {
          size: edgeBaseSize * style.sizeMultiplier,
          color: style.color,
          relationType: rel.type,
          type: 'curved',
          curvature: 0.12 + Math.random() * 0.08,
        });
      }
    }
  });

  return graph;
};

export const filterGraphByLabels = (
  graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>,
  visibleLabels: NodeLabel[],
): void => {
  graph.forEachNode((nodeId, attributes) => {
    graph.setNodeAttribute(nodeId, 'hidden', !visibleLabels.includes(attributes.nodeType));
  });
};

export const getNodesWithinHops = (
  graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>,
  startNodeId: string,
  maxHops: number,
): Set<string> => {
  const visited = new Set<string>();
  const queue: { nodeId: string; depth: number }[] = [{ nodeId: startNodeId, depth: 0 }];
  while (queue.length > 0) {
    const { nodeId, depth } = queue.shift()!;
    if (visited.has(nodeId)) continue;
    visited.add(nodeId);
    if (depth < maxHops) {
      graph.forEachNeighbor(nodeId, (neighborId) => {
        if (!visited.has(neighborId)) queue.push({ nodeId: neighborId, depth: depth + 1 });
      });
    }
  }
  return visited;
};

export const filterGraphByDepth = (
  graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>,
  selectedNodeId: string | null,
  maxHops: number | null,
  visibleLabels: NodeLabel[],
): void => {
  if (maxHops === null || selectedNodeId === null || !graph.hasNode(selectedNodeId)) {
    filterGraphByLabels(graph, visibleLabels);
    return;
  }
  const nodesInRange = getNodesWithinHops(graph, selectedNodeId, maxHops);
  graph.forEachNode((nodeId, attributes) => {
    const isLabelVisible = visibleLabels.includes(attributes.nodeType);
    graph.setNodeAttribute(nodeId, 'hidden', !isLabelVisible || !nodesInRange.has(nodeId));
  });
};
