export function settingsPath(section: string): string {
  return `/settings/${section}`;
}

export function eventSourcesSettingsPath(): string {
  return settingsPath("event-sources");
}
