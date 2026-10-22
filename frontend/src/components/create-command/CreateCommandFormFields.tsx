import type { CreateCommandWizard } from "./useCreateCommandWizard";
import { usesCommonCreateSettings } from "@/command-spec";
import { CommonCreateSettings } from "./sections/CommonCreateSettings";
import { DaylistCreateSection } from "./sections/DaylistCreateSection";
import { ExternalPlaylistCreateSection } from "./sections/ExternalPlaylistCreateSection";
import { LfmSimilarCreateSection } from "./sections/LfmSimilarCreateSection";
import { LidarrUpdateAllCreateSection } from "./sections/LidarrUpdateAllCreateSection";
import { LidarrWantedSearchCreateSection } from "./sections/LidarrWantedSearchCreateSection";
import { ListenbrainzCreateSection } from "./sections/ListenbrainzCreateSection";
import { LocalDiscoveryCreateSection } from "./sections/LocalDiscoveryCreateSection";
import { MoodPlaylistCreateSection } from "./sections/MoodPlaylistCreateSection";
import { SetlistFmCreateSection } from "./sections/SetlistFmCreateSection";
import { TopTracksCreateSection } from "./sections/TopTracksCreateSection";
import { XmplaylistCreateSection } from "./sections/XmplaylistCreateSection";

export function CreateCommandFormFields({ wizard }: { wizard: CreateCommandWizard }) {
  const { embedded, playlistType } = wizard;
  return (
    <div className={embedded ? "arr-panel-body space-y-4 px-4 py-4" : "space-y-4 py-4"}>
      {playlistType === "listenbrainz" ? (
        <ListenbrainzCreateSection wizard={wizard} />
      ) : playlistType === "daylist" ? (
        <DaylistCreateSection wizard={wizard} />
      ) : playlistType === "local_discovery" ? (
        <LocalDiscoveryCreateSection wizard={wizard} />
      ) : playlistType === "top_tracks" ? (
        <TopTracksCreateSection wizard={wizard} />
      ) : playlistType === "lfm_similar" ? (
        <LfmSimilarCreateSection wizard={wizard} />
      ) : playlistType === "setlistfm" ? (
        <SetlistFmCreateSection wizard={wizard} />
      ) : playlistType === "mood_playlist" ? (
        <MoodPlaylistCreateSection wizard={wizard} />
      ) : playlistType === "xmplaylist" ? (
        <XmplaylistCreateSection wizard={wizard} />
      ) : playlistType === "lidarr_update_all" ? (
        <LidarrUpdateAllCreateSection wizard={wizard} />
      ) : playlistType === "lidarr_wanted_search" ? (
        <LidarrWantedSearchCreateSection wizard={wizard} />
      ) : (
        <ExternalPlaylistCreateSection wizard={wizard} />
      )}
      {usesCommonCreateSettings(playlistType) ? <CommonCreateSettings wizard={wizard} /> : null}
    </div>
  );
}
