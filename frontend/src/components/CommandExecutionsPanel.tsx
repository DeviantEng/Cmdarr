import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, ChevronUp, Trash, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { CommandConfig, CommandExecution } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { isMobileViewport } from "@/lib/use-mobile";
import { ArrContentPanel } from "@/arr/components/ArrPageToolbar";

function formatDuration(seconds?: number) {
  if (seconds == null) return "In progress";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function resolveDisplayName(execution: CommandExecution, commands?: CommandConfig[]) {
  if (execution.display_name) return execution.display_name;
  const cmd = commands?.find((c) => c.command_name === execution.command_name);
  return cmd?.display_name || execution.command_name.replace(/_/g, " ");
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
  const [panelOpen, setPanelOpen] = useState(() => !collapsible || !isMobileViewport());
  const [expandedExecutionId, setExpandedExecutionId] = useState<number | null>(null);
  const [killingExecutionId, setKillingExecutionId] = useState<number | null>(null);

  const loadExecutions = async () => {
    try {
      const data = await api.getAllExecutions(50);
      setRecentExecutions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Error loading executions:", err);
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
                  <div key={execution.id} className="rounded-lg border bg-muted/50 p-3 md:p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 items-start gap-2 sm:items-center sm:gap-3">
                        <div
                          className={cn(
                            "flex h-8 w-8 items-center justify-center rounded-full",
                            execution.status === "completed"
                              ? "bg-green-100 dark:bg-green-900"
                              : execution.status === "failed"
                                ? "bg-red-100 dark:bg-red-900"
                                : execution.status === "running"
                                  ? "bg-yellow-100 dark:bg-yellow-900"
                                  : "bg-muted"
                          )}
                        >
                          {execution.status === "running" ? (
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-yellow-600 border-t-transparent" />
                          ) : execution.status === "completed" ? (
                            <span className="text-green-600 dark:text-green-400">✓</span>
                          ) : execution.status === "failed" ? (
                            <span className="text-red-600 dark:text-red-400">✕</span>
                          ) : (
                            <span className="text-muted-foreground">○</span>
                          )}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-medium">{displayName}</p>
                          <p className="text-xs text-muted-foreground sm:text-sm">
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
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 sm:justify-end">
                        <span className={`text-sm font-medium ${statusColor}`}>{statusLabel}</span>
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
                        <p className="text-xs text-muted-foreground">
                          {duration != null ? formatDuration(duration) : "In progress"}
                        </p>
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
                    {execution.status === "completed" && (
                      <div className="mt-3 rounded-md bg-green-500/10 p-3 text-sm text-green-700 dark:text-green-400">
                        {displayName} completed successfully in {formatDuration(duration)}
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
                        {isExpanded ? "Hide Details" : "Show Details"}
                      </button>
                      {isExpanded && (
                        <div className="mt-2 space-y-2 rounded-md bg-muted p-3 text-sm">
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
                              <span className="text-right text-destructive">
                                {execution.error_message}
                              </span>
                            </div>
                          )}
                          {execution.status !== "running" && (
                            <div className="border-t pt-3">
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
                            <div className="border-t pt-3">
                              <h5 className="mb-2 font-medium">Execution Summary</h5>
                              <pre className="whitespace-pre-wrap font-sans text-xs">
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
      ) : null}
    </Shell>
  );
}
