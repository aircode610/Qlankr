import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";

export function AuthedNav() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate("/login");
  }

  return (
    <nav className="flex items-center justify-between border-b p-3">
      <Link to="/projects" className="font-semibold">Qlankr</Link>
      <div className="flex items-center gap-3 text-sm">
        <Link to="/settings" className="underline">Settings</Link>
        {user && (
          <>
            <span className="text-gray-500">{user.email}</span>
            <button onClick={handleSignOut} className="rounded border px-2 py-1">Sign out</button>
          </>
        )}
      </div>
    </nav>
  );
}
