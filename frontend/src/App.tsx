import { BrowserRouter as Router } from "react-router-dom";
import { ThemeProvider } from "@/lib/theme";
import { UiShellProvider } from "@/lib/ui-shell";
import { Toaster } from "@/components/ui/sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { AppShell } from "@/components/AppShell";

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="cmdarr-ui-theme">
      <UiShellProvider>
        <Router>
          <AuthGuard>
            <AppShell />
          </AuthGuard>
        </Router>
        <Toaster />
      </UiShellProvider>
    </ThemeProvider>
  );
}

export default App;
