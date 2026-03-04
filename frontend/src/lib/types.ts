// API Types based on FastAPI backend models

export interface CommandConfig {
  id: number;
  command_name: string;
  display_name: string;
  description?: string;
  enabled: boolean;
  schedule_cron?: string | null;
  schedule_override?: boolean;
  timeout_minutes?: number;
  config_json?: Record<string, unknown>;
  command_type?: string;
  last_run?: string;
  last_success?: boolean;
  last_duration?: number;
  last_error?: string;
  next_run?: string;
  created_at: string;
  updated_at: string;
}

export interface CommandExecution {
  id: number;
  command_name: string;
  status: "pending" | "running" | "completed" | "failed" | "timeout" | "cancelled";
  triggered_by: string;
  started_at?: string;
  completed_at?: string;
  duration?: number;
  duration_seconds?: number;
  result_summary?: Record<string, unknown>;
  output_summary?: string;
  error_message?: string;
  is_running?: boolean;
  target?: string;
}

export interface ImportListMetrics {
  lastfm: ImportListMetric;
  unified: ImportListMetric;
  timestamp?: string;
}

export interface ImportListMetric {
  exists: boolean;
  entry_count: number;
  file_size: number;
  age_human: string;
  status: string;
}

export interface CommandUpdateRequest {
  enabled?: boolean;
  schedule_cron?: string;
  schedule_override?: boolean;
  timeout_minutes?: number;
  config_json?: Record<string, unknown>;
}

export interface CommandExecutionRequest {
  triggered_by?: string;
}

export interface ConfigSetting {
  key: string;
  value: unknown;
  default_value: string;
  data_type: string;
  category: string;
  description: string;
  is_sensitive: boolean;
  is_required: boolean;
  effective_value: unknown;
  options?: string[];
}

export interface ConfigUpdateRequest {
  value: unknown;
  data_type?: string;
  options?: string[];
}

export interface ConnectivityTestResult {
  service: string;
  status: "success" | "warning" | "error";
  success: boolean;
  message: string;
  error?: string;
}

export interface StatusInfo {
  app_name: string;
  version: string;
  runtime_mode?: string;
  docker_image_tag?: string | null;
  uptime_seconds: number;
  database_status: string;
  configuration_status: string;
  timestamp: string;
  execution_stats?: {
    total_execution_count: number;
    total_success_count: number;
    total_failure_count: number;
  };
}

export interface ApiResponse<T = unknown> {
  data?: T;
  error?: string;
  message?: string;
}

// New Releases feature
export interface NewReleaseAlbum {
  name: string;
  release_date: string;
  album_type: string;
  total_tracks?: number;
  spotify_url: string;
  harmony_url: string;
}

export interface NewReleaseArtist {
  artist_name: string;
  lidarr_mbid: string;
  spotify_artist_id: string;
  lidarr_artist_url?: string | null;
  albums: NewReleaseAlbum[];
}

export interface NewReleasesResponse {
  success: boolean;
  album_types: string[];
  artists_checked: number;
  artists_with_releases: number;
  total_lidarr_artists: number;
  skipped_in_musicbrainz?: number;
  skipped_by_type?: number;
  skipped_live?: number;
  results: NewReleaseArtist[];
}

// DB-backed pending items (flat, one per album)
export interface NewReleasePendingItem {
  id: number;
  artist_mbid: string;
  artist_name: string;
  spotify_artist_id?: string | null;
  album_title: string;
  album_type?: string | null;
  release_date?: string | null;
  total_tracks?: number | null;
  spotify_url?: string | null;
  harmony_url?: string | null;
  lidarr_artist_id?: number | null;
  lidarr_artist_url?: string | null;
  musicbrainz_artist_url?: string | null;
  added_at?: string | null;
  source: string;
  status: string;
}

export interface PendingReleasesResponse {
  success: boolean;
  total: number;
  limit: number;
  offset: number;
  items: NewReleasePendingItem[];
}

export interface ScanArtistUrlAlbum {
  name: string;
  release_date: string;
  album_type: string;
  total_tracks?: number;
  album_url: string;
  harmony_url: string;
}

export interface ScanArtistUrlResponse {
  success: boolean;
  artist_name: string;
  artist_in_mb: boolean;
  musicbrainz_artist_url?: string | null;
  total_albums: number;
  missing_count: number;
  albums: ScanArtistUrlAlbum[];
}

export interface LidarrArtistSuggestion {
  artist_mbid: string;
  artist_name: string;
  lidarr_id?: number | null;
  spotify_artist_id?: string | null;
}

export interface LibraryCacheStatus {
  target: string;
  status: string;
  last_generated: number | null;
  size_mb: number;
  object_count: number;
  cache_hits?: number;
  cache_misses?: number;
  hit_rate?: number;
  last_used?: number | null;
  memory_usage_mb?: number;
  message?: string;
  error?: string;
}
