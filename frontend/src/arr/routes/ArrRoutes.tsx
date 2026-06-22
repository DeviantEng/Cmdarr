import { Navigate, Route, Routes } from "react-router-dom";
import { ArrCommandsPage } from "@/arr/pages/ArrCommandsPage";
import { ArrNewReleasesPage } from "@/arr/pages/ArrNewReleasesPage";
import { ArrEventsPage } from "@/arr/pages/ArrEventsPage";
import { ArrImportListsPage } from "@/arr/pages/ArrImportListsPage";
import { ArrSettingsPage } from "@/arr/pages/settings/ArrSettingsPage";
import { ArrSystemStatusPage } from "@/arr/pages/system/ArrSystemStatusPage";

export function ArrRoutes() {
  return (
    <Routes>
      <Route path="/" element={<ArrCommandsPage />} />
      <Route path="/new-releases" element={<ArrNewReleasesPage />} />
      <Route path="/events" element={<ArrEventsPage />} />
      <Route path="/import-lists" element={<ArrImportListsPage />} />
      <Route path="/settings" element={<Navigate to="/settings/application" replace />} />
      <Route path="/settings/:section" element={<ArrSettingsPage />} />
      <Route path="/system/status" element={<ArrSystemStatusPage />} />
      <Route path="/config" element={<Navigate to="/settings/application" replace />} />
      <Route path="/status" element={<Navigate to="/system/status" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
