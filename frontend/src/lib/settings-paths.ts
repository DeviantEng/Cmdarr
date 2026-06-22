import type { UiShell } from "@/lib/ui-shell-context";

export function settingsPath(section: string, shell: UiShell): string {
  return shell === "arr" ? `/settings/${section}` : "/config";
}

export function eventSourcesSettingsPath(shell: UiShell): string {
  return settingsPath("event-sources", shell);
}
