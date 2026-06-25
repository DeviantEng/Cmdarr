import { Fragment, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, ChevronUp, Loader2, Trash, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { CommandConfig, CommandExecution } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { isMobileViewport } from "@/lib/use-mobile";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";

function formatDuration(seconds?: number) {
  if (seconds == null) return "In progress";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatStartedAt(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function resolveDisplayName(execution: CommandExecution, commands?: CommandConfig[]) {
  if (execution.display_name) return execution.display_name;
  const cmd = commands?.find((c) => c.command_name === execution.command_name);
  return cmd?.display_name || execution.command_name.replace(/_/g, " ");
}

function statusBadgeVariant(status: CommandExecution["status"]) {
  if (status === "completed") return "default" as const;
  if (status === "failed") return "destructive" as const;
  if (status === "running") return "secondary" as const;
  return "outline" as const;
}

function statusLabel(status: CommandExecution["status"]) {
  if (status === "running") return "Running";
  if (status === "completed") return "Success";
  if (status === "cancelled") return "Cancelled";
  return "Failed";
}

type ExecutionDetailsProps = {
  execution: CommandExecution;
  displayName: string;
  duration?: number;
  onDelete: (id: number) => void;
};

function ExecutionDetails({ execution, displayName, duration, onDelete }: ExecutionDetailsProps) {
  return (
    <div className="arr-history-detail">
      <dl>
        <dt>Command</dt>
        <dd>{displayName}</dd>
        <dt>Execution ID</dt>
        <dd className="font-mono">{execution.id}</dd>
        <dt>Started</dt>
        <dd>{execution.started_at ? new Date(execution.started_at).toLocaleString() : "—"}</dd>
        {execution.completed_at ? (
          <>
            <dt>Completed</dt>
            <dd>{new Date(execution.completed_at).toLocaleString()}</dd>
          </>
        ) : null}
        <dt>Duration</dt>
        <dd>{formatDuration(duration)}</dd>
        <dt>Triggered by</dt>
        <dd className="capitalize">{execution.triggered_by}</dd>
        {execution.target && execution.target !== "unknown" ? (
          <>
            <dt>Target</dt>
            <dd className="uppercase">{String(execution.target)}</dd>
          </>
        ) : null}
        {execution.error_message ? (
          <>
            <dt>Error</dt>
            <dd className="text-destructive">{execution.error_message}</dd>
          </>
        ) : null}
      </dl>
      {execution.status === "completed" && execution.output_summary ? (
        <div className="mt-3 border-t border-border pt-3">
          <div className="mb-1 font-medium">Summary</div>
          <pre className="whitespace-pre-wrap font-sans text-xs text-muted-foreground">
            {execution.output_summary}
          </pre>
        </div>
      ) : null}
      {execution.status !== "running" ? (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3">
          <Button variant="destructive" size="sm" onClick={() => onDelete(execution.id)}>
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      ) : null}
    </div>
  );
}

type CommandExecutionsPanelProps = {
  useArrPanel?: boolean;
  /** When false, always show the execution list (history page). */
  collapsible?: boolean;
  commands?: CommandConfig[];
  pausePolling?: boolean;
};

export function CommandExecutionsPanel({
  useArrPanel = false,
  collapsible = false,
  commands,
  pausePolling = false,
}: CommandExecutionsPanelProps) {
  const [recentExecutions, setRecentExecutions] = useState<CommandExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [panelOpen, setPanelOpen] = useState(() => !collapsible || !isMobileViewport());
  const [expandedExecutionId, setExpandedExecutionId] = useState<number | null>(null);
  const [killingExecutionId, setKillingExecutionId] = useState<number | null>(null);
  const compactArr = useArrPanel && !collapsible;

  const loadExecutions = async () => {
    try {
      const data = await api.getAllExecutions(50);
      setRecentExecutions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Error loading executions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadExecutions();
  }, []);

  useEffect(() => {
    const hasRunning = recentExecutions.some((e) => e.status === "running");
    if (!hasRunning || pausePolling) return;
    const id = setInterval(loadExecutions, 10000);
    return () => clearInterval(id);
  }, [recentExecutions, pausePolling]);

  const handleKillExecution = async (executionId: number) => {
    try {
      setKillingExecutionId(executionId);
      await api.killExecution(executionId);
      toast.success("Execution cancelled");
      void loadExecutions();
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
      if (expandedExecutionId === executionId) setExpandedExecutionId(null);
      void loadExecutions();
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
      void loadExecutions();
    } catch {
      toast.error("Failed to cleanup executions");
    }
  };

  const cleanupButton = (
    <Button variant="secondary" size="sm" onClick={handleCleanupExecutions}>
      <Trash className="mr-2 h-4 w-4" />
      Cleanup old
    </Button>
  );

  if (compactArr) {
    return (
      <ArrContentPanel>
        <ArrSectionHeader
          title="Execution log"
          description={
            recentExecutions.length > 0
              ? `${recentExecutions.length} recent run${recentExecutions.length === 1 ? "" : "s"}`
              : "Runs appear here after commands execute"
          }
          actions={cleanupButton}
        />
        {loading ? (
          <ArrPanelBody className="flex min-h-[240px] items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </ArrPanelBody>
        ) : recentExecutions.length === 0 ? (
          <ArrPanelBody className="py-12 text-center text-sm text-muted-foreground">
            No executions yet.
          </ArrPanelBody>
        ) : (
          <>
            <div className="divide-y md:hidden">
              {recentExecutions.map((execution) => {
                const isExpanded = expandedExecutionId === execution.id;
                const duration = execution.duration ?? execution.duration_seconds;
                const displayName = resolveDisplayName(execution, commands);

                return (
                  <div key={execution.id}>
                    <button
                      type="button"
                      className="flex w-full items-start gap-2 px-3 py-2.5 text-left hover:bg-muted/40"
                      onClick={() => setExpandedExecutionId(isExpanded ? null : execution.id)}
                    >
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium">{displayName}</span>
                          <Badge
                            variant={statusBadgeVariant(execution.status)}
                            className="shrink-0 text-[10px]"
                          >
                            {statusLabel(execution.status)}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-x-2 text-[11px] text-muted-foreground">
                          <span>{formatStartedAt(execution.started_at)}</span>
                          <span>{formatDuration(duration)}</span>
                          <span className="capitalize">{execution.triggered_by}</span>
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                    </button>
                    {isExpanded ? (
                      <ExecutionDetails
                        execution={execution}
                        displayName={displayName}
                        duration={duration}
                        onDelete={handleDeleteExecution}
                      />
                    ) : null}
                  </div>
                );
              })}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="arr-table w-full">
                <thead className="border-b">
                  <tr>
                    <th className="w-8 px-2" />
                    <th>Command</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Duration</th>
                    <th>Trigger</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recentExecutions.map((execution) => {
                    const isExpanded = expandedExecutionId === execution.id;
                    const duration = execution.duration ?? execution.duration_seconds;
                    const displayName = resolveDisplayName(execution, commands);

                    return (
                      <Fragment key={execution.id}>
                        <tr className="border-b last:border-b-0 hover:bg-muted/30">
                          <td className="px-2">
                            <button
                              type="button"
                              className="rounded p-1 text-muted-foreground hover:text-foreground"
                              onClick={() =>
                                setExpandedExecutionId(isExpanded ? null : execution.id)
                              }
                              aria-label={isExpanded ? "Hide details" : "Show details"}
                            >
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </button>
                          </td>
                          <td className="max-w-[16rem] truncate font-medium">{displayName}</td>
                          <td>
                            <Badge
                              variant={statusBadgeVariant(execution.status)}
                              className="text-[10px]"
                            >
                              {statusLabel(execution.status)}
                            </Badge>
                          </td>
                          <td className="whitespace-nowrap text-muted-foreground">
                            {formatStartedAt(execution.started_at)}
                          </td>
                          <td className="whitespace-nowrap text-muted-foreground">
                            {formatDuration(duration)}
                          </td>
                          <td className="capitalize text-muted-foreground">
                            {execution.triggered_by}
                          </td>
                          <td className="text-right">
                            {execution.status === "running" ? (
                              <Button
                                variant="destructive"
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => handleKillExecution(execution.id)}
                                disabled={killingExecutionId === execution.id}
                              >
                                {killingExecutionId === execution.id ? "Killing…" : "Kill"}
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </td>
                        </tr>
                        {isExpanded ? (
                          <tr>
                            <td colSpan={7} className="p-0">
                              <ExecutionDetails
                                execution={execution}
                                displayName={displayName}
                                duration={duration}
                                onDelete={handleDeleteExecution}
                              />
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </ArrContentPanel>
    );
  }

  const isOpen = collapsible ? panelOpen : true;
  const Shell = useArrPanel ? ArrContentPanel : Card;

  return (
    <Shell>
      <div
        className={cn(
          "flex flex-col gap-2 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
          useArrPanel ? "arr-section-header" : "sm:px-6 sm:py-4"
        )}
      >
        {collapsible ? (
          <button
            type="button"
            onClick={() => setPanelOpen((open) => !open)}
            className="flex min-w-0 flex-1 items-center gap-2 text-left"
            aria-expanded={isOpen}
          >
            {isOpen ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <h3
              className={cn(
                "font-medium",
                useArrPanel ? "text-sm font-semibold" : "text-lg font-medium"
              )}
            >
              Recent Executions
            </h3>
            {recentExecutions.length > 0 ? (
              <Badge variant="secondary" className="shrink-0 tabular-nums">
                {recentExecutions.length}
              </Badge>
            ) : null}
          </button>
        ) : (
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <h3
              className={cn(
                "font-medium",
                useArrPanel ? "text-sm font-semibold" : "text-lg font-medium"
              )}
            >
              Recent Executions
            </h3>
            {recentExecutions.length > 0 ? (
              <Badge variant="secondary" className="shrink-0 tabular-nums">
                {recentExecutions.length}
              </Badge>
            ) : null}
          </div>
        )}
        <Button
          variant={useArrPanel ? "secondary" : "outline"}
          size="sm"
          className="shrink-0 self-start sm:self-auto"
          onClick={handleCleanupExecutions}
        >
          <Trash className="mr-2 h-4 w-4" />
          Cleanup Old
        </Button>
      </div>
      {isOpen ? (
        <div className={cn("p-4 md:p-6", useArrPanel && "arr-panel-body")}>
          {recentExecutions.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <p className="font-medium">No executions yet</p>
              <p className="mt-1 text-sm">Command executions will appear here once they run.</p>
            </div>
          ) : (
            <div className="space-y-3 md:space-y-4">
              {recentExecutions.map((execution) => {
                const isExpanded = expandedExecutionId === execution.id;
                const duration = execution.duration ?? execution.duration_seconds;
                const displayName = resolveDisplayName(execution, commands);
                const statusColor =
                  execution.status === "completed"
                    ? "text-green-600 dark:text-green-400"
                    : execution.status === "failed"
                      ? "text-red-600 dark:text-red-400"
                      : execution.status === "running"
                        ? "text-yellow-600 dark:text-yellow-400"
                        : "text-muted-foreground";

                return (
                  <div key={execution.id} className="rounded-lg border bg-muted/50 p-3 md:p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 items-start gap-2 sm:items-center sm:gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-medium">{displayName}</p>
                          <p className="text-xs text-muted-foreground sm:text-sm">
                            {formatStartedAt(execution.started_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 sm:justify-end">
                        <span className={`text-sm font-medium ${statusColor}`}>
                          {statusLabel(execution.status)}
                          {execution.status === "running" ? "…" : ""}
                        </span>
                        {execution.status === "running" && (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleKillExecution(execution.id)}
                            disabled={killingExecutionId === execution.id}
                          >
                            <X className="mr-1 h-3 w-3" />
                            {killingExecutionId === execution.id ? "Killing..." : "Kill"}
                          </Button>
                        )}
                        <p className="text-xs text-muted-foreground">{formatDuration(duration)}</p>
                        <p className="text-xs capitalize text-muted-foreground">
                          {execution.triggered_by}
                        </p>
                      </div>
                    </div>
                    {execution.status === "failed" && execution.error_message && (
                      <div className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                        {execution.error_message}
                      </div>
                    )}
                    <div className="mt-3">
                      <button
                        type="button"
                        onClick={() => setExpandedExecutionId(isExpanded ? null : execution.id)}
                        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
                      >
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                        {isExpanded ? "Hide details" : "Show details"}
                      </button>
                      {isExpanded ? (
                        <ExecutionDetails
                          execution={execution}
                          displayName={displayName}
                          duration={duration}
                          onDelete={handleDeleteExecution}
                        />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : null}
    </Shell>
  );
}
