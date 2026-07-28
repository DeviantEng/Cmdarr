import { useCallback, useEffect, useState } from "react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { CommandConfig } from "@/lib/types";
import { toast } from "sonner";

type RecentAdd = {
  mbid?: string;
  name?: string;
  added_at?: string;
  similar_to?: string;
};

type DiscoveryStats = {
  success: boolean;
  command?: {
    enabled: boolean;
    last_run?: string | null;
    last_success?: boolean | null;
    last_duration?: number | null;
    last_error?: string | null;
    config?: Record<string, unknown>;
  };
  last_run_stats?: Record<string, unknown> | null;
  cooldown_count?: number;
  recent_adds?: RecentAdd[];
};

export function ArrSystemDiscoveryPage() {
  const [stats, setStats] = useState<DiscoveryStats | null>(null);
  const [command, setCommand] = useState<CommandConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, cmd] = await Promise.all([
        api.getLastfmDiscoverySystemStats(),
        api.getCommand("discovery_lastfm").catch(() => null),
      ]);
      setStats(s);
      setCommand(cmd);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load discovery stats");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const cfg = stats?.command?.config || command?.config_json || {};
  const runStats = stats?.last_run_stats || {};

  return (
    <div className="arr-page-panels space-y-6">
      <ArrPageHeader
        title="Discovery"
        description="KPIs and recent activity for Last.fm Discovery (scheduled + interactive)."
      />
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Scheduled command"
          value={stats?.command?.enabled || command?.enabled ? "Enabled" : "Disabled"}
        />
        <Kpi label="Artists in cooldown" value={String(stats?.cooldown_count ?? "—")} />
        <Kpi label="Last run added" value={String(runStats.added_count ?? "—")} />
        <Kpi label="Last run failed" value={String(runStats.failed_count ?? "—")} />
      </div>

      <ArrContentPanel>
        <ArrSectionHeader title="Scheduled command" />
        <ArrPanelBody className="space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={command?.enabled || stats?.command?.enabled ? "default" : "secondary"}>
              {command?.enabled || stats?.command?.enabled ? "Enabled" : "Disabled"}
            </Badge>
            <span className="text-muted-foreground">
              Quality profile #{String(cfg.quality_profile_id ?? "—")} · Metadata profile #
              {String(cfg.metadata_profile_id ?? "—")}
            </span>
          </div>
          <p className="text-muted-foreground">
            Last run: {command?.last_run || stats?.command?.last_run || "never"}
            {command?.last_success === false || stats?.command?.last_success === false
              ? " · failed"
              : ""}
          </p>
          {(command?.last_error || stats?.command?.last_error) && (
            <p className="text-destructive text-xs">
              {command?.last_error || stats?.command?.last_error}
            </p>
          )}
        </ArrPanelBody>
      </ArrContentPanel>

      <ArrContentPanel>
        <ArrSectionHeader title="Recent auto-adds" />
        <ArrPanelBody>
          {(stats?.recent_adds || []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent auto-adds recorded yet.</p>
          ) : (
            <ul className="divide-y text-sm">
              {(stats?.recent_adds || [])
                .slice()
                .reverse()
                .map((row, i) => (
                  <li
                    key={`${row.mbid}-${row.added_at}-${i}`}
                    className="flex flex-wrap gap-2 py-2"
                  >
                    <span className="font-medium">{row.name || row.mbid}</span>
                    {row.similar_to ? (
                      <span className="text-muted-foreground">similar to {row.similar_to}</span>
                    ) : null}
                    <span className="ml-auto text-xs text-muted-foreground">{row.added_at}</span>
                  </li>
                ))}
            </ul>
          )}
        </ArrPanelBody>
      </ArrContentPanel>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}
