import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createProject, listProjects, Project } from "../services/api";

function displayName(p: Project): string {
  if (p.name) return p.name;
  if (p.owner && p.repo_name) return `${p.owner}/${p.repo_name}`;
  return "(unnamed)";
}

export function ProjectsListPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const list = await listProjects();
      setProjects(list);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const p = await createProject({ name: projectName.trim() });
      setProjects((prev) => [p, ...prev]);
      setProjectName("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Your projects</h1>
      <form onSubmit={add} className="mb-6 flex gap-2">
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="Project name"
          className="flex-1 rounded border p-2"
        />
        <button disabled={busy || !projectName.trim()} className="rounded bg-black px-4 py-2 text-white disabled:opacity-50">
          Create
        </button>
      </form>
      {error && <p className="mb-3 text-sm text-red-700">{error}</p>}
      <ul className="space-y-2">
        {projects.map((p) => (
          <li key={p.id} className="rounded border p-3">
            <div className="flex items-center gap-2">
              <Link to={`/projects/${p.id}`} className="font-medium underline">
                {displayName(p)}
              </Link>
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs">{p.index_status}</span>
              {p.repo_url && (
                <span className="text-xs text-gray-500 truncate max-w-md">{p.repo_url}</span>
              )}
              {p.graph_stats?.node_count != null && (
                <span className="text-xs text-gray-500">
                  {p.graph_stats.node_count} nodes, {p.graph_stats.edge_count} edges
                </span>
              )}
            </div>
          </li>
        ))}
        {projects.length === 0 && (
          <li className="text-sm text-gray-500">No projects yet. Create one above.</li>
        )}
      </ul>
    </div>
  );
}
