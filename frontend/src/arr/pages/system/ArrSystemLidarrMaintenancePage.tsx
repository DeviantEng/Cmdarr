import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { RefreshCw, Loader2 } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { LidarrWantedIgnoreDialog } from "@/components/LidarrWantedIgnoreDialog";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

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
};

function StatBox({
  label,
  value,
  clickable,
  onClick,
}: {
  label: string;
  value: string | number;
  clickable?: boolean;
  onClick?: () => void;
}) {
  const body = (
    <>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </>
  );
  if (clickable && onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "rounded-md border border-border bg-background/50 px-3 py-2 text-left transition-colors",
          "hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        )}
      >
        {body}
      </button>
    );
  }
  return <div className="rounded-md border border-border bg-background/50 px-3 py-2">{body}</div>;
}

function CommandSummary({
  commands,
}: {
  commands: Array<{
    display_name: string;
    enabled: boolean;
    last_run: string | null;
    total_execution_count: number;
  }>;
}) {
  if (!commands.length) return null;
  return (
    <ul className="mt-3 space-y-1 text-sm">
      {commands.map((c) => (
        <li key={c.display_name} className="flex flex-wrap items-center gap-2">
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
  );
}

export function ArrSystemLidarrMaintenancePage() {
  const [stats, setStats] = useState<MaintenanceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [ignoreOpen, setIgnoreOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = await api.request<MaintenanceStats>("/api/lidarr-maintenance/stats");
      setStats(s);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load Lidarr maintenance stats");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const ignoreCount = stats?.ignore.active_count ?? 0;

  return (
    <div>
      <ArrPageHeader
        title="Lidarr Maintenance"
        description="Update All and Wanted Search status. Run history lives under Commands → History."
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
          <ArrSectionHeader
            title="Update All"
            description="Library metadata refresh (RefreshArtist)."
          />
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
            <CommandSummary commands={stats?.update_all.commands ?? []} />
            {!stats?.update_all.command_count ? (
              <p className="mt-2 text-sm text-muted-foreground">
                No Update All command yet — create one from{" "}
                <Link className="underline underline-offset-2" to="/commands/add">
                  Commands → Add New
                </Link>
                .
              </p>
            ) : null}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Wanted Search"
            description="Top-X Wanted album searches. Grabs and empty results share a cooldown."
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
                <StatBox
                  label="Ignored albums"
                  value={ignoreCount}
                  clickable={ignoreCount > 0}
                  onClick={() => setIgnoreOpen(true)}
                />
              </div>
            ) : null}
            <CommandSummary commands={stats?.wanted_search.commands ?? []} />
            {!stats?.wanted_search.command_count ? (
              <p className="mt-2 text-sm text-muted-foreground">
                No Wanted Search command yet — create one from{" "}
                <Link className="underline underline-offset-2" to="/commands/add">
                  Commands → Add New
                </Link>
                .
              </p>
            ) : ignoreCount === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                No albums currently ignored. Expired ignore rows are purged automatically on each
                Wanted Search run.
              </p>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                Click <span className="font-medium text-foreground">Ignored albums</span> to search,
                restore, or clear the cooldown list.
              </p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>
      </div>

      <LidarrWantedIgnoreDialog
        open={ignoreOpen}
        onOpenChange={setIgnoreOpen}
        onChanged={() => void load()}
      />
    </div>
  );
}
