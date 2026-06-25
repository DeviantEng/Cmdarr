import { useState, useEffect, type ReactNode } from "react";
import {
  ArrContentPanel,
  ArrPageToolbar,
  ArrPanelBody,
  ArrSectionHeader,
} from "@/arr/components/ArrPageToolbar";
import { cn } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Server,
  RotateCcw,
  RefreshCw,
  RotateCw,
  Trash2,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  ArtistEventsStats,
  MigrationStatus,
  StatusInfo,
  LibraryCacheStatus,
  NrdMetrics,
} from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

export type StatusSection =
  | "health"
  | "system-info"
  | "migrations"
  | "artist-events"
  | "library-cache"
  | "new-releases"
  | "api-endpoints";

const ALL_STATUS_SECTIONS: StatusSection[] = [
  "health",
  "system-info",
  "migrations",
  "artist-events",
  "library-cache",
  "new-releases",
  "api-endpoints",
];

function StatusSectionPanel({
  useArrPanel,
  title,
  description,
  actions,
  children,
  bodyClassName,
}: {
  useArrPanel: boolean;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  bodyClassName?: string;
}) {
  if (useArrPanel) {
    return (
      <ArrContentPanel>
        <ArrSectionHeader title={title} description={description} actions={actions} />
        <ArrPanelBody className={bodyClassName}>{children}</ArrPanelBody>
      </ArrContentPanel>
    );
  }

  return (
    <Card>
      <CardHeader className={actions ? "space-y-2 py-3" : undefined}>
        {actions ? (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="text-base">{title}</CardTitle>
              {description ? (
                <CardDescription className="text-xs leading-snug">{description}</CardDescription>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>
          </div>
        ) : (
          <>
            <CardTitle>{title}</CardTitle>
            {description ? <CardDescription>{description}</CardDescription> : null}
          </>
        )}
      </CardHeader>
      <CardContent className={bodyClassName}>{children}</CardContent>
    </Card>
  );
}

type StatusPageProps = {
  sections?: StatusSection[];
  showPageHeader?: boolean;
  useArrPanel?: boolean;
};

export function StatusPage({
  sections = ALL_STATUS_SECTIONS,
  showPageHeader = true,
  useArrPanel = false,
}: StatusPageProps) {
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [health, setHealth] = useState<{
    status: string;
    message: string;
    timestamp: string;
  } | null>(null);
  const [cacheStatus, setCacheStatus] = useState<{
    plex: LibraryCacheStatus;
    jellyfin: LibraryCacheStatus;
  } | null>(null);
  const [nrdMetrics, setNrdMetrics] = useState<NrdMetrics | null>(null);
  const [cacheActionLoading, setCacheActionLoading] = useState<"refresh" | "rebuild" | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissedOpen, setDismissedOpen] = useState(false);
  const [dismissed, setDismissed] = useState<
    { id: number; artist_name: string; album_title: string; release_date?: string }[]
  >([]);
  const [dismissedTotal, setDismissedTotal] = useState(0);
  const [confirmRestoreAllOpen, setConfirmRestoreAllOpen] = useState(false);
  const [confirmResetOpen, setConfirmResetOpen] = useState(false);
  const [confirmInvalidateEventsOpen, setConfirmInvalidateEventsOpen] = useState(false);
  const [confirmActionLoading, setConfirmActionLoading] = useState<
    "restore-all" | "reset" | "invalidate-events" | null
  >(null);
  const [artistEventsStats, setArtistEventsStats] = useState<ArtistEventsStats | null>(null);
  const [migrationStatus, setMigrationStatus] = useState<MigrationStatus | null>(null);
  const [migrationRunning, setMigrationRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const showSection = (section: StatusSection) => sections.includes(section);

  const loadStatus = async () => {
    setError(null);
    try {
      const [bundle, healthData, cacheData, nrdData, migData] = await Promise.all([
        api.getStatus(),
        api.healthCheck().catch(() => null),
        api.getCacheStatus().catch(() => null),
        api.getNrdMetrics().catch(() => null),
        api.getMigrationStatus().catch(() => null),
      ]);
      setStatus(bundle.system);
      setArtistEventsStats(bundle.artist_events);
      setHealth(healthData);
      setCacheStatus(cacheData);
      setNrdMetrics(nrdData);
      setMigrationStatus(migData);
    } catch {
      setError("Failed to load status");
      toast.error("Failed to load status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadDismissed = async () => {
    try {
      const data = await api.getDismissedReleases({ limit: 100 });
      setDismissed(data.items);
      setDismissedTotal(data.total);
    } catch {
      setDismissed([]);
      setDismissedTotal(0);
    }
  };

  const handleRestore = async (id: number) => {
    try {
      await api.restoreDismissed(id);
      toast.success("Restored - will reappear on next scan");
      loadDismissed();
    } catch {
      toast.error("Failed to restore");
    }
  };

  const handleRestoreAll = async () => {
    setConfirmActionLoading("restore-all");
    try {
      const res = await api.restoreAllDismissed();
      toast.success(res.message ?? `Restored ${res.restored_count ?? 0} items`);
      setConfirmRestoreAllOpen(false);
      loadDismissed();
    } catch {
      toast.error("Failed to restore all");
    } finally {
      setConfirmActionLoading(null);
    }
  };

  const handleReset = async () => {
    setConfirmActionLoading("reset");
    try {
      const res = await api.resetNrdScanHistory();
      toast.success(res.message ?? `Cleared ${res.deleted_count ?? 0} scan records`);
      setConfirmResetOpen(false);
      loadStatus();
      loadDismissed();
    } catch {
      toast.error("Failed to reset scan history");
    } finally {
      setConfirmActionLoading(null);
    }
  };

  const handleInvalidateArtistEvents = async () => {
    setConfirmActionLoading("invalidate-events");
    try {
      const res = await api.invalidateArtistEventsCache();
      toast.success(
        `Cleared ${res.deleted_event_rows} events; ${res.reset_refresh_rows} artists due for refresh`
      );
      setConfirmInvalidateEventsOpen(false);
      loadStatus();
    } catch {
      toast.error("Failed to clear artist events cache");
    } finally {
      setConfirmActionLoading(null);
    }
  };

  const formatCacheTime = (ts: number | null) => {
    if (!ts) return "Never";
    return new Date(ts * 1000).toLocaleString();
  };

  const handleCacheRefresh = async (forceRebuild: boolean) => {
    setCacheActionLoading(forceRebuild ? "rebuild" : "refresh");
    try {
      const result = await api.refreshLibraryCache("all", forceRebuild);
      if (result.success) {
        toast.success(result.message ?? (forceRebuild ? "Cache rebuilt" : "Cache refreshed"));
        loadStatus();
      } else {
        toast.error(result.error ?? "Cache operation failed");
      }
    } catch {
      toast.error("Cache operation failed");
    } finally {
      setCacheActionLoading(null);
    }
  };

  const handleRunMigrations = async () => {
    setMigrationRunning(true);
    try {
      const res = await api.runDbMigrationsManual();
      if (res.migrations_run > 0) {
        toast.success(
          `Ran ${res.migrations_run} migration(s): ${res.migration_names.join(", ") || "none"}`
        );
      } else {
        toast.success("No migrations needed (already applied)");
      }
      const migData = await api.getMigrationStatus();
      setMigrationStatus(migData);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to run migrations");
    } finally {
      setMigrationRunning(false);
    }
  };

  const openDismissed = () => {
    setDismissedOpen(true);
    loadDismissed();
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);

    return parts.join(" ") || "<1m";
  };

  if (loading) {
    return (
      <div className={cn("space-y-6", useArrPanel && "arr-page-panels")}>
        {showPageHeader ? (
          <div className="mb-8">
            <h1 className="text-3xl font-bold">Status</h1>
            <p className="mt-2 text-muted-foreground">System status and health information</p>
          </div>
        ) : null}
        <div className="text-center text-muted-foreground">Loading status...</div>
      </div>
    );
  }

  const isHealthy = health?.status === "healthy";

  const healthBadge = isHealthy ? (
    <Badge variant="default" className="flex items-center gap-1 whitespace-nowrap">
      <CheckCircle2 className="h-4 w-4" />
      Healthy
    </Badge>
  ) : (
    <Badge variant="destructive" className="flex items-center gap-1 whitespace-nowrap">
      <XCircle className="h-4 w-4" />
      Unhealthy
    </Badge>
  );

  return (
    <div className={cn("space-y-6", useArrPanel && "arr-page-panels")}>
      {showPageHeader ? (
        <div>
          <h1 className="text-3xl font-bold">Status</h1>
          <p className="mt-2 text-muted-foreground">System status and health information</p>
        </div>
      ) : null}

      {useArrPanel ? (
        <ArrPageToolbar>
          <Button variant="outline" size="sm" onClick={() => void loadStatus()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </ArrPageToolbar>
      ) : null}

      {error && (
        <div className="flex flex-col gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="min-w-0 text-sm text-destructive">{error}</p>
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 self-start sm:self-auto"
            onClick={() => loadStatus()}
          >
            Try Again
          </Button>
        </div>
      )}

      {/* Overall Health */}
      {showSection("health") ? (
        <StatusSectionPanel
          useArrPanel={useArrPanel}
          title="System Health"
          description="Overall system status"
          actions={healthBadge}
        >
          <p className="text-sm text-muted-foreground">{health?.message}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Last checked: {health?.timestamp ? new Date(health.timestamp).toLocaleString() : "N/A"}
          </p>
        </StatusSectionPanel>
      ) : null}

      {/* System Information */}
      {showSection("system-info") && status ? (
        useArrPanel ? (
          <ArrContentPanel>
            <ArrSectionHeader
              title="System Information"
              description="Application runtime, database, and execution summary"
            />
            <ArrPanelBody>
              <div className="arr-stats-grid">
                <div>
                  <div className="text-lg font-semibold">{status.app_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {status.version}
                    {status.runtime_mode && (
                      <> · {status.runtime_mode === "docker" ? "Docker" : "Python"}</>
                    )}
                  </div>
                </div>
                <div>
                  <div className="text-lg font-semibold">{formatUptime(status.uptime_seconds)}</div>
                  <div className="text-xs text-muted-foreground">Uptime</div>
                </div>
                <div>
                  <div className="text-lg font-semibold capitalize">{status.database_status}</div>
                  <div className="text-xs text-muted-foreground">Database</div>
                </div>
                <div>
                  <div className="text-lg font-semibold capitalize">
                    {status.configuration_status}
                  </div>
                  <div className="text-xs text-muted-foreground">Configuration</div>
                </div>
                {status.execution_stats ? (
                  <div>
                    <div className="text-lg font-semibold">
                      {status.execution_stats.total_execution_count.toLocaleString()}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Executions · {status.execution_stats.total_success_count.toLocaleString()} ok
                      · {status.execution_stats.total_failure_count.toLocaleString()} failed
                    </div>
                  </div>
                ) : null}
              </div>
            </ArrPanelBody>
          </ArrContentPanel>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Application</CardTitle>
                <Server className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{status.app_name}</div>
                <p className="text-xs text-muted-foreground">
                  {status.version}
                  {status.runtime_mode && (
                    <> · {status.runtime_mode === "docker" ? "Docker" : "Python"}</>
                  )}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Uptime</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatUptime(status.uptime_seconds)}</div>
                <p className="text-xs text-muted-foreground">Running smoothly</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Database</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold capitalize">{status.database_status}</div>
                <p className="text-xs text-muted-foreground">
                  {status.database_status === "connected"
                    ? "Operating normally"
                    : "Check connection"}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Configuration</CardTitle>
                <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold capitalize">{status.configuration_status}</div>
                <p className="text-xs text-muted-foreground">
                  {status.configuration_status === "valid" ? "All set" : "Needs attention"}
                </p>
              </CardContent>
            </Card>

            {status.execution_stats && (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Execution Stats</CardTitle>
                  <Activity className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {status.execution_stats.total_execution_count.toLocaleString()} total
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {status.execution_stats.total_success_count.toLocaleString()} success ·{" "}
                    {status.execution_stats.total_failure_count.toLocaleString()} failed
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )
      ) : null}

      {showSection("migrations") && migrationStatus?.dev_manual_available ? (
        <StatusSectionPanel
          useArrPanel={useArrPanel}
          title="Database migrations"
          description={`Dev build only. Pending migrations run automatically on startup and are recorded in a per-migration ledger (${migrationStatus.current_version}${migrationStatus.last_run_version ? `, last recorded ${migrationStatus.last_run_version}` : ""}). Use this button to apply any still-pending migrations after pulling schema changes on the same -dev version.`}
          actions={
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={handleRunMigrations}
              disabled={migrationRunning}
            >
              {migrationRunning ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              )}
              Run migrations
            </Button>
          }
          bodyClassName="space-y-3"
        >
          {migrationStatus.pending_migrations.length > 0 ? (
            <div>
              <p className="mb-1 text-xs font-medium text-amber-600 dark:text-amber-400">
                Pending ({migrationStatus.pending_migrations.length})
              </p>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {migrationStatus.pending_migrations.map((m) => (
                  <li key={m.name}>
                    <span className="font-mono text-[10px]">{m.version}</span> · {m.name} —{" "}
                    {m.description}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No pending migrations.</p>
          )}
          {migrationStatus.applied_migrations.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Applied ({migrationStatus.applied_migrations.length})
              </p>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {migrationStatus.applied_migrations.map((m) => (
                  <li key={m.name}>
                    <span className="font-mono text-[10px]">{m.version}</span> · {m.name}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </StatusSectionPanel>
      ) : null}

      {showSection("artist-events") && artistEventsStats ? (
        <StatusSectionPanel
          useArrPanel={useArrPanel}
          title="Artist Events"
          description="Cached shows from the event refresh command. Clearing deletes stored events and per-artist scan timestamps so every library artist is due on the next run. Artist hides (from the Events page) are kept; single-event hides tied to deleted rows are removed."
          actions={
            <Button
              variant="outline"
              size="sm"
              className="shrink-0 text-destructive hover:text-destructive"
              onClick={() => setConfirmInvalidateEventsOpen(true)}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
              Clear event cache
            </Button>
          }
        >
          <div
            className={cn(
              "grid gap-3 text-sm",
              useArrPanel ? "arr-stats-grid" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6"
            )}
          >
            <div>
              <div className="text-lg font-semibold tabular-nums">
                {artistEventsStats.lidarr_artists.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Lidarr artists</div>
            </div>
            <div>
              <div className="text-lg font-semibold tabular-nums">
                {artistEventsStats.artists_scanned_at_least_once.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Scanned ≥ once</div>
            </div>
            <div>
              <div className="text-lg font-semibold tabular-nums">
                {artistEventsStats.scan_coverage_percent.toFixed(1)}%
              </div>
              <div className="text-xs text-muted-foreground">Scan coverage</div>
            </div>
            <div>
              <div className="text-lg font-semibold tabular-nums">
                {artistEventsStats.upcoming_events_stored.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Upcoming stored</div>
            </div>
            <div>
              <div className="text-lg font-semibold tabular-nums">
                {artistEventsStats.hidden_artists.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Hidden artists</div>
            </div>
            <div>
              <div className="text-lg font-semibold tabular-nums">
                {artistEventsStats.hidden_events.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Hidden events</div>
            </div>
          </div>
        </StatusSectionPanel>
      ) : null}

      {/* Library Cache */}
      {showSection("library-cache") && cacheStatus ? (
        <StatusSectionPanel
          useArrPanel={useArrPanel}
          title="Library Cache"
          description="Plex and Jellyfin music library cache stats and controls"
          actions={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleCacheRefresh(false)}
                disabled={!!cacheActionLoading}
              >
                <RefreshCw
                  className={`mr-1.5 h-3.5 w-3.5 ${cacheActionLoading === "refresh" ? "animate-spin" : ""}`}
                />
                Refresh
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleCacheRefresh(true)}
                disabled={!!cacheActionLoading}
              >
                <RotateCw
                  className={`mr-1.5 h-3.5 w-3.5 ${cacheActionLoading === "rebuild" ? "animate-spin" : ""}`}
                />
                Force Rebuild
              </Button>
            </>
          }
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border p-4">
              <div className="font-medium capitalize mb-2">Plex</div>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Objects</dt>
                  <dd>{cacheStatus.plex.object_count.toLocaleString()}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Last built</dt>
                  <dd>{formatCacheTime(cacheStatus.plex.last_generated)}</dd>
                </div>
                {cacheStatus.plex.hit_rate != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Hit rate</dt>
                    <dd>{(cacheStatus.plex.hit_rate * 100).toFixed(1)}%</dd>
                  </div>
                )}
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd>
                    <Badge
                      variant={cacheStatus.plex.status === "Available" ? "default" : "secondary"}
                    >
                      {cacheStatus.plex.status}
                    </Badge>
                  </dd>
                </div>
              </dl>
            </div>
            <div className="rounded-lg border p-4">
              <div className="font-medium capitalize mb-2">Jellyfin</div>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Objects</dt>
                  <dd>{cacheStatus.jellyfin.object_count.toLocaleString()}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Last built</dt>
                  <dd>{formatCacheTime(cacheStatus.jellyfin.last_generated)}</dd>
                </div>
                {cacheStatus.jellyfin.hit_rate != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Hit rate</dt>
                    <dd>{(cacheStatus.jellyfin.hit_rate * 100).toFixed(1)}%</dd>
                  </div>
                )}
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd>
                    <Badge
                      variant={
                        cacheStatus.jellyfin.status === "Available" ? "default" : "secondary"
                      }
                    >
                      {cacheStatus.jellyfin.status}
                    </Badge>
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </StatusSectionPanel>
      ) : null}

      {showSection("new-releases") ? (
        <StatusSectionPanel
          useArrPanel={useArrPanel}
          title="New Releases"
          description={
            nrdMetrics?.available
              ? `Lidarr artist scan coverage (within ${nrdMetrics.cache_ttl_days ?? 14}-day TTL). Dismissed releases can be restored below.`
              : "Dismissed releases from New Releases can be restored here"
          }
          bodyClassName="space-y-4"
        >
          {nrdMetrics?.available ? (
            <div className={cn(useArrPanel ? "arr-stats-grid" : "grid gap-4 sm:grid-cols-3")}>
              <div className={cn(!useArrPanel && "rounded-lg border p-4")}>
                <div className="text-2xl font-bold">
                  {nrdMetrics.total_lidarr_artists?.toLocaleString() ?? "—"}
                </div>
                <p className="text-sm text-muted-foreground">Lidarr artists</p>
              </div>
              <div className={cn(!useArrPanel && "rounded-lg border p-4")}>
                <div className="text-2xl font-bold">
                  {nrdMetrics.artists_scanned_fresh?.toLocaleString() ?? "—"}
                </div>
                <p className="text-sm text-muted-foreground">Scanned (fresh)</p>
                {nrdMetrics.total_lidarr_artists != null &&
                  nrdMetrics.total_lidarr_artists > 0 &&
                  nrdMetrics.artists_scanned_fresh != null && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {(
                        (nrdMetrics.artists_scanned_fresh / nrdMetrics.total_lidarr_artists) *
                        100
                      ).toFixed(1)}
                      % coverage
                    </p>
                  )}
              </div>
              <div className={cn(!useArrPanel && "rounded-lg border p-4")}>
                <div className="text-2xl font-bold">
                  {nrdMetrics.artists_not_scanned?.toLocaleString() ?? "—"}
                </div>
                <p className="text-sm text-muted-foreground">Not yet scanned</p>
              </div>
            </div>
          ) : null}
          <Button variant="outline" onClick={openDismissed}>
            <RotateCcw className="mr-2 h-4 w-4" />
            View / Restore Dismissed
          </Button>
        </StatusSectionPanel>
      ) : null}

      {showSection("new-releases") ? (
        <>
          {/* Dismissed Dialog */}
          <Dialog open={dismissedOpen} onOpenChange={setDismissedOpen}>
            <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
              <DialogHeader>
                <DialogTitle>Dismissed Releases</DialogTitle>
                <DialogDescription>
                  Restore to allow them to reappear on the next New Releases scan.
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-4 flex-1 overflow-hidden">
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setConfirmRestoreAllOpen(true)}
                    disabled={dismissedTotal === 0}
                  >
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                    Restore All
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setConfirmResetOpen(true)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                    Reset
                  </Button>
                </div>
                <div className="flex-1 overflow-y-auto space-y-2">
                  {dismissed.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No dismissed releases.</p>
                  ) : (
                    dismissed.map((item) => (
                      <div
                        key={item.id}
                        className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0 flex-1">
                          <span className="font-medium">{item.artist_name}</span>
                          <span className="mx-2 text-muted-foreground">—</span>
                          <span>{item.album_title}</span>
                          {item.release_date && (
                            <span className="ml-2 text-xs text-muted-foreground">
                              {item.release_date}
                            </span>
                          )}
                        </div>
                        <Button variant="outline" size="sm" onClick={() => handleRestore(item.id)}>
                          <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                          Restore
                        </Button>
                      </div>
                    ))
                  )}
                  {dismissedTotal > dismissed.length && (
                    <p className="text-xs text-muted-foreground">
                      Showing {dismissed.length} of {dismissedTotal}
                    </p>
                  )}
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {/* Restore All confirmation */}
          <Dialog open={confirmRestoreAllOpen} onOpenChange={setConfirmRestoreAllOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Restore All Dismissed</DialogTitle>
                <DialogDescription>
                  This will restore all {dismissedTotal} dismissed release
                  {dismissedTotal === 1 ? "" : "s"} so they reappear on the next New Releases scan.
                  Continue?
                </DialogDescription>
              </DialogHeader>
              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setConfirmRestoreAllOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleRestoreAll}
                  disabled={confirmActionLoading === "restore-all"}
                >
                  {confirmActionLoading === "restore-all" ? "Restoring…" : "Restore All"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>

          {/* Reset scan history confirmation */}
          <Dialog open={confirmResetOpen} onOpenChange={setConfirmResetOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-destructive">
                  <AlertTriangle className="h-5 w-5" />
                  Reset New Releases Discovery
                </DialogTitle>
                <DialogDescription>
                  This will wipe all artist scan history from the database. Every Lidarr artist will
                  be treated as "not yet scanned" and NRD will start fresh on the next run. This
                  cannot be undone. Continue?
                </DialogDescription>
              </DialogHeader>
              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setConfirmResetOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleReset}
                  disabled={confirmActionLoading === "reset"}
                >
                  {confirmActionLoading === "reset" ? "Resetting…" : "Reset"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </>
      ) : null}

      {showSection("artist-events") ? (
        <Dialog open={confirmInvalidateEventsOpen} onOpenChange={setConfirmInvalidateEventsOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="h-5 w-5" />
                Clear artist events cache?
              </DialogTitle>
              <DialogDescription>
                This deletes all stored upcoming events and clears per-artist event-scan timestamps.
                The Artist Events page will be empty until the next refresh. Every Lidarr artist
                will be due for scanning again. Artist-level hides are kept; hides on individual
                events are dropped with those rows.
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setConfirmInvalidateEventsOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleInvalidateArtistEvents}
                disabled={confirmActionLoading === "invalidate-events"}
              >
                {confirmActionLoading === "invalidate-events" ? "Clearing…" : "Clear cache"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      ) : null}

      {showSection("api-endpoints") ? (
        <StatusSectionPanel
          useArrPanel={useArrPanel}
          title="API Endpoints"
          description="Available API endpoints"
        >
          <div className={cn("space-y-2", useArrPanel && "arr-list-rows -mx-4")}>
            <div
              className={cn(
                "flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between",
                useArrPanel ? "px-4 py-3" : "rounded-lg border p-3"
              )}
            >
              <div className="min-w-0">
                <div className="font-medium">Health Check</div>
                <div className="truncate text-sm text-muted-foreground">/health</div>
              </div>
              <Badge variant="outline" className="shrink-0 self-start sm:self-auto">
                GET
              </Badge>
            </div>
            <div
              className={cn(
                "flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between",
                useArrPanel ? "px-4 py-3" : "rounded-lg border p-3"
              )}
            >
              <div className="min-w-0">
                <div className="font-medium">Commands API</div>
                <div className="truncate text-sm text-muted-foreground">/api/commands</div>
              </div>
              <Badge variant="outline" className="shrink-0 self-start sm:self-auto">
                REST
              </Badge>
            </div>
            <div
              className={cn(
                "flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between",
                useArrPanel ? "px-4 py-3" : "rounded-lg border p-3"
              )}
            >
              <div className="min-w-0">
                <div className="font-medium">Configuration API</div>
                <div className="truncate text-sm text-muted-foreground">/api/config</div>
              </div>
              <Badge variant="outline" className="shrink-0 self-start sm:self-auto">
                REST
              </Badge>
            </div>
          </div>
        </StatusSectionPanel>
      ) : null}
    </div>
  );
}
