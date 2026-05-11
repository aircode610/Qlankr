import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { Zap, Sun, Moon } from "@/lib/lucide-icons";
import { supabase } from "../services/supabase";
import { useTheme } from "../hooks/useTheme";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/projects";
  const { theme, toggleTheme } = useTheme();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [magicSent, setMagicSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signInWithPassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) { setError(error.message); return; }
    navigate(from, { replace: true });
  }

  async function sendMagicLink() {
    setError(null);
    setBusy(true);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setBusy(false);
    if (error) { setError(error.message); return; }
    setMagicSent(true);
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-void">
      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-md border border-border-subtle bg-elevated text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
      </button>

      <div className="w-full max-w-sm rounded-xl border border-border-subtle bg-surface p-8">
        {/* Brand */}
        <div className="mb-8 flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-dim shadow-glow">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <span className="text-base font-semibold tracking-tight text-text-primary">Qlankr</span>
        </div>

        <h1 className="mb-6 text-xl font-semibold text-text-primary">Sign in</h1>

        <form onSubmit={signInWithPassword} className="space-y-3">
          <input
            type="email"
            required
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border-subtle bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
          />
          <input
            type="password"
            required
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border-subtle bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
          />
          <button
            disabled={busy}
            className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
          >
            Sign in
          </button>
        </form>

        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1 bg-border-subtle" />
          <span className="text-xs text-text-muted">or</span>
          <div className="h-px flex-1 bg-border-subtle" />
        </div>

        <button
          type="button"
          onClick={sendMagicLink}
          disabled={busy || !email}
          className="w-full rounded-md border border-border-subtle bg-elevated px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-hover hover:text-text-primary disabled:opacity-50"
        >
          Email me a magic link
        </button>

        {magicSent && <p className="mt-3 text-sm text-emerald-400">Check your inbox.</p>}
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

        <p className="mt-6 text-sm text-text-muted">
          No account?{" "}
          <a href="/signup" className="text-accent hover:underline">Sign up</a>
        </p>
      </div>
    </div>
  );
}
