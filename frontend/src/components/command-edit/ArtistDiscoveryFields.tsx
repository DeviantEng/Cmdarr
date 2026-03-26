import type { CommandEditFormState } from "./types";
import type { Dispatch, SetStateAction } from "react";
import { PlaylistSyncArtistDiscoveryControl } from "./PlaylistSyncArtistDiscoveryControl";

type Props = {
  editForm: CommandEditFormState;
  setEditForm: Dispatch<SetStateAction<CommandEditFormState>>;
  checkboxId?: string;
};

/** Edit-dialog wrapper: same UI as create (PlaylistSyncArtistDiscoveryControl). */
export function ArtistDiscoveryFields({
  editForm,
  setEditForm,
  checkboxId = "edit-artist-discovery-shared",
}: Props) {
  return (
    <PlaylistSyncArtistDiscoveryControl
      checkboxId={checkboxId}
      value={{
        enable_artist_discovery: editForm.enable_artist_discovery ?? false,
        artist_discovery_max_per_run: editForm.artist_discovery_max_per_run ?? 2,
      }}
      onChange={(next) =>
        setEditForm((f) => ({
          ...f,
          enable_artist_discovery: next.enable_artist_discovery,
          artist_discovery_max_per_run: next.artist_discovery_max_per_run,
        }))
      }
    />
  );
}
