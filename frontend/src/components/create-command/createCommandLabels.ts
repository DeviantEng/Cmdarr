import type { PlaylistType } from "./shared";
import { cw } from "./shared";

export function createCommandTitle(step: "type" | "form", playlistType: PlaylistType): string {
  if (step === "type") return cw.titleChooseType;
  switch (playlistType) {
    case "daylist":
      return cw.titleDaylist;
    case "top_tracks":
      return cw.titleArtistEssentials;
    case "lfm_similar":
      return cw.titleLfmSimilar;
    case "setlistfm":
      return cw.titleSetlistFm;
    case "local_discovery":
      return cw.titleLocalDiscovery;
    case "mood_playlist":
      return cw.titleMoodPlaylist;
    case "xmplaylist":
      return cw.titleXmplaylist;
    case "lidarr_update_all":
      return cw.titleLidarrUpdateAll;
    case "lidarr_wanted_search":
      return cw.titleLidarrWantedSearch;
    case "listenbrainz":
      return cw.titleListenbrainz;
    default:
      return cw.titleExternal;
  }
}

export function createCommandDescription(
  step: "type" | "form",
  playlistType: PlaylistType
): string {
  if (step === "type") return cw.descChooseType;
  switch (playlistType) {
    case "daylist":
      return cw.descDaylist;
    case "top_tracks":
      return cw.descTopTracks;
    case "lfm_similar":
      return cw.descLfmSimilar;
    case "setlistfm":
      return cw.descSetlistFm;
    case "local_discovery":
      return cw.descLocalDiscovery;
    case "mood_playlist":
      return cw.descMoodPlaylist;
    case "xmplaylist":
      return cw.descXmplaylist;
    case "lidarr_update_all":
      return cw.descLidarrUpdateAll;
    case "lidarr_wanted_search":
      return cw.descLidarrWantedSearch;
    default:
      return cw.descDefault;
  }
}

export function createCommandSubmitLabel(playlistType: PlaylistType): string {
  switch (playlistType) {
    case "daylist":
      return cw.submitDaylist;
    case "top_tracks":
      return cw.submitArtistEssentials;
    case "lfm_similar":
      return cw.submitLfmSimilar;
    case "setlistfm":
      return cw.submitSetlistFm;
    case "local_discovery":
      return cw.submitLocalDiscovery;
    case "xmplaylist":
      return cw.submitXmplaylist;
    case "mood_playlist":
      return cw.submitMoodPlaylist;
    case "lidarr_update_all":
      return cw.submitLidarrUpdateAll;
    case "lidarr_wanted_search":
      return cw.submitLidarrWantedSearch;
    default:
      return cw.submitPlaylistSync;
  }
}
