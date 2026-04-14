import type { GraphNode, GraphRelationship } from 'qlankr-shared';

export interface KnowledgeGraph {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  nodeCount: number;
  relationshipCount: number;
  addNode: (node: GraphNode) => void;
  addRelationship: (relationship: GraphRelationship) => void;
}
