import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Loader2, Plus } from "@/lib/lucide-icons";
import { createProject, listProjects, Project } from "../services/api";

function displayName(p: Project): string {
  if (p.name) return p.name;
  if (p.owner && p.repo_name) return `${p.owner}/${p.repo_name}`;
  return "(unnamed)";
}

const STATUS_STYLES: Record<string, string> = {
  ready:    "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  indexing: "border-blue-500/25 bg-blue-500/10 text-blue-400",
  pending:  "border-border-default bg-elevated text-text-muted",
  failed:   "border-red-500/25 bg-red-500/10 text-red-400",
  stale:    "border-yellow-500/25 bg-yellow-500/10 text-yellow-400",
};

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

  useEffect(() => { void refresh(); }, []);

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
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="mb-8 text-xl font-semibold text-text-primary">Projects</h1>

      {/* Create form */}
      <form onSubmit={add} className="mb-8 flex gap-2">
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="New project name"
          className="flex-1 rounded-md border border-border-subtle bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
        />
        <button
          disabled={busy || !projectName.trim()}
          className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          Create
        </button>
      </form>

      {error && (
        <p className="mb-4 rounded-md border border-red-500/25 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      {/* Project list */}
      <ul className="space-y-2">
        {projects.map((p) => (
          <li key={p.id}>
            <Link
              to={`/projects/${p.id}`}
              className="flex items-center gap-3 rounded-lg border border-border-subtle bg-elevated px-4 py-3 transition-colors hover:border-border-default hover:bg-hover"
            >
              <div className="min-w-0 flex-1">
                <span className="block font-medium text-text-primary">{displayName(p)}</span>
                {p.repo_url && (
                  <span className="block max-w-md truncate text-xs text-text-muted">{p.repo_url}</span>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {p.graph_stats?.node_count != null && (
                  <span className="text-xs text-text-muted">
                    {p.graph_stats.node_count} nodes
                  </span>
                )}
                <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[p.index_status] ?? STATUS_STYLES.pending}`}>
                  {p.index_status}
                </span>
              </div>
            </Link>
          </li>
        ))}
        {projects.length === 0 && (
          <li className="py-12 text-center text-sm text-text-muted">
            No projects yet. Create one above.
          </li>
        )}
      </ul>
    </div>
  );
}
