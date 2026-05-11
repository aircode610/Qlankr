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

// Outer shell: AuthedNav + scrollable content area.
// Used for /projects (list) and /settings only.
function OuterShell() {
  return (
    <div className="flex min-h-screen flex-col bg-void">
      <AuthedNav />
      <div className="flex-1">
        <Outlet />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppStateProvider>
          <Routes>
            {/* Public auth pages */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />

            {/* Protected routes */}
            <Route element={<RequireAuth><Outlet /></RequireAuth>}>
              {/* Pages that use AuthedNav (projects list, settings) */}
              <Route element={<OuterShell />}>
                <Route path="/projects" element={<ProjectsListPage />} />
                <Route path="/settings" element={<SettingsPanel />} />
              </Route>

              {/* Workspace — has its own full-screen layout with Navbar */}
              <Route path="/projects/:id" element={<ProjectDetailLayout />}>
                <Route index element={<LegacyApp />} />
                <Route path="history" element={<HistoryList />} />
                <Route path="history/pr/:runId" element={<PrAnalysisReplay />} />
                <Route path="history/bug/:runId" element={<BugReportReplay />} />
              </Route>
            </Route>

            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </AppStateProvider>
      </BrowserRouter>
    </AuthProvider>
  );
}
