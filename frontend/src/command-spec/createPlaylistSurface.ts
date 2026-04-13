/**
 * Create-wizard surfaces that use the shared "Common Settings" block in
 * CreatePlaylistSyncDialog (Target, Plex users, sync mode, schedule, artist discovery, expiry).
 * Types with dedicated forms above the fold skip Common Settings — keep in sync with the dialog.
 */
export const PLAYLIST_TYPES_SKIP_COMMON_CREATE_SETTINGS = [
  "daylist",
  "top_tracks",
  "lfm_similar",
  "local_discovery",
  "mood_playlist",
  "xmplaylist",
] as const;

export type PlaylistTypeSkippingCommon =
  (typeof PLAYLIST_TYPES_SKIP_COMMON_CREATE_SETTINGS)[number];

export function usesCommonCreateSettings(playlistType: string): boolean {
  return !(PLAYLIST_TYPES_SKIP_COMMON_CREATE_SETTINGS as readonly string[]).includes(playlistType);
}
