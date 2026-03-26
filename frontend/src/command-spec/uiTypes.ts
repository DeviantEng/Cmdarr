import type { CommandEditSectionId } from "./editSectionIds";

/**
 * Mode for resolving which compound UI blocks appear (create wizard vs edit dialog).
 * @see getFieldsForContext — runtime resolver; TSDoc here is the product-facing overview.
 */
export type CommandUIMode = "create" | "edit";

/**
 * Context passed to field visibility/editability predicates.
 * Keep this serializable-friendly (plain data from CommandConfig or create wizard state).
 */
export type ResolveContext = {
  mode: CommandUIMode;
  commandName?: string;
  configJson?: Record<string, unknown> | null;
  /** Create wizard: `PlaylistType` from CreatePlaylistSyncDialog */
  playlistType?: string;
  target?: string;
  source?: string;
};

/**
 * Shared widget kinds for compound blocks used on both create and edit surfaces.
 * Add kinds as more slices migrate into the spec.
 */
export type CompoundWidgetKind = "artist_discovery" | "plex_playlist_target";

/**
 * Declarative compound field: visibility/editability are pure functions of ResolveContext.
 */
export type CompoundFieldDef = {
  id: string;
  widget: CompoundWidgetKind;
  /** Links to edit dialog section id when applicable (docs / tooling). */
  editSectionId?: CommandEditSectionId;
  visible: (ctx: ResolveContext) => boolean;
  editable: (ctx: ResolveContext) => boolean;
};
