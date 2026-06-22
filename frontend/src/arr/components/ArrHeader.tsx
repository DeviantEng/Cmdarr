import { Menu, Moon, Sun, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UiShellToggle } from "@/components/UiShellToggle";
import { useTheme } from "@/lib/use-theme";
import { api } from "@/lib/api";
import { arrPageTitle } from "@/arr/arr-nav";
import { useLocation } from "react-router-dom";

type ArrHeaderProps = {
  onOpenSidebar: () => void;
};

export function ArrHeader({ onOpenSidebar }: ArrHeaderProps) {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const title = arrPageTitle(location.pathname);

  return (
    <header
      className="flex h-[var(--arr-header-height)] shrink-0 items-center justify-between gap-3 border-b px-3 sm:px-4"
      style={{
        background: "var(--arr-header-bg)",
        borderColor: "var(--arr-header-border)",
      }}
    >
      <div className="flex min-w-0 items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 lg:hidden"
          onClick={onOpenSidebar}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{title}</p>
          <p className="hidden text-xs text-muted-foreground sm:block">Cmdarr preview · v0.3.17</p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <span
          className="mr-1 hidden h-2 w-2 rounded-full bg-emerald-500 sm:inline-block"
          title="Health indicator (placeholder)"
        />
        <UiShellToggle compact />
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9"
          onClick={async () => {
            await api.logout();
            window.location.href = "/";
          }}
          title="Log out"
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
