import type { UiShell } from "@/lib/ui-shell";

export function eventSourcesSettingsPath(shell: UiShell): string {
  return shell === "arr" ? "/settings/event-sources" : "/config";
}
