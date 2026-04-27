import { Zap, Layers, GitPullRequest, Loader2, Settings2 } from '@/lib/lucide-icons';

export type AppView = 'graph' | 'analyze' | 'settings';

interface NavbarProps {
  view: AppView;
  onViewChange: (v: AppView) => void;
  repoName: string | null;
  analyzing: boolean;
  activeWorkflowLabel: string | null;
}

export const Navbar = ({ view, onViewChange, repoName, analyzing, activeWorkflowLabel }: NavbarProps) => (
  <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border-subtle bg-surface px-4">
    {/* Brand */}
    <div className="flex items-center gap-2">
      <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-violet-800 shadow-[0_0_8px_rgba(124,58,237,0.4)]">
        <Zap className="h-3.5 w-3.5 text-white" />
      </div>
      <span className="text-sm font-semibold tracking-tight text-text-primary">Qlankr</span>
    </div>

    {/* Divider */}
    <div className="h-4 w-px bg-border-subtle" />

    {/* Indexed repo badge */}
    {repoName && (
      <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/8 px-2.5 py-0.5 text-[11px] text-emerald-400">
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
        <span className="max-w-[160px] truncate font-mono">{repoName}</span>
      </div>
    )}

    {/* Active workflow badge */}
    {analyzing && activeWorkflowLabel && (
      <div className="flex items-center gap-1.5 rounded-full border border-accent/30 bg-accent/8 px-2.5 py-0.5 text-[11px] text-accent">
        <Loader2 className="h-3 w-3 animate-spin" />
        {activeWorkflowLabel}
      </div>
    )}

    {/* Push tabs to the right */}
    <div className="flex-1" />

    {/* Tab switcher */}
    <div className="flex items-center gap-0.5 rounded-lg border border-border-subtle bg-elevated p-1">
      <button
        onClick={() => onViewChange('graph')}
        className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
          view === 'graph'
            ? 'bg-surface text-text-primary shadow-sm'
            : 'text-text-muted hover:text-text-secondary'
        }`}
      >
        <Layers className="h-3.5 w-3.5" />
        Graph
      </button>
      <button
        onClick={() => onViewChange('analyze')}
        className={`relative flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
          view === 'analyze'
            ? 'bg-surface text-text-primary shadow-sm'
            : 'text-text-muted hover:text-text-secondary'
        }`}
      >
        <GitPullRequest className="h-3.5 w-3.5" />
        Analyze
        {analyzing && (
          <span className="absolute -right-1 -top-1 h-2 w-2 animate-pulse rounded-full bg-accent" />
        )}
      </button>
      <button
        onClick={() => onViewChange('settings')}
        className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
          view === 'settings'
            ? 'bg-surface text-text-primary shadow-sm'
            : 'text-text-muted hover:text-text-secondary'
        }`}
      >
        <Settings2 className="h-3.5 w-3.5" />
        Settings
      </button>
    </div>
  </header>
);
