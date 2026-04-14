import type { NodeLabel } from 'qlankr-shared';

export const NODE_COLORS: Record<NodeLabel, string> = {
  Project: '#a855f7',
  Package: '#8b5cf6',
  Module: '#7c3aed',
  Folder: '#6366f1',
  File: '#3b82f6',
  Class: '#f59e0b',
  Function: '#10b981',
  Method: '#14b8a6',
  Variable: '#64748b',
  Interface: '#ec4899',
  Enum: '#f97316',
  Decorator: '#eab308',
  Import: '#475569',
  Type: '#a78bfa',
  CodeElement: '#64748b',
  Community: '#818cf8',
  Process: '#f43f5e',
  Section: '#60a5fa',
  Struct: '#f59e0b',
  Trait: '#ec4899',
  Impl: '#14b8a6',
  TypeAlias: '#a78bfa',
  Const: '#64748b',
  Static: '#64748b',
  Namespace: '#7c3aed',
  Union: '#f97316',
  Typedef: '#a78bfa',
  Macro: '#eab308',
  Property: '#64748b',
  Record: '#f59e0b',
  Delegate: '#14b8a6',
  Annotation: '#eab308',
  Constructor: '#10b981',
  Template: '#a78bfa',
  Route: '#f43f5e',
  Tool: '#a855f7',
};

export const NODE_SIZES: Record<NodeLabel, number> = {
  Project: 20, Package: 16, Module: 13, Folder: 10, File: 6,
  Class: 8, Function: 4, Method: 3, Variable: 2, Interface: 7,
  Enum: 5, Decorator: 2, Import: 1.5, Type: 3, CodeElement: 2,
  Community: 0, Process: 0, Section: 8, Struct: 8, Trait: 7,
  Impl: 3, TypeAlias: 3, Const: 2, Static: 2, Namespace: 13,
  Union: 5, Typedef: 3, Macro: 2, Property: 2, Record: 8,
  Delegate: 3, Annotation: 2, Constructor: 4, Template: 3,
  Route: 5, Tool: 5,
};

export const COMMUNITY_COLORS = [
  '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6',
  '#8b5cf6', '#d946ef', '#ec4899', '#f43f5e', '#14b8a6', '#84cc16',
];

export const getCommunityColor = (communityIndex: number): string => {
  return COMMUNITY_COLORS[communityIndex % COMMUNITY_COLORS.length];
};

export const DEFAULT_VISIBLE_LABELS: NodeLabel[] = [
  'Project', 'Package', 'Module', 'Folder', 'File', 'Class',
  'Function', 'Method', 'Interface', 'Enum', 'Type',
];

export const FILTERABLE_LABELS: NodeLabel[] = [
  'Folder', 'File', 'Class', 'Interface', 'Enum', 'Type',
  'Function', 'Method', 'Variable', 'Decorator', 'Import',
];

export type EdgeType = 'CONTAINS' | 'DEFINES' | 'IMPORTS' | 'CALLS' | 'EXTENDS' | 'IMPLEMENTS';

export const ALL_EDGE_TYPES: EdgeType[] = [
  'CONTAINS', 'DEFINES', 'IMPORTS', 'CALLS', 'EXTENDS', 'IMPLEMENTS',
];

export const DEFAULT_VISIBLE_EDGES: EdgeType[] = [
  'CONTAINS', 'DEFINES', 'IMPORTS', 'EXTENDS', 'IMPLEMENTS', 'CALLS',
];

export const EDGE_INFO: Record<EdgeType, { color: string; label: string }> = {
  CONTAINS: { color: '#2d5a3d', label: 'Contains' },
  DEFINES: { color: '#0e7490', label: 'Defines' },
  IMPORTS: { color: '#1d4ed8', label: 'Imports' },
  CALLS: { color: '#7c3aed', label: 'Calls' },
  EXTENDS: { color: '#c2410c', label: 'Extends' },
  IMPLEMENTS: { color: '#be185d', label: 'Implements' },
};
