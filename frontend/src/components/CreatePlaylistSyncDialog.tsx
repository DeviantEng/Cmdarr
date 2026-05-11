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
  Users,
  Mic2,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ExpirationFields } from "@/components/ExpirationFields";
import { PlexPlaylistTargetSection } from "@/components/PlexPlaylistTargetSection";
import { toExpiresAtIso } from "@/lib/expiration";
import {
  commandUiCopy,
  isCompoundFieldVisible,
  resolveContextForCreate,
  PLAYLIST_TYPES_SKIP_COMMON_CREATE_SETTINGS,
} from "@/command-spec";
import { PlaylistSyncArtistDiscoveryControl } from "@/components/command-edit/PlaylistSyncArtistDiscoveryControl";

type PlaylistType =
  | "listenbrainz"
  | "other"
  | "daylist"
  | "top_tracks"
  | "lfm_similar"
  | "setlistfm"
  | "local_discovery"
  | "mood_playlist"
  | "xmplaylist";

/** @see PLAYLIST_TYPES_SKIP_COMMON_CREATE_SETTINGS in command-spec/createPlaylistSurface.ts */

type XmplaylistStationRow = {
  name: string;
  deeplink: string;
  number: number | null;
  label: string;
};

const cw = commandUiCopy.createWizard;
const sch = commandUiCopy.schedule;
const d = commandUiCopy.daylist;
const ld = commandUiCopy.localDiscovery;
const tt = commandUiCopy.topTracks;
const lf = commandUiCopy.lfmSimilar;
const sf = commandUiCopy.setlistFm;
const mood = commandUiCopy.moodPlaylist;
const xm = commandUiCopy.xmplaylist;
const lb = commandUiCopy.listenbrainz;
const ps = commandUiCopy.playlistSync;

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
    historical_ratio: 0.3,
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
    historical_ratio: 0.3,
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

  const [lfmSimilarForm, setLfmSimilarForm] = useState({
    seed_artists: "",
    similar_per_seed: 5,
    max_artists: 25,
    include_seeds: true,
    top_x: 5,
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

  const [setlistfmForm, setSetlistfmForm] = useState({
    artists: "",
    max_tracks_per_artist: 25,
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
    sync_to_multiple_plex_users: false,
    plex_account_ids: [] as string[],
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
        historical_ratio: 0.3,
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
        historical_ratio: 0.3,
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
        sync_to_multiple_plex_users: false,
        plex_account_ids: [],
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
    if (playlistType === "lfm_similar") {
      if (
        lfmSimilarForm.seed_artists
          .trim()
          .split("\n")
          .filter((a) => a.trim()).length === 0
      )
        return false;
      if (lfmSimilarForm.expires_at_enabled && !lfmSimilarForm.expires_at) return false;
      return true;
    }
    if (playlistType === "setlistfm") {
      if (
        setlistfmForm.artists
          .trim()
          .split("\n")
          .filter((a) => a.trim()).length === 0
      )
        return false;
      if (setlistfmForm.expires_at_enabled && !setlistfmForm.expires_at) return false;
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
      if (
        xmplaylistForm.target === "plex" &&
        xmplaylistForm.sync_to_multiple_plex_users &&
        xmplaylistForm.plex_account_ids.length === 0
      ) {
        return false;
      }
      return true;
    }
    if (
      playlistType === "other" &&
      formData.target === "plex" &&
      formData.sync_to_multiple_plex_users &&
      formData.plex_account_ids.length === 0
    ) {
      return false;
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
      } else if (playlistType === "lfm_similar") {
        const payload: Record<string, unknown> = {
          seed_artists: lfmSimilarForm.seed_artists
            .trim()
            .split("\n")
            .filter((a) => a.trim()),
          similar_per_seed: lfmSimilarForm.similar_per_seed,
          max_artists: lfmSimilarForm.max_artists,
          include_seeds: lfmSimilarForm.include_seeds,
          top_x: lfmSimilarForm.top_x,
          target: lfmSimilarForm.target,
          use_custom_playlist_name: lfmSimilarForm.use_custom_playlist_name,
          custom_playlist_name: lfmSimilarForm.custom_playlist_name,
          schedule_cron: lfmSimilarForm.schedule_override
            ? lfmSimilarForm.schedule_cron
            : undefined,
          enabled: lfmSimilarForm.enabled,
        };
        if (lfmSimilarForm.expires_at_enabled && lfmSimilarForm.expires_at) {
          payload.expires_at = toExpiresAtIso(lfmSimilarForm.expires_at);
          payload.expires_at_delete_playlist = lfmSimilarForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string; command_name: string }>(
          "/api/commands/lfm-similar/create",
          { method: "POST", body: JSON.stringify(payload) }
        );
        toast.success(response.message || "Last.fm Similar command created");
      } else if (playlistType === "setlistfm") {
        const payload: Record<string, unknown> = {
          artists: setlistfmForm.artists
            .trim()
            .split("\n")
            .filter((a) => a.trim()),
          max_tracks_per_artist: Math.max(3, Math.min(30, setlistfmForm.max_tracks_per_artist)),
          target: setlistfmForm.target,
          use_custom_playlist_name: setlistfmForm.use_custom_playlist_name,
          custom_playlist_name: setlistfmForm.custom_playlist_name,
          schedule_cron: setlistfmForm.schedule_override ? setlistfmForm.schedule_cron : undefined,
          enabled: setlistfmForm.enabled,
        };
        if (setlistfmForm.expires_at_enabled && setlistfmForm.expires_at) {
          payload.expires_at = toExpiresAtIso(setlistfmForm.expires_at);
          payload.expires_at_delete_playlist = setlistfmForm.expires_at_delete_playlist ?? true;
        }
        const response = await api.request<{ message: string; command_name: string }>(
          "/api/commands/setlistfm/create",
          { method: "POST", body: JSON.stringify(payload) }
        );
        toast.success(response.message || "Setlist.fm command created");
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
        if (
          xmplaylistForm.target === "plex" &&
          xmplaylistForm.sync_to_multiple_plex_users &&
          xmplaylistForm.plex_account_ids.length > 0
        ) {
          payload.plex_account_ids = xmplaylistForm.plex_account_ids;
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
              ? cw.titleChooseType
              : playlistType === "daylist"
                ? cw.titleDaylist
                : playlistType === "top_tracks"
                  ? cw.titleArtistEssentials
                  : playlistType === "lfm_similar"
                    ? cw.titleLfmSimilar
                    : playlistType === "setlistfm"
                      ? cw.titleSetlistFm
                      : playlistType === "local_discovery"
                        ? cw.titleLocalDiscovery
                        : playlistType === "mood_playlist"
                          ? cw.titleMoodPlaylist
                          : playlistType === "xmplaylist"
                            ? cw.titleXmplaylist
                            : playlistType === "listenbrainz"
                              ? cw.titleListenbrainz
                              : cw.titleExternal}
          </DialogTitle>
          <DialogDescription>
            {step === "type"
              ? cw.descChooseType
              : playlistType === "daylist"
                ? cw.descDaylist
                : playlistType === "top_tracks"
                  ? cw.descTopTracks
                  : playlistType === "lfm_similar"
                    ? cw.descLfmSimilar
                    : playlistType === "setlistfm"
                      ? cw.descSetlistFm
                      : playlistType === "local_discovery"
                        ? cw.descLocalDiscovery
                        : playlistType === "mood_playlist"
                          ? cw.descMoodPlaylist
                          : playlistType === "xmplaylist"
                            ? cw.descXmplaylist
                            : cw.descDefault}
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
                <h3 className="font-semibold">{cw.cardDaylistTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardDaylistBlurb}</p>
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
                <h3 className="font-semibold">{cw.cardLocalDiscoveryTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardLocalDiscoveryBlurb}</p>
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
                <h3 className="font-semibold">{cw.cardListenbrainzTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardListenbrainzBlurb}</p>
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
                <h3 className="font-semibold">{cw.cardExternalTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardExternalBlurb}</p>
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
                <h3 className="font-semibold">{cw.cardArtistEssentialsTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardArtistEssentialsBlurb}</p>
              </div>
            </button>

            {/* Last.fm Similar */}
            <button
              onClick={() => handleSelectType("lfm_similar")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900">
                <Users className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">{cw.cardLfmSimilarTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardLfmSimilarBlurb}</p>
              </div>
            </button>

            {/* Setlist.fm */}
            <button
              onClick={() => handleSelectType("setlistfm")}
              className="flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-rose-100 dark:bg-rose-900">
                <Mic2 className="h-5 w-5 text-rose-600 dark:text-rose-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold">{cw.cardSetlistFmTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardSetlistFmBlurb}</p>
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
                <h3 className="font-semibold">{cw.cardXmplaylistTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardXmplaylistBlurb}</p>
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
                <h3 className="font-semibold">{cw.cardMoodTitle}</h3>
                <p className="text-xs text-muted-foreground">{cw.cardMoodBlurb}</p>
              </div>
            </button>
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {playlistType === "listenbrainz" ? (
              <>
                {/* Playlist Types */}
                <div className="space-y-2">
                  <Label>{lb.playlistTypesLabel}</Label>
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
                  <Label>{lb.retentionHeading}</Label>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <Label className="text-xs">{lb.weeklyExploration}</Label>
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
                      <Label className="text-xs">{lb.weeklyJams}</Label>
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
                      <Label className="text-xs">{lb.dailyJams}</Label>
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
                  <p className="text-xs text-muted-foreground">{lb.retentionHelper}</p>
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
                  <span className="text-sm">{lb.cleanupCheckbox}</span>
                </label>
              </>
            ) : playlistType === "daylist" ? (
              <>
                {/* Primary settings */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>{d.plexAccountLabel}</Label>
                    <Select
                      value={daylistForm.plex_history_account_id}
                      onValueChange={(v) =>
                        setDaylistForm((prev) => ({ ...prev, plex_history_account_id: v }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={d.selectPlexPlaceholder} />
                      </SelectTrigger>
                      <SelectContent>
                        {plexAccounts.map((acc) => (
                          <SelectItem
                            key={acc.id}
                            value={acc.id}
                            disabled={daylistUsedIds.has(acc.id)}
                          >
                            {acc.name || `Account ${acc.id}`}
                            {daylistUsedIds.has(acc.id) ? d.accountSuffixInUse : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">{d.plexAccountHelp}</p>
                  </div>

                  <div className="space-y-2">
                    <Label>{d.runAtMinuteLabel}</Label>
                    <NumericInput
                      value={daylistForm.schedule_minute}
                      onChange={(v) =>
                        setDaylistForm((prev) => ({ ...prev, schedule_minute: v ?? 0 }))
                      }
                      min={0}
                      max={59}
                      defaultValue={0}
                    />
                    <p className="text-xs text-muted-foreground">{d.runAtMinuteHelp}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{d.excludePlayedLabel}</Label>
                      <NumericInput
                        value={daylistForm.exclude_played_days}
                        onChange={(v) =>
                          setDaylistForm((prev) => ({ ...prev, exclude_played_days: v ?? 3 }))
                        }
                        min={1}
                        max={30}
                        defaultValue={3}
                      />
                      <p className="text-xs text-muted-foreground">{d.excludePlayedHelp}</p>
                    </div>
                    <div className="space-y-2">
                      <Label>{d.historyLookbackLabel}</Label>
                      <NumericInput
                        value={daylistForm.history_lookback_days}
                        onChange={(v) =>
                          setDaylistForm((prev) => ({ ...prev, history_lookback_days: v ?? 45 }))
                        }
                        min={7}
                        max={365}
                        defaultValue={45}
                      />
                      <p className="text-xs text-muted-foreground">{d.historyLookbackHelp}</p>
                    </div>
                    <div className="space-y-2">
                      <Label>{d.maxTracksLabel}</Label>
                      <NumericInput
                        value={daylistForm.max_tracks}
                        onChange={(v) =>
                          setDaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))
                        }
                        min={10}
                        max={200}
                        defaultValue={50}
                      />
                      <p className="text-xs text-muted-foreground">{d.maxTracksHelp}</p>
                    </div>
                  </div>
                </div>

                {/* Advanced settings (collapsible) */}
                <details className="rounded-lg border p-4">
                  <summary className="cursor-pointer font-medium text-sm text-muted-foreground hover:text-foreground transition-colors">
                    {d.advancedSummary}
                  </summary>
                  <div className="mt-4 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>
                          {d.historicalRatioLabel} {daylistForm.historical_ratio}
                        </Label>
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
                        <p className="text-xs text-muted-foreground">{d.historicalRatioHelp}</p>
                      </div>
                      <div className="space-y-2">
                        <Label>{d.sonicSimilarLimitLabel}</Label>
                        <NumericInput
                          value={daylistForm.sonic_similar_limit}
                          onChange={(v) =>
                            setDaylistForm((prev) => ({ ...prev, sonic_similar_limit: v ?? 10 }))
                          }
                          min={1}
                          max={30}
                          defaultValue={10}
                        />
                        <p className="text-xs text-muted-foreground">{d.sonicSimilarLimitHelp}</p>
                      </div>
                      <div className="space-y-2">
                        <Label>{d.sonicSimilarPlaylistLimitLabel}</Label>
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
                          {d.sonicSimilarPlaylistLimitHelp}
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label>
                          {d.sonicSimilarDistanceLabel} {daylistForm.sonic_similarity_distance}
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
                          {d.sonicSimilarDistanceHelp}
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
                      <span className="text-sm">{d.usePrimaryMood}</span>
                    </label>
                    <p className="text-xs text-muted-foreground -mt-2">{d.usePrimaryMoodHelp}</p>

                    <div className="space-y-2">
                      <Label>{d.timezoneLabel}</Label>
                      <Input
                        placeholder={d.timezonePlaceholder}
                        value={daylistForm.timezone}
                        onChange={(e) =>
                          setDaylistForm((prev) => ({ ...prev, timezone: e.target.value }))
                        }
                      />
                      <p className="text-xs text-muted-foreground">{d.timezoneHelp}</p>
                    </div>

                    <div className="space-y-2">
                      <Label>{d.timePeriodsLabel}</Label>
                      <p className="text-xs text-muted-foreground mb-2">{d.timePeriodsHelp}</p>
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
                  <span className="text-sm">{cw.enableAfterCreation}</span>
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
                  <Label>{ld.plexAccountLabel}</Label>
                  <Select
                    value={localDiscoveryForm.plex_history_account_id}
                    onValueChange={(v) =>
                      setLocalDiscoveryForm((prev) => ({ ...prev, plex_history_account_id: v }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={ld.selectPlaceholder} />
                    </SelectTrigger>
                    <SelectContent>
                      {plexAccounts.map((acc) => (
                        <SelectItem
                          key={acc.id}
                          value={acc.id}
                          disabled={localDiscoveryUsedIds.has(acc.id)}
                        >
                          {acc.name || acc.id}
                          {localDiscoveryUsedIds.has(acc.id) ? ld.accountSuffixInUse : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">{ld.plexAccountHelp}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{ld.lookbackDaysLabel}</Label>
                    <NumericInput
                      value={localDiscoveryForm.lookback_days}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({ ...prev, lookback_days: v ?? 90 }))
                      }
                      min={7}
                      max={365}
                      defaultValue={90}
                    />
                    <p className="text-xs text-muted-foreground">{ld.lookbackDaysHelp}</p>
                  </div>
                  <div className="space-y-2">
                    <Label>{ld.excludePlayedLabel}</Label>
                    <NumericInput
                      value={localDiscoveryForm.exclude_played_days}
                      onChange={(v) =>
                        setLocalDiscoveryForm((prev) => ({ ...prev, exclude_played_days: v ?? 3 }))
                      }
                      min={0}
                      max={30}
                      defaultValue={3}
                    />
                    <p className="text-xs text-muted-foreground">{ld.excludePlayedHelp}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{ld.topArtistsCountLabel}</Label>
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
                    <p className="text-xs text-muted-foreground">{ld.topArtistsCountHelp}</p>
                  </div>
                  <div className="space-y-2">
                    <Label>{ld.artistPoolSizeLabel}</Label>
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
                    <p className="text-xs text-muted-foreground">{ld.artistPoolSizeHelp}</p>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>{ld.maxTracksLabel}</Label>
                  <NumericInput
                    value={localDiscoveryForm.max_tracks}
                    onChange={(v) =>
                      setLocalDiscoveryForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))
                    }
                    min={1}
                    max={200}
                    defaultValue={50}
                  />
                  <p className="text-xs text-muted-foreground">{ld.maxTracksHelp}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{ld.sonicSimilarLimitLabel}</Label>
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
                    <p className="text-xs text-muted-foreground">{ld.sonicSimilarLimitHelp}</p>
                  </div>
                  <div className="space-y-2">
                    <Label>
                      {ld.historicalRatioLabel} {localDiscoveryForm.historical_ratio}
                    </Label>
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
                    <p className="text-xs text-muted-foreground">{ld.historicalRatioHelp}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{ld.sonicSimilarityDistanceLabel}</Label>
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
                      {ld.sonicSimilarityDistanceHelp}
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
                    <Label htmlFor="create-ld-schedule-override">{sch.overrideLabel}</Label>
                  </div>
                  {localDiscoveryForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder={sch.createCronPlaceholder}
                          value={localDiscoveryForm.schedule_cron}
                          onChange={(e) =>
                            setLocalDiscoveryForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
                    </>
                  )}
                  {!localDiscoveryForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">{sch.usesGlobalDefault}</p>
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
                  <span className="text-sm">{cw.enableAfterCreation}</span>
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
                  <Label>{tt.artistsLabel}</Label>
                  <textarea
                    className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder={tt.artistsPlaceholder}
                    value={topTracksForm.artists}
                    onChange={(e) =>
                      setTopTracksForm((prev) => ({ ...prev, artists: e.target.value }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">{tt.artistsHelp}</p>
                </div>
                <div className="space-y-2">
                  <Label>{tt.topXLabelCreate}</Label>
                  <NumericInput
                    placeholder="5"
                    value={topTracksForm.top_x}
                    onChange={(v) => setTopTracksForm((prev) => ({ ...prev, top_x: v ?? 5 }))}
                    min={1}
                    max={20}
                    defaultValue={5}
                  />
                  <p className="text-xs text-muted-foreground">{tt.topXHelp}</p>
                </div>
                <div className="space-y-2">
                  <Label>{tt.targetLabel}</Label>
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
                  <p className="text-xs text-muted-foreground">{tt.targetWhereHelp}</p>
                </div>
                <div className="space-y-2">
                  <Label>{tt.sourceLabelCreate}</Label>
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
                      <SelectItem value="plex">{tt.plexOptionRating}</SelectItem>
                      <SelectItem value="lastfm">{tt.lastfmOption}</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">{tt.sourceHelp}</p>
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
                  <span className="text-sm">{tt.useCustomPlaylistName}</span>
                </label>
                {topTracksForm.use_custom_playlist_name && (
                  <div className="space-y-2">
                    <Label>{tt.customPlaylistNameLabel}</Label>
                    <Input
                      value={topTracksForm.custom_playlist_name}
                      onChange={(e) =>
                        setTopTracksForm((prev) => ({
                          ...prev,
                          custom_playlist_name: e.target.value,
                        }))
                      }
                      placeholder={tt.customPlaylistPlaceholder}
                    />
                    <p className="text-xs text-muted-foreground">{tt.customPlaylistNameHelper}</p>
                  </div>
                )}
                {!topTracksForm.use_custom_playlist_name && (
                  <p className="text-xs text-muted-foreground">{tt.autoNameHelp}</p>
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
                    <Label htmlFor="create-tt-schedule-override">{sch.overrideLabel}</Label>
                  </div>
                  {topTracksForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder={sch.createCronPlaceholder}
                          value={topTracksForm.schedule_cron}
                          onChange={(e) =>
                            setTopTracksForm((prev) => ({ ...prev, schedule_cron: e.target.value }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
                    </>
                  )}
                  {!topTracksForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">{sch.usesGlobalDefault}</p>
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
                  <span className="text-sm">{cw.enableAfterCreation}</span>
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
            ) : playlistType === "lfm_similar" ? (
              <>
                <div className="space-y-2">
                  <Label>{lf.seedArtistsLabel}</Label>
                  <textarea
                    className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder={lf.seedArtistsPlaceholder}
                    value={lfmSimilarForm.seed_artists}
                    onChange={(e) =>
                      setLfmSimilarForm((prev) => ({ ...prev, seed_artists: e.target.value }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">{lf.seedArtistsHelp}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{lf.similarPerSeedLabel}</Label>
                    <NumericInput
                      placeholder="5"
                      value={lfmSimilarForm.similar_per_seed}
                      onChange={(v) =>
                        setLfmSimilarForm((prev) => ({ ...prev, similar_per_seed: v ?? 5 }))
                      }
                      min={1}
                      max={50}
                      defaultValue={5}
                    />
                    <p className="text-xs text-muted-foreground">{lf.similarPerSeedHelp}</p>
                  </div>
                  <div className="space-y-2">
                    <Label>{lf.maxArtistsLabel}</Label>
                    <NumericInput
                      placeholder="25"
                      value={lfmSimilarForm.max_artists}
                      onChange={(v) =>
                        setLfmSimilarForm((prev) => ({ ...prev, max_artists: v ?? 25 }))
                      }
                      min={1}
                      max={200}
                      defaultValue={25}
                    />
                    <p className="text-xs text-muted-foreground">{lf.maxArtistsHelp}</p>
                  </div>
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={lfmSimilarForm.include_seeds}
                    onChange={(e) =>
                      setLfmSimilarForm((prev) => ({ ...prev, include_seeds: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">{lf.includeSeedsLabel}</span>
                </label>
                <p className="text-xs text-muted-foreground">{lf.includeSeedsHelp}</p>
                <div className="space-y-2">
                  <Label>{lf.topXLabel}</Label>
                  <NumericInput
                    placeholder="5"
                    value={lfmSimilarForm.top_x}
                    onChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, top_x: v ?? 5 }))}
                    min={1}
                    max={20}
                    defaultValue={5}
                  />
                  <p className="text-xs text-muted-foreground">{lf.topXHelp}</p>
                </div>
                <div className="space-y-2">
                  <Label>{lf.targetLabel}</Label>
                  <Select
                    value={lfmSimilarForm.target}
                    onValueChange={(v: "plex" | "jellyfin") =>
                      setLfmSimilarForm((prev) => ({ ...prev, target: v }))
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
                  <p className="text-xs text-muted-foreground">{lf.targetWhereHelp}</p>
                </div>
                <p className="text-xs text-muted-foreground">{lf.lastfmNote}</p>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={lfmSimilarForm.use_custom_playlist_name}
                    onChange={(e) =>
                      setLfmSimilarForm((prev) => ({
                        ...prev,
                        use_custom_playlist_name: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">{lf.useCustomPlaylistName}</span>
                </label>
                {lfmSimilarForm.use_custom_playlist_name && (
                  <div className="space-y-2">
                    <Label>{lf.customPlaylistNameLabel}</Label>
                    <Input
                      value={lfmSimilarForm.custom_playlist_name}
                      onChange={(e) =>
                        setLfmSimilarForm((prev) => ({
                          ...prev,
                          custom_playlist_name: e.target.value,
                        }))
                      }
                      placeholder={lf.customPlaylistPlaceholder}
                    />
                    <p className="text-xs text-muted-foreground">{lf.customPlaylistNameHelper}</p>
                  </div>
                )}
                {!lfmSimilarForm.use_custom_playlist_name && (
                  <p className="text-xs text-muted-foreground">{lf.autoNameHelp}</p>
                )}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-lf-schedule-override"
                      checked={lfmSimilarForm.schedule_override}
                      onChange={(e) =>
                        setLfmSimilarForm((prev) => ({
                          ...prev,
                          schedule_override: e.target.checked,
                        }))
                      }
                      className="rounded border-input"
                    />
                    <Label htmlFor="create-lf-schedule-override">{sch.overrideLabel}</Label>
                  </div>
                  {lfmSimilarForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder={sch.createCronPlaceholder}
                          value={lfmSimilarForm.schedule_cron}
                          onChange={(e) =>
                            setLfmSimilarForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
                    </>
                  )}
                  {!lfmSimilarForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">{sch.usesGlobalDefault}</p>
                  )}
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={lfmSimilarForm.enabled}
                    onChange={(e) =>
                      setLfmSimilarForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">{cw.enableAfterCreation}</span>
                </label>
                <ExpirationFields
                  idPrefix="create-lf"
                  enabled={lfmSimilarForm.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setLfmSimilarForm((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={lfmSimilarForm.expires_at}
                  onValueChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, expires_at: v }))}
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={lfmSimilarForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setLfmSimilarForm((prev) => ({
                      ...prev,
                      expires_at_delete_playlist: v,
                    }))
                  }
                />
              </>
            ) : playlistType === "setlistfm" ? (
              <>
                <div className="space-y-2">
                  <Label>{sf.artistsLabel}</Label>
                  <textarea
                    className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder={sf.artistsPlaceholder}
                    value={setlistfmForm.artists}
                    onChange={(e) =>
                      setSetlistfmForm((prev) => ({ ...prev, artists: e.target.value }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">{sf.artistsHelp}</p>
                </div>
                <div className="space-y-2">
                  <Label>{sf.maxTracksPerArtistLabel}</Label>
                  <NumericInput
                    placeholder="25"
                    value={setlistfmForm.max_tracks_per_artist}
                    onChange={(v) =>
                      setSetlistfmForm((prev) => ({
                        ...prev,
                        max_tracks_per_artist: v ?? 25,
                      }))
                    }
                    min={3}
                    max={30}
                    defaultValue={25}
                  />
                  <p className="text-xs text-muted-foreground">{sf.maxTracksPerArtistHelp}</p>
                  <p className="text-xs text-muted-foreground">{sf.setlistDiscoveryHelp}</p>
                </div>
                <div className="space-y-2">
                  <Label>{sf.targetLabel}</Label>
                  <Select
                    value={setlistfmForm.target}
                    onValueChange={(v: "plex" | "jellyfin") =>
                      setSetlistfmForm((prev) => ({ ...prev, target: v }))
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
                  <p className="text-xs text-muted-foreground">{sf.targetWhereHelp}</p>
                </div>
                <p className="text-xs text-muted-foreground">{sf.setlistNote}</p>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={setlistfmForm.use_custom_playlist_name}
                    onChange={(e) =>
                      setSetlistfmForm((prev) => ({
                        ...prev,
                        use_custom_playlist_name: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">{sf.useCustomPlaylistName}</span>
                </label>
                {setlistfmForm.use_custom_playlist_name && (
                  <div className="space-y-2">
                    <Label>{sf.customPlaylistNameLabel}</Label>
                    <Input
                      value={setlistfmForm.custom_playlist_name}
                      onChange={(e) =>
                        setSetlistfmForm((prev) => ({
                          ...prev,
                          custom_playlist_name: e.target.value,
                        }))
                      }
                      placeholder={sf.customPlaylistPlaceholder}
                    />
                    <p className="text-xs text-muted-foreground">{sf.customPlaylistNameHelper}</p>
                  </div>
                )}
                {!setlistfmForm.use_custom_playlist_name && (
                  <p className="text-xs text-muted-foreground">{sf.autoNameHelp}</p>
                )}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="create-sf-schedule-override"
                      checked={setlistfmForm.schedule_override}
                      onChange={(e) =>
                        setSetlistfmForm((prev) => ({
                          ...prev,
                          schedule_override: e.target.checked,
                        }))
                      }
                      className="rounded border-input"
                    />
                    <Label htmlFor="create-sf-schedule-override">{sch.overrideLabel}</Label>
                  </div>
                  {setlistfmForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder={sch.createCronPlaceholder}
                          value={setlistfmForm.schedule_cron}
                          onChange={(e) =>
                            setSetlistfmForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
                    </>
                  )}
                  {!setlistfmForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">{sch.usesGlobalDefault}</p>
                  )}
                </div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={setlistfmForm.enabled}
                    onChange={(e) =>
                      setSetlistfmForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">{cw.enableAfterCreation}</span>
                </label>
                <ExpirationFields
                  idPrefix="create-sf"
                  enabled={setlistfmForm.expires_at_enabled}
                  onEnabledChange={(v) =>
                    setSetlistfmForm((prev) => ({
                      ...prev,
                      expires_at_enabled: v,
                      expires_at: v && !prev.expires_at ? "" : prev.expires_at,
                    }))
                  }
                  value={setlistfmForm.expires_at}
                  onValueChange={(v) => setSetlistfmForm((prev) => ({ ...prev, expires_at: v }))}
                  showDeletePlaylistOption={true}
                  deletePlaylistOnExpiry={setlistfmForm.expires_at_delete_playlist ?? true}
                  onDeletePlaylistChange={(v) =>
                    setSetlistfmForm((prev) => ({
                      ...prev,
                      expires_at_delete_playlist: v,
                    }))
                  }
                />
              </>
            ) : playlistType === "mood_playlist" ? (
              <>
                <div className="space-y-2">
                  <Label>{mood.moodsHeading}</Label>
                  <div className="max-h-[200px] overflow-y-auto rounded-md border border-input p-2">
                    {moodsList.length === 0 ? (
                      <p className="text-sm text-muted-foreground">{mood.loadingMoods}</p>
                    ) : (
                      <div className="grid grid-cols-3 gap-1">
                        {moodsList.map((moodName) => (
                          <label key={moodName} className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={moodPlaylistForm.moods.includes(moodName)}
                              onChange={() => handleToggleMood(moodName)}
                              className="rounded border-gray-300"
                            />
                            <span className="text-sm">{moodName}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">{mood.rankingHelper}</p>
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
                  <span className="text-sm">{mood.useCustomPlaylistName}</span>
                </label>
                {moodPlaylistForm.use_custom_playlist_name && (
                  <div className="space-y-2">
                    <Label>{mood.customPlaylistNameLabel}</Label>
                    <Input
                      value={moodPlaylistForm.custom_playlist_name}
                      onChange={(e) =>
                        setMoodPlaylistForm((prev) => ({
                          ...prev,
                          custom_playlist_name: e.target.value,
                        }))
                      }
                      placeholder={mood.customPlaylistPlaceholder}
                    />
                    <p className="text-xs text-muted-foreground">{mood.customPlaylistNameHelper}</p>
                  </div>
                )}
                {!moodPlaylistForm.use_custom_playlist_name && (
                  <p className="text-xs text-muted-foreground">{mood.autoNameHelp}</p>
                )}
                <div className="space-y-2">
                  <Label>{mood.maxTracksLabel}</Label>
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
                  <p className="text-xs text-muted-foreground">{mood.maxTracksHelp}</p>
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
                  <span className="text-sm">{mood.forceFresh}</span>
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
                  <span className="text-sm">{mood.limitByYear}</span>
                </label>
                {moodPlaylistForm.limit_by_year && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{mood.minYear}</Label>
                      <NumericInput
                        placeholder={mood.minYearPlaceholder}
                        value={moodPlaylistForm.min_year}
                        onChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, min_year: v }))}
                        min={1800}
                        max={2100}
                        defaultValue={1800}
                        allowEmpty
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{mood.maxYear}</Label>
                      <NumericInput
                        placeholder={mood.maxYearPlaceholder}
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
                  <p className="text-xs text-muted-foreground">{mood.yearRangeHelp}</p>
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
                    <Label htmlFor="create-mood-schedule-override">{sch.overrideLabel}</Label>
                  </div>
                  {moodPlaylistForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder={sch.createCronPlaceholder}
                          value={moodPlaylistForm.schedule_cron}
                          onChange={(e) =>
                            setMoodPlaylistForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
                    </>
                  )}
                  {!moodPlaylistForm.schedule_override && (
                    <p className="text-xs text-muted-foreground">{sch.usesGlobalDefault}</p>
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
                  <span className="text-sm">{cw.enableAfterCreation}</span>
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
                  <Label>{xm.stationLabel}</Label>
                  <p className="text-xs text-muted-foreground">{xm.stationSearchHint}</p>
                  {xmplaylistForm.station_label ? (
                    <p className="text-sm font-medium">
                      {xm.selectedStationLabel} {xmplaylistForm.station_label}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">{xm.noStationSelected}</p>
                  )}
                  <Input
                    placeholder={xm.filterStationsPlaceholder}
                    value={xmplaylistStationFilter}
                    onChange={(e) => setXmplaylistStationFilter(e.target.value)}
                    disabled={xmplaylistStationsLoading}
                  />
                  <div className="max-h-40 overflow-y-auto rounded-md border border-input">
                    {xmplaylistStationsLoading ? (
                      <p className="p-3 text-sm text-muted-foreground">{xm.loadingStations}</p>
                    ) : filteredXmStations.length === 0 ? (
                      <p className="p-3 text-sm text-muted-foreground">{xm.noStationsMatch}</p>
                    ) : (
                      filteredXmStations.map((s) => (
                        <button
                          key={s.deeplink}
                          type="button"
                          className="block w-full border-b border-border px-3 py-1.5 text-left text-sm last:border-b-0 hover:bg-accent"
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
                  <Label>{xm.playlistSourceLabel}</Label>
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
                      <SelectItem value="newest">{xm.newestTracksOption}</SelectItem>
                      <SelectItem value="most_heard">{xm.mostPlayedOption}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {xmplaylistForm.playlist_kind === "most_heard" && (
                  <div className="space-y-2">
                    <Label>{xm.timePeriodLabel}</Label>
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
                        <SelectItem value="1">{xm.period1Day}</SelectItem>
                        <SelectItem value="7">{xm.period7Days}</SelectItem>
                        <SelectItem value="14">{xm.period14Days}</SelectItem>
                        <SelectItem value="30">{xm.period30Days}</SelectItem>
                        <SelectItem value="60">{xm.period60Days}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="space-y-2">
                  <Label>{xm.maxTracksInPlaylistLabel}</Label>
                  <NumericInput
                    value={xmplaylistForm.max_tracks}
                    onChange={(v) =>
                      setXmplaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))
                    }
                    min={1}
                    max={50}
                    defaultValue={50}
                  />
                  <p className="text-xs text-muted-foreground">{xm.maxTracksHelpRange}</p>
                </div>
                <div className="space-y-2">
                  <Label>{ps.targetLabel}</Label>
                  <Select
                    value={xmplaylistForm.target}
                    onValueChange={(v: "plex" | "jellyfin") =>
                      setXmplaylistForm((prev) => ({
                        ...prev,
                        target: v,
                        sync_to_multiple_plex_users:
                          v === "jellyfin" ? false : prev.sync_to_multiple_plex_users,
                        plex_account_ids: v === "jellyfin" ? [] : prev.plex_account_ids,
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
                {isCompoundFieldVisible(
                  "compound.plex_playlist_target",
                  resolveContextForCreate({
                    playlistType: "xmplaylist",
                    target: xmplaylistForm.target,
                  })
                ) && (
                  <PlexPlaylistTargetSection
                    accounts={plexAccounts}
                    syncToMultiple={xmplaylistForm.sync_to_multiple_plex_users}
                    selectedAccountIds={xmplaylistForm.plex_account_ids}
                    onSyncToMultipleChange={(checked) =>
                      setXmplaylistForm((prev) => ({
                        ...prev,
                        sync_to_multiple_plex_users: checked,
                        plex_account_ids: checked ? prev.plex_account_ids : [],
                      }))
                    }
                    onToggleAccount={(accountId, selected) =>
                      setXmplaylistForm((prev) => ({
                        ...prev,
                        plex_account_ids: selected
                          ? [...prev.plex_account_ids, accountId]
                          : prev.plex_account_ids.filter((id) => id !== accountId),
                      }))
                    }
                  />
                )}
                {isCompoundFieldVisible(
                  "compound.artist_discovery",
                  resolveContextForCreate({
                    playlistType: "xmplaylist",
                    target: xmplaylistForm.target,
                  })
                ) && (
                  <PlaylistSyncArtistDiscoveryControl
                    checkboxId="create-xm-artist-discovery"
                    value={{
                      enable_artist_discovery: xmplaylistForm.enable_artist_discovery,
                      artist_discovery_max_per_run:
                        xmplaylistForm.artist_discovery_max_per_run ?? 2,
                    }}
                    onChange={(next) =>
                      setXmplaylistForm((prev) => ({
                        ...prev,
                        enable_artist_discovery: next.enable_artist_discovery,
                        artist_discovery_max_per_run: next.artist_discovery_max_per_run,
                      }))
                    }
                  />
                )}
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
                    <Label htmlFor="create-xm-schedule-override">{sch.overrideLabel}</Label>
                  </div>
                  {xmplaylistForm.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder={sch.createCronPlaceholder}
                          value={xmplaylistForm.schedule_cron}
                          onChange={(e) =>
                            setXmplaylistForm((prev) => ({
                              ...prev,
                              schedule_cron: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
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
                  <span className="text-sm">{cw.enableAfterCreation}</span>
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
                  <Label>{ps.playlistUrlLabel}</Label>
                  <div className="relative">
                    <Input
                      type="url"
                      placeholder={ps.playlistUrlPlaceholder}
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
                  <p className="text-xs text-muted-foreground">{ps.publicSourcesHelp}</p>
                </div>
              </>
            )}

            {/* Common Settings (hidden when a dedicated form above already covers these fields) */}
            {!(PLAYLIST_TYPES_SKIP_COMMON_CREATE_SETTINGS as readonly string[]).includes(
              playlistType
            ) && (
              <>
                <div className="space-y-2">
                  <Label>{ps.targetLabel}</Label>
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

                {isCompoundFieldVisible(
                  "compound.plex_playlist_target",
                  resolveContextForCreate({
                    playlistType,
                    target: formData.target,
                  })
                ) && (
                  <PlexPlaylistTargetSection
                    accounts={plexAccounts}
                    syncToMultiple={formData.sync_to_multiple_plex_users}
                    selectedAccountIds={formData.plex_account_ids}
                    onSyncToMultipleChange={(checked) =>
                      setFormData((prev) => ({
                        ...prev,
                        sync_to_multiple_plex_users: checked,
                        plex_account_ids: checked ? prev.plex_account_ids : [],
                      }))
                    }
                    onToggleAccount={(accountId, selected) =>
                      setFormData((prev) => ({
                        ...prev,
                        plex_account_ids: selected
                          ? [...prev.plex_account_ids, accountId]
                          : prev.plex_account_ids.filter((id) => id !== accountId),
                      }))
                    }
                  />
                )}

                <div className="space-y-2">
                  <Label>{ps.syncModeLabel}</Label>
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
                      <SelectItem value="full">{ps.syncModeFull}</SelectItem>
                      <SelectItem value="append">{ps.syncModeAppend}</SelectItem>
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
                      {sch.overrideLabel}
                    </Label>
                  </div>
                  {formData.schedule_override && (
                    <>
                      <div className="space-y-2 rounded-lg border p-4">
                        <Input
                          placeholder={sch.createCronPlaceholder}
                          value={formData.schedule_cron}
                          onChange={(e) =>
                            setFormData((prev) => ({ ...prev, schedule_cron: e.target.value }))
                          }
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
                    </>
                  )}
                  {!formData.schedule_override && (
                    <p className="text-xs text-muted-foreground">{sch.usesGlobalDefault}</p>
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
                  <span className="text-sm">{cw.enableAfterCreation}</span>
                </label>

                {isCompoundFieldVisible(
                  "compound.artist_discovery",
                  resolveContextForCreate({
                    playlistType,
                    target: formData.target,
                  })
                ) && (
                  <PlaylistSyncArtistDiscoveryControl
                    checkboxId="create-enable-artist-discovery"
                    value={{
                      enable_artist_discovery: formData.enable_artist_discovery,
                      artist_discovery_max_per_run:
                        formData.artist_discovery_max_per_run ??
                        (formData.enable_artist_discovery ? 2 : 0),
                    }}
                    onChange={(next) =>
                      setFormData((prev) => ({
                        ...prev,
                        enable_artist_discovery: next.enable_artist_discovery,
                        artist_discovery_max_per_run: next.artist_discovery_max_per_run,
                      }))
                    }
                  />
                )}

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
                  {cw.submitCreating}
                </>
              ) : playlistType === "daylist" ? (
                cw.submitDaylist
              ) : playlistType === "top_tracks" ? (
                cw.submitArtistEssentials
              ) : playlistType === "lfm_similar" ? (
                cw.submitLfmSimilar
              ) : playlistType === "setlistfm" ? (
                cw.submitSetlistFm
              ) : playlistType === "local_discovery" ? (
                cw.submitLocalDiscovery
              ) : playlistType === "xmplaylist" ? (
                cw.submitXmplaylist
              ) : playlistType === "mood_playlist" ? (
                cw.submitMoodPlaylist
              ) : (
                cw.submitPlaylistSync
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
