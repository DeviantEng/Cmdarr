import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPageToolbar, ArrPanelBody } from "@/arr/components/ArrPageToolbar";
import { CommandExecutionsPanel } from "@/components/CommandExecutionsPanel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import type { CommandConfig, ExecutionHistorySince, ExecutionHistorySummary } from "@/lib/types";

const TIME_RANGE_OPTIONS: { value: ExecutionHistorySince; label: string }[] = [
  { value: "1d", label: "Last 24 hours" },
  { value: "3d", label: "Last 3 days" },
  { value: "7d", label: "Last 7 days" },
  { value: "14d", label: "Last 14 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "1y", label: "Last year" },
  { value: "all", label: "All time" },
];

function formatAvgDuration(seconds: number | null | undefined) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function filterSubtitle(since: ExecutionHistorySince, commandLabel: string) {
  const timeLabel = TIME_RANGE_OPTIONS.find((o) => o.value === since)?.label ?? since;
  return `${timeLabel.toLowerCase()} · ${commandLabel}`;
}

export function ArrCommandHistoryPage() {
  const [since, setSince] = useState<ExecutionHistorySince>("30d");
  const [commandName, setCommandName] = useState<string>("all");
  const [commands, setCommands] = useState<CommandConfig[]>([]);
  const [summary, setSummary] = useState<ExecutionHistorySummary | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    void api
      .getCommands()
      .then(setCommands)
      .catch(() => setCommands([]));
  }, []);

  const commandLabel = useMemo(() => {
    if (commandName === "all") return "all commands";
    const cmd = commands.find((c) => c.command_name === commandName);
    return cmd?.display_name ?? commandName.replace(/_/g, " ");
  }, [commandName, commands]);

  const handleSummary = useCallback((next: ExecutionHistorySummary) => {
    setSummary(next);
  }, []);

  const handleReload = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const successRate =
    summary && summary.total_count > 0
      ? Math.round((summary.success_count / summary.total_count) * 100)
      : null;

  return (
    <div>
      <ArrPageHeader
        title="History"
        description="Command runs with status, timing, and details. Filters apply to the table and summary below."
      />
      <div className="arr-page-panels space-y-4">
        <ArrContentPanel>
          <ArrPageToolbar>
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
              <Select value={since} onValueChange={(v) => setSince(v as ExecutionHistorySince)}>
                <SelectTrigger className="w-full sm:w-[180px]">
                  <SelectValue placeholder="Time range" />
                </SelectTrigger>
                <SelectContent>
                  {TIME_RANGE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={commandName} onValueChange={setCommandName}>
                <SelectTrigger className="w-full sm:w-[220px]">
                  <SelectValue placeholder="Command" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All commands</SelectItem>
                  {commands.map((cmd) => (
                    <SelectItem key={cmd.command_name} value={cmd.command_name}>
                      {cmd.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </ArrPageToolbar>
          <ArrPanelBody>
            {summary ? (
              <div className="arr-stats-grid">
                <div>
                  <div className="text-lg font-semibold tabular-nums">
                    {summary.total_count.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Total runs</div>
                </div>
                <div>
                  <div className="text-lg font-semibold tabular-nums">
                    {summary.failure_count.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Failures</div>
                </div>
                <div>
                  <div className="text-lg font-semibold tabular-nums">
                    {formatAvgDuration(summary.avg_duration_seconds)}
                  </div>
                  <div className="text-xs text-muted-foreground">Avg duration</div>
                </div>
                <div>
                  <div className="text-lg font-semibold tabular-nums">
                    {successRate != null ? `${successRate}%` : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground">Success rate</div>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[72px] items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            )}
            <p className="mt-3 text-xs text-muted-foreground">
              Summary for {filterSubtitle(since, commandLabel)}. System status shows lifetime
              totals.
            </p>
          </ArrPanelBody>
        </ArrContentPanel>

        <CommandExecutionsPanel
          commands={commands}
          historySince={since}
          historyCommandName={commandName === "all" ? null : commandName}
          refreshKey={refreshKey}
          onSummaryChange={handleSummary}
          onExecutionsChange={handleReload}
        />
      </div>
    </div>
  );
}
