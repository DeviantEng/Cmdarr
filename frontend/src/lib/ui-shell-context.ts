import { createContext } from "react";

export type UiShell = "legacy" | "arr";

export const UI_SHELL_STORAGE_KEY = "cmdarr-ui-shell";

export type UiShellContextValue = {
  shell: UiShell;
  setShell: (shell: UiShell) => void;
  toggleShell: () => void;
  isArr: boolean;
};

export const UiShellContext = createContext<UiShellContextValue | null>(null);
