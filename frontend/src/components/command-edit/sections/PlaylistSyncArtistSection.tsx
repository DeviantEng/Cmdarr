import { isCompoundFieldVisible, resolveContextForEditCommand } from "@/command-spec";
import { ArtistDiscoveryFields } from "../ArtistDiscoveryFields";
import type { CommandEditRenderContext } from "../types";

export function PlaylistSyncArtistSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const r = resolveContextForEditCommand(ctx.editingCommand);
  if (!isCompoundFieldVisible("compound.artist_discovery", r)) return null;

  return (
    <ArtistDiscoveryFields
      editForm={ctx.editForm}
      setEditForm={ctx.setEditForm}
      checkboxId="edit-enable-artist-discovery"
    />
  );
}
