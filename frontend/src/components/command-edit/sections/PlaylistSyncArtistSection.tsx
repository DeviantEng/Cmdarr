import type { CommandEditRenderContext } from "../types";
import { ArtistDiscoveryFields } from "../ArtistDiscoveryFields";

export function PlaylistSyncArtistSection({ ctx }: { ctx: CommandEditRenderContext }) {
  return (
    <ArtistDiscoveryFields
      editForm={ctx.editForm}
      setEditForm={ctx.setEditForm}
      checkboxId="edit-enable-artist-discovery"
    />
  );
}
