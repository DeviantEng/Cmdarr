import { useContext } from "react";
import { UiShellContext } from "@/lib/ui-shell-context";

export function useUiShell() {
  const ctx = useContext(UiShellContext);
  if (!ctx) {
    throw new Error("useUiShell must be used within UiShellProvider");
  }
  return ctx;
}

export type { UiShell } from "@/lib/ui-shell-context";
