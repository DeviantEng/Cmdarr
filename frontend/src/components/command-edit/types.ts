import type { Dispatch, SetStateAction } from "react";
import type { CommandConfig } from "@/lib/types";

/** Edit dialog form state (all command types). */
export type CommandEditFormState = {
  schedule_override?: boolean;
  schedule_cron?: string;
  artists_per_run?: number;
  /** artist_events_refresh: days between per-artist fetches */
  refresh_ttl_days?: number;
  album_types?: string[];
  new_releases_source?: "spotify" | "deezer";
  artists_to_query?: number;
  similar_per_artist?: number;
  artist_cooldown_days?: number;
  limit?: number;
  min_match_score?: number;
  enable_artist_discovery?: boolean;
  artist_discovery_max_per_run?: number;
  schedule_minute?: number;
  plex_history_account_id?: string;
  exclude_played_days?: number;
  history_lookback_days?: number;
  max_tracks?: number;
  sonic_similar_limit?: number;
  sonic_similarity_limit?: number;
  sonic_similarity_distance?: number;
  historical_ratio?: number;
  timezone?: string;
  time_periods?: Record<string, { start: number; end: number }>;
  artists?: string;
  seed_artists?: string;
  similar_per_seed?: number;
  max_artists?: number;
  include_seeds?: boolean;
  top_x?: number;
  /** setlist.fm: cap tracks per artist block */
  max_tracks_per_artist?: number;
  /** setlist.fm: API pagination depth */
  max_setlist_pages?: number;
  source?: string;
  target?: string;
  use_custom_playlist_name?: boolean;
  custom_playlist_name?: string;
  moods?: string[];
  exclude_last_run?: boolean;
  limit_by_year?: boolean;
  min_year?: number;
  max_year?: number;
  lookback_days?: number;
  top_artists_count?: number;
  artist_pool_size?: number;
  expires_at_enabled?: boolean;
  expires_at?: string;
  expires_at_delete_playlist?: boolean;
  use_primary_mood?: boolean;
  weekly_exploration_keep?: number;
  weekly_jams_keep?: number;
  daily_jams_keep?: number;
  cleanup_enabled?: boolean;
  playlist_types?: string[];
  plex_account_ids?: string[];
  sync_to_multiple_plex_users?: boolean;
  xm_station_deeplink?: string;
  xm_station_display_name?: string;
  xm_playlist_kind?: "newest" | "most_heard";
  xm_most_heard_days?: number;
  plex_playlist_account_id?: string;
};

export type XmplaylistStationRow = {
  name: string;
  deeplink: string;
  number: number | null;
  label: string;
};

export type CommandEditRenderContext = {
  editingCommand: CommandConfig;
  editForm: CommandEditFormState;
  setEditForm: Dispatch<SetStateAction<CommandEditFormState>>;
  plexAccounts: { id: string; name: string }[];
  daylistUsedIds: Set<string>;
  localDiscoveryUsedIds: Set<string>;
  moodsList: string[];
  xmplaylistEditFilter: string;
  setXmplaylistEditFilter: (v: string) => void;
  xmplaylistEditLoading: boolean;
  filteredXmEditStations: XmplaylistStationRow[];
  nrdSources: { id: string; name: string; configured: boolean }[];
};
