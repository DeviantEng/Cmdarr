import { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, AlertCircle, Music, Globe, Sun, ListMusic, Compass } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  ExpirationFields,
  toExpiresAtIso,
} from "@/components/ExpirationFields";

type PlaylistType = "listenbrainz" | "other" | "daylist" | "top_tracks" | "local_discovery";

const DEFAULT_DAYLIST_TIME_PERIODS: Record<string, { start: number; end: number }> = {
  Dawn: { start: 3, end: 5 },
  "Early Morning": { start: 6, end: 8 },
  Morning: { start: 9, end: 11 },
  Afternoon: { start: 12, end: 15 },
  Evening: { start: 16, end: 18 },
  Night: { start: 19, end: 21 },
  "Late Night": { start: 22, end: 2 },
};

function hoursFromRange(start: number, end: number): number[] {
  if (end >= start) return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  return [
    ...Array.from({ length: 24 - start }, (_, i) => start + i),
    ...Array.from({ length: end + 1 }, (_, i) => i),
  ];
}

interface CreatePlaylistSyncDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

interface PlaylistValidation {
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

export function CreatePlaylistSyncDialog({
  open,
  onOpenChange,
  onSuccess,
}: CreatePlaylistSyncDialogProps) {
  const [step, setStep] = useState<"type" | "form">("type");
  const [playlistType, setPlaylistType] = useState<PlaylistType>("other");
  const [formData, setFormData] = useState({
    playlist_url: "",
    playlist_types: [] as string[],
    target: "plex",
    sync_mode: "full",
    enabled: true,
    weekly_exploration_keep: 3,
    weekly_jams_keep: 3,
    daily_jams_keep: 3,
    cleanup_enabled: true,
    enable_artist_discovery: false,
    expires_at_enabled: false,
    expires_at: "",
    expires_at_delete_playlist: true,
  });
  const [validation, setValidation] = useState<PlaylistValidation>({
    isValidating: false,
    isValid: false,
    error: "",
    metadata: null,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [daylistExists, setDaylistExists] = useState(false);
  const [localDiscoveryExists, setLocalDiscoveryExists] = useState(false);
  const [plexAccounts, setPlexAccounts] = useState<{ id: string; name: string }[]>([]);
  const [daylistForm, setDaylistForm] = useState({
    plex_history_account_id: "",
    schedule_minute: 0,
    enabled: true,
    exclude_played_days: 3,
    history_lookback_days: 45,
    max_tracks: 50,
    sonic_similar_limit: 10,
    sonic_similarity_limit: 50,
    sonic_similarity_distance: 0.8,
    historical_ratio: 0.4,
    timezone: "",
    time_periods: { ...DEFAULT_DAYLIST_TIME_PERIODS } as Record<
      string,
      { start: number; end: number }
    >,
    expires_at_enabled: false,
    expires_at: "",
    expires_at_delete_playlist: true,
    use_primary_mood: false,
  });

  const [localDiscoveryForm, setLocalDiscoveryForm] = useState({
    plex_history_account_id: "",
    lookback_days: 30,
    exclude_played_days: 3,
    top_artists_count: 10,
    artist_pool_size: 20,
    max_tracks: 50,
    sonic_similar_limit: 15,
    sonic_similarity_distance: 0.25,
    historical_ratio: 0.4,
    schedule_cron: "0 6 * * *",
    schedule_override: true,
    enabled: true,
    expires_at_enabled: false,
    expires_at: "",
  });

  const [topTracksForm, setTopTracksForm] = useState({
    artists: "",
    top_x: 5,
    source: "plex" as "plex" | "lastfm",
    target: "plex" as "plex" | "jellyfin",
    use_custom_playlist_name: false,
    custom_playlist_name: "",
    schedule_cron: "0 6 * * *",
    schedule_override: true,
    enabled: true,
    expires_at_enabled: false,
    expires_at: "",
    expires_at_delete_playlist: true,
  });

  // Fetch daylist exists, local discovery exists, and plex accounts when dialog opens
  useEffect(() => {
    if (!open) return;
    api
      .request<{ exists: boolean }>("/api/commands/daylist/exists")
      .then((r) => setDaylistExists(r.exists));
    api
      .request<{ exists: boolean }>("/api/commands/local-discovery/exists")
      .then((r) => setLocalDiscoveryExists(r.exists));
    api
      .request<{ accounts: { id: string; name: string }[] }>("/api/commands/plex-accounts")
      .then((r) => setPlexAccounts(r.accounts || []))
      .catch(() => setPlexAccounts([]));
  }, [open]);

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      setStep("type");
      setPlaylistType("other");
      setFormData({
        playlist_url: "",
        playlist_types: [],
        target: "plex",
        sync_mode: "full",
        enabled: true,
        weekly_exploration_keep: 3,
        weekly_jams_keep: 3,
        daily_jams_keep: 3,
        cleanup_enabled: true,
        enable_artist_discovery: false,
        expires_at_enabled: false,
        expires_at: "",
        expires_at_delete_playlist: true,
      });
      setDaylistForm({
        plex_history_account_id: "",
        schedule_minute: 0,
        enabled: true,
        exclude_played_days: 3,
        history_lookback_days: 45,
        max_tracks: 50,
        sonic_similar_limit: 10,
        sonic_similarity_limit: 50,
        sonic_similarity_distance: 0.8,
        historical_ratio: 0.4,
        timezone: "",
        time_periods: { ...DEFAULT_DAYLIST_TIME_PERIODS },
        expires_at_enabled: false,
        expires_at: "",
        expires_at_delete_playlist: true,
        use_primary_mood: false,
      });
      setValidation({
        isValidating: false,
        isValid: false,
        error: "",
        metadata: null,
      });
      setLocalDiscoveryForm({
        plex_history_account_id: "",
        lookback_days: 30,
        exclude_played_days: 3,
        top_artists_count: 10,
        artist_pool_size: 20,
        max_tracks: 50,
        sonic_similar_limit: 15,
        sonic_similarity_distance: 0.25,
        historical_ratio: 0.4,
        schedule_cron: "0 6 * * *",
        schedule_override: true,
        enabled: true,
        expires_at_enabled: false,
        expires_at: "",
      });
    }
  }, [open]);

  const validatePlaylistUrl = useCallback(async () => {
    if (!formData.playlist_url) return;

    setValidation((prev) => ({ ...prev, isValidating: true, error: "" }));

    try {
      const response = await api.request<{
        valid: boolean;
        error?: string;
        metadata?: unknown;
      }>(
        `/api/commands/playlist-sync/validate-url?url=${encodeURIComponent(formData.playlist_url)}`
      );

      setValidation({
        isValidating: false,
        isValid: response.valid,
        error: response.error || "",
        metadata: response.metadata || null,
      });
    } catch {
      setValidation({
        isValidating: false,
        isValid: false,
        error: "Failed to validate URL",
        metadata: null,
      });
    }
  }, [formData.playlist_url]);

  // Debounced URL validation
  useEffect(() => {
    if (playlistType !== "other" || !formData.playlist_url) {
      setValidation({
        isValidating: false,
        isValid: false,
        error: "",
        metadata: null,
      });
      return;
    }

    const timeoutId = setTimeout(() => {
      validatePlaylistUrl();
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [formData.playlist_url, playlistType, validatePlaylistUrl]);

  const handleSelectType = (type: PlaylistType) => {
    if (type === "daylist" && daylistExists) return;
    if (type === "local_discovery" && localDiscoveryExists) return;
    setPlaylistType(type);
    setStep("form");
    if (type === "listenbrainz") {
      setFormData((prev) => ({
        ...prev,
        playlist_types: ["weekly_exploration"],
      }));
    }
  };

  const handleTogglePlaylistType = (type: string) => {
    setFormData((prev) => ({
      ...prev,
      playlist_types: prev.playlist_types.includes(type)
        ? prev.playlist_types.filter((t) => t !== type)
        : [...prev.playlist_types, type],
    }));
  };

  const canSubmit = () => {
    if (playlistType === "listenbrainz") {
      if (formData.playlist_types.length === 0) return false;
      if (formData.expires_at_enabled && !formData.expires_at) return false;
      return true;
    }
    if (playlistType === "daylist") {
      if (!daylistForm.plex_history_account_id) return false;
      if (daylistForm.expires_at_enabled && !daylistForm.expires_at) return false;
      return true;
    }
    if (playlistType === "top_tracks") {
      if (topTracksForm.artists.trim().split("\n").filter((a) => a.trim()).length === 0)
        return false;
      if (topTracksForm.expires_at_enabled && !topTracksForm.expires_at) return false;
      return true;
    }
    if (playlistType === "local_discovery") {
      if (!localDiscoveryForm.plex_history_account_id) return false;
      if (localDiscoveryForm.expires_at_enabled && !localDiscoveryForm.expires_at) return false;
      return true;
    }
    if (!validation.isValid) return false;
    if (formData.expires_at_enabled && !formData.expires_at) return false;
    return true;
  };

  const handleSubmit = async () => {
    if (!canSubmit()) {
      toast.error("Please complete all required fields");
      return;
    }

    setIsSubmitting(true);

    try {
      if (playlistType === "top_tracks") {
        const payload: Record<string, unknown> = {
          artists: topTracksForm.artists.trim().split("\n").filter((a) => a.trim()),
          top_x: topTracksForm.top_x,
          source: topTracksForm.source,
          target: topTracksForm.target,
          use_custom_playlist_name: topTracksForm.use_custom_playlist_name,
          custom_playlist_name: topTracksForm.custom_playlist_name,
          schedule_cron: topTracksForm.schedule_override ? topTracksForm.schedule_cron : undefined,
          enabled: topTracksForm.enabled,
        };
        if (topTracksForm.expires_at_enabled && topTracksForm.expires_at) {
          payload.expires_at = toExpiresAtIso(topTracksForm.expires_at);
          payload.expires_at_delete_playlist = topTracksForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string; command_name: string }>(
          "/api/commands/top-tracks/create",
          { method: "POST", body: JSON.stringify(payload) }
        );
        toast.success(response.message || "Artist Essentials command created");
      } else if (playlistType === "daylist") {
        const time_periods: Record<string, number[]> = {};
        for (const [period, { start, end }] of Object.entries(daylistForm.time_periods)) {
          time_periods[period] = hoursFromRange(start, end);
        }
        const daylistPayload: Record<string, unknown> = {
          plex_history_account_id: daylistForm.plex_history_account_id,
          schedule_minute: daylistForm.schedule_minute,
          enabled: daylistForm.enabled,
          exclude_played_days: daylistForm.exclude_played_days,
          history_lookback_days: daylistForm.history_lookback_days,
          max_tracks: daylistForm.max_tracks,
          sonic_similar_limit: daylistForm.sonic_similar_limit,
          sonic_similarity_limit: daylistForm.sonic_similarity_limit,
          sonic_similarity_distance: daylistForm.sonic_similarity_distance,
          historical_ratio: daylistForm.historical_ratio,
          timezone: daylistForm.timezone || undefined,
          time_periods,
          use_primary_mood: daylistForm.use_primary_mood,
        };
        if (daylistForm.expires_at_enabled && daylistForm.expires_at) {
          daylistPayload.expires_at = toExpiresAtIso(daylistForm.expires_at);
          daylistPayload.expires_at_delete_playlist = daylistForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string }>("/api/commands/daylist/create", {
          method: "POST",
          body: JSON.stringify(daylistPayload),
        });
        toast.success(response.message || "Daylist command created successfully");
      } else if (playlistType === "local_discovery") {
        const payload: Record<string, unknown> = {
          plex_history_account_id: localDiscoveryForm.plex_history_account_id,
          lookback_days: localDiscoveryForm.lookback_days,
          exclude_played_days: localDiscoveryForm.exclude_played_days,
          top_artists_count: localDiscoveryForm.top_artists_count,
          artist_pool_size: localDiscoveryForm.artist_pool_size,
          max_tracks: localDiscoveryForm.max_tracks,
          sonic_similar_limit: localDiscoveryForm.sonic_similar_limit,
          sonic_similarity_distance: localDiscoveryForm.sonic_similarity_distance,
          historical_ratio: localDiscoveryForm.historical_ratio,
          schedule_cron: localDiscoveryForm.schedule_override ? localDiscoveryForm.schedule_cron : undefined,
          enabled: localDiscoveryForm.enabled,
        };
        if (localDiscoveryForm.expires_at_enabled && localDiscoveryForm.expires_at) {
          payload.expires_at = toExpiresAtIso(localDiscoveryForm.expires_at);
        }
        const response = await api.request<{ message: string }>(
          "/api/commands/local-discovery/create",
          { method: "POST", body: JSON.stringify(payload) }
        );
        toast.success(response.message || "Local Discovery command created");
      } else {
        const payload: Record<string, unknown> = {
          ...formData,
          playlist_type: playlistType,
        };
        if (formData.expires_at_enabled && formData.expires_at) {
          payload.expires_at = toExpiresAtIso(formData.expires_at);
          payload.expires_at_delete_playlist = formData.expires_at_delete_playlist ?? true;
        } else {
          delete payload.expires_at;
          delete payload.expires_at_delete_playlist;
        }
        const response = await api.request<{ message: string }>(
          "/api/commands/playlist-sync/create",
          {
            method: "POST",
            body: JSON.stringify(payload),
          }
        );
        toast.success(response.message || "Playlist sync command created successfully");
      }
      onSuccess();
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create command");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === "type"
              ? "Create New Command"
              : playlistType === "daylist"
                ? "Configure Daylist"
                : playlistType === "top_tracks"
                  ? "Configure Artist Essentials"
                  : playlistType === "local_discovery"
                    ? "Configure Local Discovery"
                    : `Configure ${playlistType === "listenbrainz" ? "ListenBrainz" : "External"} Playlist`}
          </DialogTitle>
          <DialogDescription>
            {step === "type"
              ? "Choose the type of command to create"
              : playlistType === "daylist"
                ? "Configure your daylist settings"
                : playlistType === "top_tracks"
                  ? "Artists must exist in your library. One artist per line."
                  : playlistType === "local_discovery"
                    ? "Top artists from play history + sonically similar tracks. Fresh each run."
                    : "Configure your playlist sync settings"}
          </DialogDescription>
        </DialogHeader>

        {step === "type" ? (
          <div className="grid gap-4 py-4">
            {/* ListenBrainz Option */}
            <button
              onClick={() => handleSelectType("listenbrainz")}
              className="flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900">
                <Music className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">ListenBrainz Curated</h3>
                <p className="text-sm text-muted-foreground">
                  Sync Weekly Exploration, Weekly Jams, or Daily Jams playlists
                </p>
              </div>
            </button>

            {/* External Playlist Option */}
            <button
              onClick={() => handleSelectType("other")}
              className="flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900">
                <Globe className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">External Playlist</h3>
                <p className="text-sm text-muted-foreground">
                  Sync public playlists from Spotify, Deezer, or other sources
                </p>
              </div>
            </button>

            {/* Daylist Option */}
            <button
              onClick={() => handleSelectType("daylist")}
              disabled={daylistExists}
              className={cn(
                "flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors",
                daylistExists
                  ? "cursor-not-allowed opacity-50"
                  : "hover:border-primary hover:bg-accent"
              )}
              title={daylistExists ? "Daylist command already exists" : undefined}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900">
                <Sun className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">Daylist</h3>
                <p className="text-sm text-muted-foreground">
                  Time-of-day playlists from Plex listening history and Sonic Analysis. Plex only.
                  Inspired by Meloday.
                </p>
              </div>
            </button>

            {/* Artist Essentials Option */}
            <button
              onClick={() => handleSelectType("top_tracks")}
              className="flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                <ListMusic className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">Artist Essentials</h3>
                <p className="text-sm text-muted-foreground">
                  Generate playlist from artist list with top X tracks per artist (Plex or Last.fm).
                </p>
              </div>
            </button>

            {/* Local Discovery Option */}
            <button
              onClick={() => handleSelectType("local_discovery")}
              disabled={localDiscoveryExists}
              className={cn(
                "flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors",
                localDiscoveryExists
                  ? "cursor-not-allowed opacity-50"
                  : "hover:border-primary hover:bg-accent"
              )}
              title={localDiscoveryExists ? "Local Discovery command already exists" : undefined}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-teal-100 dark:bg-teal-900">
                <Compass className="h-6 w-6 text-teal-600 dark:text-teal-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">Local Discovery</h3>
                <p className="text-sm text-muted-foreground">
                  Top artists from play history + sonically similar tracks. Fresh each run. Plex only.
                </p>
              </div>
            </button>
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {playlistType === "listenbrainz" ? (
              <>
                {/* Playlist Types */}
                <div className="space-y-2">
                  <Label>Playlist Types</Label>
                  <div className="space-y-2">
                    {["weekly_exploration", "weekly_jams", "daily_jams"].map((type) => (
                      <label key={type} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={formData.playlist_types.includes(type)}
                          onChange={() => handleTogglePlaylistType(type)}
                          className="rounded border-gray-300"
                        />
                        <span className="text-sm">
                          {type
                            .split("_")
                            .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                            .join(" ")}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Retention Settings */}
                <div className="space-y-2">
                  <Label>Retention Settings</Label>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <Label className="text-xs">Weekly Exploration</Label>
                      <Input
                        type="number"
                        min="1"
                        max="10"
                        value={formData.weekly_exploration_keep}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            weekly_exploration_keep: parseInt(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Weekly Jams</Label>
                      <Input
                        type="number"
                        min="1"
                        max="10"
                        value={formData.weekly_jams_keep}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            weekly_jams_keep: parseInt(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Daily Jams</Label>
                      <Input
                        type="number"
                        min="1"
                        max="10"
                        value={formData.daily_jams_keep}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            daily_jams_keep: parseInt(e.target.value),
                          }))
                        }
                      />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Number of playlists to keep for each type (older ones will be deleted)
                  </p>
                </div>

                {/* Cleanup Toggle */}
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.cleanup_enabled}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        cleanup_enabled: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable playlist cleanup (delete old playlists)</span>
                </label>
              </>
            ) : playlistType === "daylist" ? (
              <>
                {/* Primary settings */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Plex Account (play history source)</Label>
                    <Select
                      value={daylistForm.plex_history_account_id}
                      onValueChange={(v) =>
                        setDaylistForm((prev) => ({ ...prev, plex_history_account_id: v }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select Plex account" />
                      </SelectTrigger>
                      <SelectContent>
                        {plexAccounts.map((acc) => (
                          <SelectItem key={acc.id} value={acc.id}>
                            {acc.name || `Account ${acc.id}`}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Plex Home users only. Daylist uses this account&apos;s play history.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>Run at minute of hour (0–59)</Label>
                    <Input
                      type="number"
                      min={0}
                      max={59}
                      value={daylistForm.schedule_minute}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        setDaylistForm((prev) => ({ ...prev, schedule_minute: isNaN(v) ? 0 : v }));
                      }}
                      onBlur={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (!isNaN(v))
                          setDaylistForm((prev) => ({
                            ...prev,
                            schedule_minute: Math.max(0, Math.min(59, v)),
                          }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Daylist runs hourly at this minute. Runs only when the day period changes
                      (Dawn, Morning, etc.). Min: 0, max: 59.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Exclude played (days)</Label>
                      <Input
                        type="number"
                        min={1}
                        max={30}
                        value={daylistForm.exclude_played_days}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          setDaylistForm((prev) => ({
                            ...prev,
                            exclude_played_days: isNaN(v) ? 3 : v,
                          }));
                        }}
                        onBlur={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!isNaN(v))
                            setDaylistForm((prev) => ({
                              ...prev,
                              exclude_played_days: Math.max(1, Math.min(30, v)),
                            }));
                          else setDaylistForm((prev) => ({ ...prev, exclude_played_days: 3 }));
                        }}
                      />
                      <p className="text-xs text-muted-foreground">
                        Skip tracks played in last N days. Min: 1, max: 30.
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label>History lookback (days)</Label>
                      <Input
                        type="number"
                        min={7}
                        max={365}
                        value={daylistForm.history_lookback_days}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          setDaylistForm((prev) => ({
                            ...prev,
                            history_lookback_days: isNaN(v) ? 45 : v,
                          }));
                        }}
                        onBlur={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!isNaN(v))
                            setDaylistForm((prev) => ({
                              ...prev,
                              history_lookback_days: Math.max(7, Math.min(365, v)),
                            }));
                          else setDaylistForm((prev) => ({ ...prev, history_lookback_days: 45 }));
                        }}
                      />
                      <p className="text-xs text-muted-foreground">
                        Days of play history to analyze. Min: 7, max: 365.
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label>Max tracks</Label>
                      <Input
                        type="number"
                        min={10}
                        max={200}
                        value={daylistForm.max_tracks}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          setDaylistForm((prev) => ({ ...prev, max_tracks: isNaN(v) ? 50 : v }));
                        }}
                        onBlur={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!isNaN(v))
                            setDaylistForm((prev) => ({
                              ...prev,
                              max_tracks: Math.max(10, Math.min(200, v)),
                            }));
                          else setDaylistForm((prev) => ({ ...prev, max_tracks: 50 }));
                        }}
                      />
                      <p className="text-xs text-muted-foreground">
                        Target playlist size. Min: 10, max: 200.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Advanced settings (collapsible) */}
                <details className="rounded-lg border p-4">
                  <summary className="cursor-pointer font-medium text-sm text-muted-foreground hover:text-foreground transition-colors">
                    Advanced settings
                  </summary>
                  <div className="mt-4 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Historical ratio: {daylistForm.historical_ratio}</Label>
                        <input
                          type="range"
                          min={0.1}
                          max={0.8}
                          step={0.1}
                          value={daylistForm.historical_ratio}
                          onChange={(e) =>
                            setDaylistForm((prev) => ({
                              ...prev,
                              historical_ratio: parseFloat(e.target.value),
                            }))
                          }
                          className="slider-range"
                        />
                        <p className="text-xs text-muted-foreground">
                          Share of tracks from history. Min: 0.1, max: 0.8.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label>Sonically similar limit</Label>
                        <Input
                          type="number"
                          min={1}
                          max={30}
                          value={daylistForm.sonic_similar_limit}
                          onChange={(e) => {
                            const v = parseInt(e.target.value, 10);
                            setDaylistForm((prev) => ({
                              ...prev,
                              sonic_similar_limit: isNaN(v) ? 10 : v,
                            }));
                          }}
                          onBlur={(e) => {
                            const v = parseInt(e.target.value, 10);
                            if (!isNaN(v))
                              setDaylistForm((prev) => ({
                                ...prev,
                                sonic_similar_limit: Math.max(1, Math.min(30, v)),
                              }));
                            else setDaylistForm((prev) => ({ ...prev, sonic_similar_limit: 10 }));
                          }}
                        />
                        <p className="text-xs text-muted-foreground">
                          Max similar tracks per seed. Min: 1, max: 30.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label>Sonically similar playlist limit</Label>
                        <Input
                          type="number"
                          min={10}
                          max={200}
                          value={daylistForm.sonic_similarity_limit}
                          onChange={(e) => {
                            const v = parseInt(e.target.value, 10);
                            setDaylistForm((prev) => ({
                              ...prev,
                              sonic_similarity_limit: isNaN(v) ? 50 : v,
                            }));
                          }}
                          onBlur={(e) => {
                            const v = parseInt(e.target.value, 10);
                            if (!isNaN(v))
                              setDaylistForm((prev) => ({
                                ...prev,
                                sonic_similarity_limit: Math.max(10, Math.min(200, v)),
                              }));
                            else
                              setDaylistForm((prev) => ({ ...prev, sonic_similarity_limit: 50 }));
                          }}
                        />
                        <p className="text-xs text-muted-foreground">
                          Max tracks to fetch from Plex sonic API per request. Min: 10, max: 200.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label>
                          Sonically similar distance: {daylistForm.sonic_similarity_distance}
                        </Label>
                        <input
                          type="range"
                          min={0.1}
                          max={2}
                          step={0.1}
                          value={daylistForm.sonic_similarity_distance}
                          onChange={(e) =>
                            setDaylistForm((prev) => ({
                              ...prev,
                              sonic_similarity_distance: parseFloat(e.target.value),
                            }))
                          }
                          className="slider-range"
                        />
                        <p className="text-xs text-muted-foreground">
                          0.1 = very similar, 2 = more diverse. Min: 0.1, max: 2.
                        </p>
                      </div>
                    </div>

                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={daylistForm.use_primary_mood}
                        onChange={(e) =>
                          setDaylistForm((prev) => ({ ...prev, use_primary_mood: e.target.checked }))
                        }
                        className="rounded border-input"
                      />
                      <span className="text-sm">Use primary mood for cover (default: secondary)</span>
                    </label>
                    <p className="text-xs text-muted-foreground -mt-2">
                      Cover text uses the second-most-common mood by default (Meloday). Enable to use
                      the most common mood instead.
                    </p>

                    <div className="space-y-2">
                      <Label>Timezone (optional)</Label>
                      <Input
                        placeholder="e.g. America/New_York"
                        value={daylistForm.timezone}
                        onChange={(e) =>
                          setDaylistForm((prev) => ({ ...prev, timezone: e.target.value }))
                        }
                      />
                      <p className="text-xs text-muted-foreground">
                        Leave empty to use scheduler timezone
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label>Time periods (Start–End hour, 0–23)</Label>
                      <p className="text-xs text-muted-foreground mb-2">
                        When each period runs. Late Night wraps (e.g. 22–2 = 22,23,0,1,2). Hours
                        0–23.
                      </p>
                      <div className="grid gap-2">
                        {Object.entries(daylistForm.time_periods).map(
                          ([period, { start, end }]) => (
                            <div key={period} className="flex items-center gap-3">
                              <span className="w-28 text-sm">{period}</span>
                              <Input
                                type="number"
                                min={0}
                                max={23}
                                className="w-16"
                                value={start}
                                onChange={(e) => {
                                  const v = parseInt(e.target.value, 10);
                                  setDaylistForm((prev) => ({
                                    ...prev,
                                    time_periods: {
                                      ...prev.time_periods,
                                      [period]: {
                                        ...prev.time_periods[period],
                                        start: isNaN(v) ? 0 : v,
                                      },
                                    },
                                  }));
                                }}
                                onBlur={(e) => {
                                  const v = parseInt(e.target.value, 10);
                                  if (!isNaN(v)) {
                                    const clamped = Math.max(0, Math.min(23, v));
                                    setDaylistForm((prev) => ({
                                      ...prev,
                                      time_periods: {
                                        ...prev.time_periods,
                                        [period]: { ...prev.time_periods[period], start: clamped },
                                      },
                                    }));
                                  }
                                }}
                              />
                              <span className="text-muted-foreground">–</span>
                              <Input
                                type="number"
                                min={0}
                                max={23}
                                className="w-16"
                                value={end}
                                onChange={(e) => {
                                  const v = parseInt(e.target.value, 10);
                                  setDaylistForm((prev) => ({
                                    ...prev,
                                    time_periods: {
                                      ...prev.time_periods,
                                      [period]: {
                                        ...prev.time_periods[period],
                                        end: isNaN(v) ? 0 : v,
                                      },
                                    },
                                  }));
                                }}
                                onBlur={(e) => {
                                  const v = parseInt(e.target.value, 10);
                                  if (!isNaN(v)) {
                                    const clamped = Math.max(0, Math.min(23, v));
                                    setDaylistForm((prev) => ({
                                      ...prev,
                                      time_periods: {
                                        ...prev.time_periods,
                                        [period]: { ...prev.time_periods[period], end: clamped },
                                      },
                                    }));
                                  }
                                }}
                              />
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  </div>
                </details>

                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={daylistForm.enabled}
                    onChange={(e) =>
                      setDaylistForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable immediately after creation</span>
                </label>

                <ExpirationFields
                  idPrefix="create-daylist"
                  enabled={daylistForm.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setDaylistForm((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={daylistForm.expires_at}
                  onValueChange={(v) =>
                    setDaylistForm((prev) => ({ ...prev, expires_at: v }))
                  }
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={daylistForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setDaylistForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
                  }
                />
              </>
            ) : playlistType === "local_discovery" ? (
              <>
                <div className="space-y-2">
                  <Label>Plex Account (play history source)</Label>
                  <Select
                    value={localDiscoveryForm.plex_history_account_id}
                    onValueChange={(v) =>
                      setLocalDiscoveryForm((prev) => ({ ...prev, plex_history_account_id: v }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select account" />
                    </SelectTrigger>
                    <SelectContent>
                      {plexAccounts.map((acc) => (
                        <SelectItem key={acc.id} value={acc.id}>
                          {acc.name || acc.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Plex Home users only. Local Discovery uses this account&apos;s play history.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Lookback days</Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      value={localDiscoveryForm.lookback_days}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          lookback_days: isNaN(v) ? 30 : Math.max(7, Math.min(365, v)),
                        }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      How far back to count plays. Shorter = more day-to-day variety. Min: 7, max: 365.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Exclude played days</Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      value={localDiscoveryForm.exclude_played_days}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          exclude_played_days: isNaN(v) ? 3 : Math.max(0, Math.min(30, v)),
                        }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Skip tracks played in last N days. Reduces repetition. Min: 0, max: 30.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Top artists count</Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      value={localDiscoveryForm.top_artists_count}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          top_artists_count: isNaN(v) ? 10 : Math.max(1, Math.min(20, v)),
                        }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      How many top artists to randomly pick each run. Min: 1, max: 20.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Artist pool size</Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      value={localDiscoveryForm.artist_pool_size}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          artist_pool_size: isNaN(v) ? 20 : Math.max(prev.top_artists_count, Math.min(50, v)),
                        }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Size of artist pool to sample from (must be ≥ top artists count). Min: top artists, max: 50.
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Max tracks</Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    value={localDiscoveryForm.max_tracks}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      setLocalDiscoveryForm((prev) => ({
                        ...prev,
                        max_tracks: isNaN(v) ? 50 : Math.max(1, Math.min(200, v)),
                      }));
                    }}
                  />
                  <p className="text-xs text-muted-foreground">
                    Target playlist size. Min: 1, max: 200.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Sonic similar limit</Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      value={localDiscoveryForm.sonic_similar_limit}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          sonic_similar_limit: isNaN(v) ? 15 : Math.max(5, Math.min(50, v)),
                        }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Max sonically similar tracks per seed. Min: 5, max: 50.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Historical ratio: {localDiscoveryForm.historical_ratio}</Label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={localDiscoveryForm.historical_ratio}
                      onChange={(e) =>
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          historical_ratio: parseFloat(e.target.value),
                        }))
                      }
                      className="w-full"
                    />
                    <p className="text-xs text-muted-foreground">
                      Share of tracks from play history vs sonically similar. 0.4 = 40% history, 60% similar.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Sonic similarity distance</Label>
                    <Input
                      type="text"
                      inputMode="decimal"
                      value={localDiscoveryForm.sonic_similarity_distance}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          sonic_similarity_distance: isNaN(v) ? 0.25 : Math.max(0.1, Math.min(1, v)),
                        }));
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Plex sonic match threshold. Lower = stricter. Min: 0.1, max: 1.
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Schedule (cron)</Label>
                  <Input
                    value={localDiscoveryForm.schedule_cron}
                    onChange={(e) =>
                      setLocalDiscoveryForm((prev) => ({ ...prev, schedule_cron: e.target.value }))
                    }
                    placeholder="0 6 * * *"
                  />
                  <p className="text-xs text-muted-foreground">e.g. 0 6 * * * = daily at 6am</p>
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localDiscoveryForm.enabled}
                    onChange={(e) =>
                      setLocalDiscoveryForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable immediately after creation</span>
                </label>
                <ExpirationFields
                  idPrefix="create-ld"
                  enabled={localDiscoveryForm.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setLocalDiscoveryForm((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={localDiscoveryForm.expires_at}
                  onValueChange={(v) =>
                    setLocalDiscoveryForm((prev) => ({ ...prev, expires_at: v }))
                  }
                />
              </>
            ) : playlistType === "top_tracks" ? (
              <>
                <div className="space-y-2">
                  <Label>Artists (one per line)</Label>
                  <textarea
                    className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="Artist One&#10;Artist Two&#10;Artist Three"
                    value={topTracksForm.artists}
                    onChange={(e) =>
                      setTopTracksForm((prev) => ({ ...prev, artists: e.target.value }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Artists must exist in your library. Names are validated against the library cache.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Top X tracks per artist</Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    placeholder="5"
                    value={topTracksForm.top_x}
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      const v = parseInt(raw, 10);
                      setTopTracksForm((prev) => ({
                        ...prev,
                        top_x: raw === "" ? 5 : isNaN(v) ? prev.top_x : Math.max(1, Math.min(20, v)),
                      }));
                    }}
                    onBlur={(e) => {
                      const raw = e.target.value.trim();
                      const v = parseInt(raw, 10);
                      if (raw === "" || isNaN(v) || v < 1 || v > 20) {
                        setTopTracksForm((prev) => ({ ...prev, top_x: 5 }));
                      }
                    }}
                  />
                  <p className="text-xs text-muted-foreground">
                    Number of top tracks per artist. Min: 1, max: 20.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Target</Label>
                  <Select
                    value={topTracksForm.target}
                    onValueChange={(v: "plex" | "jellyfin") =>
                      setTopTracksForm((prev) => ({
                        ...prev,
                        target: v,
                        source: v === "jellyfin" ? "lastfm" : prev.source,
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="plex">Plex</SelectItem>
                      <SelectItem value="jellyfin">Jellyfin</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Where to create the playlist.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Source (Jellyfin target uses Last.fm only)</Label>
                  <Select
                    value={topTracksForm.target === "jellyfin" ? "lastfm" : topTracksForm.source}
                    disabled={topTracksForm.target === "jellyfin"}
                    onValueChange={(v: "plex" | "lastfm") =>
                      setTopTracksForm((prev) => ({ ...prev, source: v }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="plex">Plex (ratingCount)</SelectItem>
                      <SelectItem value="lastfm">Last.fm</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Plex uses ratingCount; Last.fm uses play counts. Jellyfin requires Last.fm.
                  </p>
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={topTracksForm.use_custom_playlist_name}
                    onChange={(e) =>
                      setTopTracksForm((prev) => ({
                        ...prev,
                        use_custom_playlist_name: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Use custom playlist name</span>
                </label>
                {topTracksForm.use_custom_playlist_name && (
                  <div className="space-y-2">
                    <Label>Custom playlist name</Label>
                    <Input
                      value={topTracksForm.custom_playlist_name}
                      onChange={(e) =>
                        setTopTracksForm((prev) => ({
                          ...prev,
                          custom_playlist_name: e.target.value,
                        }))
                      }
                      placeholder="e.g. Road Trip Mix"
                    />
                    <p className="text-xs text-muted-foreground">
                      Override auto-generated name. Shown as [Cmdarr] Artist Essentials: &lt;name&gt;.
                    </p>
                  </div>
                )}
                {!topTracksForm.use_custom_playlist_name && (
                  <p className="text-xs text-muted-foreground">
                    Playlist name is auto-generated from artist names (e.g. Artist1 · Artist2 + 3 More).
                  </p>
                )}
                <div className="space-y-2">
                  <Label>Schedule (cron)</Label>
                  <Input
                    value={topTracksForm.schedule_cron}
                    onChange={(e) =>
                      setTopTracksForm((prev) => ({ ...prev, schedule_cron: e.target.value }))
                    }
                    placeholder="0 6 * * *"
                  />
                  <p className="text-xs text-muted-foreground">
                    e.g. 0 6 * * * = daily at 6am
                  </p>
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={topTracksForm.enabled}
                    onChange={(e) =>
                      setTopTracksForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable immediately after creation</span>
                </label>

                <ExpirationFields
                  idPrefix="create-tt"
                  enabled={topTracksForm.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setTopTracksForm((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={topTracksForm.expires_at}
                  onValueChange={(v) =>
                    setTopTracksForm((prev) => ({ ...prev, expires_at: v }))
                  }
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={topTracksForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setTopTracksForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
                  }
                />
              </>
            ) : (
              <>
                {/* Playlist URL */}
                <div className="space-y-2">
                  <Label>Playlist URL</Label>
                  <div className="relative">
                    <Input
                      type="url"
                      placeholder="https://open.spotify.com/playlist/..."
                      value={formData.playlist_url}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          playlist_url: e.target.value,
                        }))
                      }
                      className={
                        validation.error
                          ? "border-destructive"
                          : validation.isValid
                            ? "border-green-500"
                            : ""
                      }
                    />
                    {validation.isValidating && (
                      <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin" />
                    )}
                    {validation.isValid && (
                      <CheckCircle2 className="absolute right-3 top-3 h-4 w-4 text-green-500" />
                    )}
                    {validation.error && (
                      <AlertCircle className="absolute right-3 top-3 h-4 w-4 text-destructive" />
                    )}
                  </div>
                  {validation.error && (
                    <p className="text-sm text-destructive">{validation.error}</p>
                  )}
                  {validation.metadata && (
                    <div className="rounded-lg border bg-muted p-3">
                      <p className="font-medium">{validation.metadata.name}</p>
                      {validation.metadata.description && (
                        <p className="text-sm text-muted-foreground">
                          {validation.metadata.description}
                        </p>
                      )}
                      <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                        {validation.metadata.track_count && (
                          <span>{validation.metadata.track_count} tracks</span>
                        )}
                        {validation.metadata.source && (
                          <Badge variant="outline">{validation.metadata.source}</Badge>
                        )}
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Supports Spotify, Deezer public playlists
                  </p>
                </div>
              </>
            )}

            {/* Common Settings (hidden for daylist, top_tracks, local_discovery - they have their own forms) */}
            {playlistType !== "daylist" && playlistType !== "top_tracks" && playlistType !== "local_discovery" && (
              <>
                <div className="space-y-2">
                  <Label>Target</Label>
                  <Select
                    value={formData.target}
                    onValueChange={(value) => setFormData((prev) => ({ ...prev, target: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="plex">Plex</SelectItem>
                      <SelectItem value="jellyfin">Jellyfin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Sync Mode</Label>
                  <Select
                    value={formData.sync_mode}
                    onValueChange={(value) =>
                      setFormData((prev) => ({ ...prev, sync_mode: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="full">Full Sync</SelectItem>
                      <SelectItem value="append">Append Only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <p className="text-sm text-muted-foreground">
                  New commands use the global schedule (Config → Scheduler). You can override
                  per-command after creation.
                </p>

                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        enabled: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable immediately after creation</span>
                </label>

                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.enable_artist_discovery}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        enable_artist_discovery: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable artist discovery for this playlist</span>
                </label>

                <ExpirationFields
                  idPrefix="create-ext"
                  enabled={formData.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setFormData((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={formData.expires_at}
                  onValueChange={(v) => setFormData((prev) => ({ ...prev, expires_at: v }))}
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={formData.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setFormData((prev) => ({ ...prev, expires_at_delete_playlist: v }))
                  }
                />
              </>
            )}
          </div>
        )}

        <DialogFooter>
          {step === "form" && (
            <Button variant="outline" onClick={() => setStep("type")}>
              Back
            </Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {step === "form" && (
            <Button onClick={handleSubmit} disabled={!canSubmit() || isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : playlistType === "daylist" ? (
                "Create Daylist"
              ) : playlistType === "top_tracks" ? (
                "Create Artist Essentials"
              ) : playlistType === "local_discovery" ? (
                "Create Local Discovery"
              ) : (
                "Create Playlist Sync"
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
