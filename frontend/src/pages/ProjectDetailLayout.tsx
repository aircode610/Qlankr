import { useEffect } from "react";
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import { getProject } from "../services/api";
import { useAppState } from "../hooks/useAppState";

export function ProjectDetailLayout() {
  const { id } = useParams<{ id: string }>();
  const { pathname } = useLocation();
  const { currentProject, setCurrentProject } = useAppState();

  useEffect(() => {
    if (!id) return;
    getProject(id).then(setCurrentProject).catch(() => setCurrentProject(null));
  }, [id, setCurrentProject]);

  if (!currentProject) return <div className="p-8 text-sm text-gray-500">Loading project…</div>;

  const onHistoryTab = pathname.includes("/history");

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-3 border-b border-border-subtle bg-surface px-4 py-2 text-sm">
        <Link to="/projects" className="text-text-muted underline">← Projects</Link>
        <span className="font-medium text-text-primary">{currentProject.owner}/{currentProject.repo_name}</span>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">{currentProject.index_status}</span>
        <nav className="ml-auto flex gap-2 text-xs">
          <Link
            to=""
            className={`rounded px-2 py-0.5 ${!onHistoryTab ? "bg-gray-200 text-gray-900" : "text-text-muted hover:bg-gray-100"}`}
          >
            Project
          </Link>
          <Link
            to="history"
            className={`rounded px-2 py-0.5 ${onHistoryTab ? "bg-gray-200 text-gray-900" : "text-text-muted hover:bg-gray-100"}`}
          >
            History
          </Link>
        </nav>
      </header>

      {/* Only show the "needs indexing" banner if the project actually hasn't
          been indexed yet (no repo attached). The local_graph_present flag is
          unreliable — gitnexus stores graphs in its own location, not our
          per-user dir, so the filesystem check returns false even when the
          graph is fully queryable via MCP. */}
      {!onHistoryTab && (!currentProject.owner || !currentProject.repo_name) && (
        <div className="border-b border-yellow-400 bg-yellow-50 px-4 py-2 text-xs text-yellow-800">
          This project doesn't have a repository attached yet. Use the indexing screen below.
        </div>
      )}
      {!onHistoryTab && currentProject.index_status === "failed" && (
        <div className="border-b border-red-400 bg-red-50 px-4 py-2 text-xs text-red-800">
          Last indexing run failed: {currentProject.index_error ?? "see backend logs"}.
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
