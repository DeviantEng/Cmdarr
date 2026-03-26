import { usesCommonCreateSettings } from "../createPlaylistSurface";
import type { CompoundFieldDef, ResolveContext } from "../uiTypes";

function isPlaylistSyncEdit(name?: string): boolean {
  return !!name?.startsWith("playlist_sync_");
}

function isXmplaylistEdit(name?: string): boolean {
  return !!name?.startsWith("xmplaylist_");
}

/**
 * Compound fields shared across playlist_sync and xmplaylist create/edit surfaces.
 * Order is stable for tests and optional future generic renderers.
 */
export const COMPOUND_FIELDS: CompoundFieldDef[] = [
  {
    id: "compound.artist_discovery",
    widget: "artist_discovery",
    editSectionId: "playlist_sync_artist_discovery",
    visible(ctx: ResolveContext) {
      if (ctx.mode === "edit") {
        return isPlaylistSyncEdit(ctx.commandName) || isXmplaylistEdit(ctx.commandName);
      }
      if (ctx.playlistType === "xmplaylist") return true;
      if (!ctx.playlistType) return false;
      return (
        usesCommonCreateSettings(ctx.playlistType) &&
        (ctx.playlistType === "other" || ctx.playlistType === "listenbrainz")
      );
    },
    editable() {
      return true;
    },
  },
  {
    id: "compound.plex_playlist_target",
    widget: "plex_playlist_target",
    editSectionId: "playlist_sync_plex_target",
    visible(ctx: ResolveContext) {
      if (ctx.target !== "plex") return false;
      if (ctx.mode === "edit") {
        if (isXmplaylistEdit(ctx.commandName)) return true;
        const cfg = ctx.configJson || {};
        return (
          isPlaylistSyncEdit(ctx.commandName) &&
          cfg.playlist_url != null &&
          (cfg.source as string) !== "listenbrainz"
        );
      }
      if (ctx.playlistType === "xmplaylist") return true;
      return ctx.playlistType === "other";
    },
    editable() {
      return true;
    },
  },
];
