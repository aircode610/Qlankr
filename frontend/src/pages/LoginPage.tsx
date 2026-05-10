import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { supabase } from "../services/supabase";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/projects";

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
    if (error) {
      setError(error.message);
      return;
    }
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
    if (error) {
      setError(error.message);
      return;
    }
    setMagicSent(true);
  }

  return (
    <div className="mx-auto max-w-sm p-8">
      <h1 className="mb-6 text-2xl font-semibold">Sign in</h1>
      <form onSubmit={signInWithPassword} className="space-y-3">
        <input
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border p-2"
        />
        <input
          type="password"
          required
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border p-2"
        />
        <button disabled={busy} className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-50">
          Sign in
        </button>
      </form>
      <div className="my-4 text-center text-xs text-gray-500">or</div>
      <button
        type="button"
        onClick={sendMagicLink}
        disabled={busy || !email}
        className="w-full rounded border px-4 py-2 disabled:opacity-50"
      >
        Email me a magic link
      </button>
      {magicSent && <p className="mt-3 text-sm text-green-700">Check your inbox.</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <p className="mt-6 text-sm">
        No account? <a href="/signup" className="underline">Sign up</a>
      </p>
    </div>
  );
}
