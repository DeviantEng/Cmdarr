import { Route, Routes } from "react-router-dom";
import { CommandsPage } from "@/pages/Commands";
import { ConfigPage } from "@/pages/Config";
import { StatusPage } from "@/pages/Status";
import { ImportListsPage } from "@/pages/ImportLists";
import { NewReleasesPage } from "@/pages/NewReleases";
import { EventsPage } from "@/pages/Events";

export function LegacyRoutes() {
  return (
    <Routes>
      <Route path="/" element={<CommandsPage />} />
      <Route path="/config" element={<ConfigPage />} />
      <Route path="/status" element={<StatusPage />} />
      <Route path="/import-lists" element={<ImportListsPage />} />
      <Route path="/new-releases" element={<NewReleasesPage />} />
      <Route path="/events" element={<EventsPage />} />
    </Routes>
  );
}
