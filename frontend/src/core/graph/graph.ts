import type { GraphNode, GraphRelationship } from 'qlankr-shared';
import type { KnowledgeGraph } from './types';

export const createKnowledgeGraph = (): KnowledgeGraph => {
  const nodeMap = new Map<string, GraphNode>();
  const relationshipMap = new Map<string, GraphRelationship>();

  const addNode = (node: GraphNode) => {
    if (!nodeMap.has(node.id)) {
      nodeMap.set(node.id, node);
    }
  };

  const addRelationship = (relationship: GraphRelationship) => {
    if (!relationshipMap.has(relationship.id)) {
      relationshipMap.set(relationship.id, relationship);
    }
  };

  return {
    get nodes() { return Array.from(nodeMap.values()); },
    get relationships() { return Array.from(relationshipMap.values()); },
    get nodeCount() { return nodeMap.size; },
    get relationshipCount() { return relationshipMap.size; },
    addNode,
    addRelationship,
  };
};
