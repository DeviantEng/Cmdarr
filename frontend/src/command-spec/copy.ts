/**
 * Single source for command create/edit UI copy (labels, helper text).
 * Runtime source of truth — keep in sync with widgets in command-edit/.
 */

export const commandUiCopy = {
  base: {
    displayNameLabel: "Display Name",
    descriptionLabel: "Description",
    dialogDescription: "Configure command settings and schedule",
  },
  schedule: {
    overrideLabel: "Override default schedule",
    cronPlaceholder: "0 3 * * *",
    cronHelp:
      "Cron format: minute hour day month weekday (e.g. 0 3 * * * = 3 AM daily)",
    usesGlobalDefault: "Uses global default (Config → Scheduler)",
  },
  lastRun: { label: "Last Run" },
  lastStatus: { label: "Last Status", success: "Success", failed: "Failed" },
  playlistSync: {
    playlistUrlLabel: "Playlist URL",
    artistDiscovery: {
      checkboxLabel: "Add new artists",
      helper:
        "Artists discovered missing from Lidarr are added to the Playlist Sync Discovery import list. Discovery always runs to report counts; this controls whether to add.",
      maxLabel: "Max artists to add per run",
      maxHelper: "0 = no limit. First run adds none—only reports count.",
    },
  },
  xmplaylist: {
    sourceLockedHint: "Source mode is fixed after creation.",
    targetReadOnlyLabel: "Target",
    targetReadOnlyHelp: "Create a new command to change Plex or Jellyfin.",
  },
  topTracks: {
    targetReadOnlyHelp: "Create a new command to change Plex or Jellyfin.",
  },
} as const;
