import { BrowserRouter as Router } from "react-router";
import { ThemeProvider } from "@/lib/theme";
import { Toaster } from "@/components/ui/sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { AppShell } from "@/components/AppShell";

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="cmdarr-ui-theme">
      <Router>
        <AuthGuard>
          <AppShell />
        </AuthGuard>
      </Router>
      <Toaster />
    </ThemeProvider>
  );
}

export default App;
