import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../services/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: "tok" } } }),
    },
  },
}));

import { ProjectsListPage } from "../pages/ProjectsListPage";
import * as api from "../services/api";

describe("ProjectsListPage", () => {
  it("renders projects from the API", async () => {
    vi.spyOn(api, "listProjects").mockResolvedValue([
      {
        id: "p1",
        user_id: "u",
        repo_url: "https://github.com/foo/bar",
        owner: "foo",
        repo_name: "bar",
        index_status: "ready",
        graph_stats: { node_count: 10, edge_count: 20 },
        last_indexed_at: "2026-05-10T12:00:00Z",
        created_at: "2026-05-10T11:00:00Z",
      },
    ]);

    render(
      <MemoryRouter>
        <ProjectsListPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("foo/bar")).toBeInTheDocument());
    expect(screen.getByText(/ready/i)).toBeInTheDocument();
  });
});
