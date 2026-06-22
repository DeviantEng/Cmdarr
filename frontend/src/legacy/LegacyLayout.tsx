import { Link, useLocation } from "react-router-dom";
import { Moon, Sun, Menu, X, LogOut } from "lucide-react";
import { useTheme } from "@/lib/use-theme";
import { Button } from "@/components/ui/button";
import { UiShellToggle } from "@/components/UiShellToggle";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

const navItems = [
  { path: "/", label: "Commands" },
  { path: "/new-releases", label: "New Releases" },
  { path: "/events", label: "Artist Events" },
  { path: "/import-lists", label: "Import Lists" },
  { path: "/config", label: "Configuration" },
  { path: "/status", label: "Status" },
];

export function LegacyLayout({ children }: { children: React.ReactNode }) {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileMenuOpen]);

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  return (
    <div className="min-h-screen bg-background transition-colors duration-200">
      <nav className="relative z-50 border-b bg-card shadow-sm">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 justify-between">
            <div className="flex items-center">
              <Link to="/" className="flex items-center space-x-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                  <span className="text-sm font-bold text-primary-foreground">C</span>
                </div>
                <span className="text-xl font-bold">Cmdarr</span>
              </Link>
            </div>

            <div className="hidden items-center space-x-4 lg:flex lg:space-x-6">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    location.pathname === item.path
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </div>

            <div className="flex items-center gap-1 sm:gap-2">
              <UiShellToggle compact />
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10"
                onClick={async () => {
                  await api.logout();
                  window.location.href = "/";
                }}
                title="Log out"
                aria-label="Log out"
              >
                <LogOut className="h-5 w-5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10"
                onClick={toggleTheme}
                title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
                aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              >
                {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>

              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10 lg:hidden"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                title={mobileMenuOpen ? "Close menu" : "Open menu"}
                aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
                aria-expanded={mobileMenuOpen}
              >
                {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {mobileMenuOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden" role="presentation">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close menu"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="absolute inset-x-0 top-16 z-50 max-h-[calc(100vh-4rem)] overflow-y-auto border-b bg-card shadow-lg">
            <div className="space-y-1 px-2 py-3">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(
                    "block rounded-md px-3 py-3 text-base font-medium transition-colors",
                    location.pathname === item.path
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <main className="mx-auto min-w-0 max-w-7xl overflow-x-hidden px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
}
