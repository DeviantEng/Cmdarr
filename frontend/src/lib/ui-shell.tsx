import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type UiShell = "legacy" | "arr";

const STORAGE_KEY = "cmdarr-ui-shell";

type UiShellContextValue = {
  shell: UiShell;
  setShell: (shell: UiShell) => void;
  toggleShell: () => void;
  isArr: boolean;
};

const UiShellContext = createContext<UiShellContextValue | null>(null);

export function UiShellProvider({ children }: { children: ReactNode }) {
  const [shell, setShellState] = useState<UiShell>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "arr" ? "arr" : "legacy";
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, shell);
    document.documentElement.dataset.uiShell = shell;
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

export function useUiShell() {
  const ctx = useContext(UiShellContext);
  if (!ctx) {
    throw new Error("useUiShell must be used within UiShellProvider");
  }
  return ctx;
}
