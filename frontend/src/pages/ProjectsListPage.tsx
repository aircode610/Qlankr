import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createProject, listProjects, Project } from "../services/api";

export function ProjectsListPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [repoUrl, setRepoUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const p = await createProject(repoUrl);
      setProjects((prev) => [p, ...prev]);
      setRepoUrl("");
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
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          className="flex-1 rounded border p-2"
        />
        <button disabled={busy || !repoUrl} className="rounded bg-black px-4 py-2 text-white disabled:opacity-50">
          Add
        </button>
      </form>
      {error && <p className="mb-3 text-sm text-red-700">{error}</p>}
      <ul className="space-y-2">
        {projects.map((p) => (
          <li key={p.id} className="rounded border p-3">
            <Link to={`/projects/${p.id}`} className="font-medium underline">
              {p.owner}/{p.repo_name}
            </Link>
            <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-xs">{p.index_status}</span>
            {p.graph_stats?.node_count != null && (
              <span className="ml-2 text-xs text-gray-500">
                {p.graph_stats.node_count} nodes, {p.graph_stats.edge_count} edges
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
