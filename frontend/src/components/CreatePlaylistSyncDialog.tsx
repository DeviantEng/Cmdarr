import { useState, useEffect, useCallback, useMemo } from "react";
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
import { NumericInput } from "@/components/NumericInput";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Music,
  Globe,
  Sun,
  ListMusic,
  Compass,
  Sparkles,
  Radio,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ExpirationFields } from "@/components/ExpirationFields";
import { toExpiresAtIso } from "@/lib/expiration";

type PlaylistType =
  | "listenbrainz"
  | "other"
  | "daylist"
  | "top_tracks"
  | "local_discovery"
  | "mood_playlist"
  | "xmplaylist";

type XmplaylistStationRow = {
  name: string;
  deeplink: string;
  number: number | null;
  label: string;
};

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
    sync_to_multiple_plex_users: false,
    plex_account_ids: [] as string[],
    sync_mode: "full",
    enabled: true,
    weekly_exploration_keep: 3,
    weekly_jams_keep: 3,
    daily_jams_keep: 3,
    cleanup_enabled: true,
    enable_artist_discovery: false,
    artist_discovery_max_per_run: 2,
    schedule_cron: "0 6 * * *",
    schedule_override: false,
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
  const [plexAccounts, setPlexAccounts] = useState<{ id: string; name: string }[]>([]);
  const [daylistUsedIds, setDaylistUsedIds] = useState<Set<string>>(new Set());
  const [localDiscoveryUsedIds, setLocalDiscoveryUsedIds] = useState<Set<string>>(new Set());
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
    lookback_days: 90,
    exclude_played_days: 3,
    top_artists_count: 10,
    artist_pool_size: 20,
    max_tracks: 50,
    sonic_similar_limit: 15,
    sonic_similarity_distance: 0.25,
    historical_ratio: 0.4,
    schedule_cron: "0 6 * * *",
    schedule_override: false,
    enabled: true,
    expires_at_enabled: false,
    expires_at: "",
    expires_at_delete_playlist: true,
  });

  const [topTracksForm, setTopTracksForm] = useState({
    artists: "",
    top_x: 5,
    source: "plex" as "plex" | "lastfm",
    target: "plex" as "plex" | "jellyfin",
    use_custom_playlist_name: false,
    custom_playlist_name: "",
    schedule_cron: "0 6 * * *",
    schedule_override: false,
    enabled: true,
    expires_at_enabled: false,
    expires_at: "",
    expires_at_delete_playlist: true,
  });

  const [moodPlaylistForm, setMoodPlaylistForm] = useState({
    moods: [] as string[],
    use_custom_playlist_name: false,
    custom_playlist_name: "",
    max_tracks: 50,
    exclude_last_run: true,
    limit_by_year: false,
    min_year: undefined as number | undefined,
    max_year: undefined as number | undefined,
    schedule_cron: "0 6 * * *",
    schedule_override: false,
    enabled: true,
    expires_at_enabled: false,
    expires_at: "",
    expires_at_delete_playlist: true,
  });
  const [moodsList, setMoodsList] = useState<string[]>([]);

  const [xmplaylistForm, setXmplaylistForm] = useState({
    station_deeplink: "",
    station_display_name: "",
    station_label: "",
    playlist_kind: "newest" as "newest" | "most_heard",
    most_heard_days: 30 as 1 | 7 | 14 | 30 | 60,
    max_tracks: 50,
    target: "plex" as "plex" | "jellyfin",
    plex_playlist_account_id: "",
    enable_artist_discovery: false,
    artist_discovery_max_per_run: 2,
    schedule_cron: "0 6 * * *",
    schedule_override: false,
    enabled: true,
    expires_at_enabled: false,
    expires_at: "",
    expires_at_delete_playlist: true,
  });
  const [xmplaylistStations, setXmplaylistStations] = useState<XmplaylistStationRow[]>([]);
  const [xmplaylistStationsLoading, setXmplaylistStationsLoading] = useState(false);
  const [xmplaylistStationFilter, setXmplaylistStationFilter] = useState("");

  const filteredXmStations = useMemo(() => {
    const q = xmplaylistStationFilter.trim().toLowerCase();
    if (!q) return xmplaylistStations;
    return xmplaylistStations.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.deeplink.includes(q) ||
        (s.number != null && String(s.number).includes(q))
    );
  }, [xmplaylistStations, xmplaylistStationFilter]);

  const fetchPlexAccounts = () =>
    api
      .request<{
        accounts: { id: string; name: string }[];
        daylist_used_ids?: string[];
        local_discovery_used_ids?: string[];
      }>("/api/commands/plex-accounts")
      .then((r) => {
        setPlexAccounts(r.accounts || []);
        setDaylistUsedIds(new Set(r.daylist_used_ids || []));
        setLocalDiscoveryUsedIds(new Set(r.local_discovery_used_ids || []));
      })
      .catch(() => {
        setPlexAccounts([]);
        setDaylistUsedIds(new Set());
        setLocalDiscoveryUsedIds(new Set());
      });

  // Fetch mood playlist moods and plex accounts when dialog opens
  useEffect(() => {
    if (!open) return;
    api
      .request<{ moods: string[] }>("/api/commands/mood-playlist/moods")
      .then((r) => setMoodsList(r.moods || []))
      .catch(() => setMoodsList([]));
    fetchPlexAccounts();
  }, [open]);

  // Refetch plex accounts when showing Daylist or Local Discovery form (ensures used_ids are current)
  useEffect(() => {
    if (!open) return;
    if (step === "form" && (playlistType === "daylist" || playlistType === "local_discovery")) {
      fetchPlexAccounts();
    }
  }, [open, step, playlistType]);

  useEffect(() => {
    if (!open || step !== "form" || playlistType !== "xmplaylist") return;
    setXmplaylistStationsLoading(true);
    api
      .request<{ stations: XmplaylistStationRow[] }>("/api/commands/xmplaylist/stations")
      .then((r) => setXmplaylistStations(r.stations || []))
      .catch(() => {
        setXmplaylistStations([]);
        toast.error("Could not load stations from xmplaylist.com");
      })
      .finally(() => setXmplaylistStationsLoading(false));
  }, [open, step, playlistType]);

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      setStep("type");
      setPlaylistType("other");
      setFormData({
        playlist_url: "",
        playlist_types: [],
        target: "plex",
        sync_to_multiple_plex_users: false,
        plex_account_ids: [],
        sync_mode: "full",
        enabled: true,
        weekly_exploration_keep: 3,
        weekly_jams_keep: 3,
        daily_jams_keep: 3,
        cleanup_enabled: true,
        enable_artist_discovery: false,
        artist_discovery_max_per_run: 2,
        schedule_cron: "0 6 * * *",
        schedule_override: false,
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
        lookback_days: 90,
        exclude_played_days: 3,
        top_artists_count: 10,
        artist_pool_size: 20,
        max_tracks: 50,
        sonic_similar_limit: 15,
        sonic_similarity_distance: 0.25,
        historical_ratio: 0.4,
        schedule_cron: "0 6 * * *",
        schedule_override: false,
        enabled: true,
        expires_at_enabled: false,
        expires_at: "",
        expires_at_delete_playlist: true,
      });
      setMoodPlaylistForm({
        moods: [],
        use_custom_playlist_name: false,
        custom_playlist_name: "",
        max_tracks: 50,
        exclude_last_run: true,
        limit_by_year: false,
        min_year: undefined,
        max_year: undefined,
        schedule_cron: "0 6 * * *",
        schedule_override: false,
        enabled: true,
        expires_at_enabled: false,
        expires_at: "",
        expires_at_delete_playlist: true,
      });
      setXmplaylistForm({
        station_deeplink: "",
        station_display_name: "",
        station_label: "",
        playlist_kind: "newest",
        most_heard_days: 30,
        max_tracks: 50,
        target: "plex",
        plex_playlist_account_id: "",
        enable_artist_discovery: false,
        artist_discovery_max_per_run: 2,
        schedule_cron: "0 6 * * *",
        schedule_override: false,
        enabled: true,
        expires_at_enabled: false,
        expires_at: "",
        expires_at_delete_playlist: true,
      });
      setXmplaylistStationFilter("");
      setXmplaylistStations([]);
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

  const handleToggleMood = (mood: string) => {
    setMoodPlaylistForm((prev) => ({
      ...prev,
      moods: prev.moods.includes(mood)
        ? prev.moods.filter((m) => m !== mood)
        : [...prev.moods, mood],
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
      if (
        topTracksForm.artists
          .trim()
          .split("\n")
          .filter((a) => a.trim()).length === 0
      )
        return false;
      if (topTracksForm.expires_at_enabled && !topTracksForm.expires_at) return false;
      return true;
    }
    if (playlistType === "mood_playlist") {
      if (moodPlaylistForm.moods.length === 0) return false;
      if (moodPlaylistForm.expires_at_enabled && !moodPlaylistForm.expires_at) return false;
      return true;
    }
    if (playlistType === "local_discovery") {
      if (!localDiscoveryForm.plex_history_account_id) return false;
      if (localDiscoveryForm.expires_at_enabled && !localDiscoveryForm.expires_at) return false;
      return true;
    }
    if (playlistType === "xmplaylist") {
      if (!xmplaylistForm.station_deeplink.trim()) return false;
      if (xmplaylistForm.expires_at_enabled && !xmplaylistForm.expires_at) return false;
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
          artists: topTracksForm.artists
            .trim()
            .split("\n")
            .filter((a) => a.trim()),
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
          daylistPayload.expires_at_delete_playlist =
            daylistForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string }>("/api/commands/daylist/create", {
          method: "POST",
          body: JSON.stringify(daylistPayload),
        });
        toast.success(response.message || "Daylist command created successfully");
      } else if (playlistType === "mood_playlist") {
        const payload: Record<string, unknown> = {
          moods: moodPlaylistForm.moods,
          use_custom_playlist_name: moodPlaylistForm.use_custom_playlist_name,
          custom_playlist_name: moodPlaylistForm.custom_playlist_name,
          max_tracks: moodPlaylistForm.max_tracks,
          exclude_last_run: moodPlaylistForm.exclude_last_run,
          limit_by_year: moodPlaylistForm.limit_by_year,
          min_year: moodPlaylistForm.limit_by_year ? moodPlaylistForm.min_year : undefined,
          max_year: moodPlaylistForm.limit_by_year ? moodPlaylistForm.max_year : undefined,
          schedule_cron: moodPlaylistForm.schedule_override
            ? moodPlaylistForm.schedule_cron
            : undefined,
          enabled: moodPlaylistForm.enabled,
        };
        if (moodPlaylistForm.expires_at_enabled && moodPlaylistForm.expires_at) {
          payload.expires_at = toExpiresAtIso(moodPlaylistForm.expires_at);
          payload.expires_at_delete_playlist = moodPlaylistForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string; command_name: string }>(
          "/api/commands/mood-playlist/create",
          { method: "POST", body: JSON.stringify(payload) }
        );
        toast.success(response.message || "Mood Playlist command created");
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
          schedule_cron: localDiscoveryForm.schedule_override
            ? localDiscoveryForm.schedule_cron
            : undefined,
          enabled: localDiscoveryForm.enabled,
        };
        if (localDiscoveryForm.expires_at_enabled && localDiscoveryForm.expires_at) {
          payload.expires_at = toExpiresAtIso(localDiscoveryForm.expires_at);
          payload.expires_at_delete_playlist =
            localDiscoveryForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string }>(
          "/api/commands/local-discovery/create",
          { method: "POST", body: JSON.stringify(payload) }
        );
        toast.success(response.message || "Local Discovery command created");
      } else if (playlistType === "xmplaylist") {
        const payload: Record<string, unknown> = {
          station_deeplink: xmplaylistForm.station_deeplink.trim(),
          station_display_name:
            xmplaylistForm.station_display_name.trim() || xmplaylistForm.station_deeplink.trim(),
          playlist_kind: xmplaylistForm.playlist_kind,
          most_heard_days:
            xmplaylistForm.playlist_kind === "most_heard" ? xmplaylistForm.most_heard_days : 30,
          max_tracks: xmplaylistForm.max_tracks,
          target: xmplaylistForm.target,
          enable_artist_discovery: xmplaylistForm.enable_artist_discovery,
          artist_discovery_max_per_run: xmplaylistForm.artist_discovery_max_per_run,
          schedule_cron: xmplaylistForm.schedule_override
            ? xmplaylistForm.schedule_cron
            : undefined,
          enabled: xmplaylistForm.enabled,
        };
        if (xmplaylistForm.target === "plex" && xmplaylistForm.plex_playlist_account_id.trim()) {
          payload.plex_playlist_account_id = xmplaylistForm.plex_playlist_account_id.trim();
        }
        if (xmplaylistForm.expires_at_enabled && xmplaylistForm.expires_at) {
          payload.expires_at = toExpiresAtIso(xmplaylistForm.expires_at);
          payload.expires_at_delete_playlist = xmplaylistForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string; command_name: string }>(
          "/api/commands/xmplaylist/create",
          { method: "POST", body: JSON.stringify(payload) }
        );
        toast.success(response.message || "XM Playlist command created");
      } else {
        const payload: Record<string, unknown> = {
          ...formData,
          playlist_type: playlistType,
          schedule_cron: formData.schedule_override ? formData.schedule_cron : undefined,
          plex_account_ids: formData.sync_to_multiple_plex_users ? formData.plex_account_ids : [],
        };
        delete payload.sync_to_multiple_plex_users;
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
                    : playlistType === "mood_playlist"
                      ? "Configure Mood Playlist"
                      : playlistType === "xmplaylist"
                        ? "Configure XMPlaylist (SiriusXM History)"
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
                    : playlistType === "mood_playlist"
                      ? "Select moods from Plex Sonic Analysis. Tracks matching multiple moods rank higher."
                      : playlistType === "xmplaylist"
                        ? "Data from xmplaylist.com. Tracks are matched to your Plex or Jellyfin library."
                        : "Configure your playlist sync settings"}
          </DialogDescription>
        </DialogHeader>

        {step === "type" ? (
          <div className="grid gap-3 py-4">
            {/* Daylist */}
            <button
              onClick={() => handleSelectType("daylist")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900">
                <Sun className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">Daylist</h3>
                <p className="text-xs text-muted-foreground">
                  Time-of-day playlists from Plex listening history and Sonic Analysis. Plex only.
                </p>
              </div>
            </button>

            {/* Local Discovery */}
            <button
              onClick={() => handleSelectType("local_discovery")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-teal-100 dark:bg-teal-900">
                <Compass className="h-5 w-5 text-teal-600 dark:text-teal-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">Local Discovery</h3>
                <p className="text-xs text-muted-foreground">
                  Top artists from play history + sonically similar tracks. Fresh each run. Plex
                  only.
                </p>
              </div>
            </button>

            {/* ListenBrainz Curated */}
            <button
              onClick={() => handleSelectType("listenbrainz")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900">
                <Music className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">ListenBrainz Curated</h3>
                <p className="text-xs text-muted-foreground">
                  Sync Weekly Exploration, Weekly Jams, or Daily Jams playlists
                </p>
              </div>
            </button>

            {/* External Playlist */}
            <button
              onClick={() => handleSelectType("other")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900">
                <Globe className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">External Playlist</h3>
                <p className="text-xs text-muted-foreground">
                  Sync public playlists from Spotify, Deezer, or other sources
                </p>
              </div>
            </button>

            {/* Top Tracks / Artist Essentials */}
            <button
              onClick={() => handleSelectType("top_tracks")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                <ListMusic className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">Artist Essentials</h3>
                <p className="text-xs text-muted-foreground">
                  Generate playlist from artist list with top X tracks per artist (Plex or Last.fm).
                </p>
              </div>
            </button>

            {/* XMPlaylist (SiriusXM History) */}
            <button
              onClick={() => handleSelectType("xmplaylist")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-100 dark:bg-sky-900">
                <Radio className="h-5 w-5 text-sky-600 dark:text-sky-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">XMPlaylist (SiriusXM History)</h3>
                <p className="text-xs text-muted-foreground">
                  Newest or most-played tracks per station via xmplaylist.com → Plex or Jellyfin.
                </p>
              </div>
            </button>

            {/* Mood Playlist */}
            <button
              onClick={() => handleSelectType("mood_playlist")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-900">
                <Sparkles className="h-5 w-5 text-violet-600 dark:text-violet-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">Mood Playlist</h3>
                <p className="text-xs text-muted-foreground">
                  Generate from selected Plex moods. Fresh each run with exclude-last-run.
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
                      <NumericInput
                        value={formData.weekly_exploration_keep}
                        onChange={(v) =>
                          setFormData((prev) => ({ ...prev, weekly_exploration_keep: v ?? 3 }))
                        }
                        min={1}
                        max={20}
                        defaultValue={3}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Weekly Jams</Label>
                      <NumericInput
                        value={formData.weekly_jams_keep}
                        onChange={(v) =>
                          setFormData((prev) => ({ ...prev, weekly_jams_keep: v ?? 3 }))
                        }
                        min={1}
                        max={20}
                        defaultValue={3}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Daily Jams</Label>
                      <NumericInput
                        value={formData.daily_jams_keep}
                        onChange={(v) =>
                          setFormData((prev) => ({ ...prev, daily_jams_keep: v ?? 3 }))
                        }
                        min={1}
                        max={20}
                        defaultValue={3}
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
                          <SelectItem
                            key={acc.id}
                            value={acc.id}
                            disabled={daylistUsedIds.has(acc.id)}
                          >
                            {acc.name || `Account ${acc.id}`}
                            {daylistUsedIds.has(acc.id) ? " (already has Daylist)" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Plex Home users only. Daylist uses this account&apos;s play history. One
                      Daylist per user.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>Run at minute of hour (0–59)</Label>
                    <NumericInput
                      value={daylistForm.schedule_minute}
                      onChange={(v) =>
                        setDaylistForm((prev) => ({ ...prev, schedule_minute: v ?? 0 }))
                      }
                      min={0}
                      max={59}
                      defaultValue={0}
                    />
                    <p className="text-xs text-muted-foreground">
                      Daylist runs hourly at this minute. Runs only when the day period changes
                      (Dawn, Morning, etc.). Min: 0, max: 59.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Exclude played (days)</Label>
                      <NumericInput
                        value={daylistForm.exclude_played_days}
                        onChange={(v) =>
                          setDaylistForm((prev) => ({ ...prev, exclude_played_days: v ?? 3 }))
                        }
                        min={1}
                        max={30}
                        defaultValue={3}
                      />
                      <p className="text-xs text-muted-foreground">
                        Skip tracks played in last N days. Min: 1, max: 30.
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label>History lookback (days)</Label>
                      <NumericInput
                        value={daylistForm.history_lookback_days}
                        onChange={(v) =>
                          setDaylistForm((prev) => ({ ...prev, history_lookback_days: v ?? 45 }))
                        }
                        min={7}
                        max={365}
                        defaultValue={45}
                      />
                      <p className="text-xs text-muted-foreground">
                        Days of play history to analyze. Min: 7, max: 365.
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label>Max tracks</Label>
                      <NumericInput
                        value={daylistForm.max_tracks}
                        onChange={(v) =>
                          setDaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))
                        }
                        min={10}
                        max={200}
                        defaultValue={50}
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
                        <NumericInput
                          value={daylistForm.sonic_similar_limit}
                          onChange={(v) =>
                            setDaylistForm((prev) => ({ ...prev, sonic_similar_limit: v ?? 10 }))
                          }
                          min={1}
                          max={30}
                          defaultValue={10}
                        />
                        <p className="text-xs text-muted-foreground">
                          Max similar tracks per seed. Min: 1, max: 30.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label>Sonically similar playlist limit</Label>
                        <NumericInput
                          value={daylistForm.sonic_similarity_limit}
                          onChange={(v) =>
                            setDaylistForm((prev) => ({
                              ...prev,
                              sonic_similarity_limit: v ?? 50,
                            }))
                          }
                          min={10}
                          max={200}
                          defaultValue={50}
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
                          setDaylistForm((prev) => ({
                            ...prev,
                            use_primary_mood: e.target.checked,
                          }))
                        }
                        className="rounded border-input"
                      />
                      <span className="text-sm">
                        Use primary mood for cover (default: secondary)
                      </span>
                    </label>
                    <p className="text-xs text-muted-foreground -mt-2">
                      Cover text uses the second-most-common mood by default (Meloday). Enable to
                      use the most common mood instead.
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
                                type="text"
                                inputMode="numeric"
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
                                        start: isNaN(v) ? prev.time_periods[period].start : v,
                                      },
                                    },
                                  }));
                                }}
                              />
                              <span className="text-muted-foreground">–</span>
                              <Input
                                type="text"
                                inputMode="numeric"
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
                                        end: isNaN(v) ? prev.time_periods[period].end : v,
                                      },
                                    },
                                  }));
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
                  onValueChange={(v) => setDaylistForm((prev) => ({ ...prev, expires_at: v }))}
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
                        <SelectItem
                          key={acc.id}
                          value={acc.id}
                          disabled={localDiscoveryUsedIds.has(acc.id)}
                        >
                          {acc.name || acc.id}
                          {localDiscoveryUsedIds.has(acc.id)
                            ? " (already has Local Discovery)"
                            : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Plex Home users only. Local Discovery uses this account&apos;s play history. One
                    Local Discovery per user.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Lookback days</Label>
                    <NumericInput
                      value={localDiscoveryForm.lookback_days}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({ ...prev, lookback_days: v ?? 90 }))
                      }
                      min={7}
                      max={365}
                      defaultValue={90}
                    />
                    <p className="text-xs text-muted-foreground">
                      How far back to count plays. Shorter = more day-to-day variety. Min: 7, max:
                      365.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Exclude played days</Label>
                    <NumericInput
                      value={localDiscoveryForm.exclude_played_days}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({ ...prev, exclude_played_days: v ?? 3 }))
                      }
                      min={0}
                      max={30}
                      defaultValue={3}
                    />
                    <p className="text-xs text-muted-foreground">
                      Skip tracks played in last N days. Reduces repetition. Min: 0, max: 30.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Top artists count</Label>
                    <NumericInput
                      value={localDiscoveryForm.top_artists_count}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          top_artists_count: v ?? 10,
                        }))
                      }
                      min={1}
                      max={20}
                      defaultValue={10}
                    />
                    <p className="text-xs text-muted-foreground">
                      How many top artists to randomly pick each run. Min: 1, max: 20.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Artist pool size</Label>
                    <NumericInput
                      value={localDiscoveryForm.artist_pool_size}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          artist_pool_size: v ?? 20,
                        }))
                      }
                      min={1}
                      max={50}
                      defaultValue={20}
                    />
                    <p className="text-xs text-muted-foreground">
                      Size of artist pool to sample from (must be ≥ top artists count).
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Max tracks</Label>
                  <NumericInput
                    value={localDiscoveryForm.max_tracks}
                    onChange={(v) =>
                      setLocalDiscoveryForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))
                    }
                    min={1}
                    max={200}
                    defaultValue={50}
                  />
                  <p className="text-xs text-muted-foreground">
                    Target playlist size. Min: 1, max: 200.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Sonic similar limit</Label>
                    <NumericInput
                      value={localDiscoveryForm.sonic_similar_limit}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          sonic_similar_limit: v ?? 10,
                        }))
                      }
                      min={5}
                      max={50}
                      defaultValue={15}
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
                      Share of tracks from play history vs sonically similar. 0.4 = 40% history, 60%
                      similar.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Sonic similarity distance</Label>
                    <NumericInput
                      value={localDiscoveryForm.sonic_similarity_distance}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          sonic_similarity_distance: v ?? 0.25,
                        }))
                      }
                      min={0.1}
                      max={1}
                      defaultValue={0.25}
                      numericType="float"
                    />
                    <p className="text-xs text-muted-foreground">
                      Plex sonic match threshold. Lower = stricter. Min: 0.1, max: 1.
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-ld-schedule-override"
                      checked={localDiscoveryForm.schedule_override}
                      onChange={(e) =>
                        setLocalDiscoveryForm((prev) => ({
                          ...prev,
                          schedule_override: e.target.checked,
                        }))
                      }
                      className="rounded border-input"
                    />
                    <Label htmlFor="create-ld-schedule-override">Override default schedule</Label>
                  </div>
                  {localDiscoveryForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder="0 6 * * *"
                          value={localDiscoveryForm.schedule_cron}
                          onChange={(e) =>
                            setLocalDiscoveryForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Cron format: minute hour day month weekday (e.g. 0 6 * * * = daily at 6am)
                      </p>
                    </>
                  )}
                  {!localDiscoveryForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">
                      Uses global default (Config → Scheduler)
                    </p>
                  )}
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
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={localDiscoveryForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setLocalDiscoveryForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
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
                    Artists must exist in your library. Names are validated against the library
                    cache.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Top X tracks per artist</Label>
                  <NumericInput
                    placeholder="5"
                    value={topTracksForm.top_x}
                    onChange={(v) => setTopTracksForm((prev) => ({ ...prev, top_x: v ?? 5 }))}
                    min={1}
                    max={20}
                    defaultValue={5}
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
                  <p className="text-xs text-muted-foreground">Where to create the playlist.</p>
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
                      Override auto-generated name. Shown as [Cmdarr] Artist Essentials:
                      &lt;name&gt;.
                    </p>
                  </div>
                )}
                {!topTracksForm.use_custom_playlist_name && (
                  <p className="text-xs text-muted-foreground">
                    Playlist name is auto-generated from artist names (e.g. Artist1 · Artist2 + 3
                    More).
                  </p>
                )}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-tt-schedule-override"
                      checked={topTracksForm.schedule_override}
                      onChange={(e) =>
                        setTopTracksForm((prev) => ({
                          ...prev,
                          schedule_override: e.target.checked,
                        }))
                      }
                      className="rounded border-input"
                    />
                    <Label htmlFor="create-tt-schedule-override">Override default schedule</Label>
                  </div>
                  {topTracksForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder="0 6 * * *"
                          value={topTracksForm.schedule_cron}
                          onChange={(e) =>
                            setTopTracksForm((prev) => ({ ...prev, schedule_cron: e.target.value }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Cron format: minute hour day month weekday (e.g. 0 6 * * * = daily at 6am)
                      </p>
                    </>
                  )}
                  {!topTracksForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">
                      Uses global default (Config → Scheduler)
                    </p>
                  )}
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
                  onValueChange={(v) => setTopTracksForm((prev) => ({ ...prev, expires_at: v }))}
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={topTracksForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setTopTracksForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
                  }
                />
              </>
            ) : playlistType === "mood_playlist" ? (
              <>
                <div className="space-y-2">
                  <Label>Moods (select one or more)</Label>
                  <div className="max-h-[200px] overflow-y-auto rounded-md border border-input p-2">
                    {moodsList.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Loading moods...</p>
                    ) : (
                      <div className="grid grid-cols-3 gap-1">
                        {moodsList.map((mood) => (
                          <label key={mood} className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={moodPlaylistForm.moods.includes(mood)}
                              onChange={() => handleToggleMood(mood)}
                              className="rounded border-gray-300"
                            />
                            <span className="text-sm">{mood}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Tracks matching multiple selected moods rank higher. Uses Plex Sonic Analysis.
                  </p>
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={moodPlaylistForm.use_custom_playlist_name}
                    onChange={(e) =>
                      setMoodPlaylistForm((prev) => ({
                        ...prev,
                        use_custom_playlist_name: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Use custom playlist name</span>
                </label>
                {moodPlaylistForm.use_custom_playlist_name && (
                  <div className="space-y-2">
                    <Label>Custom playlist name</Label>
                    <Input
                      value={moodPlaylistForm.custom_playlist_name}
                      onChange={(e) =>
                        setMoodPlaylistForm((prev) => ({
                          ...prev,
                          custom_playlist_name: e.target.value,
                        }))
                      }
                      placeholder="e.g. Chill Vibes"
                    />
                    <p className="text-xs text-muted-foreground">
                      Override auto-generated name. Shown as [Cmdarr] Mood: &lt;name&gt;.
                    </p>
                  </div>
                )}
                {!moodPlaylistForm.use_custom_playlist_name && (
                  <p className="text-xs text-muted-foreground">
                    Playlist name is auto-generated from mood names (e.g. Chill · Relaxed + 2 More).
                  </p>
                )}
                <div className="space-y-2">
                  <Label>Max tracks</Label>
                  <NumericInput
                    placeholder="50"
                    value={moodPlaylistForm.max_tracks}
                    onChange={(v) =>
                      setMoodPlaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))
                    }
                    min={1}
                    max={200}
                    defaultValue={50}
                  />
                  <p className="text-xs text-muted-foreground">Min 1, max 200</p>
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={moodPlaylistForm.exclude_last_run}
                    onChange={(e) =>
                      setMoodPlaylistForm((prev) => ({
                        ...prev,
                        exclude_last_run: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Force fresh (exclude tracks from previous run)</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={moodPlaylistForm.limit_by_year}
                    onChange={(e) =>
                      setMoodPlaylistForm((prev) => ({
                        ...prev,
                        limit_by_year: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Limit by release year (album year)</span>
                </label>
                {moodPlaylistForm.limit_by_year && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Min year</Label>
                      <NumericInput
                        placeholder="e.g. 1990"
                        value={moodPlaylistForm.min_year}
                        onChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, min_year: v }))}
                        min={1800}
                        max={2100}
                        defaultValue={1800}
                        allowEmpty
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Max year</Label>
                      <NumericInput
                        placeholder="e.g. 2010"
                        value={moodPlaylistForm.max_year}
                        onChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, max_year: v }))}
                        min={1800}
                        max={2100}
                        defaultValue={2100}
                        allowEmpty
                      />
                    </div>
                  </div>
                )}
                {moodPlaylistForm.limit_by_year && (
                  <p className="text-xs text-muted-foreground">
                    Set min and/or max. Tracks without year metadata are excluded. Range: 1800–2100.
                  </p>
                )}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-mood-schedule-override"
                      checked={moodPlaylistForm.schedule_override}
                      onChange={(e) =>
                        setMoodPlaylistForm((prev) => ({
                          ...prev,
                          schedule_override: e.target.checked,
                        }))
                      }
                      className="rounded border-input"
                    />
                    <Label htmlFor="create-mood-schedule-override">Override default schedule</Label>
                  </div>
                  {moodPlaylistForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder="0 6 * * *"
                          value={moodPlaylistForm.schedule_cron}
                          onChange={(e) =>
                            setMoodPlaylistForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Cron format: minute hour day month weekday (e.g. 0 6 * * * = daily at 6am)
                      </p>
                    </>
                  )}
                  {!moodPlaylistForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">
                      Uses global default (Config → Scheduler)
                    </p>
                  )}
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={moodPlaylistForm.enabled}
                    onChange={(e) =>
                      setMoodPlaylistForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable immediately after creation</span>
                </label>

                <ExpirationFields
                  idPrefix="create-mood"
                  enabled={moodPlaylistForm.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setMoodPlaylistForm((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={moodPlaylistForm.expires_at}
                  onValueChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, expires_at: v }))}
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={moodPlaylistForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setMoodPlaylistForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
                  }
                />
              </>
            ) : playlistType === "xmplaylist" ? (
              <>
                <div className="space-y-2">
                  <Label>Station</Label>
                  <p className="text-xs text-muted-foreground">
                    Search by channel number or name. Sorted by channel number.
                  </p>
                  {xmplaylistForm.station_label ? (
                    <p className="text-sm font-medium">Selected: {xmplaylistForm.station_label}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">No station selected</p>
                  )}
                  <Input
                    placeholder="Filter stations…"
                    value={xmplaylistStationFilter}
                    onChange={(e) => setXmplaylistStationFilter(e.target.value)}
                    disabled={xmplaylistStationsLoading}
                  />
                  <div className="max-h-52 overflow-y-auto rounded-md border border-input">
                    {xmplaylistStationsLoading ? (
                      <p className="p-3 text-sm text-muted-foreground">Loading stations…</p>
                    ) : filteredXmStations.length === 0 ? (
                      <p className="p-3 text-sm text-muted-foreground">No stations match.</p>
                    ) : (
                      filteredXmStations.map((s) => (
                        <button
                          key={s.deeplink}
                          type="button"
                          className="block w-full border-b border-border px-3 py-2 text-left text-sm last:border-b-0 hover:bg-accent"
                          onClick={() =>
                            setXmplaylistForm((prev) => ({
                              ...prev,
                              station_deeplink: s.deeplink,
                              station_display_name: s.name,
                              station_label: s.label,
                            }))
                          }
                        >
                          {s.label}
                        </button>
                      ))
                    )}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Playlist source</Label>
                  <Select
                    value={xmplaylistForm.playlist_kind}
                    onValueChange={(v: "newest" | "most_heard") =>
                      setXmplaylistForm((prev) => ({ ...prev, playlist_kind: v }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="newest">Newest tracks</SelectItem>
                      <SelectItem value="most_heard">Most played</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {xmplaylistForm.playlist_kind === "most_heard" && (
                  <div className="space-y-2">
                    <Label>Time period</Label>
                    <Select
                      value={String(xmplaylistForm.most_heard_days)}
                      onValueChange={(v) =>
                        setXmplaylistForm((prev) => ({
                          ...prev,
                          most_heard_days: parseInt(v, 10) as 1 | 7 | 14 | 30 | 60,
                        }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1 day</SelectItem>
                        <SelectItem value="7">7 days</SelectItem>
                        <SelectItem value="14">14 days</SelectItem>
                        <SelectItem value="30">30 days</SelectItem>
                        <SelectItem value="60">60 days</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="space-y-2">
                  <Label>Max tracks in playlist</Label>
                  <NumericInput
                    value={xmplaylistForm.max_tracks}
                    onChange={(v) =>
                      setXmplaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))
                    }
                    min={1}
                    max={50}
                    defaultValue={50}
                  />
                  <p className="text-xs text-muted-foreground">Between 1 and 50.</p>
                </div>
                <div className="space-y-2">
                  <Label>Target</Label>
                  <Select
                    value={xmplaylistForm.target}
                    onValueChange={(v: "plex" | "jellyfin") =>
                      setXmplaylistForm((prev) => ({ ...prev, target: v }))
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
                </div>
                {xmplaylistForm.target === "plex" && plexAccounts.length > 0 && (
                  <div className="space-y-2">
                    <Label>Plex playlist user (optional)</Label>
                    <Select
                      value={xmplaylistForm.plex_playlist_account_id || "__default__"}
                      onValueChange={(v) =>
                        setXmplaylistForm((prev) => ({
                          ...prev,
                          plex_playlist_account_id: v === "__default__" ? "" : v,
                        }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Server default" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__default__">Server default</SelectItem>
                        {plexAccounts.map((acc) => (
                          <SelectItem key={acc.id} value={acc.id}>
                            {acc.name || acc.id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Use a Plex Home user token when creating playlists in their library.
                    </p>
                  </div>
                )}
                <div className="space-y-2 rounded-lg border p-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-xm-artist-discovery"
                      checked={xmplaylistForm.enable_artist_discovery}
                      onChange={(e) =>
                        setXmplaylistForm((prev) => ({
                          ...prev,
                          enable_artist_discovery: e.target.checked,
                        }))
                      }
                      className="rounded border-input"
                    />
                    <Label
                      htmlFor="create-xm-artist-discovery"
                      className="cursor-pointer font-normal"
                    >
                      Artist discovery (Lidarr import list)
                    </Label>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Unmatched artists can be added to the Playlist Sync Discovery import list
                    (MusicBrainz + Lidarr). First run previews only.
                  </p>
                  {xmplaylistForm.enable_artist_discovery && (
                    <div className="space-y-2 pt-2">
                      <Label>Max artists to add per run</Label>
                      <NumericInput
                        value={xmplaylistForm.artist_discovery_max_per_run}
                        onChange={(v) =>
                          setXmplaylistForm((prev) => ({
                            ...prev,
                            artist_discovery_max_per_run: v ?? 2,
                          }))
                        }
                        min={0}
                        max={50}
                        defaultValue={2}
                      />
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-xm-schedule-override"
                      checked={xmplaylistForm.schedule_override}
                      onChange={(e) =>
                        setXmplaylistForm((prev) => ({
                          ...prev,
                          schedule_override: e.target.checked,
                        }))
                      }
                      className="rounded border-input"
                    />
                    <Label htmlFor="create-xm-schedule-override">Override default schedule</Label>
                  </div>
                  {xmplaylistForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder="0 6 * * *"
                          value={xmplaylistForm.schedule_cron}
                          onChange={(e) =>
                            setXmplaylistForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Cron: minute hour day month weekday (e.g. 0 6 * * * = daily 6am)
                      </p>
                    </>
                  )}
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={xmplaylistForm.enabled}
                    onChange={(e) =>
                      setXmplaylistForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable immediately after creation</span>
                </label>
                <ExpirationFields
                  idPrefix="create-xm"
                  enabled={xmplaylistForm.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setXmplaylistForm((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={xmplaylistForm.expires_at}
                  onValueChange={(v) => setXmplaylistForm((prev) => ({ ...prev, expires_at: v }))}
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={xmplaylistForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setXmplaylistForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
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

            {/* Common Settings (hidden for daylist, top_tracks, local_discovery, mood_playlist - they have their own forms) */}
            {playlistType !== "daylist" &&
              playlistType !== "top_tracks" &&
              playlistType !== "local_discovery" &&
              playlistType !== "mood_playlist" && (
                <>
                  <div className="space-y-2">
                    <Label>Target</Label>
                    <Select
                      value={formData.target}
                      onValueChange={(value) =>
                        setFormData((prev) => ({
                          ...prev,
                          target: value,
                          sync_to_multiple_plex_users:
                            value === "jellyfin" ? false : prev.sync_to_multiple_plex_users,
                          plex_account_ids: value === "jellyfin" ? [] : prev.plex_account_ids,
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
                  </div>

                  {formData.target === "plex" && playlistType === "other" && (
                    <div className="space-y-2">
                      <label className="flex cursor-pointer items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.sync_to_multiple_plex_users}
                          onChange={(e) =>
                            setFormData((prev) => ({
                              ...prev,
                              sync_to_multiple_plex_users: e.target.checked,
                              plex_account_ids: e.target.checked ? prev.plex_account_ids : [],
                            }))
                          }
                          className="rounded border-input"
                        />
                        <span className="text-sm font-medium">Sync to multiple Plex users</span>
                      </label>
                      {formData.sync_to_multiple_plex_users && (
                        <div className="flex flex-wrap gap-3 rounded-lg border p-3">
                          {plexAccounts.map((acc) => (
                            <label
                              key={acc.id}
                              className="flex cursor-pointer items-center gap-2 text-sm"
                            >
                              <input
                                type="checkbox"
                                checked={formData.plex_account_ids.includes(acc.id)}
                                onChange={(e) =>
                                  setFormData((prev) => ({
                                    ...prev,
                                    plex_account_ids: e.target.checked
                                      ? [...prev.plex_account_ids, acc.id]
                                      : prev.plex_account_ids.filter((id) => id !== acc.id),
                                  }))
                                }
                                className="rounded border-input"
                              />
                              {acc.name || `Account ${acc.id}`}
                            </label>
                          ))}
                          {plexAccounts.length === 0 && (
                            <span className="text-sm text-muted-foreground">
                              No Plex accounts available
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}

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

                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="create-ext-schedule-override"
                        checked={formData.schedule_override}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            schedule_override: e.target.checked,
                          }))
                        }
                        className="rounded border-input"
                      />
                      <Label
                        htmlFor="create-ext-schedule-override"
                        className="cursor-pointer font-normal"
                      >
                        Override default schedule
                      </Label>
                    </div>
                    {formData.schedule_override && (
                      <>
                        <div className="space-y-2 rounded-lg border p-4">
                          <Input
                            placeholder="0 6 * * *"
                            value={formData.schedule_cron}
                            onChange={(e) =>
                              setFormData((prev) => ({ ...prev, schedule_cron: e.target.value }))
                            }
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Cron format: minute hour day month weekday (e.g. 0 6 * * * = daily at 6am)
                        </p>
                      </>
                    )}
                    {!formData.schedule_override && (
                      <p className="text-xs text-muted-foreground">
                        Uses global default (Config → Scheduler)
                      </p>
                    )}
                  </div>

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

                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="create-enable-artist-discovery"
                        checked={formData.enable_artist_discovery}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            enable_artist_discovery: e.target.checked,
                          }))
                        }
                        className="rounded border-input"
                      />
                      <Label
                        htmlFor="create-enable-artist-discovery"
                        className="cursor-pointer font-normal"
                      >
                        Add new artists
                      </Label>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Artists discovered missing from Lidarr are added to the Playlist Sync
                      Discovery import list. Discovery always runs to report counts; this controls
                      whether to add.
                    </p>
                    {formData.enable_artist_discovery && (
                      <div className="space-y-2 rounded-lg border p-4">
                        <Label htmlFor="create-artist-discovery-max">
                          Max artists to add per run
                        </Label>
                        <NumericInput
                          id="create-artist-discovery-max"
                          placeholder="2"
                          value={
                            formData.artist_discovery_max_per_run ??
                            (formData.enable_artist_discovery ? 2 : 0)
                          }
                          onChange={(v) =>
                            setFormData((prev) => ({
                              ...prev,
                              artist_discovery_max_per_run: v ?? 2,
                            }))
                          }
                          min={0}
                          max={50}
                          defaultValue={2}
                        />
                        <p className="text-xs text-muted-foreground">
                          0 = no limit. Limits how many new artists are added per sync run;
                          remaining artists are added on subsequent runs. First run adds none—only
                          reports count.
                        </p>
                      </div>
                    )}
                  </div>

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
              ) : playlistType === "xmplaylist" ? (
                "Create XMPlaylist"
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

}
