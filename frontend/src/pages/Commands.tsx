import { useState, useEffect, useMemo } from "react";
import {
  LayoutGrid,
  List,
  Play,
  Pencil,
  Trash2,
  MoreVertical,
  Plus,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  X,
  Trash,
} from "lucide-react";
import { api } from "@/lib/api";
import type { CommandConfig, CommandExecution } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import { PlexPlaylistTargetSection } from "@/components/PlexPlaylistTargetSection";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CreatePlaylistSyncDialog } from "@/components/CreatePlaylistSyncDialog";
import { ExpirationFields } from "@/components/ExpirationFields";
import { fromExpiresAtIso, toExpiresAtIso } from "@/lib/expiration";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

type ViewMode = "card" | "list";
type SortField = "name" | "status" | "type" | "schedule" | "last_run";
type SortDirection = "asc" | "desc";

const BUILTIN_COMMANDS = [
  "discovery_lastfm",
  "library_cache_builder",
  "new_releases_discovery",
  "playlist_sync_discovery_maintenance",
];

const VIEW_MODE_KEY = "cmdarr_commands_view_mode";

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

function hoursToRange(hours: number[]): { start: number; end: number } {
  if (hours.length === 0) return { start: 0, end: 0 };
  const low = hours.filter((h) => h < 12);
  const high = hours.filter((h) => h >= 12);
  if (low.length > 0 && high.length > 0) return { start: Math.min(...high), end: Math.max(...low) };
  return { start: Math.min(...hours), end: Math.max(...hours) };
}

function getStoredViewMode(): ViewMode {
  try {
    const stored = localStorage.getItem(VIEW_MODE_KEY);
    if (stored === "card" || stored === "list") return stored;
  } catch {
    /* ignore */
  }
  return "card";
}

export function CommandsPage() {
  const [commands, setCommands] = useState<CommandConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>(getStoredViewMode);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "enabled" | "disabled">("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const SortIcon = ({ column }: { column: SortField }) => {
    if (sortField !== column) return <span className="inline-block w-4" />;
    return sortDirection === "asc" ? (
      <ChevronUp className="ml-1 inline h-4 w-4" />
    ) : (
      <ChevronDown className="ml-1 inline h-4 w-4" />
    );
  };
  const [showNewCommandDialog, setShowNewCommandDialog] = useState(false);
  const [editingCommand, setEditingCommand] = useState<CommandConfig | null>(null);
  const [editForm, setEditForm] = useState<{
    schedule_override?: boolean;
    schedule_cron?: string;
    artists_per_run?: number;
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
    top_x?: number;
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
  }>({});
  const [plexAccounts, setPlexAccounts] = useState<{ id: string; name: string }[]>([]);
  const [daylistUsedIds, setDaylistUsedIds] = useState<Set<string>>(new Set());
  const [localDiscoveryUsedIds, setLocalDiscoveryUsedIds] = useState<Set<string>>(new Set());
  const [moodsList, setMoodsList] = useState<string[]>([]);
  type XmplaylistStationRow = {
    name: string;
    deeplink: string;
    number: number | null;
    label: string;
  };
  const [xmplaylistEditStations, setXmplaylistEditStations] = useState<XmplaylistStationRow[]>([]);
  const [xmplaylistEditLoading, setXmplaylistEditLoading] = useState(false);
  const [xmplaylistEditFilter, setXmplaylistEditFilter] = useState("");
  const filteredXmEditStations = useMemo(() => {
    const q = xmplaylistEditFilter.trim().toLowerCase();
    if (!q) return xmplaylistEditStations;
    return xmplaylistEditStations.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.deeplink.includes(q) ||
        (s.number != null && String(s.number).includes(q))
    );
  }, [xmplaylistEditStations, xmplaylistEditFilter]);
  const [recentExecutions, setRecentExecutions] = useState<CommandExecution[]>([]);
  const [expandedExecutionId, setExpandedExecutionId] = useState<number | null>(null);
  const [killingExecutionId, setKillingExecutionId] = useState<number | null>(null);
  const [nrdSources, setNrdSources] = useState<{ id: string; name: string; configured: boolean }[]>(
    []
  );

  useEffect(() => {
    loadCommands();
    loadExecutions();
  }, []);

  useEffect(() => {
    if (editingCommand?.command_name === "new_releases_discovery") {
      api
        .request<{ sources: { id: string; name: string; configured: boolean }[] }>(
          "/api/commands/new-releases-sources"
        )
        .then((r) => setNrdSources(r.sources || []))
        .catch(() => setNrdSources([]));
    } else {
      setNrdSources([]);
    }
  }, [editingCommand?.command_name]);

  useEffect(() => {
    if (
      editingCommand?.command_name === "new_releases_discovery" &&
      nrdSources.length > 0 &&
      editForm.new_releases_source === "spotify"
    ) {
      const spotifySrc = nrdSources.find((s) => s.id === "spotify");
      if (spotifySrc && !spotifySrc.configured) {
        setEditForm((f) => ({ ...f, new_releases_source: "deezer" }));
      }
    }
  }, [editingCommand?.command_name, nrdSources, editForm.new_releases_source]);

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_MODE_KEY, viewMode);
    } catch {
      /* ignore */
    }
  }, [viewMode]);

  const loadExecutions = async () => {
    try {
      const data = await api.getAllExecutions(50);
      setRecentExecutions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Error loading executions:", err);
    }
  };

  // Poll executions every 10s when commands are running; pause when edit dialog is open
  useEffect(() => {
    const hasRunning = recentExecutions.some((e) => e.status === "running");
    if (!hasRunning || editingCommand) return;
    const id = setInterval(loadExecutions, 10000);
    return () => clearInterval(id);
  }, [recentExecutions, editingCommand]);

  // Auto-refresh commands every 5s; pause when edit or create dialog is open
  useEffect(() => {
    if (editingCommand || showNewCommandDialog) return;
    const id = setInterval(loadCommands, 5000);
    return () => clearInterval(id);
  }, [editingCommand, showNewCommandDialog]);

  const getCommandDisplayName = (commandName: string) => {
    const cmd = commands.find((c) => c.command_name === commandName);
    return cmd?.display_name || commandName.replace(/_/g, " ");
  };

  const formatDuration = (seconds?: number) => {
    if (seconds == null) return "In progress";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return s > 0 ? `${m}m ${s}s` : `${m}m`;
  };

  const handleKillExecution = async (executionId: number) => {
    try {
      setKillingExecutionId(executionId);
      await api.killExecution(executionId);
      toast.success("Execution cancelled");
      loadCommands();
      loadExecutions();
    } catch {
      toast.error("Failed to cancel execution");
    } finally {
      setKillingExecutionId(null);
    }
  };

  const handleDeleteExecution = async (executionId: number) => {
    try {
      await api.deleteExecution(executionId);
      toast.success("Execution deleted");
      loadExecutions();
    } catch {
      toast.error("Failed to delete execution");
    }
  };

  const handleCleanupExecutions = async () => {
    try {
      const result = await api.cleanupExecutions(undefined, 50);
      toast.success(
        result.deleted_count ? `Cleaned up ${result.deleted_count} old executions` : result.message
      );
      loadExecutions();
    } catch {
      toast.error("Failed to cleanup executions");
    }
  };

  const loadCommands = async () => {
    try {
      setError(null);
      console.log("Loading commands...");
      const data = await api.getCommands();
      console.log("Commands loaded:", data);
      // Ensure we always have an array
      setCommands(Array.isArray(data) ? data : []);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "Failed to load commands";
      setError(errorMsg);
      toast.error(errorMsg);
      console.error("Error loading commands:", error);
      setCommands([]); // Ensure commands is always an array
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async (command: CommandConfig) => {
    try {
      const result = await api.executeCommand(command.command_name, { triggered_by: "manual" });
      const displayName = command.display_name || command.command_name;
      toast.success(result?.message || `Command "${displayName}" started`);
      loadCommands();
      loadExecutions();
    } catch (error) {
      toast.error(`Failed to execute command`);
      console.error(error);
    }
  };

  const handleToggleEnabled = async (command: CommandConfig) => {
    try {
      await api.updateCommand(command.command_name, { enabled: !command.enabled });
      toast.success(`Command ${command.enabled ? "disabled" : "enabled"}`);
      await loadCommands();
      if (editingCommand?.command_name === command.command_name) {
        const updated = (await api.getCommands()).find(
          (c) => c.command_name === command.command_name
        );
        if (updated) setEditingCommand(updated);
      }
    } catch (error) {
      toast.error("Failed to update command");
      console.error(error);
    }
  };

  const handleEdit = (command: CommandConfig) => {
    setEditingCommand(command);
    const cfg = command.config_json || {};
    const typesStr = (cfg.album_types as string) || "album";
    const src = (cfg.new_releases_source as string) || "deezer";
    const isDaylist = command.command_name.startsWith("daylist_");

    const timePeriods: Record<string, { start: number; end: number }> = {
      ...DEFAULT_DAYLIST_TIME_PERIODS,
    };
    const storedPeriods = cfg.time_periods as Record<string, number[]> | undefined;
    if (storedPeriods && typeof storedPeriods === "object") {
      for (const [period, hours] of Object.entries(storedPeriods)) {
        if (Array.isArray(hours) && hours.length > 0) {
          timePeriods[period] = hoursToRange(hours);
        }
      }
    }

    const cfgPlexIdsRaw = Array.isArray(cfg.plex_account_ids) ? cfg.plex_account_ids.map(String) : [];
    let syncMultiPlex = cfgPlexIdsRaw.length > 0;
    let plexAccountIdsList = cfgPlexIdsRaw;
    if (command.command_name.startsWith("xmplaylist_")) {
      const legacyPlexPlaylistId = String(cfg.plex_playlist_account_id ?? "").trim();
      if (cfgPlexIdsRaw.length === 0 && legacyPlexPlaylistId) {
        syncMultiPlex = true;
        plexAccountIdsList = [legacyPlexPlaylistId];
      }
    }

    setEditForm({
      schedule_override: !!command.schedule_override,
      schedule_cron: command.schedule_cron || "0 3 * * *",
      artists_per_run: typeof cfg.artists_per_run === "number" ? cfg.artists_per_run : 5,
      album_types: typesStr
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
      new_releases_source: src === "spotify" ? "spotify" : "deezer",
      artists_to_query: typeof cfg.artists_to_query === "number" ? cfg.artists_to_query : 3,
      similar_per_artist: typeof cfg.similar_per_artist === "number" ? cfg.similar_per_artist : 1,
      artist_cooldown_days:
        typeof cfg.artist_cooldown_days === "number" ? cfg.artist_cooldown_days : 30,
      limit: typeof cfg.limit === "number" ? cfg.limit : 5,
      min_match_score: typeof cfg.min_match_score === "number" ? cfg.min_match_score : 0.9,
      enable_artist_discovery: !!cfg.enable_artist_discovery,
      artist_discovery_max_per_run:
        typeof cfg.artist_discovery_max_per_run === "number" ? cfg.artist_discovery_max_per_run : 2,
      schedule_minute: typeof cfg.schedule_minute === "number" ? cfg.schedule_minute : 0,
      plex_history_account_id: (cfg.plex_history_account_id ?? "") as string,
      exclude_played_days:
        typeof cfg.exclude_played_days === "number" ? cfg.exclude_played_days : 3,
      history_lookback_days:
        typeof cfg.history_lookback_days === "number" ? cfg.history_lookback_days : 45,
      max_tracks: typeof cfg.max_tracks === "number" ? cfg.max_tracks : 50,
      sonic_similar_limit:
        typeof cfg.sonic_similar_limit === "number" ? cfg.sonic_similar_limit : 10,
      sonic_similarity_limit:
        typeof cfg.sonic_similarity_limit === "number" ? cfg.sonic_similarity_limit : 50,
      sonic_similarity_distance:
        typeof cfg.sonic_similarity_distance === "number" ? cfg.sonic_similarity_distance : 0.8,
      historical_ratio: typeof cfg.historical_ratio === "number" ? cfg.historical_ratio : 0.4,
      timezone: (cfg.timezone as string) || "",
      time_periods: timePeriods,
      use_primary_mood: !!cfg.use_primary_mood,
      artists: Array.isArray(cfg.artists)
        ? (cfg.artists as string[]).join("\n")
        : (cfg.artists as string) || "",
      top_x: typeof cfg.top_x === "number" ? cfg.top_x : 5,
      source: (cfg.source as string) || "plex",
      target: (cfg.target as string) || "plex",
      use_custom_playlist_name: Boolean(
        cfg.use_custom_playlist_name ??
        (cfg.playlist_name && (cfg.playlist_name as string) !== "Mood Playlist")
      ),
      custom_playlist_name:
        (cfg.custom_playlist_name as string) ?? (cfg.playlist_name as string) ?? "",
      moods: Array.isArray(cfg.moods) ? (cfg.moods as string[]) : [],
      exclude_last_run: cfg.exclude_last_run !== false,
      limit_by_year: !!cfg.limit_by_year || !!cfg.min_year_enabled,
      min_year: (() => {
        const v = cfg.min_year;
        if (v == null) return undefined;
        const n = typeof v === "number" ? v : parseInt(String(v), 10);
        return isNaN(n) ? undefined : Math.max(1800, Math.min(2100, n));
      })(),
      max_year: (() => {
        const v = cfg.max_year;
        if (v == null) return undefined;
        const n = typeof v === "number" ? v : parseInt(String(v), 10);
        return isNaN(n) ? undefined : Math.max(1800, Math.min(2100, n));
      })(),
      lookback_days: typeof cfg.lookback_days === "number" ? cfg.lookback_days : 90,
      top_artists_count: typeof cfg.top_artists_count === "number" ? cfg.top_artists_count : 10,
      artist_pool_size: typeof cfg.artist_pool_size === "number" ? cfg.artist_pool_size : 20,
      expires_at_enabled: !!(cfg.expires_at as string),
      expires_at: fromExpiresAtIso(cfg.expires_at as string),
      expires_at_delete_playlist: cfg.expires_at_delete_playlist !== false,
      weekly_exploration_keep:
        typeof cfg.weekly_exploration_keep === "number" ? cfg.weekly_exploration_keep : 2,
      weekly_jams_keep: typeof cfg.weekly_jams_keep === "number" ? cfg.weekly_jams_keep : 2,
      daily_jams_keep: typeof cfg.daily_jams_keep === "number" ? cfg.daily_jams_keep : 3,
      cleanup_enabled: cfg.cleanup_enabled !== false,
      playlist_types: Array.isArray(cfg.playlist_types) ? cfg.playlist_types : [],
      sync_to_multiple_plex_users: syncMultiPlex,
      plex_account_ids: plexAccountIdsList,
      xm_station_deeplink: (cfg.station_deeplink as string) || "",
      xm_station_display_name: (cfg.station_display_name as string) || "",
      xm_playlist_kind: (cfg.playlist_kind as string) === "most_heard" ? "most_heard" : "newest",
      xm_most_heard_days: typeof cfg.most_heard_days === "number" ? cfg.most_heard_days : 30,
      plex_playlist_account_id: "",
    });
    if (isDaylist || command.command_name.startsWith("local_discovery_")) {
      const editingParam = `editing_command=${encodeURIComponent(command.command_name)}`;
      api
        .request<{
          accounts: { id: string; name: string }[];
          daylist_used_ids?: string[];
          local_discovery_used_ids?: string[];
        }>(`/api/commands/plex-accounts?${editingParam}`)
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
      setMoodsList([]);
      setXmplaylistEditStations([]);
      setXmplaylistEditFilter("");
    } else if (command.command_name.startsWith("mood_playlist_")) {
      api
        .request<{ moods: string[] }>("/api/commands/mood-playlist/moods")
        .then((r) => setMoodsList(r.moods || []))
        .catch(() => setMoodsList([]));
      setPlexAccounts([]);
      setDaylistUsedIds(new Set());
      setLocalDiscoveryUsedIds(new Set());
      setXmplaylistEditStations([]);
      setXmplaylistEditFilter("");
    } else if (command.command_name.startsWith("xmplaylist_")) {
      setMoodsList([]);
      setDaylistUsedIds(new Set());
      setLocalDiscoveryUsedIds(new Set());
      setXmplaylistEditFilter("");
      setXmplaylistEditLoading(true);
      api
        .request<{ stations: XmplaylistStationRow[] }>("/api/commands/xmplaylist/stations")
        .then((r) => setXmplaylistEditStations(r.stations || []))
        .catch(() => setXmplaylistEditStations([]))
        .finally(() => setXmplaylistEditLoading(false));
      api
        .request<{ accounts: { id: string; name: string }[] }>("/api/commands/plex-accounts")
        .then((r) => setPlexAccounts(r.accounts || []))
        .catch(() => setPlexAccounts([]));
    } else if (
      command.command_name.startsWith("playlist_sync_") &&
      cfg.playlist_url != null &&
      (cfg.source as string) !== "listenbrainz"
    ) {
      api
        .request<{ accounts: { id: string; name: string }[] }>("/api/commands/plex-accounts")
        .then((r) => setPlexAccounts(r.accounts || []))
        .catch(() => setPlexAccounts([]));
      setDaylistUsedIds(new Set());
      setLocalDiscoveryUsedIds(new Set());
      setMoodsList([]);
      setXmplaylistEditStations([]);
      setXmplaylistEditFilter("");
    } else {
      setPlexAccounts([]);
      setDaylistUsedIds(new Set());
      setLocalDiscoveryUsedIds(new Set());
      setMoodsList([]);
      setXmplaylistEditStations([]);
      setXmplaylistEditFilter("");
    }
  };

  const handleSaveCommand = async (updates: {
    schedule_cron?: string;
    schedule_override?: boolean;
    config_json?: Record<string, unknown>;
  }) => {
    if (!editingCommand) return;
    try {
      await api.updateCommand(editingCommand.command_name, updates);
      toast.success("Command updated");
      await loadCommands();
      const updated = (await api.getCommands()).find(
        (c) => c.command_name === editingCommand.command_name
      );
      if (updated) setEditingCommand(updated);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update command");
      console.error(error);
    }
  };

  const handleDelete = async (commandName: string) => {
    if (BUILTIN_COMMANDS.includes(commandName)) return;
    if (
      !confirm(
        `Are you sure you want to delete the command "${commandName}"? This cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await api.deleteCommand(commandName);
      toast.success("Command deleted");
      loadCommands();
    } catch (error) {
      toast.error("Failed to delete command");
      console.error(error);
    }
  };

  // Filter and sort commands (defensive check to ensure commands is an array)
  const safeCommands = Array.isArray(commands) ? commands : [];
  const filteredCommands = safeCommands
    .filter((cmd) => {
      // Search filter
      if (
        searchQuery &&
        !cmd.display_name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !cmd.command_name.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false;
      }
      // Status filter
      if (statusFilter === "enabled" && !cmd.enabled) return false;
      if (statusFilter === "disabled" && cmd.enabled) return false;
      // Type filter
      if (typeFilter !== "all" && cmd.command_type !== typeFilter) return false;
      return true;
    })
    .sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "name":
          comparison = a.display_name.localeCompare(b.display_name);
          break;
        case "status":
          comparison = Number(b.enabled) - Number(a.enabled);
          break;
        case "type":
          comparison = (a.command_type || "").localeCompare(b.command_type || "");
          break;
        case "schedule": {
          const sa = a.schedule_override && a.schedule_cron ? a.schedule_cron : "Default";
          const sb = b.schedule_override && b.schedule_cron ? b.schedule_cron : "Default";
          comparison = sa.localeCompare(sb);
          break;
        }
        case "last_run":
          comparison = (a.last_run || "").localeCompare(b.last_run || "");
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });

  const commandTypes = [
    "all",
    ...Array.from(new Set(safeCommands.map((c) => c.command_type).filter(Boolean))),
  ] as string[];
  const activeFilterCount = [
    statusFilter !== "all",
    typeFilter !== "all",
    searchQuery !== "",
  ].filter(Boolean).length;

  if (loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Commands</h1>
          <p className="mt-2 text-muted-foreground">Manage and monitor your Cmdarr commands</p>
        </div>
        <div className="text-center text-muted-foreground">Loading commands...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Commands</h1>
          <p className="mt-2 text-muted-foreground">Manage and monitor your Cmdarr commands</p>
        </div>
        <Card className="border-destructive">
          <CardContent className="flex min-h-[200px] flex-col items-center justify-center gap-4 p-8">
            <p className="text-lg font-medium text-destructive">Failed to Load Commands</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={loadCommands}>Try Again</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Commands</h1>
        <p className="mt-2 text-muted-foreground">Manage and monitor your Cmdarr commands</p>
      </div>

      {/* Controls Row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Left Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* View Toggle */}
          <div className="flex items-center rounded-lg bg-muted p-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setViewMode("card")}
              className={cn(viewMode === "card" && "bg-background shadow-sm")}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setViewMode("list")}
              className={cn(viewMode === "list" && "bg-background shadow-sm")}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>

          {/* Search */}
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search commands..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>

          {/* Filters Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Filter className="mr-2 h-4 w-4" />
                Filter
                {activeFilterCount > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {activeFilterCount}
                  </Badge>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-64">
              <div className="p-2">
                <div className="mb-3">
                  <label className="mb-1.5 block text-sm font-medium">Status</label>
                  <Select
                    value={statusFilter}
                    onValueChange={(v) => setStatusFilter(v as "all" | "enabled" | "disabled")}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="enabled">Enabled</SelectItem>
                      <SelectItem value="disabled">Disabled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="mb-3">
                  <label className="mb-1.5 block text-sm font-medium">Type</label>
                  <Select value={typeFilter} onValueChange={setTypeFilter}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {commandTypes.map((type) => (
                        <SelectItem key={type} value={type}>
                          {type === "all" ? "All" : type}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    setStatusFilter("all");
                    setTypeFilter("all");
                    setSearchQuery("");
                  }}
                >
                  Clear Filters
                </Button>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Right Controls */}
        <Button onClick={() => setShowNewCommandDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Command
        </Button>
      </div>

      {/* Commands Display */}
      {filteredCommands.length === 0 ? (
        <Card>
          <CardContent className="flex min-h-[400px] flex-col items-center justify-center gap-4 py-12">
            <div className="text-center">
              <h3 className="text-xl font-semibold">
                {safeCommands.length === 0 ? "No Commands Yet" : "No Commands Match Filters"}
              </h3>
              <p className="mt-2 text-muted-foreground">
                {safeCommands.length === 0
                  ? "Get started by creating your first command"
                  : "Try adjusting your filters to see more commands"}
              </p>
            </div>
            {safeCommands.length === 0 && (
              <Button size="lg" onClick={() => setShowNewCommandDialog(true)}>
                <Plus className="mr-2 h-5 w-5" />
                Create Your First Command
              </Button>
            )}
          </CardContent>
        </Card>
      ) : viewMode === "card" ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCommands.map((command) => (
            <Card key={command.id} className="flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-base">{command.display_name}</CardTitle>
                    {command.description && (
                      <CardDescription className="mt-1 text-xs">
                        {command.description}
                      </CardDescription>
                    )}
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleExecute(command)}>
                        <Play className="mr-2 h-4 w-4" />
                        Run Now
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleEdit(command)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => handleToggleEnabled(command)}>
                        {command.enabled ? "Disable" : "Enable"}
                      </DropdownMenuItem>
                      {!BUILTIN_COMMANDS.includes(command.command_name) && (
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => handleDelete(command.command_name)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                <div className="flex items-center gap-2">
                  <Badge variant={command.enabled ? "default" : "secondary"}>
                    {command.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                  {command.command_type && (
                    <Badge variant="outline" className="text-xs">
                      {command.command_type || "unknown"}
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  Schedule:{" "}
                  <span className="font-mono">
                    {command.schedule_override && command.schedule_cron
                      ? command.schedule_cron
                      : "Default"}
                  </span>
                </div>
                {command.last_run && (
                  <div className="text-xs text-muted-foreground">
                    Last run: {new Date(command.last_run).toLocaleString()}
                  </div>
                )}
                {command.last_success !== null && (
                  <div className="text-xs">
                    Status:{" "}
                    <span
                      className={
                        command.last_success
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400"
                      }
                    >
                      {command.last_success ? "Success" : "Failed"}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    <button
                      onClick={() => handleSort("name")}
                      className="flex items-center cursor-pointer hover:text-foreground"
                    >
                      Name <SortIcon column="name" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    <button
                      onClick={() => handleSort("status")}
                      className="flex items-center cursor-pointer hover:text-foreground"
                    >
                      Status <SortIcon column="status" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    <button
                      onClick={() => handleSort("type")}
                      className="flex items-center cursor-pointer hover:text-foreground"
                    >
                      Type <SortIcon column="type" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    <button
                      onClick={() => handleSort("schedule")}
                      className="flex items-center cursor-pointer hover:text-foreground"
                    >
                      Schedule <SortIcon column="schedule" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    <button
                      onClick={() => handleSort("last_run")}
                      className="flex items-center cursor-pointer hover:text-foreground"
                    >
                      Last Run <SortIcon column="last_run" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredCommands.map((command) => (
                  <tr key={command.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">
                      <div>
                        <div className="font-medium">{command.display_name}</div>
                        {command.description && (
                          <div className="text-xs text-muted-foreground">{command.description}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={command.enabled ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {command.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {command.command_type && (
                        <Badge variant="outline" className="text-xs">
                          {command.command_type}
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground font-mono">
                      {command.schedule_override && command.schedule_cron
                        ? command.schedule_cron
                        : "Default"}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {command.last_run ? new Date(command.last_run).toLocaleString() : "Never"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleExecute(command)}>
                            <Play className="mr-2 h-4 w-4" />
                            Run Now
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleEdit(command)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleToggleEnabled(command)}>
                            {command.enabled ? "Disable" : "Enable"}
                          </DropdownMenuItem>
                          {!BUILTIN_COMMANDS.includes(command.command_name) && (
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => handleDelete(command.command_name)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Recent Executions */}
      <Card>
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-medium">Recent Executions</h3>
          <Button variant="outline" size="sm" onClick={handleCleanupExecutions}>
            <Trash className="mr-2 h-4 w-4" />
            Cleanup Old
          </Button>
        </div>
        <div className="p-6">
          {recentExecutions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p className="font-medium">No executions yet</p>
              <p className="text-sm mt-1">Command executions will appear here once they run.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {recentExecutions.map((execution) => {
                const isExpanded = expandedExecutionId === execution.id;
                const duration = execution.duration ?? execution.duration_seconds;
                const statusLabel =
                  execution.status === "running"
                    ? "Running..."
                    : execution.status === "completed"
                      ? "Success"
                      : execution.status === "cancelled"
                        ? "Cancelled"
                        : "Failed";
                const statusColor =
                  execution.status === "completed"
                    ? "text-green-600 dark:text-green-400"
                    : execution.status === "failed"
                      ? "text-red-600 dark:text-red-400"
                      : execution.status === "running"
                        ? "text-yellow-600 dark:text-yellow-400"
                        : "text-muted-foreground";

                return (
                  <div key={execution.id} className="p-4 rounded-lg bg-muted/50 border">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center ${
                            execution.status === "completed"
                              ? "bg-green-100 dark:bg-green-900"
                              : execution.status === "failed"
                                ? "bg-red-100 dark:bg-red-900"
                                : execution.status === "running"
                                  ? "bg-yellow-100 dark:bg-yellow-900"
                                  : "bg-muted"
                          }`}
                        >
                          {execution.status === "running" ? (
                            <div className="w-4 h-4 border-2 border-yellow-600 border-t-transparent rounded-full animate-spin" />
                          ) : execution.status === "completed" ? (
                            <span className="text-green-600 dark:text-green-400">✓</span>
                          ) : execution.status === "failed" ? (
                            <span className="text-red-600 dark:text-red-400">✕</span>
                          ) : (
                            <span className="text-muted-foreground">○</span>
                          )}
                        </div>
                        <div>
                          <p className="font-medium">
                            {execution.display_name ??
                              getCommandDisplayName(execution.command_name)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {execution.started_at
                              ? new Date(execution.started_at).toLocaleString()
                              : "—"}
                          </p>
                          {execution.target && execution.target !== "unknown" && (
                            <p className="text-xs text-blue-600 dark:text-blue-400">
                              Target: {String(execution.target).toUpperCase()}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="text-right flex items-center gap-2">
                        <span className={`font-medium ${statusColor}`}>{statusLabel}</span>
                        {execution.status === "running" && (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleKillExecution(execution.id)}
                            disabled={killingExecutionId === execution.id}
                          >
                            <X className="h-3 w-3 mr-1" />
                            {killingExecutionId === execution.id ? "Killing..." : "Kill"}
                          </Button>
                        )}
                        <p className="text-xs text-muted-foreground">
                          {duration != null ? formatDuration(duration) : "In progress"}
                        </p>
                        <p className="text-xs text-muted-foreground capitalize">
                          {execution.triggered_by}
                        </p>
                      </div>
                    </div>
                    {execution.status === "failed" && execution.error_message && (
                      <div className="mt-3 p-3 rounded-md bg-destructive/10 text-destructive text-sm">
                        {execution.error_message}
                      </div>
                    )}
                    {execution.status === "completed" && (
                      <div className="mt-3 p-3 rounded-md bg-green-500/10 text-green-700 dark:text-green-400 text-sm">
                        {execution.display_name ?? getCommandDisplayName(execution.command_name)}{" "}
                        completed successfully in {formatDuration(duration)}
                      </div>
                    )}
                    <div className="mt-3">
                      <button
                        onClick={() => setExpandedExecutionId(isExpanded ? null : execution.id)}
                        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
                      >
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                        {isExpanded ? "Hide Details" : "Show Details"}
                      </button>
                      {isExpanded && (
                        <div className="mt-2 p-3 rounded-md bg-muted space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Execution ID:</span>
                            <span className="font-mono">{execution.id}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Started:</span>
                            <span>
                              {execution.started_at
                                ? new Date(execution.started_at).toLocaleString()
                                : "—"}
                            </span>
                          </div>
                          {execution.completed_at && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Completed:</span>
                              <span>{new Date(execution.completed_at).toLocaleString()}</span>
                            </div>
                          )}
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Duration:</span>
                            <span>{formatDuration(duration)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Triggered by:</span>
                            <span className="capitalize">{execution.triggered_by}</span>
                          </div>
                          {execution.error_message && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Error:</span>
                              <span className="text-destructive text-right">
                                {execution.error_message}
                              </span>
                            </div>
                          )}
                          {execution.status !== "running" && (
                            <div className="pt-3 border-t">
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => handleDeleteExecution(execution.id)}
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete Execution
                              </Button>
                            </div>
                          )}
                          {execution.status === "completed" && execution.output_summary && (
                            <div className="pt-3 border-t">
                              <h5 className="font-medium mb-2">Execution Summary</h5>
                              <pre className="text-xs whitespace-pre-wrap font-sans">
                                {execution.output_summary}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      {/* New Command Dialog */}
      <CreatePlaylistSyncDialog
        open={showNewCommandDialog}
        onOpenChange={setShowNewCommandDialog}
        onSuccess={loadCommands}
      />

      {/* Edit Command Dialog */}
      <Dialog open={!!editingCommand} onOpenChange={(open) => !open && setEditingCommand(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-4 flex-shrink-0">
            <DialogTitle>Edit Command: {editingCommand?.display_name}</DialogTitle>
            <DialogDescription>Configure command settings and schedule</DialogDescription>
          </DialogHeader>
          {editingCommand && (
            <>
              <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-6">
                <div className="space-y-4 py-4">
                  <div className="grid gap-4">
                    {/* Display Name */}
                    <div className="space-y-2">
                      <Label>Display Name</Label>
                      <Input value={editingCommand.display_name} disabled />
                    </div>

                    {/* Description */}
                    <div className="space-y-2">
                      <Label>Description</Label>
                      <Input value={String(editingCommand.description ?? "")} disabled />
                    </div>

                    {/* Enabled Status */}
                    <div className="flex items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <Label>Enabled</Label>
                        <div className="text-sm text-muted-foreground">
                          Command is currently {editingCommand.enabled ? "enabled" : "disabled"}
                        </div>
                      </div>
                      <Badge variant={editingCommand.enabled ? "default" : "secondary"}>
                        {editingCommand.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>

                    {/* Playlist sync - read-only playlist URL */}
                    {editingCommand.command_name.startsWith("playlist_sync_") &&
                      editingCommand.config_json?.playlist_url != null && (
                        <div className="space-y-2">
                          <Label>Playlist URL</Label>
                          <Input
                            value={String(editingCommand.config_json.playlist_url)}
                            disabled
                            className="font-mono text-sm"
                          />
                        </div>
                      )}

                    {/* Playlist sync - artist discovery option (matches Override schedule / Enable expiration pattern) */}
                    {editingCommand.command_name.startsWith("playlist_sync_") && (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="edit-enable-artist-discovery"
                            checked={editForm.enable_artist_discovery ?? false}
                            onChange={(e) =>
                              setEditForm((f) => ({
                                ...f,
                                enable_artist_discovery: e.target.checked,
                              }))
                            }
                            className="rounded border-input"
                          />
                          <Label
                            htmlFor="edit-enable-artist-discovery"
                            className="cursor-pointer font-normal"
                          >
                            Add new artists
                          </Label>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Artists discovered missing from Lidarr are added to the Playlist Sync
                          Discovery import list. Discovery always runs to report counts; this
                          controls whether to add.
                        </p>
                        {editForm.enable_artist_discovery && (
                          <div className="space-y-2 rounded-lg border p-4">
                            <Label htmlFor="edit-artist-discovery-max">
                              Max artists to add per run
                            </Label>
                            <NumericInput
                              id="edit-artist-discovery-max"
                              placeholder="2"
                              value={editForm.artist_discovery_max_per_run ?? 2}
                              onChange={(v) =>
                                setEditForm((f) => ({
                                  ...f,
                                  artist_discovery_max_per_run: v ?? 2,
                                }))
                              }
                              min={0}
                              max={50}
                              defaultValue={2}
                            />
                            <p className="text-xs text-muted-foreground">
                              0 = no limit. First run adds none—only reports count.
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* External playlist sync - Plex users (edit only) */}
                    {editingCommand.command_name.startsWith("playlist_sync_") &&
                      editingCommand.config_json?.playlist_url != null &&
                      (editingCommand.config_json?.source as string) !== "listenbrainz" &&
                      (editingCommand.config_json?.target as string) === "plex" && (
                        <PlexPlaylistTargetSection
                          accounts={plexAccounts}
                          syncToMultiple={!!editForm.sync_to_multiple_plex_users}
                          selectedAccountIds={editForm.plex_account_ids ?? []}
                          onSyncToMultipleChange={(checked) =>
                            setEditForm((f) => ({
                              ...f,
                              sync_to_multiple_plex_users: checked,
                              plex_account_ids: checked ? (f.plex_account_ids ?? []) : [],
                            }))
                          }
                          onToggleAccount={(accountId, selected) =>
                            setEditForm((f) => ({
                              ...f,
                              plex_account_ids: selected
                                ? [...(f.plex_account_ids ?? []), accountId]
                                : (f.plex_account_ids ?? []).filter((id) => id !== accountId),
                            }))
                          }
                        />
                      )}

                    {/* ListenBrainz - retention and cleanup (edit only) */}
                    {editingCommand.command_name.startsWith("playlist_sync_") &&
                      (editingCommand.config_json?.source as string) === "listenbrainz" && (
                        <>
                          <div className="space-y-2">
                            <Label>Retention Settings</Label>
                            <div className="grid grid-cols-3 gap-4">
                              <div>
                                <Label className="text-xs">Weekly Exploration</Label>
                                <NumericInput
                                  value={editForm.weekly_exploration_keep ?? 2}
                                  onChange={(v) =>
                                    setEditForm((f) => ({
                                      ...f,
                                      weekly_exploration_keep: v ?? 2,
                                    }))
                                  }
                                  min={1}
                                  max={20}
                                  defaultValue={2}
                                />
                              </div>
                              <div>
                                <Label className="text-xs">Weekly Jams</Label>
                                <NumericInput
                                  value={editForm.weekly_jams_keep ?? 2}
                                  onChange={(v) =>
                                    setEditForm((f) => ({
                                      ...f,
                                      weekly_jams_keep: v ?? 2,
                                    }))
                                  }
                                  min={1}
                                  max={20}
                                  defaultValue={2}
                                />
                              </div>
                              <div>
                                <Label className="text-xs">Daily Jams</Label>
                                <NumericInput
                                  value={editForm.daily_jams_keep ?? 3}
                                  onChange={(v) =>
                                    setEditForm((f) => ({
                                      ...f,
                                      daily_jams_keep: v ?? 3,
                                    }))
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
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              id="edit-lb-cleanup"
                              checked={editForm.cleanup_enabled ?? true}
                              onChange={(e) =>
                                setEditForm((f) => ({
                                  ...f,
                                  cleanup_enabled: e.target.checked,
                                }))
                              }
                              className="rounded border-input"
                            />
                            <Label htmlFor="edit-lb-cleanup" className="cursor-pointer font-normal">
                              Enable playlist cleanup (delete old playlists)
                            </Label>
                          </div>
                        </>
                      )}

                    {/* Daylist - editable fields */}
                    {editingCommand.command_name.startsWith("daylist_") && (
                      <>
                        {/* Primary settings */}
                        <div className="space-y-4">
                          <div className="space-y-2">
                            <Label>Plex Account (play history source)</Label>
                            <Select
                              value={editForm.plex_history_account_id ?? ""}
                              onValueChange={(v) =>
                                setEditForm((f) => ({ ...f, plex_history_account_id: v }))
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
                              Plex Home users only. Daylist uses this account&apos;s play history.
                              One Daylist per user.
                            </p>
                          </div>
                          <div className="space-y-2">
                            <Label>Run at minute of hour (0–59)</Label>
                            <NumericInput
                              value={editForm.schedule_minute ?? 0}
                              onChange={(v) =>
                                setEditForm((f) => ({ ...f, schedule_minute: v ?? 0 }))
                              }
                              min={0}
                              max={59}
                              defaultValue={0}
                            />
                            <p className="text-xs text-muted-foreground">
                              Daylist runs hourly at this minute. Runs only when the day period
                              changes (Dawn, Morning, etc.). Min: 0, max: 59.
                            </p>
                          </div>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label>Exclude played (days)</Label>
                              <NumericInput
                                value={editForm.exclude_played_days ?? 3}
                                onChange={(v) =>
                                  setEditForm((f) => ({ ...f, exclude_played_days: v ?? 3 }))
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
                                value={editForm.history_lookback_days ?? 45}
                                onChange={(v) =>
                                  setEditForm((f) => ({
                                    ...f,
                                    history_lookback_days: v ?? 45,
                                  }))
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
                                value={editForm.max_tracks ?? 50}
                                onChange={(v) =>
                                  setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))
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
                                <Label>Historical ratio: {editForm.historical_ratio ?? 0.4}</Label>
                                <input
                                  type="range"
                                  min={0.1}
                                  max={0.8}
                                  step={0.1}
                                  value={editForm.historical_ratio ?? 0.4}
                                  onChange={(e) =>
                                    setEditForm((f) => ({
                                      ...f,
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
                                  value={editForm.sonic_similar_limit ?? 10}
                                  onChange={(v) =>
                                    setEditForm((f) => ({ ...f, sonic_similar_limit: v ?? 10 }))
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
                                  value={editForm.sonic_similarity_limit ?? 50}
                                  onChange={(v) =>
                                    setEditForm((f) => ({
                                      ...f,
                                      sonic_similarity_limit: v ?? 50,
                                    }))
                                  }
                                  min={10}
                                  max={200}
                                  defaultValue={50}
                                />
                                <p className="text-xs text-muted-foreground">
                                  Max tracks to fetch from Plex sonic API per request. Min: 10, max:
                                  200.
                                </p>
                              </div>
                              <div className="space-y-2">
                                <Label>
                                  Sonically similar distance:{" "}
                                  {editForm.sonic_similarity_distance ?? 0.8}
                                </Label>
                                <input
                                  type="range"
                                  min={0.1}
                                  max={2}
                                  step={0.1}
                                  value={editForm.sonic_similarity_distance ?? 0.8}
                                  onChange={(e) =>
                                    setEditForm((f) => ({
                                      ...f,
                                      sonic_similarity_distance: parseFloat(e.target.value) || 0.8,
                                    }))
                                  }
                                  className="slider-range"
                                />
                                <p className="text-xs text-muted-foreground">
                                  0.1 = very similar, 2 = more diverse. Min: 0.1, max: 2.
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                id="edit-use-primary-mood"
                                checked={editForm.use_primary_mood ?? false}
                                onChange={(e) =>
                                  setEditForm((f) => ({
                                    ...f,
                                    use_primary_mood: e.target.checked,
                                  }))
                                }
                                className="rounded border-input"
                              />
                              <Label htmlFor="edit-use-primary-mood" className="font-normal">
                                Use primary mood for cover (default: secondary)
                              </Label>
                            </div>
                            <p className="text-xs text-muted-foreground -mt-2">
                              Cover text uses the second-most-common mood by default (Meloday).
                              Enable to use the most common mood instead.
                            </p>
                            <div className="space-y-2">
                              <Label>Timezone (optional)</Label>
                              <Input
                                placeholder="e.g. America/New_York"
                                value={editForm.timezone ?? ""}
                                onChange={(e) =>
                                  setEditForm((f) => ({ ...f, timezone: e.target.value }))
                                }
                              />
                              <p className="text-xs text-muted-foreground">
                                Leave empty to use scheduler timezone
                              </p>
                            </div>
                            <div className="space-y-2">
                              <Label>Time periods (Start–End hour, 0–23)</Label>
                              <p className="text-xs text-muted-foreground mb-2">
                                When each period runs. Late Night wraps (e.g. 22–2 = 22,23,0,1,2).
                                Hours 0–23.
                              </p>
                              <div className="grid gap-2">
                                {Object.entries(
                                  editForm.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS
                                ).map(([period, { start, end }]) => (
                                  <div key={period} className="flex items-center gap-3">
                                    <span className="w-28 text-sm">{period}</span>
                                    <NumericInput
                                      className="w-16"
                                      value={start}
                                      onChange={(v) =>
                                        setEditForm((f) => ({
                                          ...f,
                                          time_periods: {
                                            ...(f.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS),
                                            [period]: {
                                              ...(f.time_periods?.[period] ?? { start: 0, end: 0 }),
                                              start: v ?? f.time_periods?.[period]?.start ?? 0,
                                            },
                                          },
                                        }))
                                      }
                                      min={0}
                                      max={23}
                                      defaultValue={0}
                                    />
                                    <span className="text-muted-foreground">–</span>
                                    <NumericInput
                                      className="w-16"
                                      value={end}
                                      onChange={(v) =>
                                        setEditForm((f) => ({
                                          ...f,
                                          time_periods: {
                                            ...(f.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS),
                                            [period]: {
                                              ...(f.time_periods?.[period] ?? { start: 0, end: 0 }),
                                              end: v ?? f.time_periods?.[period]?.end ?? 0,
                                            },
                                          },
                                        }))
                                      }
                                      min={0}
                                      max={23}
                                      defaultValue={0}
                                    />
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </details>
                      </>
                    )}

                    {/* Last.fm Discovery - editable fields */}
                    {editingCommand.command_name === "discovery_lastfm" && (
                      <>
                        <div className="space-y-2">
                          <Label htmlFor="edit-artists-to-query">Lidarr artists to sample</Label>
                          <NumericInput
                            id="edit-artists-to-query"
                            value={editForm.artists_to_query ?? 3}
                            onChange={(v) =>
                              setEditForm((f) => ({ ...f, artists_to_query: v ?? 3 }))
                            }
                            min={1}
                            max={100}
                            defaultValue={3}
                          />
                          <p className="text-xs text-muted-foreground">
                            Number of Lidarr artists to query Last.fm (1–100). Lower = faster.
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="edit-artist-cooldown-days">Artist cooldown (days)</Label>
                          <NumericInput
                            id="edit-artist-cooldown-days"
                            value={editForm.artist_cooldown_days ?? 30}
                            onChange={(v) =>
                              setEditForm((f) => ({ ...f, artist_cooldown_days: v ?? 30 }))
                            }
                            min={1}
                            max={365}
                            defaultValue={30}
                          />
                          <p className="text-xs text-muted-foreground">
                            Don&apos;t re-query an artist for this many days (1–365, default 30)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="edit-similar-per-artist">Similar per artist</Label>
                          <NumericInput
                            id="edit-similar-per-artist"
                            value={editForm.similar_per_artist ?? 1}
                            onChange={(v) =>
                              setEditForm((f) => ({ ...f, similar_per_artist: v ?? 1 }))
                            }
                            min={1}
                            max={50}
                            defaultValue={1}
                          />
                          <p className="text-xs text-muted-foreground">
                            Similar artists to request per Lidarr artist (1–50)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="edit-lastfm-limit">Output limit</Label>
                          <NumericInput
                            id="edit-lastfm-limit"
                            value={editForm.limit ?? 5}
                            onChange={(v) => setEditForm((f) => ({ ...f, limit: v ?? 5 }))}
                            min={1}
                            max={50}
                            defaultValue={5}
                          />
                          <p className="text-xs text-muted-foreground">
                            Max artists in final output (1–50)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="edit-min-match-score">Min match score (0–1)</Label>
                          <NumericInput
                            id="edit-min-match-score"
                            value={editForm.min_match_score ?? 0.9}
                            onChange={(v) =>
                              setEditForm((f) => ({ ...f, min_match_score: v ?? 0.9 }))
                            }
                            min={0}
                            max={1}
                            defaultValue={0.9}
                            numericType="float"
                          />
                          <p className="text-xs text-muted-foreground">
                            Minimum Last.fm match score (0–1, default 0.9)
                          </p>
                        </div>
                      </>
                    )}

                    {/* Mood Playlist - editable fields */}
                    {editingCommand.command_name.startsWith("mood_playlist_") && (
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
                                      checked={(editForm.moods ?? []).includes(mood)}
                                      onChange={() => {
                                        const current = editForm.moods ?? [];
                                        setEditForm((f) => ({
                                          ...f,
                                          moods: current.includes(mood)
                                            ? current.filter((m) => m !== mood)
                                            : [...current, mood],
                                        }));
                                      }}
                                      className="rounded border-input"
                                    />
                                    <span className="text-sm">{mood}</span>
                                  </label>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={editForm.use_custom_playlist_name ?? false}
                            onChange={(e) =>
                              setEditForm((f) => ({
                                ...f,
                                use_custom_playlist_name: e.target.checked,
                              }))
                            }
                            className="rounded border-input"
                          />
                          <span className="text-sm">Use custom playlist name</span>
                        </label>
                        {editForm.use_custom_playlist_name && (
                          <div className="space-y-2">
                            <Label>Custom playlist name</Label>
                            <Input
                              value={editForm.custom_playlist_name ?? ""}
                              onChange={(e) =>
                                setEditForm((f) => ({ ...f, custom_playlist_name: e.target.value }))
                              }
                              placeholder="e.g. Chill Vibes"
                            />
                            <p className="text-xs text-muted-foreground">
                              Override auto-generated name. Shown as [Cmdarr] Mood: &lt;name&gt;.
                            </p>
                          </div>
                        )}
                        {!editForm.use_custom_playlist_name && (
                          <p className="text-xs text-muted-foreground">
                            Playlist name is auto-generated from mood names (e.g. Chill · Relaxed +
                            2 More).
                          </p>
                        )}
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Max tracks</Label>
                            <NumericInput
                              placeholder="50"
                              value={editForm.max_tracks ?? 50}
                              onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
                              min={1}
                              max={200}
                              defaultValue={50}
                            />
                            <p className="text-xs text-muted-foreground">Min 1, max 200</p>
                          </div>
                        </div>
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={editForm.exclude_last_run ?? true}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, exclude_last_run: e.target.checked }))
                            }
                            className="rounded border-input"
                          />
                          <span className="text-sm">
                            Force fresh (exclude tracks from previous run)
                          </span>
                        </label>
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={editForm.limit_by_year ?? false}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, limit_by_year: e.target.checked }))
                            }
                            className="rounded border-input"
                          />
                          <span className="text-sm">Limit by release year (album year)</span>
                        </label>
                        {editForm.limit_by_year && (
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label>Min year</Label>
                              <NumericInput
                                placeholder="e.g. 1990"
                                value={editForm.min_year}
                                onChange={(v) => setEditForm((f) => ({ ...f, min_year: v }))}
                                min={1800}
                                max={2100}
                                allowEmpty
                              />
                            </div>
                            <div className="space-y-2">
                              <Label>Max year</Label>
                              <NumericInput
                                placeholder="e.g. 2010"
                                value={editForm.max_year}
                                onChange={(v) => setEditForm((f) => ({ ...f, max_year: v }))}
                                min={1800}
                                max={2100}
                                allowEmpty
                              />
                            </div>
                          </div>
                        )}
                        {editForm.limit_by_year && (
                          <p className="text-xs text-muted-foreground">
                            Set min and/or max. Tracks without year metadata are excluded. Range:
                            1800–2100.
                          </p>
                        )}
                      </>
                    )}

                    {/* Local Discovery - editable fields */}
                    {editingCommand.command_name.startsWith("local_discovery_") && (
                      <>
                        <div className="space-y-2">
                          <Label>Plex Account (play history source)</Label>
                          <Select
                            value={editForm.plex_history_account_id ?? ""}
                            onValueChange={(v) =>
                              setEditForm((f) => ({ ...f, plex_history_account_id: v }))
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
                            Plex Home users only. Local Discovery uses this account&apos;s play
                            history. One Local Discovery per user.
                          </p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Lookback days</Label>
                            <NumericInput
                              value={editForm.lookback_days ?? 90}
                              onChange={(v) =>
                                setEditForm((f) => ({ ...f, lookback_days: v ?? 90 }))
                              }
                              min={7}
                              max={365}
                              defaultValue={90}
                            />
                            <p className="text-xs text-muted-foreground">
                              How far back to count plays. Shorter = more day-to-day variety. Min:
                              7, max: 365.
                            </p>
                          </div>
                          <div className="space-y-2">
                            <Label>Exclude played days</Label>
                            <NumericInput
                              value={editForm.exclude_played_days ?? 3}
                              onChange={(v) =>
                                setEditForm((f) => ({ ...f, exclude_played_days: v ?? 3 }))
                              }
                              min={0}
                              max={30}
                              defaultValue={3}
                            />
                            <p className="text-xs text-muted-foreground">
                              Skip tracks played in last N days. Reduces repetition. Min: 0, max:
                              30.
                            </p>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Top artists count</Label>
                            <NumericInput
                              value={editForm.top_artists_count ?? 10}
                              onChange={(v) =>
                                setEditForm((f) => ({ ...f, top_artists_count: v ?? 10 }))
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
                              value={editForm.artist_pool_size ?? 20}
                              onChange={(v) =>
                                setEditForm((f) => ({ ...f, artist_pool_size: v ?? 20 }))
                              }
                              min={1}
                              max={50}
                              defaultValue={20}
                            />
                            <p className="text-xs text-muted-foreground">
                              Size of artist pool to sample from (must be ≥ top artists count). Min:
                              top artists, max: 50.
                            </p>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Max tracks</Label>
                            <NumericInput
                              value={editForm.max_tracks ?? 50}
                              onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
                              min={1}
                              max={200}
                              defaultValue={50}
                            />
                            <p className="text-xs text-muted-foreground">
                              Target playlist size. Min: 1, max: 200.
                            </p>
                          </div>
                          <div className="space-y-2">
                            <Label>Sonic similar limit</Label>
                            <NumericInput
                              value={editForm.sonic_similar_limit ?? 15}
                              onChange={(v) =>
                                setEditForm((f) => ({ ...f, sonic_similar_limit: v ?? 15 }))
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
                            <Label>Sonic similarity distance</Label>
                            <NumericInput
                              value={editForm.sonic_similarity_distance ?? 0.25}
                              onChange={(v) =>
                                setEditForm((f) => ({
                                  ...f,
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
                          <Label>Historical ratio: {editForm.historical_ratio ?? 0.4}</Label>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={editForm.historical_ratio ?? 0.4}
                            onChange={(e) =>
                              setEditForm((f) => ({
                                ...f,
                                historical_ratio: parseFloat(e.target.value),
                              }))
                            }
                            className="w-full"
                          />
                          <p className="text-xs text-muted-foreground">
                            Share of tracks from play history vs sonically similar. 0.4 = 40%
                            history, 60% similar.
                          </p>
                        </div>
                      </>
                    )}

                    {/* Artist Essentials - editable fields */}
                    {editingCommand.command_name.startsWith("top_tracks_") && (
                      <>
                        <div className="space-y-2">
                          <Label>Artists (one per line)</Label>
                          <textarea
                            className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            value={editForm.artists ?? ""}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, artists: e.target.value }))
                            }
                          />
                          <p className="text-xs text-muted-foreground">
                            Artists must exist in your library. Names are validated against the
                            library cache.
                          </p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Top X per artist</Label>
                            <NumericInput
                              placeholder="5"
                              value={editForm.top_x ?? 5}
                              onChange={(v) => setEditForm((f) => ({ ...f, top_x: v ?? 5 }))}
                              min={1}
                              max={20}
                              defaultValue={5}
                            />
                            <p className="text-xs text-muted-foreground">
                              Number of top tracks per artist. Min: 1, max: 20.
                            </p>
                          </div>
                          <label className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={editForm.use_custom_playlist_name ?? false}
                              onChange={(e) =>
                                setEditForm((f) => ({
                                  ...f,
                                  use_custom_playlist_name: e.target.checked,
                                }))
                              }
                              className="rounded border-input"
                            />
                            <span className="text-sm">Use custom playlist name</span>
                          </label>
                          {editForm.use_custom_playlist_name && (
                            <div className="space-y-2">
                              <Label>Custom playlist name</Label>
                              <Input
                                value={editForm.custom_playlist_name ?? ""}
                                onChange={(e) =>
                                  setEditForm((f) => ({
                                    ...f,
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
                          {!editForm.use_custom_playlist_name && (
                            <p className="text-xs text-muted-foreground">
                              Playlist name is auto-generated from artist names (e.g. Artist1 ·
                              Artist2 + 3 More).
                            </p>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Target</Label>
                            <Select
                              value={editForm.target ?? "plex"}
                              onValueChange={(v) =>
                                setEditForm((f) => ({
                                  ...f,
                                  target: v,
                                  source: v === "jellyfin" ? "lastfm" : (f.source ?? "plex"),
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
                            <Label>Source</Label>
                            <Select
                              value={
                                editForm.target === "jellyfin"
                                  ? "lastfm"
                                  : (editForm.source ?? "plex")
                              }
                              disabled={editForm.target === "jellyfin"}
                              onValueChange={(v) => setEditForm((f) => ({ ...f, source: v }))}
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="plex">Plex</SelectItem>
                                <SelectItem value="lastfm">Last.fm</SelectItem>
                              </SelectContent>
                            </Select>
                            <p className="text-xs text-muted-foreground">
                              Plex uses ratingCount; Last.fm uses play counts. Jellyfin requires
                              Last.fm.
                            </p>
                          </div>
                        </div>
                      </>
                    )}

                    {editingCommand.command_name.startsWith("xmplaylist_") && (
                      <>
                        <div className="space-y-2">
                          <Label>Station</Label>
                          <Input
                            placeholder="Filter stations…"
                            value={xmplaylistEditFilter}
                            onChange={(e) => setXmplaylistEditFilter(e.target.value)}
                            disabled={xmplaylistEditLoading}
                          />
                          <p className="text-xs text-muted-foreground">
                            Current:{" "}
                            {editForm.xm_station_display_name ||
                              editForm.xm_station_deeplink ||
                              "—"}
                          </p>
                          <div className="max-h-40 overflow-y-auto rounded-md border border-input">
                            {xmplaylistEditLoading ? (
                              <p className="p-2 text-sm text-muted-foreground">Loading…</p>
                            ) : (
                              filteredXmEditStations.map((s) => (
                                <button
                                  key={s.deeplink}
                                  type="button"
                                  className="block w-full border-b border-border px-2 py-1.5 text-left text-sm last:border-b-0 hover:bg-accent"
                                  onClick={() =>
                                    setEditForm((f) => ({
                                      ...f,
                                      xm_station_deeplink: s.deeplink,
                                      xm_station_display_name: s.name,
                                    }))
                                  }
                                >
                                  {s.label}
                                </button>
                              ))
                            )}
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Source</Label>
                            <Select
                              value={editForm.xm_playlist_kind ?? "newest"}
                              onValueChange={(v: "newest" | "most_heard") =>
                                setEditForm((f) => ({ ...f, xm_playlist_kind: v }))
                              }
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="newest">Newest</SelectItem>
                                <SelectItem value="most_heard">Most played</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          {editForm.xm_playlist_kind === "most_heard" && (
                            <div className="space-y-2">
                              <Label>Days</Label>
                              <Select
                                value={String(editForm.xm_most_heard_days ?? 30)}
                                onValueChange={(v) =>
                                  setEditForm((f) => ({
                                    ...f,
                                    xm_most_heard_days: parseInt(v, 10),
                                  }))
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="1">1</SelectItem>
                                  <SelectItem value="7">7</SelectItem>
                                  <SelectItem value="14">14</SelectItem>
                                  <SelectItem value="30">30</SelectItem>
                                  <SelectItem value="60">60</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          )}
                        </div>
                        <div className="space-y-2">
                          <Label>Max tracks</Label>
                          <NumericInput
                            value={editForm.max_tracks ?? 50}
                            onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
                            min={1}
                            max={50}
                            defaultValue={50}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Target</Label>
                          <Select
                            value={editForm.target ?? "plex"}
                            onValueChange={(v) =>
                              setEditForm((f) => ({
                                ...f,
                                target: v,
                                sync_to_multiple_plex_users:
                                  v === "jellyfin" ? false : f.sync_to_multiple_plex_users,
                                plex_account_ids: v === "jellyfin" ? [] : (f.plex_account_ids ?? []),
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
                        {editForm.target === "plex" && (
                          <PlexPlaylistTargetSection
                            accounts={plexAccounts}
                            syncToMultiple={!!editForm.sync_to_multiple_plex_users}
                            selectedAccountIds={editForm.plex_account_ids ?? []}
                            onSyncToMultipleChange={(checked) =>
                              setEditForm((f) => ({
                                ...f,
                                sync_to_multiple_plex_users: checked,
                                plex_account_ids: checked ? (f.plex_account_ids ?? []) : [],
                              }))
                            }
                            onToggleAccount={(accountId, selected) =>
                              setEditForm((f) => ({
                                ...f,
                                plex_account_ids: selected
                                  ? [...(f.plex_account_ids ?? []), accountId]
                                  : (f.plex_account_ids ?? []).filter((id) => id !== accountId),
                              }))
                            }
                          />
                        )}
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={editForm.enable_artist_discovery ?? false}
                            onChange={(e) =>
                              setEditForm((f) => ({
                                ...f,
                                enable_artist_discovery: e.target.checked,
                              }))
                            }
                            className="rounded border-input"
                          />
                          <span className="text-sm">Artist discovery</span>
                        </label>
                        {editForm.enable_artist_discovery && (
                          <div className="space-y-2">
                            <Label>Max artists per run</Label>
                            <NumericInput
                              value={editForm.artist_discovery_max_per_run ?? 2}
                              onChange={(v) =>
                                setEditForm((f) => ({
                                  ...f,
                                  artist_discovery_max_per_run: v ?? 2,
                                }))
                              }
                              min={0}
                              max={50}
                              defaultValue={2}
                            />
                          </div>
                        )}
                      </>
                    )}

                    {/* Schedule - all commands except daylist (override default cron) */}
                    {!editingCommand.command_name.startsWith("daylist_") && (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="edit-schedule-override"
                            checked={editForm.schedule_override ?? false}
                            onChange={(e) =>
                              setEditForm((f) => ({ ...f, schedule_override: e.target.checked }))
                            }
                            className="rounded border-input"
                          />
                          <Label htmlFor="edit-schedule-override">Override default schedule</Label>
                        </div>
                        {editForm.schedule_override && (
                          <>
                            <div className="space-y-2 rounded-lg border p-4">
                              <Input
                                id="edit-schedule-cron"
                                placeholder="0 3 * * *"
                                value={editForm.schedule_cron ?? "0 3 * * *"}
                                onChange={(e) =>
                                  setEditForm((f) => ({ ...f, schedule_cron: e.target.value }))
                                }
                              />
                            </div>
                            <p className="text-xs text-muted-foreground">
                              Cron format: minute hour day month weekday (e.g. 0 3 * * * = 3 AM
                              daily)
                            </p>
                          </>
                        )}
                        {!editForm.schedule_override && (
                          <p className="text-xs text-muted-foreground">
                            Uses global default (Config → Scheduler)
                          </p>
                        )}
                      </div>
                    )}

                    {/* Expiration - playlist sync, top tracks, daylist, local discovery, mood playlist (below schedule) */}
                    {(editingCommand.command_name.startsWith("playlist_sync_") ||
                      editingCommand.command_name.startsWith("top_tracks_") ||
                      editingCommand.command_name.startsWith("daylist_") ||
                      editingCommand.command_name.startsWith("local_discovery_") ||
                      editingCommand.command_name.startsWith("mood_playlist_") ||
                      editingCommand.command_name.startsWith("xmplaylist_")) && (
                      <ExpirationFields
                        idPrefix="edit-exp"
                        enabled={editForm.expires_at_enabled ?? false}
                        onEnabledChange={(v) =>
                          setEditForm((f) => ({
                            ...f,
                            expires_at_enabled: v,
                            expires_at: v && !f.expires_at ? "" : f.expires_at,
                          }))
                        }
                        value={editForm.expires_at ?? ""}
                        onValueChange={(v) => setEditForm((f) => ({ ...f, expires_at: v }))}
                        showDeletePlaylistOption={true}
                        deletePlaylistOnExpiry={editForm.expires_at_delete_playlist ?? true}
                        onDeletePlaylistChange={(v) =>
                          setEditForm((f) => ({ ...f, expires_at_delete_playlist: v }))
                        }
                      />
                    )}

                    {/* New Releases Discovery - editable fields */}
                    {editingCommand.command_name === "new_releases_discovery" && (
                      <>
                        <div className="space-y-2">
                          <Label htmlFor="edit-artists">Artists per run</Label>
                          <NumericInput
                            id="edit-artists"
                            value={editForm.artists_per_run ?? 5}
                            onChange={(v) =>
                              setEditForm((f) => ({ ...f, artists_per_run: v ?? 5 }))
                            }
                            min={1}
                            max={50}
                            defaultValue={5}
                          />
                          <p className="text-xs text-muted-foreground">
                            Max artists to scan per batch (1–50)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="edit-source">Release source</Label>
                          <select
                            id="edit-source"
                            value={editForm.new_releases_source ?? "deezer"}
                            onChange={(e) =>
                              setEditForm((f) => ({
                                ...f,
                                new_releases_source:
                                  e.target.value === "spotify" ? "spotify" : "deezer",
                              }))
                            }
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                          >
                            <option value="deezer">
                              Deezer (no account configuration required)
                            </option>
                            <option
                              value="spotify"
                              disabled={
                                !!nrdSources.find((s) => s.id === "spotify" && !s.configured)
                              }
                            >
                              Spotify (
                              {nrdSources.find((s) => s.id === "spotify")?.configured
                                ? "credentials configured"
                                : "set credentials in Config"}
                              )
                            </option>
                          </select>
                          <p className="text-xs text-muted-foreground">
                            Deezer uses public data; Spotify requires credentials in Config → Music
                            Sources
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label>Release types to include</Label>
                          <div className="flex flex-wrap gap-4">
                            {["album", "ep", "single", "other"].map((t) => (
                              <label
                                key={t}
                                className="flex items-center gap-2 cursor-pointer text-sm"
                              >
                                <input
                                  type="checkbox"
                                  checked={(editForm.album_types ?? ["album"]).includes(t)}
                                  onChange={(e) => {
                                    setEditForm((f) => {
                                      const current = f.album_types ?? ["album"];
                                      const next = e.target.checked
                                        ? [...current, t]
                                        : current.filter((x) => x !== t);
                                      return { ...f, album_types: next.length ? next : ["album"] };
                                    });
                                  }}
                                  className="rounded border-input"
                                />
                                {t.charAt(0).toUpperCase() + t.slice(1)}
                              </label>
                            ))}
                          </div>
                          <p className="text-xs text-muted-foreground">
                            Used for batch runs and ad-hoc artist scans
                          </p>
                        </div>
                      </>
                    )}

                    {/* Last Run */}
                    {editingCommand.last_run && (
                      <div className="space-y-2">
                        <Label>Last Run</Label>
                        <Input
                          value={new Date(editingCommand.last_run).toLocaleString()}
                          disabled
                        />
                      </div>
                    )}

                    {/* Last Status */}
                    {editingCommand.last_success !== null && (
                      <div className="space-y-2">
                        <Label>Last Status</Label>
                        <Badge variant={editingCommand.last_success ? "default" : "destructive"}>
                          {editingCommand.last_success ? "Success" : "Failed"}
                        </Badge>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex-shrink-0 flex justify-end gap-2 px-6 py-4 border-t bg-background">
                <Button variant="outline" onClick={() => setEditingCommand(null)}>
                  Close
                </Button>
                {editingCommand.command_name === "new_releases_discovery" && (
                  <Button
                    onClick={() =>
                      handleSaveCommand({
                        schedule_override: editForm.schedule_override,
                        schedule_cron: editForm.schedule_override
                          ? editForm.schedule_cron
                          : undefined,
                        config_json: {
                          ...(editingCommand.config_json || {}),
                          artists_per_run: editForm.artists_per_run,
                          album_types: (editForm.album_types ?? ["album"]).join(","),
                          new_releases_source: editForm.new_releases_source ?? "deezer",
                        },
                      })
                    }
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name === "discovery_lastfm" && (
                  <Button
                    onClick={() =>
                      handleSaveCommand({
                        schedule_override: editForm.schedule_override,
                        schedule_cron: editForm.schedule_override
                          ? editForm.schedule_cron
                          : undefined,
                        config_json: {
                          ...(editingCommand.config_json || {}),
                          artists_to_query: editForm.artists_to_query ?? 3,
                          similar_per_artist: editForm.similar_per_artist ?? 1,
                          artist_cooldown_days: editForm.artist_cooldown_days ?? 30,
                          limit: editForm.limit ?? 5,
                          min_match_score: editForm.min_match_score ?? 0.9,
                        },
                      })
                    }
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name.startsWith("playlist_sync_") && (
                  <Button
                    disabled={
                      (editingCommand.config_json?.source as string) !== "listenbrainz" &&
                      (editingCommand.config_json?.target as string) === "plex" &&
                      !!editForm.sync_to_multiple_plex_users &&
                      (editForm.plex_account_ids ?? []).length === 0
                    }
                    onClick={() => {
                      const cfg: Record<string, unknown> = {
                        ...(editingCommand.config_json || {}),
                        enable_artist_discovery: editForm.enable_artist_discovery ?? false,
                        artist_discovery_max_per_run:
                          editForm.artist_discovery_max_per_run ??
                          (editForm.enable_artist_discovery ? 2 : 0),
                      };
                      if ((editingCommand.config_json?.source as string) === "listenbrainz") {
                        cfg.weekly_exploration_keep = editForm.weekly_exploration_keep ?? 2;
                        cfg.weekly_jams_keep = editForm.weekly_jams_keep ?? 2;
                        cfg.daily_jams_keep = editForm.daily_jams_keep ?? 3;
                        cfg.cleanup_enabled = editForm.cleanup_enabled ?? true;
                      }
                      if (
                        (editingCommand.config_json?.source as string) !== "listenbrainz" &&
                        (editingCommand.config_json?.target as string) === "plex"
                      ) {
                        cfg.plex_account_ids = editForm.sync_to_multiple_plex_users
                          ? (editForm.plex_account_ids ?? [])
                          : [];
                      }
                      if (editForm.expires_at_enabled && editForm.expires_at) {
                        cfg.expires_at = toExpiresAtIso(editForm.expires_at);
                        cfg.expires_at_delete_playlist =
                          editForm.expires_at_delete_playlist ?? true;
                      } else {
                        delete cfg.expires_at;
                        delete cfg.expires_at_delete_playlist;
                      }
                      handleSaveCommand({
                        schedule_override: editForm.schedule_override,
                        schedule_cron: editForm.schedule_override
                          ? editForm.schedule_cron
                          : undefined,
                        config_json: cfg,
                      });
                    }}
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name.startsWith("daylist_") && (
                  <Button
                    onClick={() => {
                      const time_periods: Record<string, number[]> = {};
                      for (const [period, { start, end }] of Object.entries(
                        editForm.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS
                      )) {
                        time_periods[period] = hoursFromRange(start, end);
                      }
                      const cfg: Record<string, unknown> = {
                        ...(editingCommand.config_json || {}),
                        schedule_minute: editForm.schedule_minute ?? 0,
                        plex_history_account_id: editForm.plex_history_account_id ?? "",
                        exclude_played_days: editForm.exclude_played_days ?? 3,
                        history_lookback_days: editForm.history_lookback_days ?? 45,
                        max_tracks: editForm.max_tracks ?? 50,
                        sonic_similar_limit: editForm.sonic_similar_limit ?? 10,
                        sonic_similarity_limit: editForm.sonic_similarity_limit ?? 50,
                        sonic_similarity_distance: editForm.sonic_similarity_distance ?? 0.8,
                        historical_ratio: editForm.historical_ratio ?? 0.4,
                        timezone: editForm.timezone || undefined,
                        time_periods,
                        use_primary_mood: editForm.use_primary_mood ?? false,
                      };
                      if (editForm.expires_at_enabled && editForm.expires_at) {
                        cfg.expires_at = toExpiresAtIso(editForm.expires_at);
                        cfg.expires_at_delete_playlist =
                          editForm.expires_at_delete_playlist ?? true;
                      } else {
                        delete cfg.expires_at;
                        delete cfg.expires_at_delete_playlist;
                      }
                      handleSaveCommand({ config_json: cfg });
                    }}
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name.startsWith("top_tracks_") && (
                  <Button
                    onClick={() => {
                      const artistsRaw = (editForm.artists ?? "").trim().split("\n");
                      const artists = artistsRaw.filter((a: string) => a.trim());
                      const cfg: Record<string, unknown> = {
                        ...(editingCommand.config_json || {}),
                        artists,
                        top_x: editForm.top_x ?? 5,
                        source: editForm.source ?? "plex",
                        target: editForm.target ?? "plex",
                        use_custom_playlist_name: editForm.use_custom_playlist_name ?? false,
                        custom_playlist_name: editForm.custom_playlist_name ?? "",
                      };
                      if (editForm.expires_at_enabled && editForm.expires_at) {
                        cfg.expires_at = toExpiresAtIso(editForm.expires_at);
                        cfg.expires_at_delete_playlist =
                          editForm.expires_at_delete_playlist ?? true;
                      } else {
                        delete cfg.expires_at;
                        delete cfg.expires_at_delete_playlist;
                      }
                      handleSaveCommand({
                        schedule_override: editForm.schedule_override,
                        schedule_cron: editForm.schedule_override
                          ? editForm.schedule_cron
                          : undefined,
                        config_json: cfg,
                      });
                    }}
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name.startsWith("local_discovery_") && (
                  <Button
                    onClick={() => {
                      const cfg: Record<string, unknown> = {
                        ...(editingCommand.config_json || {}),
                        plex_history_account_id: editForm.plex_history_account_id ?? "",
                        lookback_days: editForm.lookback_days ?? 90,
                        exclude_played_days: editForm.exclude_played_days ?? 3,
                        top_artists_count: editForm.top_artists_count ?? 10,
                        artist_pool_size: editForm.artist_pool_size ?? 20,
                        max_tracks: editForm.max_tracks ?? 50,
                        sonic_similar_limit: editForm.sonic_similar_limit ?? 15,
                        sonic_similarity_distance: editForm.sonic_similarity_distance ?? 0.25,
                        historical_ratio: editForm.historical_ratio ?? 0.4,
                      };
                      if (editForm.expires_at_enabled && editForm.expires_at) {
                        cfg.expires_at = toExpiresAtIso(editForm.expires_at);
                      } else {
                        delete cfg.expires_at;
                      }
                      handleSaveCommand({
                        schedule_override: editForm.schedule_override,
                        schedule_cron: editForm.schedule_override
                          ? editForm.schedule_cron
                          : undefined,
                        config_json: cfg,
                      });
                    }}
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name.startsWith("mood_playlist_") && (
                  <Button
                    onClick={() => {
                      const cfg: Record<string, unknown> = {
                        ...(editingCommand.config_json || {}),
                        moods: editForm.moods ?? [],
                        use_custom_playlist_name: editForm.use_custom_playlist_name ?? false,
                        custom_playlist_name: editForm.custom_playlist_name ?? "",
                        max_tracks: editForm.max_tracks ?? 50,
                        exclude_last_run: editForm.exclude_last_run ?? true,
                        limit_by_year: editForm.limit_by_year ?? false,
                        min_year:
                          editForm.limit_by_year && editForm.min_year != null
                            ? Math.max(1800, Math.min(2100, editForm.min_year))
                            : undefined,
                        max_year:
                          editForm.limit_by_year && editForm.max_year != null
                            ? Math.max(1800, Math.min(2100, editForm.max_year))
                            : undefined,
                      };
                      if (editForm.expires_at_enabled && editForm.expires_at) {
                        cfg.expires_at = toExpiresAtIso(editForm.expires_at);
                      } else {
                        delete cfg.expires_at;
                      }
                      handleSaveCommand({
                        schedule_override: editForm.schedule_override,
                        schedule_cron: editForm.schedule_override
                          ? editForm.schedule_cron
                          : undefined,
                        config_json: cfg,
                      });
                    }}
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name.startsWith("xmplaylist_") && (
                  <Button
                    disabled={
                      editForm.target === "plex" &&
                      !!editForm.sync_to_multiple_plex_users &&
                      (editForm.plex_account_ids ?? []).length === 0
                    }
                    onClick={() => {
                      const cfg: Record<string, unknown> = {
                        ...(editingCommand.config_json || {}),
                        station_deeplink: (editForm.xm_station_deeplink ?? "").trim(),
                        station_display_name: (
                          editForm.xm_station_display_name ??
                          editForm.xm_station_deeplink ??
                          ""
                        ).trim(),
                        playlist_kind: editForm.xm_playlist_kind ?? "newest",
                        most_heard_days: editForm.xm_most_heard_days ?? 30,
                        max_tracks: Math.max(1, Math.min(50, editForm.max_tracks ?? 50)),
                        target: editForm.target ?? "plex",
                        enable_artist_discovery: editForm.enable_artist_discovery ?? false,
                        artist_discovery_max_per_run: editForm.artist_discovery_max_per_run ?? 2,
                      };
                      const tgt = (editForm.target ?? "plex") as string;
                      if (tgt === "plex") {
                        const multi = !!editForm.sync_to_multiple_plex_users;
                        const ids = editForm.plex_account_ids ?? [];
                        if (multi && ids.length > 0) {
                          cfg.plex_account_ids = ids;
                          delete cfg.plex_playlist_account_id;
                        } else {
                          delete cfg.plex_account_ids;
                          delete cfg.plex_playlist_account_id;
                        }
                      } else {
                        delete cfg.plex_account_ids;
                        delete cfg.plex_playlist_account_id;
                      }
                      if (editForm.expires_at_enabled && editForm.expires_at) {
                        cfg.expires_at = toExpiresAtIso(editForm.expires_at);
                        cfg.expires_at_delete_playlist =
                          editForm.expires_at_delete_playlist ?? true;
                      } else {
                        delete cfg.expires_at;
                        delete cfg.expires_at_delete_playlist;
                      }
                      handleSaveCommand({
                        schedule_override: editForm.schedule_override,
                        schedule_cron: editForm.schedule_override
                          ? editForm.schedule_cron
                          : undefined,
                        config_json: cfg,
                      });
                    }}
                  >
                    Save
                  </Button>
                )}
                {editingCommand.command_name !== "new_releases_discovery" &&
                  editingCommand.command_name !== "discovery_lastfm" &&
                  !editingCommand.command_name.startsWith("playlist_sync_") &&
                  !editingCommand.command_name.startsWith("daylist_") &&
                  !editingCommand.command_name.startsWith("top_tracks_") &&
                  !editingCommand.command_name.startsWith("mood_playlist_") &&
                  !editingCommand.command_name.startsWith("xmplaylist_") &&
                  !editingCommand.command_name.startsWith("local_discovery_") && (
                    <Button
                      onClick={() =>
                        handleSaveCommand({
                          schedule_override: editForm.schedule_override,
                          schedule_cron: editForm.schedule_override
                            ? editForm.schedule_cron
                            : undefined,
                        })
                      }
                    >
                      Save
                    </Button>
                  )}
                <Button onClick={() => handleToggleEnabled(editingCommand)}>
                  {editingCommand.enabled ? "Disable" : "Enable"}
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
