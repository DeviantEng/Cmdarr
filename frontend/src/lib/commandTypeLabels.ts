/** Friendly labels for CommandConfig.command_type filter/display. */
export function formatCommandTypeLabel(commandType: string | null | undefined): string {
  if (!commandType) return "Other";
  const labels: Record<string, string> = {
    playlist_generator: "Playlist Generator",
    playlist_sync: "Playlist Sync",
    discovery: "Discovery",
    lidarr_maintenance: "Lidarr Maintenance",
  };
  return labels[commandType] ?? commandType;
}
