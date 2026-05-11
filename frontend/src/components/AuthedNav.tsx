import { Link, useNavigate } from "react-router-dom";

import { Zap, Settings2, Sun, Moon } from "@/lib/lucide-icons";
import { useAuth } from "../auth/AuthProvider";
import { useTheme } from "../hooks/useTheme";

export function AuthedNav() {
  const { user, signOut } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate("/login");
  }

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border-subtle bg-surface px-4">
      {/* Brand */}
      <Link to="/projects" className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-dim shadow-glow">
          <Zap className="h-3.5 w-3.5 text-white" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-text-primary">Qlankr</span>
      </Link>

      <div className="h-4 w-px bg-border-subtle" />

      <div className="flex-1" />

      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        className="flex h-8 w-8 items-center justify-center rounded-md border border-border-subtle bg-elevated text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
      </button>

      {/* Nav tabs */}
      <div className="flex items-center gap-0.5 rounded-lg border border-border-subtle bg-elevated p-1">
        <Link
          to="/settings"
          className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-text-muted transition-all hover:text-text-secondary"
        >
          <Settings2 className="h-3.5 w-3.5" />
          Settings
        </Link>
      </div>

      {/* User */}
      {user && (
        <div className="flex items-center gap-2">
          <span className="max-w-[180px] truncate text-xs text-text-muted">{user.email}</span>
          <button
            onClick={handleSignOut}
            className="rounded-md border border-border-subtle bg-elevated px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
          >
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}
