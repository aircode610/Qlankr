import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { ProjectsListPage } from "./pages/ProjectsListPage";
import { ProjectDetailLayout } from "./pages/ProjectDetailLayout";
import { AppStateProvider } from "./hooks/useAppState";
import { HistoryList } from "./pages/HistoryList";
import { PrAnalysisReplay } from "./pages/PrAnalysisReplay";
import { BugReportReplay } from "./pages/BugReportReplay";
import { AuthedNav } from "./components/AuthedNav";
import { SettingsPanel } from "./components/SettingsPanel";
import LegacyApp from "./pages/LegacyApp";

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
                {/* The full legacy UI (graph + file tree + analyze + bug reproduction) renders here,
                    scoped to whichever project is open. Sprint 4's new tabs (History) live alongside. */}
                <Route index element={<LegacyApp />} />
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
