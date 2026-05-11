import { useEffect } from "react";
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import { Sun, Moon } from "@/lib/lucide-icons";
import { getProject } from "../services/api";
import { useAppState } from "../hooks/useAppState";
import { useTheme } from "../hooks/useTheme";

const STATUS_STYLES: Record<string, string> = {
  ready:    "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  indexing: "border-blue-500/25 bg-blue-500/10 text-blue-400",
  pending:  "border-border-default bg-elevated text-text-muted",
  failed:   "border-red-500/25 bg-red-500/10 text-red-400",
  stale:    "border-yellow-500/25 bg-yellow-500/10 text-yellow-400",
};

export function ProjectDetailLayout() {
  const { id } = useParams<{ id: string }>();
  const { pathname } = useLocation();
  const { currentProject, setCurrentProject } = useAppState();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    if (!id) return;
    getProject(id).then(setCurrentProject).catch(() => setCurrentProject(null));
  }, [id, setCurrentProject]);

  if (!currentProject) return (
    <div className="flex min-h-screen items-center justify-center bg-void">
      <span className="text-sm text-text-muted">Loading project…</span>
    </div>
  );

  const onHistoryTab = pathname.includes("/history");

  return (
    <div className="flex h-screen min-h-0 flex-col bg-void">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border-subtle bg-surface px-4">
        <Link to="/projects" className="text-xs text-text-muted transition-colors hover:text-text-secondary">
          ← Projects
        </Link>
        <div className="h-4 w-px bg-border-subtle" />
        <span className="text-sm font-medium text-text-primary">
          {currentProject.owner}/{currentProject.repo_name}
        </span>
        <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[currentProject.index_status] ?? STATUS_STYLES.pending}`}>
          {currentProject.index_status}
        </span>

        <div className="flex-1" />

        <button
          onClick={toggleTheme}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border-subtle bg-elevated text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </button>

        <div className="flex items-center gap-0.5 rounded-lg border border-border-subtle bg-elevated p-1">
          <Link
            to=""
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              !onHistoryTab ? "bg-surface text-text-primary shadow-sm" : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Project
          </Link>
          <Link
            to="history"
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              onHistoryTab ? "bg-surface text-text-primary shadow-sm" : "text-text-muted hover:text-text-secondary"
            }`}
          >
            History
          </Link>
        </div>
      </header>

      {!onHistoryTab && currentProject.index_status === "failed" && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-400">
          Last indexing run failed: {currentProject.index_error ?? "see backend logs"}.
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
