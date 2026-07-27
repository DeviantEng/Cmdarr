import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Trash2, Loader2 } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

type MaintenanceStats = {
  update_all: {
    command_count: number;
    total_execution_count: number;
    total_success_count: number;
    total_failure_count: number;
    commands: Array<{
      command_name: string;
      display_name: string;
      enabled: boolean;
      last_run: string | null;
      total_execution_count: number;
    }>;
  };
  wanted_search: {
    command_count: number;
    total_execution_count: number;
    total_success_count: number;
    total_failure_count: number;
    lifetime_searched: number;
    lifetime_downloads_found: number;
    lifetime_ignored: number;
    commands: Array<{
      command_name: string;
      display_name: string;
      enabled: boolean;
      last_run: string | null;
      total_execution_count: number;
      config_json: Record<string, unknown>;
    }>;
  };
  ignore: { active_count: number; total_count: number };
  recent_runs: Array<{
    id: number;
    command_name: string;
    success: boolean | null;
    status: string;
    started_at: string | null;
    duration: number | null;
    output_summary: string | null;
    triggered_by: string | null;
  }>;
};

type IgnoreItem = {
  id: number;
  lidarr_album_id: number;
  artist_name: string | null;
  album_title: string;
  album_type: string | null;
  release_date: string | null;
  ignored_until: string | null;
  search_count: number;
  command_name: string | null;
};

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border bg-background/50 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export function ArrSystemLidarrMaintenancePage() {
  const [stats, setStats] = useState<MaintenanceStats | null>(null);
  const [ignores, setIgnores] = useState<IgnoreItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, ign] = await Promise.all([
        api.request<MaintenanceStats>("/api/lidarr-maintenance/stats"),
        api.request<{ total: number; items: IgnoreItem[] }>(
          "/api/lidarr-maintenance/ignore?active_only=true&limit=200"
        ),
      ]);
      setStats(s);
      setIgnores(ign.items || []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load Lidarr maintenance stats");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const restoreOne = async (id: number) => {
    setBusy(true);
    try {
      await api.request(`/api/lidarr-maintenance/ignore/${id}`, { method: "DELETE" });
      toast.success("Removed from ignore list");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to restore");
    } finally {
      setBusy(false);
    }
  };

  const restoreAll = async () => {
    if (!confirm("Clear the entire Wanted-search ignore list?")) return;
    setBusy(true);
    try {
      const r = await api.request<{ deleted: number }>(
        "/api/lidarr-maintenance/ignore/restore-all",
        {
          method: "POST",
        }
      );
      toast.success(`Cleared ${r.deleted} ignore(s)`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to clear ignore list");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <ArrPageHeader
        title="Lidarr Maintenance"
        description="Update All / Wanted Search run stats and temporary ignore list."
        actions={
          <Button variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
            {loading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Refresh
          </Button>
        }
      />

      <div className="space-y-4">
        <ArrContentPanel>
          <ArrSectionHeader title="Update All" description="Library metadata refresh commands." />
          <ArrPanelBody>
            {stats ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatBox label="Commands" value={stats.update_all.command_count} />
                <StatBox label="Total runs" value={stats.update_all.total_execution_count} />
                <StatBox label="Successes" value={stats.update_all.total_success_count} />
                <StatBox label="Failures" value={stats.update_all.total_failure_count} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Loading…</p>
            )}
            {stats?.update_all.commands.length ? (
              <ul className="mt-3 space-y-1 text-sm">
                {stats.update_all.commands.map((c) => (
                  <li key={c.command_name} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{c.display_name}</span>
                    <Badge variant={c.enabled ? "default" : "secondary"} className="text-xs">
                      {c.enabled ? "Enabled" : "Disabled"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {c.total_execution_count} runs
                      {c.last_run ? ` · last ${new Date(c.last_run).toLocaleString()}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Wanted Search"
            description="Top-X Wanted album searches and ignore cooldown."
          />
          <ArrPanelBody>
            {stats ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatBox label="Commands" value={stats.wanted_search.command_count} />
                <StatBox label="Albums searched" value={stats.wanted_search.lifetime_searched} />
                <StatBox
                  label="Downloads found"
                  value={stats.wanted_search.lifetime_downloads_found}
                />
                <StatBox label="Times ignored" value={stats.wanted_search.lifetime_ignored} />
              </div>
            ) : null}
            {stats?.wanted_search.commands.length ? (
              <ul className="mt-3 space-y-1 text-sm">
                {stats.wanted_search.commands.map((c) => (
                  <li key={c.command_name} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{c.display_name}</span>
                    <Badge variant={c.enabled ? "default" : "secondary"} className="text-xs">
                      {c.enabled ? "Enabled" : "Disabled"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      top {String(c.config_json?.top_x ?? "—")} ·{" "}
                      {String(c.config_json?.album_types ?? "album")} · {c.total_execution_count}{" "}
                      runs
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                No Wanted Search commands yet — create one from Commands → Add New.
              </p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Ignore list"
            description={`${stats?.ignore.active_count ?? 0} active · albums with no release found are skipped until cooldown ends.`}
            actions={
              ignores.length > 0 ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void restoreAll()}
                  disabled={busy}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Clear all
                </Button>
              ) : null
            }
          />
          <ArrPanelBody>
            {ignores.length === 0 ? (
              <p className="text-sm text-muted-foreground">No albums currently ignored.</p>
            ) : (
              <ul className="divide-y divide-border">
                {ignores.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                  >
                    <div className="min-w-0">
                      <div className="font-medium truncate">
                        {item.artist_name || "?"} – {item.album_title}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {item.album_type || "?"}
                        {item.release_date ? ` · ${item.release_date}` : ""}
                        {item.ignored_until
                          ? ` · until ${new Date(item.ignored_until).toLocaleDateString()}`
                          : ""}
                        {item.search_count > 1 ? ` · searched ${item.search_count}×` : ""}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => void restoreOne(item.id)}
                    >
                      Restore
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Recent runs"
            description="Latest Update All and Wanted Search executions."
          />
          <ArrPanelBody>
            {!stats?.recent_runs?.length ? (
              <p className="text-sm text-muted-foreground">No recent runs.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {stats.recent_runs.map((run) => (
                  <li key={run.id} className="rounded-md border border-border px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{run.command_name}</span>
                      <Badge variant={run.success ? "default" : "destructive"} className="text-xs">
                        {run.status}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {run.started_at ? new Date(run.started_at).toLocaleString() : ""}
                        {run.duration != null ? ` · ${run.duration.toFixed(1)}s` : ""}
                        {run.triggered_by ? ` · ${run.triggered_by}` : ""}
                      </span>
                    </div>
                    {run.output_summary ? (
                      <pre className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
                        {run.output_summary}
                      </pre>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </ArrPanelBody>
        </ArrContentPanel>
      </div>
    </div>
  );
}
