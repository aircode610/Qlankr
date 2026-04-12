import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  ChevronRight, ChevronDown, Folder, FolderOpen, FileCode, Search, Filter,
  PanelLeftClose, PanelLeft, Box, Braces, Variable, Hash, Target, List, AtSign, Type,
} from '@/lib/lucide-icons';
import { useAppState } from '../hooks/useAppState';
import { FILTERABLE_LABELS, NODE_COLORS, ALL_EDGE_TYPES, EDGE_INFO } from '../lib/constants';
import type { GraphNode, NodeLabel } from 'qlankr-shared';

interface TreeNode {
  id: string;
  name: string;
  type: 'folder' | 'file';
  path: string;
  children: TreeNode[];
  graphNode?: GraphNode;
}

const buildFileTree = (nodes: GraphNode[]): TreeNode[] => {
  const root: TreeNode[] = [];
  const pathMap = new Map<string, TreeNode>();
  const fileNodes = nodes.filter((n) => n.label === 'Folder' || n.label === 'File');
  fileNodes.sort((a, b) => a.properties.filePath.localeCompare(b.properties.filePath));

  fileNodes.forEach((node) => {
    const parts = node.properties.filePath.split('/').filter(Boolean);
    let currentPath = '';
    let currentLevel = root;
    parts.forEach((part, index) => {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      let existing = pathMap.get(currentPath);
      if (!existing) {
        const isLastPart = index === parts.length - 1;
        existing = {
          id: isLastPart ? node.id : currentPath,
          name: part,
          type: isLastPart && node.label === 'File' ? 'file' : 'folder',
          path: currentPath,
          children: [],
          graphNode: isLastPart ? node : undefined,
        };
        pathMap.set(currentPath, existing);
        currentLevel.push(existing);
      }
      currentLevel = existing.children;
    });
  });
  return root;
};

interface TreeItemProps {
  node: TreeNode;
  depth: number;
  searchQuery: string;
  onNodeClick: (node: TreeNode) => void;
  expandedPaths: Set<string>;
  toggleExpanded: (path: string) => void;
  selectedPath: string | null;
}

const TreeItem = ({ node, depth, searchQuery, onNodeClick, expandedPaths, toggleExpanded, selectedPath }: TreeItemProps) => {
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedPath === node.path;
  const hasChildren = node.children.length > 0;

  const filteredChildren = useMemo(() => {
    if (!searchQuery) return node.children;
    const q = searchQuery.toLowerCase();
    const matches = (n: TreeNode, query: string): boolean =>
      n.name.toLowerCase().includes(query) || (n.children?.some((c) => matches(c, query)) ?? false);
    return node.children.filter((c) => matches(c, q));
  }, [node.children, searchQuery]);

  const matchesSearch = searchQuery && node.name.toLowerCase().includes(searchQuery.toLowerCase());

  return (
    <div>
      <button
        onClick={() => { if (hasChildren) toggleExpanded(node.path); onNodeClick(node); }}
        className={`relative flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-sm transition-colors hover:bg-hover ${isSelected ? 'border-l-2 border-amber-400 bg-amber-500/15 text-amber-300' : 'border-l-2 border-transparent text-text-secondary hover:text-text-primary'} ${matchesSearch ? 'bg-accent/10' : ''}`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {hasChildren ? (isExpanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-text-muted" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-text-muted" />) : <span className="w-3.5" />}
        {node.type === 'folder' ? (isExpanded ? <FolderOpen className="h-4 w-4 shrink-0" style={{ color: NODE_COLORS.Folder }} /> : <Folder className="h-4 w-4 shrink-0" style={{ color: NODE_COLORS.Folder }} />) : <FileCode className="h-4 w-4 shrink-0" style={{ color: NODE_COLORS.File }} />}
        <span className="truncate font-mono text-xs">{node.name}</span>
      </button>
      {isExpanded && filteredChildren.length > 0 && (
        <div>
          {filteredChildren.map((child) => (
            <TreeItem key={child.id} node={child} depth={depth + 1} searchQuery={searchQuery} onNodeClick={onNodeClick} expandedPaths={expandedPaths} toggleExpanded={toggleExpanded} selectedPath={selectedPath} />
          ))}
        </div>
      )}
    </div>
  );
};

const getNodeTypeIcon = (label: NodeLabel) => {
  switch (label) {
    case 'Folder': return Folder;
    case 'File': return FileCode;
    case 'Class': return Box;
    case 'Function': case 'Method': return Braces;
    case 'Interface': return Hash;
    case 'Enum': return List;
    case 'Type': return Type;
    case 'Decorator': return AtSign;
    case 'Import': return FileCode;
    case 'Variable': return Variable;
    default: return Variable;
  }
};

interface FileTreePanelProps {
  onFocusNode: (nodeId: string) => void;
}

export const FileTreePanel = ({ onFocusNode }: FileTreePanelProps) => {
  const { graph, visibleLabels, toggleLabelVisibility, visibleEdgeTypes, toggleEdgeVisibility, selectedNode, setSelectedNode, depthFilter, setDepthFilter } = useAppState();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'files' | 'filters'>('files');

  const fileTree = useMemo(() => graph ? buildFileTree(graph.nodes) : [], [graph]);

  useEffect(() => {
    if (fileTree.length > 0 && expandedPaths.size === 0)
      setExpandedPaths(new Set(fileTree.map((n) => n.path)));
  }, [fileTree.length]);

  useEffect(() => {
    const path = selectedNode?.properties?.filePath;
    if (!path) return;
    const parts = path.split('/').filter(Boolean);
    const pathsToExpand: string[] = [];
    let currentPath = '';
    for (let i = 0; i < parts.length - 1; i++) {
      currentPath = currentPath ? `${currentPath}/${parts[i]}` : parts[i];
      pathsToExpand.push(currentPath);
    }
    if (pathsToExpand.length > 0)
      setExpandedPaths((prev) => { const next = new Set(prev); pathsToExpand.forEach((p) => next.add(p)); return next; });
  }, [selectedNode?.id]);

  const toggleExpanded = useCallback((path: string) => {
    setExpandedPaths((prev) => { const next = new Set(prev); next.has(path) ? next.delete(path) : next.add(path); return next; });
  }, []);

  const handleNodeClick = useCallback((treeNode: TreeNode) => {
    if (treeNode.graphNode) {
      const isSame = selectedNode?.id === treeNode.graphNode.id;
      setSelectedNode(treeNode.graphNode);
      if (!isSame) onFocusNode(treeNode.graphNode.id);
    }
  }, [setSelectedNode, onFocusNode, selectedNode]);

  const selectedPath = selectedNode?.properties.filePath || null;

  if (isCollapsed) {
    return (
      <div className="flex h-full w-12 flex-col items-center gap-2 border-r border-border-subtle bg-surface py-3">
        <button onClick={() => setIsCollapsed(false)} className="rounded p-2 text-text-secondary transition-colors hover:bg-hover hover:text-text-primary" title="Expand"><PanelLeft className="h-5 w-5" /></button>
        <div className="my-1 h-px w-6 bg-border-subtle" />
        <button onClick={() => { setIsCollapsed(false); setActiveTab('files'); }} className={`rounded p-2 transition-colors ${activeTab === 'files' ? 'bg-accent/10 text-accent' : 'text-text-secondary hover:bg-hover hover:text-text-primary'}`} title="Explorer"><Folder className="h-5 w-5" /></button>
        <button onClick={() => { setIsCollapsed(false); setActiveTab('filters'); }} className={`rounded p-2 transition-colors ${activeTab === 'filters' ? 'bg-accent/10 text-accent' : 'text-text-secondary hover:bg-hover hover:text-text-primary'}`} title="Filters"><Filter className="h-5 w-5" /></button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-64 animate-slide-in flex-col border-r border-border-subtle bg-surface">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2">
        <div className="flex items-center gap-1">
          <button onClick={() => setActiveTab('files')} className={`rounded px-2 py-1 text-xs transition-colors ${activeTab === 'files' ? 'bg-accent/20 text-accent' : 'text-text-secondary hover:bg-hover hover:text-text-primary'}`}>Explorer</button>
          <button onClick={() => setActiveTab('filters')} className={`rounded px-2 py-1 text-xs transition-colors ${activeTab === 'filters' ? 'bg-accent/20 text-accent' : 'text-text-secondary hover:bg-hover hover:text-text-primary'}`}>Filters</button>
        </div>
        <button onClick={() => setIsCollapsed(true)} className="rounded p-1 text-text-muted transition-colors hover:bg-hover hover:text-text-primary" title="Collapse"><PanelLeftClose className="h-4 w-4" /></button>
      </div>

      {activeTab === 'files' && (
        <>
          <div className="border-b border-border-subtle px-3 py-2">
            <div className="relative">
              <Search className="absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
              <input type="text" placeholder="Search files..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full rounded border border-border-subtle bg-elevated py-1.5 pr-3 pl-8 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none" />
            </div>
          </div>
          <div className="scrollbar-thin flex-1 overflow-y-auto py-2">
            {fileTree.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-text-muted">No files loaded</div>
            ) : fileTree.map((node) => (
              <TreeItem key={node.id} node={node} depth={0} searchQuery={searchQuery} onNodeClick={handleNodeClick} expandedPaths={expandedPaths} toggleExpanded={toggleExpanded} selectedPath={selectedPath} />
            ))}
          </div>
        </>
      )}

      {activeTab === 'filters' && (
        <div className="scrollbar-thin flex-1 overflow-y-auto p-3">
          <div className="mb-3">
            <h3 className="mb-2 text-xs font-medium tracking-wide text-text-secondary uppercase">Node Types</h3>
          </div>
          <div className="flex flex-col gap-1">
            {FILTERABLE_LABELS.map((label) => {
              const Icon = getNodeTypeIcon(label);
              const isVisible = visibleLabels.includes(label);
              return (
                <button key={label} onClick={() => toggleLabelVisibility(label)} className={`flex items-center gap-2.5 rounded px-2 py-1.5 text-left transition-colors ${isVisible ? 'bg-elevated text-text-primary' : 'text-text-muted hover:bg-hover hover:text-text-secondary'}`}>
                  <div className={`flex h-5 w-5 items-center justify-center rounded ${isVisible ? '' : 'opacity-40'}`} style={{ backgroundColor: `${NODE_COLORS[label]}20` }}>
                    <Icon className="h-3 w-3" style={{ color: NODE_COLORS[label] }} />
                  </div>
                  <span className="flex-1 text-xs">{label}</span>
                  <div className={`h-2 w-2 rounded-full transition-colors ${isVisible ? 'bg-accent' : 'bg-border-subtle'}`} />
                </button>
              );
            })}
          </div>

          <div className="mt-6 border-t border-border-subtle pt-4">
            <h3 className="mb-2 text-xs font-medium tracking-wide text-text-secondary uppercase">Edge Types</h3>
            <div className="flex flex-col gap-1">
              {ALL_EDGE_TYPES.map((edgeType) => {
                const info = EDGE_INFO[edgeType];
                const isVisible = visibleEdgeTypes.includes(edgeType);
                return (
                  <button key={edgeType} onClick={() => toggleEdgeVisibility(edgeType)} className={`flex items-center gap-2.5 rounded px-2 py-1.5 text-left transition-colors ${isVisible ? 'bg-elevated text-text-primary' : 'text-text-muted hover:bg-hover hover:text-text-secondary'}`}>
                    <div className={`h-1.5 w-6 rounded-full ${isVisible ? '' : 'opacity-40'}`} style={{ backgroundColor: info.color }} />
                    <span className="flex-1 text-xs">{info.label}</span>
                    <div className={`h-2 w-2 rounded-full transition-colors ${isVisible ? 'bg-accent' : 'bg-border-subtle'}`} />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-6 border-t border-border-subtle pt-4">
            <h3 className="mb-2 text-xs font-medium tracking-wide text-text-secondary uppercase">
              <Target className="mr-1.5 inline h-3 w-3" />Focus Depth
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {[{ value: null, label: 'All' }, { value: 1, label: '1 hop' }, { value: 2, label: '2 hops' }, { value: 3, label: '3 hops' }, { value: 5, label: '5 hops' }].map(({ value, label }) => (
                <button key={label} onClick={() => setDepthFilter(value)} className={`rounded px-2 py-1 text-xs transition-colors ${depthFilter === value ? 'bg-accent text-white' : 'bg-elevated text-text-secondary hover:bg-hover hover:text-text-primary'}`}>{label}</button>
              ))}
            </div>
            {depthFilter !== null && !selectedNode && (
              <p className="mt-2 text-[10px] text-amber-400">Select a node to apply depth filter</p>
            )}
          </div>
        </div>
      )}

      {graph && (
        <div className="border-t border-border-subtle bg-elevated/50 px-3 py-2">
          <div className="flex items-center justify-between text-[10px] text-text-muted">
            <span>{graph.nodes.length} nodes</span>
            <span>{graph.relationships.length} edges</span>
          </div>
        </div>
      )}
    </div>
  );
};
