import type { UiShell } from "@/lib/ui-shell-context";

export function eventSourcesSettingsPath(shell: UiShell): string {
  return shell === "arr" ? "/settings/event-sources" : "/config";
}
