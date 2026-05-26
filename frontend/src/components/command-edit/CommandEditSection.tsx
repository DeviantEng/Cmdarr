import type { CommandEditSectionId } from "@/command-spec";
import type { CommandEditRenderContext } from "./types";
import { BaseMetaSection } from "./sections/BaseMetaSection";
import { PlaylistSyncUrlSection } from "./sections/PlaylistSyncUrlSection";
import { PlaylistSyncArtistSection } from "./sections/PlaylistSyncArtistSection";
import { PlaylistSyncPlexTargetSection } from "./sections/PlaylistSyncPlexTargetSection";
import { PlaylistSyncListenbrainzSection } from "./sections/PlaylistSyncListenbrainzSection";
import { DaylistSection } from "./sections/DaylistSection";
import { DiscoveryLastfmSection } from "./sections/DiscoveryLastfmSection";
import { MoodPlaylistSection } from "./sections/MoodPlaylistSection";
import { LocalDiscoverySection } from "./sections/LocalDiscoverySection";
import { TopTracksSection } from "./sections/TopTracksSection";
import { LfmSimilarSection } from "./sections/LfmSimilarSection";
import { SetlistFmSection } from "./sections/SetlistFmSection";
import { XmplaylistSection } from "./sections/XmplaylistSection";
import { ScheduleSection } from "./sections/ScheduleSection";
import { ExpirationSection } from "./sections/ExpirationSection";
import { NewReleasesDiscoverySection } from "./sections/NewReleasesDiscoverySection";
import { ArtistEventsRefreshSection } from "./sections/ArtistEventsRefreshSection";
import { LastRunSection } from "./sections/LastRunSection";
import { LastStatusSection } from "./sections/LastStatusSection";

export function CommandEditSection({
  sectionId,
  ctx,
}: {
  sectionId: CommandEditSectionId;
  ctx: CommandEditRenderContext;
}) {
  switch (sectionId) {
    case "base_meta":
      return <BaseMetaSection ctx={ctx} />;
    case "playlist_sync_url":
      return <PlaylistSyncUrlSection ctx={ctx} />;
    case "playlist_sync_artist_discovery":
      return <PlaylistSyncArtistSection ctx={ctx} />;
    case "playlist_sync_plex_target":
      return <PlaylistSyncPlexTargetSection ctx={ctx} />;
    case "playlist_sync_listenbrainz":
      return <PlaylistSyncListenbrainzSection ctx={ctx} />;
    case "daylist":
      return <DaylistSection ctx={ctx} />;
    case "discovery_lastfm":
      return <DiscoveryLastfmSection ctx={ctx} />;
    case "mood_playlist":
      return <MoodPlaylistSection ctx={ctx} />;
    case "local_discovery":
      return <LocalDiscoverySection ctx={ctx} />;
    case "top_tracks":
      return <TopTracksSection ctx={ctx} />;
    case "lfm_similar":
      return <LfmSimilarSection ctx={ctx} />;
    case "setlist_fm":
      return <SetlistFmSection ctx={ctx} />;
    case "xmplaylist":
      return <XmplaylistSection ctx={ctx} />;
    case "schedule":
      return <ScheduleSection ctx={ctx} />;
    case "expiration":
      return <ExpirationSection ctx={ctx} />;
    case "new_releases_discovery":
      return <NewReleasesDiscoverySection ctx={ctx} />;
    case "artist_events_refresh":
      return <ArtistEventsRefreshSection ctx={ctx} />;
    case "last_run":
      return <LastRunSection ctx={ctx} />;
    case "last_status":
      return <LastStatusSection ctx={ctx} />;
  }
}
