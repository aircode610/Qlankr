import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { ProjectsListPage } from "./pages/ProjectsListPage";
import { ProjectDetailLayout } from "./pages/ProjectDetailLayout";
import { AppStateProvider } from "./hooks/useAppState";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppStateProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />

            <Route
              path="/projects"
              element={
                <RequireAuth>
                  <ProjectsListPage />
                </RequireAuth>
              }
            />

            <Route
              path="/projects/:id"
              element={
                <RequireAuth>
                  <ProjectDetailLayout />
                </RequireAuth>
              }
            >
              <Route index element={<div className="p-4 text-sm text-gray-500">Graph view (Task 23).</div>} />
              <Route path="analyze" element={<div className="p-4">PR analysis (Task 23).</div>} />
              <Route path="bugs" element={<div className="p-4">Bug reproduction (Task 23).</div>} />
              <Route path="history" element={<div className="p-4">History (Task 31+).</div>} />
            </Route>

            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </AppStateProvider>
      </BrowserRouter>
    </AuthProvider>
  );
}
