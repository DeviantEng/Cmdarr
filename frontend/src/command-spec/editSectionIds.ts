import type { CommandConfig } from "@/lib/types";

/**
 * Ordered edit-dialog sections. Drives CommandEditScrollableBody rendering.
 */
export type CommandEditSectionId =
  | "base_meta"
  | "playlist_sync_url"
  | "playlist_sync_artist_discovery"
  | "playlist_sync_plex_target"
  | "playlist_sync_listenbrainz"
  | "daylist"
  | "discovery_lastfm"
  | "mood_playlist"
  | "local_discovery"
  | "top_tracks"
  | "lfm_similar"
  | "xmplaylist"
  | "schedule"
  | "expiration"
  | "new_releases_discovery"
  | "artist_events_refresh"
  | "last_run"
  | "last_status";

export function getCommandEditSectionOrder(cmd: CommandConfig): CommandEditSectionId[] {
  const name = cmd.command_name;
  const cfg = cmd.config_json || {};
  const base: CommandEditSectionId[] = ["base_meta"];

  if (name.startsWith("playlist_sync_")) {
    const out: CommandEditSectionId[] = [...base];
    if (cfg.playlist_url != null) out.push("playlist_sync_url");
    out.push("playlist_sync_artist_discovery");
    if (
      cfg.playlist_url != null &&
      (cfg.source as string) !== "listenbrainz" &&
      (cfg.target as string) === "plex"
    ) {
      out.push("playlist_sync_plex_target");
    }
    if ((cfg.source as string) === "listenbrainz") out.push("playlist_sync_listenbrainz");
    out.push("schedule", "expiration", "last_run", "last_status");
    return out;
  }

  if (name.startsWith("daylist_")) {
    return [...base, "daylist", "expiration", "last_run", "last_status"];
  }

  if (name === "discovery_lastfm") {
    return [...base, "discovery_lastfm", "schedule", "last_run", "last_status"];
  }

  if (name.startsWith("mood_playlist_")) {
    return [...base, "mood_playlist", "schedule", "expiration", "last_run", "last_status"];
  }

  if (name.startsWith("local_discovery_")) {
    return [...base, "local_discovery", "schedule", "expiration", "last_run", "last_status"];
  }

  if (name.startsWith("top_tracks_")) {
    return [...base, "top_tracks", "schedule", "expiration", "last_run", "last_status"];
  }

  if (name.startsWith("lfm_similar_")) {
    return [...base, "lfm_similar", "schedule", "expiration", "last_run", "last_status"];
  }

  if (name.startsWith("xmplaylist_")) {
    return [...base, "xmplaylist", "schedule", "expiration", "last_run", "last_status"];
  }

  if (name === "new_releases_discovery") {
    return [...base, "schedule", "new_releases_discovery", "last_run", "last_status"];
  }

  if (name === "artist_events_refresh") {
    return [...base, "schedule", "artist_events_refresh", "last_run", "last_status"];
  }

  return [...base, "schedule", "last_run", "last_status"];
}
