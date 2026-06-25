import { Navigate, Route, Routes } from "react-router-dom";
import { ArrCommandsPage } from "@/arr/pages/ArrCommandsPage";
import { ArrAddCommandPage } from "@/arr/pages/ArrAddCommandPage";
import { ArrCommandHistoryPage } from "@/arr/pages/ArrCommandHistoryPage";
import { ArrNewReleasesPage } from "@/arr/pages/ArrNewReleasesPage";
import { ArrEventsPage } from "@/arr/pages/ArrEventsPage";
import { ArrImportListsPage } from "@/arr/pages/ArrImportListsPage";
import { ArrSettingsPage } from "@/arr/pages/settings/ArrSettingsPage";
import { ArrSystemStatusPage } from "@/arr/pages/system/ArrSystemStatusPage";
import { ArrSystemArtistEventsPage } from "@/arr/pages/system/ArrSystemArtistEventsPage";
import { ArrSystemLibraryCachePage } from "@/arr/pages/system/ArrSystemLibraryCachePage";
import { ArrSystemNewReleasesPage } from "@/arr/pages/system/ArrSystemNewReleasesPage";

export function ArrRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/commands" replace />} />
      <Route path="/commands" element={<ArrCommandsPage />} />
      <Route path="/commands/add" element={<ArrAddCommandPage />} />
      <Route path="/commands/history" element={<ArrCommandHistoryPage />} />
      <Route path="/new-releases" element={<ArrNewReleasesPage />} />
      <Route path="/events" element={<ArrEventsPage />} />
      <Route path="/import-lists" element={<ArrImportListsPage />} />
      <Route path="/settings" element={<Navigate to="/settings/application" replace />} />
      <Route path="/settings/:section" element={<ArrSettingsPage />} />
      <Route path="/system/status" element={<ArrSystemStatusPage />} />
      <Route path="/system/library-cache" element={<ArrSystemLibraryCachePage />} />
      <Route path="/system/artist-events" element={<ArrSystemArtistEventsPage />} />
      <Route path="/system/new-releases" element={<ArrSystemNewReleasesPage />} />
      <Route path="/system" element={<Navigate to="/system/status" replace />} />
      <Route path="/config" element={<Navigate to="/settings/application" replace />} />
      <Route path="/status" element={<Navigate to="/system/status" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
