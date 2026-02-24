// API Types based on FastAPI backend models

export interface CommandConfig {
  id: number
  command_name: string
  display_name: string
  description?: string
  enabled: boolean
  schedule_hours?: number
  timeout_minutes?: number
  config_json?: Record<string, any>
  command_type?: string
  last_run?: string
  last_success?: boolean
  last_duration?: number
  last_error?: string
  next_run?: string
  created_at: string
  updated_at: string
}

export interface CommandExecution {
  id: number
  command_name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'timeout' | 'cancelled'
  triggered_by: string
  started_at?: string
  completed_at?: string
  duration?: number
  duration_seconds?: number
  result_summary?: Record<string, any>
  output_summary?: string
  error_message?: string
  is_running?: boolean
  target?: string
}

export interface ImportListMetrics {
  lastfm: ImportListMetric
  unified: ImportListMetric
  timestamp?: string
}

export interface ImportListMetric {
  exists: boolean
  entry_count: number
  file_size: number
  age_human: string
  status: string
}

export interface CommandUpdateRequest {
  enabled?: boolean
  schedule_hours?: number
  timeout_minutes?: number
  config_json?: Record<string, any>
}

export interface CommandExecutionRequest {
  triggered_by?: string
}

export interface ConfigSetting {
  key: string
  value: any
  default_value: string
  data_type: string
  category: string
  description: string
  is_sensitive: boolean
  is_required: boolean
  effective_value: any
  options?: string[]
}

export interface ConfigUpdateRequest {
  value: any
  data_type?: string
  options?: string[]
}

export interface ConnectivityTestResult {
  service: string
  status: 'success' | 'warning' | 'error'
  success: boolean
  message: string
  error?: string
}

export interface StatusInfo {
  app_name: string
  version: string
  uptime_seconds: number
  database_status: string
  configuration_status: string
  timestamp: string
}

export interface ApiResponse<T = any> {
  data?: T
  error?: string
  message?: string
}

// New Releases feature
export interface NewReleaseAlbum {
  name: string
  release_date: string
  album_type: string
  total_tracks?: number
  spotify_url: string
  harmony_url: string
}

export interface NewReleaseArtist {
  artist_name: string
  lidarr_mbid: string
  spotify_artist_id: string
  lidarr_artist_url?: string | null
  albums: NewReleaseAlbum[]
}

export interface NewReleasesResponse {
  success: boolean
  album_types: string[]
  artists_checked: number
  artists_with_releases: number
  total_lidarr_artists: number
  skipped_in_musicbrainz?: number
  skipped_by_type?: number
  skipped_live?: number
  results: NewReleaseArtist[]
}

// DB-backed pending items (flat, one per album)
export interface NewReleasePendingItem {
  id: number
  artist_mbid: string
  artist_name: string
  spotify_artist_id?: string | null
  album_title: string
  album_type?: string | null
  release_date?: string | null
  total_tracks?: number | null
  spotify_url?: string | null
  harmony_url?: string | null
  lidarr_artist_id?: number | null
  lidarr_artist_url?: string | null
  musicbrainz_artist_url?: string | null
  added_at?: string | null
  source: string
  status: string
}

export interface PendingReleasesResponse {
  success: boolean
  total: number
  limit: number
  offset: number
  items: NewReleasePendingItem[]
}

export interface LidarrArtistSuggestion {
  artist_mbid: string
  artist_name: string
  lidarr_id?: number | null
  spotify_artist_id?: string | null
}

