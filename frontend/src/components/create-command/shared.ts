import { cn } from "@/lib/utils";
import { commandUiCopy } from "@/command-spec";

export type PlaylistType =
  | "listenbrainz"
  | "other"
  | "daylist"
  | "top_tracks"
  | "lfm_similar"
  | "setlistfm"
  | "local_discovery"
  | "mood_playlist"
  | "xmplaylist"
  | "lidarr_update_all"
  | "lidarr_wanted_search";

export type XmplaylistStationRow = {
  name: string;
  deeplink: string;
  number: number | null;
  label: string;
};

export const cw = commandUiCopy.createWizard;
export const d = commandUiCopy.daylist;
export const ld = commandUiCopy.localDiscovery;
export const tt = commandUiCopy.topTracks;
export const lf = commandUiCopy.lfmSimilar;
export const sf = commandUiCopy.setlistFm;
export const mood = commandUiCopy.moodPlaylist;
export const xm = commandUiCopy.xmplaylist;
export const lb = commandUiCopy.listenbrainz;
export const ps = commandUiCopy.playlistSync;

export const DEFAULT_DAYLIST_TIME_PERIODS: Record<string, { start: number; end: number }> = {
  Dawn: { start: 3, end: 5 },
  "Early Morning": { start: 6, end: 8 },
  Morning: { start: 9, end: 11 },
  Afternoon: { start: 12, end: 15 },
  Evening: { start: 16, end: 18 },
  Night: { start: 19, end: 21 },
  "Late Night": { start: 22, end: 2 },
};

export function hoursFromRange(start: number, end: number): number[] {
  if (end >= start) return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  return [
    ...Array.from({ length: 24 - start }, (_, i) => start + i),
    ...Array.from({ length: end + 1 }, (_, i) => i),
  ];
}

export interface CreatePlaylistSyncDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
  /** Render inline on a page instead of a portaled modal. */
  embedded?: boolean;
}

export function typePickerIconClass(embedded: boolean, palette: string) {
  return cn(
    embedded
      ? "arr-create-type-icon"
      : "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
    palette
  );
}

export interface PlaylistValidation {
  isValidating: boolean;
  isValid: boolean;
  error: string;
  metadata: {
    name?: string;
    description?: string;
    track_count?: number;
    source?: string;
  } | null;
}
