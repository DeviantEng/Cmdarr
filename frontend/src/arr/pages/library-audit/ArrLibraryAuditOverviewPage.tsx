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
import { StatPieChart } from "@/arr/pages/library-audit/library-audit-charts";

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

  const misconfigured = status && (!status.enabled || !status.root_ok);
  const needsReview = stats?.review.needs_review ?? 0;

  return (
    <div>
      <ArrPageHeader
        title="Library Audit"
        description="Inventory audio files; analyze FLAC authenticity and MP3 bitrate quality."
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
              description="Enable the Library Audit command and confirm the music library path."
            />
            <ArrPanelBody className="space-y-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Command</span>
                <Badge variant={status.enabled ? "default" : "secondary"}>
                  {status.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Music path</span>
                <Badge variant={status.root_ok ? "default" : "destructive"}>
                  {status.root_ok ? "OK" : "Issue"}
                </Badge>
                <span className="break-all font-mono text-xs text-muted-foreground">
                  {status.root}
                </span>
              </div>
              {status.root_message && !status.root_ok ? (
                <p className="text-muted-foreground">{status.root_message}</p>
              ) : null}
              <p className="pt-1 text-muted-foreground">
                Enable under{" "}
                <Link className="underline underline-offset-2" to="/commands">
                  Commands → Library Audit
                </Link>
                . Set the library path under{" "}
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
            description="Presence and analysis progress for inventoried files."
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
              <div className="space-y-6">
                <div className="grid gap-6 lg:grid-cols-2">
                  <div>
                    <div className="mb-2 text-xs font-medium text-muted-foreground">Presence</div>
                    <StatPieChart
                      slices={[
                        {
                          label: "Present",
                          value: stats.library.present,
                          color: "oklch(58% 0.14 195)",
                        },
                        {
                          label: "Missing",
                          value: stats.library.missing,
                          color: "oklch(55% 0.04 260)",
                        },
                      ]}
                    />
                  </div>
                  <div>
                    <div className="mb-2 text-xs font-medium text-muted-foreground">
                      Analysis state (present)
                    </div>
                    <StatPieChart
                      slices={[
                        {
                          label: "Analyzed",
                          value: stats.library.analyzed,
                          color: "oklch(62% 0.12 145)",
                        },
                        {
                          label: "Pending",
                          value: stats.library.pending,
                          color: "oklch(72% 0.13 85)",
                        },
                        {
                          label: "Unsupported",
                          value: stats.library.unsupported ?? 0,
                          color: "oklch(52% 0.08 280)",
                        },
                        {
                          label: "Errors",
                          value: stats.library.errors,
                          color: "oklch(58% 0.17 25)",
                        },
                      ]}
                    />
                  </div>
                </div>
                {(stats.last_inventory_run || stats.last_analysis_run) && (
                  <div className="space-y-1 text-xs text-muted-foreground">
                    {stats.last_inventory_run ? (
                      <p>
                        Last inventory: {stats.last_inventory_run.status}
                        {stats.last_inventory_run.completed_at
                          ? ` · ${new Date(stats.last_inventory_run.completed_at).toLocaleString()}`
                          : ""}
                      </p>
                    ) : null}
                    {stats.last_analysis_run ? (
                      <p>
                        Last analysis batch: {stats.last_analysis_run.status}
                        {stats.last_analysis_run.completed_at
                          ? ` · ${new Date(stats.last_analysis_run.completed_at).toLocaleString()}`
                          : ""}
                      </p>
                    ) : null}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {loading
                  ? "Loading…"
                  : "Stats unavailable until the Library Audit command is enabled."}
              </p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Formats"
            description="Inventoried files by lossless/lossy kind and by extension. Analysis currently runs on FLAC and MP3."
          />
          <ArrPanelBody>
            {stats?.formats ? (
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <div className="mb-2 text-xs font-medium text-muted-foreground">By kind</div>
                  <StatPieChart
                    slices={[
                      {
                        label: "Lossless",
                        value: stats.formats.by_kind.lossless,
                        color: "oklch(58% 0.14 195)",
                      },
                      {
                        label: "Lossy",
                        value: stats.formats.by_kind.lossy,
                        color: "oklch(72% 0.13 85)",
                      },
                      {
                        label: "Unknown",
                        value: stats.formats.by_kind.unknown,
                        color: "oklch(48% 0.03 260)",
                      },
                    ]}
                  />
                </div>
                <div>
                  <div className="mb-2 text-xs font-medium text-muted-foreground">By extension</div>
                  <StatPieChart
                    maxSlices={8}
                    slices={Object.entries(stats.formats.by_extension).map(([ext, count]) => ({
                      label: ext || "unknown",
                      value: count,
                    }))}
                  />
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{loading ? "Loading…" : "—"}</p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Scan Verdicts"
            description="Latest analyzer outcomes for present files that have been scanned (FLAC authenticity / MP3 quality)."
          />
          <ArrPanelBody>
            {stats ? (
              <StatPieChart
                slices={[
                  {
                    label: "Authentic",
                    value: stats.verdicts.authentic,
                    color: "oklch(62% 0.12 145)",
                  },
                  {
                    label: "Warning",
                    value: stats.verdicts.warning,
                    color: "oklch(72% 0.13 85)",
                  },
                  {
                    label: "Suspicious",
                    value: stats.verdicts.suspicious,
                    color: "oklch(64% 0.15 45)",
                  },
                  {
                    label: "Fake certain",
                    value: stats.verdicts.fake_certain,
                    color: "oklch(58% 0.17 25)",
                  },
                  {
                    label: "Inconclusive",
                    value: stats.verdicts.inconclusive,
                    color: "oklch(52% 0.08 280)",
                  },
                  {
                    label: "Error",
                    value: stats.verdicts.error,
                    color: "oklch(48% 0.03 260)",
                  },
                ]}
              />
            ) : (
              <p className="text-sm text-muted-foreground">{loading ? "Loading…" : "—"}</p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>

        <ArrContentPanel>
          <ArrSectionHeader
            title="Review Status"
            description="Your dispositions on scanned files (needs review vs decisions already made)."
          />
          <ArrPanelBody>
            {stats ? (
              <StatPieChart
                slices={[
                  {
                    label: "Needs review",
                    value: stats.review.needs_review,
                    color: "oklch(72% 0.13 85)",
                  },
                  {
                    label: "Accepted",
                    value: stats.review.accepted,
                    color: "oklch(62% 0.12 145)",
                  },
                  {
                    label: "Best available",
                    value: stats.review.best_available,
                    color: "oklch(58% 0.14 195)",
                  },
                  {
                    label: "Confirmed transcode",
                    value: stats.review.confirmed_transcode,
                    color: "oklch(64% 0.15 45)",
                  },
                  {
                    label: "Replace",
                    value: stats.review.replace,
                    color: "oklch(58% 0.17 25)",
                  },
                  {
                    label: "Unsure",
                    value: stats.review.unsure,
                    color: "oklch(52% 0.08 280)",
                  },
                  {
                    label: "Ignored",
                    value: stats.review.ignored,
                    color: "oklch(48% 0.03 260)",
                  },
                ]}
              />
            ) : (
              <p className="text-sm text-muted-foreground">{loading ? "Loading…" : "—"}</p>
            )}
          </ArrPanelBody>
        </ArrContentPanel>
      </div>
    </div>
  );
}
