import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/lib/theme";
import { Toaster } from "@/components/ui/sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { Layout } from "@/components/Layout";
import { CommandsPage } from "@/pages/Commands";
import { ConfigPage } from "@/pages/Config";
import { StatusPage } from "@/pages/Status";
import { ImportListsPage } from "@/pages/ImportLists";
import { NewReleasesPage } from "@/pages/NewReleases";
import { EventsPage } from "@/pages/Events";

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="cmdarr-ui-theme">
      <Router>
        <AuthGuard>
          <Layout>
            <Routes>
              <Route path="/" element={<CommandsPage />} />
              <Route path="/config" element={<ConfigPage />} />
              <Route path="/status" element={<StatusPage />} />
              <Route path="/import-lists" element={<ImportListsPage />} />
              <Route path="/new-releases" element={<NewReleasesPage />} />
              <Route path="/events" element={<EventsPage />} />
            </Routes>
          </Layout>
        </AuthGuard>
      </Router>
      <Toaster />
    </ThemeProvider>
  );
}

export default App;
