import { useEffect, useState, type ReactNode } from "react";
import { UI_SHELL_STORAGE_KEY, UiShellContext, type UiShell } from "@/lib/ui-shell-context";

export function UiShellProvider({ children }: { children: ReactNode }) {
  const [shell, setShellState] = useState<UiShell>(() => {
    const stored = localStorage.getItem(UI_SHELL_STORAGE_KEY);
    return stored === "arr" ? "arr" : "legacy";
  });

  useEffect(() => {
    localStorage.setItem(UI_SHELL_STORAGE_KEY, shell);
    // Arr tokens live on `.arr-shell[data-ui-shell="arr"]` only — never on <html> (breaks login + portaled dialogs).
    document.documentElement.removeAttribute("data-ui-shell");
  }, [shell]);

  const setShell = (next: UiShell) => setShellState(next);
  const toggleShell = () => setShellState((s) => (s === "legacy" ? "arr" : "legacy"));

  return (
    <UiShellContext.Provider
      value={{
        shell,
        setShell,
        toggleShell,
        isArr: shell === "arr",
      }}
    >
      {children}
    </UiShellContext.Provider>
  );
}
