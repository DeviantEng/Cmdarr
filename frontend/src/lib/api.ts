import type {
  ArtistEventsStats,
  CommandConfig,
  CommandExecution,
  CommandUpdateRequest,
  CommandExecutionRequest,
  ConfigSetting,
  ConfigUpdateRequest,
  ConnectivityTestResult,
  StatusInfo,
  NrdMetrics,
  NewReleasesResponse,
  PendingReleasesResponse,
  LidarrArtistSuggestion,
  ScanArtistUrlResponse,
  ImportListMetrics,
  LibraryCacheStatus,
} from "./types";

class ApiError extends Error {
  status?: number;
  details?: unknown;

  constructor(message: string, status?: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = "") {
    this.baseUrl = baseUrl;
  }

  // Public request method for custom API calls
  async request<T>(endpoint: string, options?: RequestInit & { timeout?: number }): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const { timeout: timeoutMs = 30_000, ...fetchOptions } = options ?? {};

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        signal: fetchOptions.signal ?? controller.signal,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...fetchOptions.headers,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData.detail;
        const detailMsg = Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ")
          : (detail ?? `HTTP ${response.status}: ${response.statusText}`);
        throw new ApiError(detailMsg, response.status, errorData);
      }

      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      if (error instanceof Error && error.name === "AbortError") {
        throw new ApiError(`Request timed out after ${timeoutMs / 1000}s`);
      }
      throw new ApiError(error instanceof Error ? error.message : "Network request failed");
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // Commands API
  async getCommands(): Promise<CommandConfig[]> {
    return await this.request<CommandConfig[]>("/api/commands/");
  }

  async getCommand(commandName: string): Promise<CommandConfig> {
    return await this.request<CommandConfig>(`/api/commands/${commandName}`);
  }

  async updateCommand(commandName: string, data: CommandUpdateRequest): Promise<CommandConfig> {
    return await this.request<CommandConfig>(`/api/commands/${commandName}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async executeCommand(
    commandName: string,
    data?: CommandExecutionRequest
  ): Promise<{ execution_id: string; message: string }> {
    return await this.request(`/api/commands/${commandName}/execute`, {
      method: "POST",
      body: JSON.stringify(data || { triggered_by: "api" }),
    });
  }

  async cancelCommand(commandName: string): Promise<{ message: string }> {
    return await this.request(`/api/commands/${commandName}/cancel`, {
      method: "POST",
    });
  }

  async deleteCommand(commandName: string): Promise<{ message: string }> {
    return await this.request(`/api/commands/${commandName}`, {
      method: "DELETE",
    });
  }

  async getCommandExecutions(commandName: string): Promise<CommandExecution[]> {
    return await this.request<CommandExecution[]>(`/api/commands/${commandName}/executions`);
  }

  async killExecution(executionId: number): Promise<{ message: string }> {
    return await this.request(`/api/commands/executions/${executionId}/kill`, {
      method: "POST",
    });
  }

  async deleteExecution(executionId: number): Promise<{ message: string }> {
    return await this.request(`/api/commands/executions/${executionId}`, {
      method: "DELETE",
    });
  }

  async cleanupExecutions(
    commandName?: string,
    keepCount?: number
  ): Promise<{ message: string; deleted_count?: number }> {
    const params = new URLSearchParams();
    if (commandName) params.set("command_name", commandName);
    if (keepCount !== undefined) params.set("keep_count", String(keepCount));
    const query = params.toString();
    return await this.request(`/api/commands/executions/cleanup${query ? `?${query}` : ""}`, {
      method: "POST",
    });
  }

  async getAllExecutions(limit = 50): Promise<CommandExecution[]> {
    const response = await this.request<{ executions: CommandExecution[] }>(
      `/api/status/executions/recent?limit=${limit}`
    );
    return response.executions;
  }

  // Configuration API
  async getAllConfig(): Promise<Record<string, unknown>> {
    const response = await this.request<{ settings: Record<string, unknown> }>("/api/config/");
    return response.settings;
  }

  async getConfigByCategory(category: string): Promise<Record<string, unknown>> {
    const response = await this.request<{
      category: string;
      settings: Record<string, unknown>;
    }>(`/api/config/category/${category}`);
    return response.settings;
  }

  async getConfigSetting(key: string): Promise<unknown> {
    const response = await this.request<{ key: string; value: unknown }>(`/api/config/${key}`);
    return response.value;
  }

  async getConfigDetails(key: string, options?: { reveal?: boolean }): Promise<ConfigSetting> {
    const params = options?.reveal ? "?reveal=true" : "";
    return await this.request<ConfigSetting>(`/api/config/details/${key}${params}`);
  }

  async updateConfigSetting(
    key: string,
    data: ConfigUpdateRequest
  ): Promise<{ key: string; value: unknown }> {
    return await this.request(`/api/config/${key}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async testConnectivity(): Promise<{
    results: ConnectivityTestResult[];
    overall_success: boolean;
  }> {
    return await this.request("/api/config/test-connectivity", {
      method: "POST",
    });
  }

  // Status API
  async getStatus(): Promise<{ system: StatusInfo; artist_events: ArtistEventsStats | null }> {
    const response = await this.request<{
      system: StatusInfo;
      artist_events?: ArtistEventsStats;
    }>("/api/status/raw");
    return { system: response.system, artist_events: response.artist_events ?? null };
  }

  async healthCheck(): Promise<{
    status: string;
    message: string;
    timestamp: string;
  }> {
    return await this.request("/health");
  }

  // Auth API
  async getAuthStatus(): Promise<{
    setup_required: boolean;
    authenticated: boolean;
    username: string | null;
  }> {
    return await this.request("/api/auth/status");
  }

  async setup(username: string, password: string): Promise<{ message: string; username: string }> {
    return this.request("/api/auth/setup", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  }

  async login(username: string, password: string): Promise<{ message: string; username: string }> {
    return this.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  }

  async logout(): Promise<{ message: string }> {
    return this.request("/api/auth/logout", { method: "POST" });
  }

  async generateApiKey(): Promise<{ api_key: string; message: string }> {
    return this.request("/api/auth/generate-api-key", { method: "POST" });
  }

  async getNrdMetrics(): Promise<NrdMetrics> {
    return await this.request("/api/status/nrd-metrics");
  }

  async getCacheStatus(): Promise<{
    plex: LibraryCacheStatus;
    jellyfin: LibraryCacheStatus;
  }> {
    return await this.request("/api/status/cache");
  }

  async refreshLibraryCache(
    target: "plex" | "jellyfin" | "all" = "all",
    forceRebuild = false
  ): Promise<{
    success: boolean;
    message?: string;
    error?: string;
  }> {
    return await this.request("/api/commands/library_cache_builder/refresh", {
      method: "POST",
      body: JSON.stringify({ target, force_rebuild: forceRebuild }),
    });
  }

  // New Releases API
  // Import Lists API
  async getImportListMetrics(): Promise<ImportListMetrics> {
    return await this.request<ImportListMetrics>("/import_lists/metrics");
  }

  async resetImportList(listId: "lastfm" | "playlistsync"): Promise<{ success: boolean }> {
    return this.request(`/import_lists/discovery_${listId}/reset`, { method: "POST" });
  }

  async getNewReleases(params?: {
    artist_limit?: number;
    album_types?: string[];
  }): Promise<NewReleasesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.artist_limit !== undefined)
      searchParams.set("artist_limit", String(params.artist_limit));
    if (params?.album_types?.length) searchParams.set("album_types", params.album_types.join(","));
    const query = searchParams.toString();
    return this.request<NewReleasesResponse>(`/api/new-releases${query ? `?${query}` : ""}`);
  }

  // New Releases - DB-backed (pending, dismiss, run-batch, scan-artist)
  async getPendingReleases(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<PendingReleasesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));
    const query = searchParams.toString();
    return this.request<PendingReleasesResponse>(
      `/api/new-releases/pending${query ? `?${query}` : ""}`
    );
  }

  async clearRelease(itemId: number): Promise<{ success: boolean }> {
    return this.request(`/api/new-releases/clear/${itemId}`, { method: "POST" });
  }

  async clearAllPendingReleases(): Promise<{ success: boolean; cleared?: number }> {
    return this.request(`/api/new-releases/clear-all`, { method: "POST" });
  }

  async ignoreRelease(itemId: number): Promise<{ success: boolean }> {
    return this.request(`/api/new-releases/ignore/${itemId}`, { method: "POST" });
  }

  async recheckRelease(itemId: number): Promise<{ success: boolean; removed?: boolean }> {
    return this.request(`/api/new-releases/recheck/${itemId}`, { method: "POST" });
  }

  /** @deprecated Use clearRelease or ignoreRelease */
  async dismissRelease(itemId: number): Promise<{ success: boolean }> {
    return this.request(`/api/new-releases/dismiss/${itemId}`, { method: "POST" });
  }

  async getDismissedReleases(params?: { limit?: number; offset?: number }): Promise<{
    success: boolean;
    total: number;
    items: {
      id: number;
      artist_mbid: string;
      artist_name: string;
      album_title: string;
      release_date?: string;
      dismissed_at?: string;
    }[];
  }> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    const query = searchParams.toString();
    return this.request(`/api/new-releases/dismissed${query ? `?${query}` : ""}`);
  }

  async restoreDismissed(dismissedId: number): Promise<{ success: boolean }> {
    return this.request(`/api/new-releases/restore/${dismissedId}`, { method: "POST" });
  }

  async restoreAllDismissed(): Promise<{
    success: boolean;
    message?: string;
    restored_count?: number;
  }> {
    return this.request(`/api/new-releases/restore-all`, { method: "POST" });
  }

  async resetNrdScanHistory(): Promise<{
    success: boolean;
    message?: string;
    deleted_count?: number;
  }> {
    return this.request(`/api/new-releases/reset-scan-history`, { method: "POST" });
  }

  async getNewReleasesCommandStatus(): Promise<{
    enabled: boolean;
    config_json?: Record<string, unknown> | null;
    schedule_hours?: number | null;
  }> {
    return this.request(`/api/new-releases/command-status`);
  }

  async runBatch(): Promise<{ success: boolean; execution_id?: string }> {
    return this.request(`/api/new-releases/run-batch`, { method: "POST" });
  }

  async scanArtist(params: {
    artist_mbid?: string;
    artist_name?: string;
    album_types?: string[];
  }): Promise<{
    success: boolean;
    execution_id?: string;
    artist_name?: string;
  }> {
    return this.request(`/api/new-releases/scan-artist`, {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getLidarrArtists(
    q: string,
    limit = 20
  ): Promise<{
    success: boolean;
    artists: LidarrArtistSuggestion[];
  }> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.request(`/api/new-releases/lidarr-artists?${params}`);
  }

  async syncLidarrArtists(): Promise<{ success: boolean; synced?: number; updated?: number }> {
    return this.request(`/api/new-releases/sync-lidarr-artists`, { method: "POST" });
  }

  // Artist events (live shows, festivals, etc.)
  async getEventsProviderStatus(): Promise<{
    success: boolean;
    bandsintown: { enabled: boolean; configured: boolean };
    songkick: { enabled: boolean; configured: boolean };
    ticketmaster: { enabled: boolean; configured: boolean };
    any_ready: boolean;
  }> {
    return this.request("/api/events/provider-status");
  }

  async getEventsSettings(): Promise<{
    success: boolean;
    bandsintown_enabled: boolean;
    songkick_enabled: boolean;
    ticketmaster_enabled: boolean;
    user_lat: string;
    user_lon: string;
    user_label: string;
    radius_miles: number;
  }> {
    return this.request("/api/events/settings");
  }

  async geocodeEventsLocation(query: string): Promise<{
    success: boolean;
    lat: number;
    lon: number;
    label: string;
  }> {
    return this.request("/api/events/geocode", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  }

  async getUpcomingEvents(params?: {
    max_miles?: number;
    include_hidden?: boolean;
    interested_only?: boolean;
    limit?: number;
  }): Promise<{
    success: boolean;
    events: {
      id: number;
      artist_mbid: string;
      artist_name: string;
      venue_name: string | null;
      venue_city: string | null;
      venue_region: string | null;
      venue_country: string | null;
      venue_lat: number | null;
      venue_lon: number | null;
      starts_at_utc: string | null;
      local_date: string;
      sources: string[];
      source_links: { provider: string; url: string | null }[];
      interested: boolean;
      distance_miles: number | null;
      last_fm_events_url: string;
    }[];
    user_location: {
      lat: number | null;
      lon: number | null;
      label: string;
      radius_miles: number;
    };
  }> {
    const searchParams = new URLSearchParams();
    if (params?.max_miles !== undefined) searchParams.set("max_miles", String(params.max_miles));
    if (params?.include_hidden) searchParams.set("include_hidden", "true");
    if (params?.interested_only) searchParams.set("interested_only", "true");
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    const q = searchParams.toString();
    return this.request(`/api/events/upcoming${q ? `?${q}` : ""}`);
  }

  async getHiddenEventArtists(): Promise<{
    success: boolean;
    items: { artist_mbid: string; artist_name: string; hidden_at: string | null }[];
  }> {
    return this.request("/api/events/hidden");
  }

  async hideEventArtist(artist_mbid: string, artist_name?: string): Promise<{ success: boolean }> {
    return this.request("/api/events/hide", {
      method: "POST",
      body: JSON.stringify({ artist_mbid, artist_name }),
    });
  }

  async unhideEventArtist(artist_mbid: string): Promise<{ success: boolean }> {
    const enc = encodeURIComponent(artist_mbid);
    return this.request(`/api/events/unhide/${enc}`, { method: "POST" });
  }

  async unhideAllEventArtists(): Promise<{ success: boolean; removed?: number }> {
    return this.request("/api/events/unhide-all", { method: "POST" });
  }

  async getHiddenEvents(): Promise<{
    success: boolean;
    items: {
      event_id: number;
      artist_mbid: string;
      artist_name: string;
      venue_name: string | null;
      venue_city: string | null;
      local_date: string;
      hidden_at: string | null;
    }[];
  }> {
    return this.request("/api/events/hidden-events");
  }

  async hideEventRow(eventId: number): Promise<{ success: boolean }> {
    return this.request("/api/events/hide-event", {
      method: "POST",
      body: JSON.stringify({ event_id: eventId }),
    });
  }

  async unhideEventRow(eventId: number): Promise<{ success: boolean }> {
    return this.request(`/api/events/unhide-event/${eventId}`, { method: "POST" });
  }

  async unhideAllHiddenEvents(): Promise<{ success: boolean; removed?: number }> {
    return this.request("/api/events/unhide-all-events", { method: "POST" });
  }

  async setEventInterested(
    eventId: number,
    interested: boolean
  ): Promise<{ success: boolean; interested: boolean }> {
    return this.request(`/api/events/${eventId}/interested`, {
      method: "PATCH",
      body: JSON.stringify({ interested }),
    });
  }

  async invalidateArtistEventsCache(): Promise<{
    success: boolean;
    deleted_event_rows: number;
    reset_refresh_rows: number;
  }> {
    return this.request("/api/events/invalidate-cache", { method: "POST" });
  }

  async scanArtistUrl(params: {
    url: string;
    album_types?: string[];
  }): Promise<ScanArtistUrlResponse> {
    return this.request(`/api/new-releases/scan-artist-url`, {
      method: "POST",
      body: JSON.stringify(params),
    });
  }
}

// Export singleton instance
export const api = new ApiClient();

// Export class for testing
export { ApiClient, ApiError };
