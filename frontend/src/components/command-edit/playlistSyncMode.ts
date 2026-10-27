import { commandUiCopy } from "@/command-spec";

/** Stored `additive` is the older append alias. Anything else is a full replace. */
export function playlistSyncModeFromConfig(mode: unknown): "full" | "append" {
  const value = String(mode ?? "")
    .trim()
    .toLowerCase();
  return value === "append" || value === "additive" ? "append" : "full";
}

export function playlistSyncModeLabel(mode: unknown): string {
  const ps = commandUiCopy.playlistSync;
  return playlistSyncModeFromConfig(mode) === "append" ? ps.syncModeAppend : ps.syncModeFull;
}
