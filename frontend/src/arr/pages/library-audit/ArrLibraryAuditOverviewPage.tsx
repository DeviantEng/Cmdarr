import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { Loader2, RefreshCw, FlaskConical } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  libraryAuditApi,
  type LibraryAuditStats,
  type LibraryAuditStatus,
} from "@/lib/library-audit-api";
import { StatBox } from "@/arr/pages/library-audit/library-audit-shared";

export function ArrLibraryAuditOverviewPage() {
  const [status, setStatus] = useState<LibraryAuditStatus | null>(null);
  const [stats, setStats] = useState<LibraryAuditStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = await libraryAuditApi.getStatus();
      setStatus(s);
      if (s.enabled) {
        try {
          const st = await libraryAuditApi.getStats();
          setStats(st);
        } catch (e) {
          setStats(null);
          toast.error(e instanceof Error ? e.message : "Failed to load library audit stats");
        }
      } else {
        setStats(null);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load library audit status");
      setStatus(null);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runTest = async () => {
    setTesting(true);
    try {
      const result = await libraryAuditApi.test();
      if (result.success) {
        toast.success("Library Audit checks passed");
      } else {
        const failed = result.checks.filter((c) => !c.success).map((c) => c.message);
        toast.error(failed.join("; ") || "Library Audit checks failed");
      }
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const misconfigured = status && (!status.enabled || !status.root_ok || !status.provider.healthy);
  const needsReview = stats?.review.needs_review ?? 0;

  return (
    <div>
      <ArrPageHeader
        title="Library Audit"
        description="FLAC authenticity inventory, analysis queue, and review status."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => void runTest()} disabled={testing}>
              {testing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FlaskConical className="mr-2 h-4 w-4" />
              )}
              Test
            </Button>
            <Button variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Refresh
            </Button>
          </div>
        }
      />

      <div className="space-y-4">
        {misconfigured ? (
          <ArrContentPanel>
            <ArrSectionHeader
              title="Setup required"
              description="Enable Library Audit and confirm the music root and analyzer before reviewing files."
            />
            <ArrPanelBody className="space-y-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Feature</span>
                <Badge variant={status.enabled ? "default" : "secondary"}>
                  {status.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Root</span>
                <Badge variant={status.root_ok ? "default" : "destructive"}>
                  {status.root_ok ? "OK" : "Issue"}
                </Badge>
                <span className="break-all font-mono text-xs text-muted-foreground">
                  {status.root}
                </span>
              </div>
              {status.root_message ? (
                <p className="text-muted-foreground">{status.root_message}</p>
              ) : null}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Provider</span>
                <Badge variant={status.provider.healthy ? "default" : "destructive"}>
                  {status.provider.healthy ? "Healthy" : "Unhealthy"}
                </Badge>
                <span>
                  {status.provider.name || "unknown"}
                  {status.provider.version ? ` ${status.provider.version}` : ""}
                </span>
              </div>
              {status.provider.message ? (
                <p className="text-muted-foreground">{status.provider.message}</p>
              ) : null}
              <p className="pt-1 text-muted-foreground">
                Configure under{" "}
                <Link className="underline underline-offset-2" to="/settings/music-management">
                  Settings → Music Management
                </Link>
                .
              </p>
            </ArrPanelBody>
          </ArrContentPanel>
        ) : null}

        <ArrContentPanel>
          <ArrSectionHeader
            title="Library"
            description="Present files and analysis progress."
            actions={
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="secondary" size="sm">
                  <Link to="/library-audit/review">
                    Review{needsReview > 0 ? ` (${needsReview})` : ""}
                  </Link>
                </Button>
                <Button asChild variant="secondary" size="sm">
                  <Link to="/library-audit/library">Library</Link>
                </Button>
              </div>
            }
          />
          <ArrPanelBody>
            {stats ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <StatBox label="Present" value={stats.library.present} />
                <StatBox label="Analyzed" value={stats.library.analyzed} />
                <StatBox label="Pending" value={stats.library.pending} />
                <StatBox label="Errors" value={stats.library.errors} />
                <StatBox label="Missing" value={stats.library.missing} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {loading ? "Loading…" : "Stats unavailable until Library Audit is enabled."}
              </p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Verdicts"
            description="Latest analysis results for present files."
          />
          <ArrPanelBody>
            {stats ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <StatBox label="Authentic" value={stats.verdicts.authentic} />
                <StatBox label="Warning" value={stats.verdicts.warning} />
                <StatBox label="Suspicious" value={stats.verdicts.suspicious} />
                <StatBox label="Fake certain" value={stats.verdicts.fake_certain} />
                <StatBox label="Inconclusive" value={stats.verdicts.inconclusive} />
                <StatBox label="Error" value={stats.verdicts.error} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{loading ? "Loading…" : "—"}</p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Reviews"
            description="Human dispositions applied to analyzed files."
          />
          <ArrPanelBody>
            {stats ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatBox label="Needs review" value={stats.review.needs_review} />
                <StatBox label="Accepted" value={stats.review.accepted} />
                <StatBox label="Best available" value={stats.review.best_available} />
                <StatBox label="Confirmed transcode" value={stats.review.confirmed_transcode} />
                <StatBox label="Replace" value={stats.review.replace} />
                <StatBox label="Unsure" value={stats.review.unsure} />
                <StatBox label="Ignored" value={stats.review.ignored} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{loading ? "Loading…" : "—"}</p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Provider health"
            description="Analyzer used for FLAC authenticity checks."
          />
          <ArrPanelBody>
            {status ? (
              <div className="space-y-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{status.provider.name || "unknown"}</span>
                  {status.provider.version ? (
                    <span className="text-muted-foreground">v{status.provider.version}</span>
                  ) : null}
                  <Badge variant={status.provider.healthy ? "default" : "destructive"}>
                    {status.provider.healthy ? "Healthy" : "Unhealthy"}
                  </Badge>
                </div>
                {status.provider.message ? (
                  <p className="text-muted-foreground">{status.provider.message}</p>
                ) : null}
                {status.provider.modes?.length ? (
                  <p className="text-xs text-muted-foreground">
                    Modes: {status.provider.modes.join(", ")}
                  </p>
                ) : null}
                {stats?.last_inventory_run ? (
                  <p className="text-xs text-muted-foreground">
                    Last inventory: {stats.last_inventory_run.status}
                    {stats.last_inventory_run.completed_at
                      ? ` · ${new Date(stats.last_inventory_run.completed_at).toLocaleString()}`
                      : ""}
                  </p>
                ) : null}
                {stats?.last_analysis_run ? (
                  <p className="text-xs text-muted-foreground">
                    Last analysis: {stats.last_analysis_run.status}
                    {stats.last_analysis_run.completed_at
                      ? ` · ${new Date(stats.last_analysis_run.completed_at).toLocaleString()}`
                      : ""}
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{loading ? "Loading…" : "—"}</p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>
      </div>
    </div>
  );
}
