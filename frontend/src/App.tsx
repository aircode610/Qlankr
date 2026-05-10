import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { ProjectsListPage } from "./pages/ProjectsListPage";
import { ProjectDetailLayout } from "./pages/ProjectDetailLayout";
import { AppStateProvider } from "./hooks/useAppState";
import { GraphCanvas } from "./components/GraphCanvas";
import { HistoryList } from "./pages/HistoryList";
import { PrAnalysisReplay } from "./pages/PrAnalysisReplay";
import { BugReportReplay } from "./pages/BugReportReplay";
import { AuthedNav } from "./components/AuthedNav";
import { SettingsPanel } from "./components/SettingsPanel";

function AuthedShell() {
  return (
    <>
      <AuthedNav />
      <Outlet />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppStateProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />

            <Route element={<RequireAuth><AuthedShell /></RequireAuth>}>
              <Route path="/projects" element={<ProjectsListPage />} />
              <Route path="/projects/:id" element={<ProjectDetailLayout />}>
                <Route index element={<GraphCanvas />} />
                {/* PR analysis + bug reproduction need wrapper components that bind the existing
                    PrAnalysisPanel/ResearchPanel to the analyze/bug data flows (currently held
                    in LegacyApp.tsx). Follow-up task. */}
                <Route path="analyze" element={<div className="p-4 text-sm text-gray-500">PR analysis — pending data-flow wrapper.</div>} />
                <Route path="bugs" element={<div className="p-4 text-sm text-gray-500">Bug reproduction — pending data-flow wrapper.</div>} />
                <Route path="history" element={<HistoryList />} />
                <Route path="history/pr/:runId" element={<PrAnalysisReplay />} />
                <Route path="history/bug/:runId" element={<BugReportReplay />} />
              </Route>
              <Route path="/settings" element={<SettingsPanel />} />
            </Route>

            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </AppStateProvider>
      </BrowserRouter>
    </AuthProvider>
  );
}
