import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { supabase } from "../services/supabase";

export function SignupPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmSent, setConfirmSent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    if (data.session) {
      navigate("/projects", { replace: true });
    } else {
      setConfirmSent(true);
    }
  }

  return (
    <div className="mx-auto max-w-sm p-8">
      <h1 className="mb-6 text-2xl font-semibold">Create your account</h1>
      <form onSubmit={submit} className="space-y-3">
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
          minLength={8}
          placeholder="password (min 8)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border p-2"
        />
        <button disabled={busy} className="w-full rounded bg-black px-4 py-2 text-white disabled:opacity-50">
          Sign up
        </button>
      </form>
      {confirmSent && <p className="mt-3 text-sm text-green-700">Check your inbox to confirm.</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <p className="mt-6 text-sm">
        Have an account? <a href="/login" className="underline">Sign in</a>
      </p>
    </div>
  );
}
