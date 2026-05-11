import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "../auth/AuthProvider";

vi.mock("../services/supabase", () => {
  const listeners: Array<(event: string, session: unknown) => void> = [];
  return {
    supabase: {
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: { user: { id: "u-1" }, access_token: "tok" } },
        }),
        onAuthStateChange: vi.fn((cb: (e: string, s: unknown) => void) => {
          listeners.push(cb);
          return { data: { subscription: { unsubscribe: vi.fn() } } };
        }),
      },
    },
  };
});

function Probe() {
  const { user, loading } = useAuth();
  if (loading) return <div>loading</div>;
  return <div>user:{user?.id ?? "anon"}</div>;
}

describe("AuthProvider", () => {
  it("hydrates the session on mount", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    expect(screen.getByText("loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("user:u-1")).toBeInTheDocument());
  });
});
