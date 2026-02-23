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
  execution_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'timeout' | 'cancelled'
  triggered_by: string
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  result_summary?: Record<string, any>
  error_message?: string
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

