import { useState, useEffect, useMemo } from "react";
import {
  Play,
  Pencil,
  Trash2,
  MoreVertical,
  Plus,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";
import type { CommandConfig } from "@/lib/types";
import { formatCommandTypeLabel } from "@/lib/commandTypeLabels";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CreatePlaylistSyncDialog } from "@/components/CreatePlaylistSyncDialog";
import { CommandEditDialog } from "@/components/CommandEditDialog";
import { DeleteCommandDialog } from "@/components/DeleteCommandDialog";
import { CommandExecutionsPanel } from "@/components/CommandExecutionsPanel";
import { fromExpiresAtIso } from "@/lib/expiration";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { ArrContentPanel, ArrPageToolbar } from "@/arr/components/ArrPageToolbar";
import {
  DEFAULT_DAYLIST_TIME_PERIODS,
  hoursFromRange,
  hoursToRange,
} from "@/components/command-edit/daylistTime";
import { CommandEditFormBody } from "@/components/command-edit/CommandEditFormBody";
import {
  applyExpiryToConfig,
  buildScheduleAndExpiryConfig,
  buildSchedulePayload,
} from "@/components/command-edit/saveHelpers";
import type { CommandEditFormState, XmplaylistStationRow } from "@/components/command-edit/types";

type SortField = "name" | "status" | "type" | "schedule" | "last_run";
type SortDirection = "asc" | "desc";

function CommandsSortIcon({
  column,
  sortField,
  sortDirection,
}: {
  column: SortField;
  sortField: SortField;
  sortDirection: SortDirection;
}) {
  if (sortField !== column) return <span className="inline-block w-4" />;
  return sortDirection === "asc" ? (
    <ChevronUp className="ml-1 inline h-4 w-4" />
  ) : (
    <ChevronDown className="ml-1 inline h-4 w-4" />
  );
}

type CommandsToolbarControlsProps = {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  activeFilterCount: number;
  statusFilter: "all" | "enabled" | "disabled";
  setStatusFilter: (value: "all" | "enabled" | "disabled") => void;
  typeFilter: string;
  setTypeFilter: (value: string) => void;
  commandTypes: string[];
};

function CommandsToolbarControls({
  searchQuery,
  setSearchQuery,
  activeFilterCount,
  statusFilter,
  setStatusFilter,
  typeFilter,
  setTypeFilter,
  commandTypes,
}: CommandsToolbarControlsProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto">
        <div className="relative min-w-0 flex-1 sm:w-64 sm:flex-none">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search commands..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 pl-8"
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary" size="sm">
              <Filter className="mr-2 h-4 w-4" />
              Filter
              {activeFilterCount > 0 ? (
                <Badge variant="secondary" className="ml-2">
                  {activeFilterCount}
                </Badge>
              ) : null}
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
                        {type === "all" ? "All" : formatCommandTypeLabel(type)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                variant="secondary"
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
    </div>
  );
}

const BUILTIN_COMMANDS = [
  "discovery_lastfm",
  "library_cache_builder",
  "new_releases_discovery",
  "playlist_sync_discovery_maintenance",
  "artist_events_refresh",
  "library_audit",
];

function formatCommandLastRun(value: string | null | undefined, compact: boolean): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (!compact) return date.toLocaleString();
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function CommandActionsMenu({
  command,
  onExecute,
  onEdit,
  onToggleEnabled,
  onDelete,
  triggerClassName,
}: {
  command: CommandConfig;
  onExecute: (command: CommandConfig) => void;
  onEdit: (command: CommandConfig) => void;
  onToggleEnabled: (command: CommandConfig) => void;
  onDelete: (commandName: string) => void;
  triggerClassName?: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn("h-9 w-9 shrink-0", triggerClassName)}
          aria-label={`Actions for ${command.display_name}`}
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onExecute(command)}>
          <Play className="mr-2 h-4 w-4" />
          Run Now
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onEdit(command)}>
          <Pencil className="mr-2 h-4 w-4" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => onToggleEnabled(command)}>
          {command.enabled ? "Disable" : "Enable"}
        </DropdownMenuItem>
        {!BUILTIN_COMMANDS.includes(command.command_name) && (
          <DropdownMenuItem
            className="text-destructive"
            onClick={() => onDelete(command.command_name)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

type CommandsListBodyProps = {
  filteredCommands: CommandConfig[];
  sortField: SortField;
  sortDirection: SortDirection;
  handleSort: (field: SortField) => void;
  handleExecute: (command: CommandConfig) => void;
  handleEdit: (command: CommandConfig) => void;
  handleToggleEnabled: (command: CommandConfig) => void;
  handleDelete: (commandName: string) => void;
};

function CommandsListBody({
  filteredCommands,
  sortField,
  sortDirection,
  handleSort,
  handleExecute,
  handleEdit,
  handleToggleEnabled,
  handleDelete,
}: CommandsListBodyProps) {
  return (
    <>
      <div className="divide-y md:hidden">
        {filteredCommands.map((command) => (
          <div key={command.id} className="flex items-start gap-2 px-3 py-2.5">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-start gap-2">
                <span className="min-w-0 flex-1 truncate text-sm font-medium leading-snug">
                  {command.display_name}
                </span>
                <Badge
                  variant={command.enabled ? "default" : "secondary"}
                  className="shrink-0 text-[10px]"
                >
                  {command.enabled ? "On" : "Off"}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
                {command.command_type ? (
                  <span className="truncate">{formatCommandTypeLabel(command.command_type)}</span>
                ) : null}
                <span className="font-mono">
                  {command.schedule_override && command.schedule_cron
                    ? command.schedule_cron
                    : "Default"}
                </span>
                <span>{formatCommandLastRun(command.last_run, true)}</span>
                {command.last_success !== null ? (
                  <span
                    className={
                      command.last_success
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }
                  >
                    {command.last_success ? "OK" : "Fail"}
                  </span>
                ) : null}
              </div>
            </div>
            <CommandActionsMenu
              command={command}
              onExecute={handleExecute}
              onEdit={handleEdit}
              onToggleEnabled={handleToggleEnabled}
              onDelete={handleDelete}
            />
          </div>
        ))}
      </div>
      <div className="hidden overflow-x-auto md:block">
        <table className="arr-table w-full">
          <thead className="border-b">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium">
                <button
                  onClick={() => handleSort("name")}
                  className="flex cursor-pointer items-center hover:text-foreground"
                >
                  Name{" "}
                  <CommandsSortIcon
                    column="name"
                    sortField={sortField}
                    sortDirection={sortDirection}
                  />
                </button>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium">
                <button
                  onClick={() => handleSort("status")}
                  className="flex cursor-pointer items-center hover:text-foreground"
                >
                  Status{" "}
                  <CommandsSortIcon
                    column="status"
                    sortField={sortField}
                    sortDirection={sortDirection}
                  />
                </button>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium">
                <button
                  onClick={() => handleSort("type")}
                  className="flex cursor-pointer items-center hover:text-foreground"
                >
                  Type{" "}
                  <CommandsSortIcon
                    column="type"
                    sortField={sortField}
                    sortDirection={sortDirection}
                  />
                </button>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium">
                <button
                  onClick={() => handleSort("schedule")}
                  className="flex cursor-pointer items-center hover:text-foreground"
                >
                  Schedule{" "}
                  <CommandsSortIcon
                    column="schedule"
                    sortField={sortField}
                    sortDirection={sortDirection}
                  />
                </button>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium">
                <button
                  onClick={() => handleSort("last_run")}
                  className="flex cursor-pointer items-center hover:text-foreground"
                >
                  Last Run{" "}
                  <CommandsSortIcon
                    column="last_run"
                    sortField={sortField}
                    sortDirection={sortDirection}
                  />
                </button>
              </th>
              <th className="px-4 py-3 text-right text-sm font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filteredCommands.map((command) => (
              <tr key={command.id}>
                <td className="px-4 py-3">
                  <div>
                    <div className="font-medium">{command.display_name}</div>
                    {command.description ? (
                      <div className="text-xs text-muted-foreground">{command.description}</div>
                    ) : null}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={command.enabled ? "default" : "secondary"} className="text-xs">
                    {command.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  {command.command_type ? (
                    <Badge variant="outline" className="text-xs">
                      {formatCommandTypeLabel(command.command_type)}
                    </Badge>
                  ) : null}
                </td>
                <td className="px-4 py-3 font-mono text-sm text-muted-foreground">
                  {command.schedule_override && command.schedule_cron
                    ? command.schedule_cron
                    : "Default"}
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {command.last_run ? new Date(command.last_run).toLocaleString() : "Never"}
                </td>
                <td className="px-4 py-3 text-right">
                  <CommandActionsMenu
                    command={command}
                    onExecute={handleExecute}
                    onEdit={handleEdit}
                    onToggleEnabled={handleToggleEnabled}
                    onDelete={handleDelete}
                    triggerClassName="h-8 w-8"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

type CommandsPageProps = {
  showExecutions?: boolean;
};

export function CommandsPage({ showExecutions = true }: CommandsPageProps) {
  const [commands, setCommands] = useState<CommandConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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

  const [showNewCommandDialog, setShowNewCommandDialog] = useState(false);
  const [deleteCommandTarget, setDeleteCommandTarget] = useState<string | null>(null);
  const [deleteCommandDeleting, setDeleteCommandDeleting] = useState(false);
  const [editingCommand, setEditingCommand] = useState<CommandConfig | null>(null);
  const [editForm, setEditForm] = useState<CommandEditFormState>({});
  const [plexAccounts, setPlexAccounts] = useState<{ id: string; name: string }[]>([]);
  const [daylistUsedIds, setDaylistUsedIds] = useState<Set<string>>(new Set());
  const [localDiscoveryUsedIds, setLocalDiscoveryUsedIds] = useState<Set<string>>(new Set());
  const [moodsList, setMoodsList] = useState<string[]>([]);
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
  const [nrdSources, setNrdSources] = useState<{ id: string; name: string; configured: boolean }[]>(
    []
  );

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

  useEffect(() => {
    loadCommands();
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

  // Auto-refresh commands every 5s; pause when edit or create dialog is open
  useEffect(() => {
    if (editingCommand || showNewCommandDialog) return;
    const id = setInterval(loadCommands, 5000);
    return () => clearInterval(id);
  }, [editingCommand, showNewCommandDialog]);

  const handleExecute = async (command: CommandConfig) => {
    try {
      const result = await api.executeCommand(command.command_name, { triggered_by: "manual" });
      const displayName = command.display_name || command.command_name;
      toast.success(result?.message || `Command "${displayName}" started`);
      loadCommands();
    } catch (error) {
      toast.error(`Failed to execute command`);
      console.error(error);
    }
  };

  const handleToggleEnabled = async (command: CommandConfig) => {
    try {
      const enabling = !command.enabled;
      if (enabling && command.command_name === "discovery_lastfm") {
        const cfg = command.config_json || {};
        const q = Number(cfg.quality_profile_id || 0);
        const m = Number(cfg.metadata_profile_id || 0);
        if (!Number.isFinite(q) || q < 1 || !Number.isFinite(m) || m < 1) {
          toast.error(
            "Set Lidarr quality and metadata profiles in command settings before enabling Last.fm Discovery"
          );
          return;
        }
      }
      await api.updateCommand(command.command_name, { enabled: enabling });
      toast.success(`Command ${command.enabled ? "disabled" : "enabled"}`);
      await loadCommands();
      if (editingCommand?.command_name === command.command_name) {
        const updated = (await api.getCommands()).find(
          (c) => c.command_name === command.command_name
        );
        if (updated) setEditingCommand(updated);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update command");
      console.error(error);
    }
  };

  const handleEdit = (command: CommandConfig) => {
    setEditingCommand(command);
    const cfg = command.config_json || {};
    const typesStr = (cfg.album_types as string) || "album";
    const src = (cfg.new_releases_source as string) || "deezer";
    const nrdSource = src === "spotify_scraper" || src === "spotify" ? "spotify" : "deezer";
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

    const cfgPlexIdsRaw = Array.isArray(cfg.plex_account_ids)
      ? cfg.plex_account_ids.map(String)
      : [];
    let syncMultiPlex = cfgPlexIdsRaw.length > 0;
    let plexAccountIdsList = cfgPlexIdsRaw;
    if (command.command_name.startsWith("xmplaylist_")) {
      const legacyPlexPlaylistId = String(cfg.plex_playlist_account_id ?? "").trim();
      if (cfgPlexIdsRaw.length === 0 && legacyPlexPlaylistId) {
        syncMultiPlex = true;
        plexAccountIdsList = [legacyPlexPlaylistId];
      }
    }

    const isArtistEvents = command.command_name === "artist_events_refresh";
    const isNrd = command.command_name === "new_releases_discovery";
    const apCfg = cfg.artists_per_run;
    const artistsPerRunVal =
      typeof apCfg === "number"
        ? isArtistEvents
          ? Math.min(50, Math.max(1, apCfg))
          : isNrd
            ? Math.min(100, Math.max(1, apCfg))
            : apCfg
        : isArtistEvents
          ? 20
          : isNrd
            ? 25
            : 5;

    setEditForm({
      schedule_override: !!command.schedule_override,
      schedule_cron: command.schedule_cron || "0 6 * * *",
      artists_per_run: artistsPerRunVal,
      refresh_ttl_days: typeof cfg.refresh_ttl_days === "number" ? cfg.refresh_ttl_days : 14,
      analysis_batch_size:
        typeof cfg.analysis_batch_size === "number"
          ? Math.min(500, Math.max(1, cfg.analysis_batch_size))
          : 25,
      triage_batch_size:
        typeof cfg.triage_batch_size === "number"
          ? Math.min(500, Math.max(25, cfg.triage_batch_size))
          : typeof cfg.analysis_batch_size === "number"
            ? Math.min(500, Math.max(25, cfg.analysis_batch_size))
            : 150,
      deep_batch_size:
        typeof cfg.deep_batch_size === "number"
          ? Math.min(50, Math.max(0, cfg.deep_batch_size))
          : 10,
      prefer_triage_first: cfg.prefer_triage_first !== false,
      triage_sample_seconds:
        typeof cfg.triage_sample_seconds === "number"
          ? Math.min(120, Math.max(5, cfg.triage_sample_seconds))
          : 20,
      deep_sample_seconds:
        typeof cfg.deep_sample_seconds === "number"
          ? Math.min(180, Math.max(15, cfg.deep_sample_seconds))
          : 60,
      short_track_seconds:
        typeof cfg.short_track_seconds === "number"
          ? Math.min(60, Math.max(1, cfg.short_track_seconds))
          : 10,
      inventory_interval_hours:
        typeof cfg.inventory_interval_hours === "number"
          ? Math.min(168, Math.max(1, cfg.inventory_interval_hours))
          : 24,
      missing_retention_days:
        typeof cfg.missing_retention_days === "number"
          ? Math.min(3650, Math.max(1, cfg.missing_retention_days))
          : 90,
      continual_validation_enabled: !!cfg.continual_validation_enabled,
      continual_validation_batch_size:
        typeof cfg.continual_validation_batch_size === "number"
          ? Math.min(100, Math.max(1, cfg.continual_validation_batch_size))
          : 50,
      continual_validation_interval_days:
        typeof cfg.continual_validation_interval_days === "number"
          ? Math.min(365, Math.max(1, cfg.continual_validation_interval_days))
          : 14,
      album_types: typesStr
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
      new_releases_source: nrdSource,
      artists_to_query: typeof cfg.artists_to_query === "number" ? cfg.artists_to_query : 3,
      similar_per_artist: typeof cfg.similar_per_artist === "number" ? cfg.similar_per_artist : 1,
      artist_cooldown_days:
        typeof cfg.artist_cooldown_days === "number" ? cfg.artist_cooldown_days : 30,
      limit: typeof cfg.limit === "number" ? cfg.limit : 5,
      min_match_score: typeof cfg.min_match_score === "number" ? cfg.min_match_score : 0.9,
      quality_profile_id:
        typeof cfg.quality_profile_id === "number" && cfg.quality_profile_id > 0
          ? cfg.quality_profile_id
          : null,
      metadata_profile_id:
        typeof cfg.metadata_profile_id === "number" && cfg.metadata_profile_id > 0
          ? cfg.metadata_profile_id
          : null,
      search_for_missing_albums: !!cfg.search_for_missing_albums,
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
      historical_ratio: typeof cfg.historical_ratio === "number" ? cfg.historical_ratio : 0.3,
      timezone: (cfg.timezone as string) || "",
      time_periods: timePeriods,
      use_primary_mood: !!cfg.use_primary_mood,
      artists: Array.isArray(cfg.artists)
        ? (cfg.artists as string[]).join("\n")
        : (cfg.artists as string) || "",
      seed_artists: (() => {
        const s = cfg.seed_artists ?? cfg.artists;
        if (Array.isArray(s)) return (s as string[]).join("\n");
        return (s as string) || "";
      })(),
      similar_per_seed: typeof cfg.similar_per_seed === "number" ? cfg.similar_per_seed : 5,
      max_artists: typeof cfg.max_artists === "number" ? cfg.max_artists : 25,
      include_seeds: cfg.include_seeds !== false,
      top_x: typeof cfg.top_x === "number" ? cfg.top_x : 5,
      max_tracks_per_artist:
        typeof cfg.max_tracks_per_artist === "number" ? cfg.max_tracks_per_artist : 25,
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
        typeof cfg.weekly_exploration_keep === "number" ? cfg.weekly_exploration_keep : 3,
      weekly_jams_keep: typeof cfg.weekly_jams_keep === "number" ? cfg.weekly_jams_keep : 3,
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
      ignore_days: typeof cfg.ignore_days === "number" ? cfg.ignore_days : 14,
      settle_seconds: typeof cfg.settle_seconds === "number" ? cfg.settle_seconds : 30,
      sort_by: (cfg.sort_by as string) || "oldest_release_date",
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

  const handleDelete = (commandName: string) => {
    if (BUILTIN_COMMANDS.includes(commandName)) return;
    setDeleteCommandTarget(commandName);
  };

  const confirmDeleteCommand = async (deletePlaylist: boolean) => {
    if (!deleteCommandTarget) return;
    setDeleteCommandDeleting(true);
    try {
      await api.deleteCommand(deleteCommandTarget, { deletePlaylist });
      toast.success("Command deleted");
      setDeleteCommandTarget(null);
      loadCommands();
    } catch (error) {
      toast.error("Failed to delete command");
      console.error(error);
    } finally {
      setDeleteCommandDeleting(false);
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
      <div className="arr-page-panels">
        <div className="text-center text-muted-foreground">Loading commands...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="arr-page-panels">
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
    <div className="min-w-0 space-y-6 arr-page-panels">
      {/* Controls Row */}
      <ArrPageToolbar>
        <CommandsToolbarControls
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          activeFilterCount={activeFilterCount}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          typeFilter={typeFilter}
          setTypeFilter={setTypeFilter}
          commandTypes={commandTypes}
        />
      </ArrPageToolbar>

      {/* Commands Display */}
      {filteredCommands.length === 0 ? (
        <ArrContentPanel>
          <div className="arr-panel-body flex min-h-[400px] flex-col items-center justify-center gap-4 py-12">
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
            {safeCommands.length === 0 ? (
              <Button size="lg" onClick={() => setShowNewCommandDialog(true)}>
                <Plus className="mr-2 h-5 w-5" />
                Create Your First Command
              </Button>
            ) : null}
          </div>
        </ArrContentPanel>
      ) : (
        <ArrContentPanel>
          <CommandsListBody
            filteredCommands={filteredCommands}
            sortField={sortField}
            sortDirection={sortDirection}
            handleSort={handleSort}
            handleExecute={handleExecute}
            handleEdit={handleEdit}
            handleToggleEnabled={handleToggleEnabled}
            handleDelete={handleDelete}
          />
        </ArrContentPanel>
      )}

      {showExecutions ? (
        <CommandExecutionsPanel commands={commands} pausePolling={!!editingCommand} />
      ) : null}

      <CreatePlaylistSyncDialog
        open={showNewCommandDialog}
        onOpenChange={setShowNewCommandDialog}
        onSuccess={loadCommands}
      />

      <CommandEditDialog
        command={editingCommand}
        onOpenChange={(open) => !open && setEditingCommand(null)}
        formBody={
          editingCommand ? (
            <CommandEditFormBody
              ctx={{
                editingCommand,
                editForm,
                setEditForm,
                plexAccounts,
                daylistUsedIds,
                localDiscoveryUsedIds,
                moodsList,
                xmplaylistEditFilter,
                setXmplaylistEditFilter,
                xmplaylistEditLoading,
                filteredXmEditStations,
                nrdSources,
              }}
            />
          ) : null
        }
        footer={
          editingCommand ? (
            <>
              <Button variant="outline" onClick={() => setEditingCommand(null)}>
                Close
              </Button>
              {editingCommand.command_name === "new_releases_discovery" && (
                <Button
                  onClick={() =>
                    handleSaveCommand({
                      ...buildSchedulePayload(editForm),
                      config_json: {
                        ...(editingCommand.config_json || {}),
                        artists_per_run: Math.min(100, Math.max(1, editForm.artists_per_run ?? 25)),
                        album_types: (editForm.album_types ?? ["album"]).join(","),
                        new_releases_source: editForm.new_releases_source ?? "deezer",
                        continual_validation_enabled: !!editForm.continual_validation_enabled,
                        continual_validation_batch_size: Math.min(
                          100,
                          Math.max(1, editForm.continual_validation_batch_size ?? 50)
                        ),
                        continual_validation_interval_days: Math.min(
                          365,
                          Math.max(1, editForm.continual_validation_interval_days ?? 14)
                        ),
                      },
                    })
                  }
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name === "discovery_lastfm" && (
                <Button
                  onClick={() => {
                    const q = Number(editForm.quality_profile_id || 0);
                    const m = Number(editForm.metadata_profile_id || 0);
                    if (!Number.isFinite(q) || q < 1 || !Number.isFinite(m) || m < 1) {
                      toast.error(
                        "Select Lidarr quality and metadata profiles before saving (required to enable)"
                      );
                      return;
                    }
                    void handleSaveCommand({
                      ...buildSchedulePayload(editForm),
                      config_json: {
                        ...(editingCommand.config_json || {}),
                        artists_to_query: editForm.artists_to_query ?? 3,
                        similar_per_artist: editForm.similar_per_artist ?? 1,
                        artist_cooldown_days: editForm.artist_cooldown_days ?? 30,
                        limit: editForm.limit ?? 5,
                        min_match_score: editForm.min_match_score ?? 0.9,
                        quality_profile_id: q,
                        metadata_profile_id: m,
                        search_for_missing_albums: !!editForm.search_for_missing_albums,
                      },
                    });
                  }}
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name === "artist_events_refresh" && (
                <Button
                  onClick={() =>
                    handleSaveCommand({
                      ...buildSchedulePayload(editForm),
                      config_json: {
                        ...(editingCommand.config_json || {}),
                        artists_per_run: Math.min(50, Math.max(1, editForm.artists_per_run ?? 20)),
                        refresh_ttl_days: Math.min(
                          365,
                          Math.max(1, editForm.refresh_ttl_days ?? 14)
                        ),
                      },
                    })
                  }
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name === "library_audit" && (
                <Button
                  onClick={() =>
                    handleSaveCommand({
                      ...buildSchedulePayload(editForm),
                      config_json: {
                        ...(editingCommand.config_json || {}),
                        triage_batch_size: Math.min(
                          500,
                          Math.max(
                            25,
                            editForm.triage_batch_size ?? editForm.analysis_batch_size ?? 150
                          )
                        ),
                        deep_batch_size: Math.min(50, Math.max(0, editForm.deep_batch_size ?? 10)),
                        prefer_triage_first: editForm.prefer_triage_first !== false,
                        deep_after_triage_pct: 80,
                        provider_mode: "triage",
                        triage_sample_seconds: Math.min(
                          120,
                          Math.max(5, editForm.triage_sample_seconds ?? 20)
                        ),
                        deep_sample_seconds: Math.min(
                          180,
                          Math.max(15, editForm.deep_sample_seconds ?? 60)
                        ),
                        short_track_seconds: Math.min(
                          60,
                          Math.max(1, editForm.short_track_seconds ?? 10)
                        ),
                        require_deep_for_fake_certain: true,
                        inventory_interval_hours: Math.min(
                          168,
                          Math.max(1, editForm.inventory_interval_hours ?? 24)
                        ),
                        missing_retention_days: Math.min(
                          3650,
                          Math.max(1, editForm.missing_retention_days ?? 90)
                        ),
                      },
                    })
                  }
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name.startsWith("lidarr_update_all_") && (
                <Button onClick={() => handleSaveCommand(buildSchedulePayload(editForm))}>
                  Save
                </Button>
              )}
              {editingCommand.command_name.startsWith("lidarr_wanted_search_") && (
                <Button
                  onClick={() =>
                    handleSaveCommand({
                      ...buildSchedulePayload(editForm),
                      config_json: {
                        ...(editingCommand.config_json || {}),
                        top_x: Math.min(50, Math.max(1, editForm.top_x ?? 10)),
                        ignore_days: Math.min(365, Math.max(1, editForm.ignore_days ?? 14)),
                        settle_seconds: Math.min(300, Math.max(0, editForm.settle_seconds ?? 30)),
                        sort_by: editForm.sort_by || "oldest_release_date",
                        album_types: (editForm.album_types ?? ["album"]).join(","),
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
                      cfg.weekly_exploration_keep = editForm.weekly_exploration_keep ?? 3;
                      cfg.weekly_jams_keep = editForm.weekly_jams_keep ?? 3;
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
                    handleSaveCommand(buildScheduleAndExpiryConfig(editForm, cfg));
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
                      historical_ratio: editForm.historical_ratio ?? 0.3,
                      timezone: editForm.timezone || undefined,
                      time_periods,
                      use_primary_mood: editForm.use_primary_mood ?? false,
                    };
                    applyExpiryToConfig(cfg, editForm);
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
                    handleSaveCommand(
                      buildScheduleAndExpiryConfig(editForm, {
                        ...(editingCommand.config_json || {}),
                        artists,
                        top_x: editForm.top_x ?? 5,
                        source: editForm.source ?? "plex",
                        target: editForm.target ?? "plex",
                        use_custom_playlist_name: editForm.use_custom_playlist_name ?? false,
                        custom_playlist_name: editForm.custom_playlist_name ?? "",
                      })
                    );
                  }}
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name.startsWith("lfm_similar_") && (
                <Button
                  onClick={() => {
                    const seedsRaw = (editForm.seed_artists ?? "").trim().split("\n");
                    const seed_artists = seedsRaw.filter((a: string) => a.trim());
                    handleSaveCommand(
                      buildScheduleAndExpiryConfig(editForm, {
                        ...(editingCommand.config_json || {}),
                        seed_artists,
                        similar_per_seed: Math.max(1, Math.min(50, editForm.similar_per_seed ?? 5)),
                        max_artists: Math.max(1, Math.min(200, editForm.max_artists ?? 25)),
                        include_seeds: editForm.include_seeds !== false,
                        top_x: Math.max(1, Math.min(20, editForm.top_x ?? 5)),
                        source: "lastfm",
                        target: editForm.target ?? "plex",
                        use_custom_playlist_name: editForm.use_custom_playlist_name ?? false,
                        custom_playlist_name: editForm.custom_playlist_name ?? "",
                      })
                    );
                  }}
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name.startsWith("setlistfm_") && (
                <Button
                  onClick={() => {
                    const artistsRaw = (editForm.artists ?? "").trim().split("\n");
                    const artists = artistsRaw.filter((a: string) => a.trim());
                    const base: Record<string, unknown> = {
                      ...(editingCommand.config_json || {}),
                      artists,
                      max_tracks_per_artist: Math.max(
                        3,
                        Math.min(30, editForm.max_tracks_per_artist ?? 25)
                      ),
                      target: editForm.target ?? "plex",
                      use_custom_playlist_name: editForm.use_custom_playlist_name ?? false,
                      custom_playlist_name: editForm.custom_playlist_name ?? "",
                    };
                    delete base.max_setlist_pages;
                    handleSaveCommand(buildScheduleAndExpiryConfig(editForm, base));
                  }}
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name.startsWith("local_discovery_") && (
                <Button
                  onClick={() =>
                    handleSaveCommand(
                      buildScheduleAndExpiryConfig(editForm, {
                        ...(editingCommand.config_json || {}),
                        plex_history_account_id: editForm.plex_history_account_id ?? "",
                        lookback_days: editForm.lookback_days ?? 90,
                        exclude_played_days: editForm.exclude_played_days ?? 3,
                        top_artists_count: editForm.top_artists_count ?? 10,
                        artist_pool_size: editForm.artist_pool_size ?? 20,
                        max_tracks: editForm.max_tracks ?? 50,
                        sonic_similar_limit: editForm.sonic_similar_limit ?? 15,
                        sonic_similarity_distance: editForm.sonic_similarity_distance ?? 0.25,
                        historical_ratio: editForm.historical_ratio ?? 0.3,
                      })
                    )
                  }
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name.startsWith("mood_playlist_") && (
                <Button
                  onClick={() =>
                    handleSaveCommand(
                      buildScheduleAndExpiryConfig(editForm, {
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
                      })
                    )
                  }
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
                    handleSaveCommand(buildScheduleAndExpiryConfig(editForm, cfg));
                  }}
                >
                  Save
                </Button>
              )}
              {editingCommand.command_name !== "new_releases_discovery" &&
                editingCommand.command_name !== "discovery_lastfm" &&
                editingCommand.command_name !== "artist_events_refresh" &&
                editingCommand.command_name !== "library_audit" &&
                !editingCommand.command_name.startsWith("playlist_sync_") &&
                !editingCommand.command_name.startsWith("daylist_") &&
                !editingCommand.command_name.startsWith("top_tracks_") &&
                !editingCommand.command_name.startsWith("lfm_similar_") &&
                !editingCommand.command_name.startsWith("setlistfm_") &&
                !editingCommand.command_name.startsWith("mood_playlist_") &&
                !editingCommand.command_name.startsWith("xmplaylist_") &&
                !editingCommand.command_name.startsWith("local_discovery_") &&
                !editingCommand.command_name.startsWith("lidarr_update_all_") &&
                !editingCommand.command_name.startsWith("lidarr_wanted_search_") && (
                  <Button onClick={() => handleSaveCommand(buildSchedulePayload(editForm))}>
                    Save
                  </Button>
                )}
              <Button onClick={() => handleToggleEnabled(editingCommand)}>
                {editingCommand.enabled ? "Disable" : "Enable"}
              </Button>
            </>
          ) : null
        }
      />
      <DeleteCommandDialog
        open={deleteCommandTarget !== null}
        commandName={deleteCommandTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteCommandTarget(null);
        }}
        onConfirm={confirmDeleteCommand}
        isDeleting={deleteCommandDeleting}
      />
    </div>
  );
}
