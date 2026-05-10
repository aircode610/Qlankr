import { useEffect } from "react";
import { Link, Outlet, useParams } from "react-router-dom";

import { getProject } from "../services/api";
import { useAppState } from "../hooks/useAppState";

export function ProjectDetailLayout() {
  const { id } = useParams<{ id: string }>();
  const { currentProject, setCurrentProject } = useAppState();

  useEffect(() => {
    if (!id) return;
    getProject(id).then(setCurrentProject).catch(() => setCurrentProject(null));
  }, [id, setCurrentProject]);

  if (!currentProject) return <div className="p-8 text-sm text-gray-500">Loading project…</div>;

  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <Link to="/projects" className="text-sm underline">← Projects</Link>
          <h1 className="text-xl font-semibold">{currentProject.owner}/{currentProject.repo_name}</h1>
        </div>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs">{currentProject.index_status}</span>
      </header>

      {!currentProject.local_graph_present && (
        <div className="mb-4 rounded border border-yellow-400 bg-yellow-50 p-3 text-sm">
          This project has no indexed graph on this machine. Re-index to enable analysis.
        </div>
      )}

      <nav className="mb-4 flex gap-3 border-b text-sm">
        <Link to="" className="px-3 py-2 hover:underline">Graph</Link>
        <Link to="analyze" className="px-3 py-2 hover:underline">PR Analysis</Link>
        <Link to="bugs" className="px-3 py-2 hover:underline">Bug Reproduction</Link>
        <Link to="history" className="px-3 py-2 hover:underline">History</Link>
      </nav>

      <Outlet />
    </div>
  );
}
