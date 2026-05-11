import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";

export function AuthCallbackPage() {
  const { loading, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    navigate(user ? "/projects" : "/login", { replace: true });
  }, [loading, user, navigate]);

  return <div className="p-8 text-sm text-gray-500">Signing you in…</div>;
}
