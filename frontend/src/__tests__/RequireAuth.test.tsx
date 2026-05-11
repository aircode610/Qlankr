import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { RequireAuth } from "../auth/RequireAuth";
import * as AuthMod from "../auth/AuthProvider";

vi.mock("../services/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  },
}));

describe("RequireAuth", () => {
  it("renders children when authenticated", () => {
    vi.spyOn(AuthMod, "useAuth").mockReturnValue({
      session: { user: { id: "u" } } as never,
      user: { id: "u" } as never,
      loading: false,
      signOut: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/secret"]}>
        <Routes>
          <Route path="/secret" element={<RequireAuth><div>secret</div></RequireAuth>} />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("secret")).toBeInTheDocument();
  });

  it("redirects to /login when not authenticated", () => {
    vi.spyOn(AuthMod, "useAuth").mockReturnValue({
      session: null,
      user: null,
      loading: false,
      signOut: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/secret"]}>
        <Routes>
          <Route path="/secret" element={<RequireAuth><div>secret</div></RequireAuth>} />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("login page")).toBeInTheDocument();
  });
});
