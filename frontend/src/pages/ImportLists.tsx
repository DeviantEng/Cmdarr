import { useState, useEffect, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrContentPanel,
  ArrPageToolbar,
  ArrPanelBody,
  ArrSectionHeader,
} from "@/arr/components/ArrPageToolbar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import type { ImportListMetrics } from "@/lib/types";
import { toast } from "sonner";
import { Copy, RefreshCw, RotateCcw } from "lucide-react";

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatStatus(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

function getStatusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "fresh") return "default";
  if (status === "stale") return "secondary";
  if (status === "very_stale" || status === "empty") return "destructive";
  return "outline";
}

type ResetListId = "playlistsync";

type ListMetricsEntry = {
  exists: boolean;
  entry_count: number;
  file_size: number;
  age_human: string;
  status: string;
};

type ImportListEndpointSectionProps = {
  title: string;
  description: string;
  url: string;
  badge: ReactNode;
  onCopy: () => void;
  onReset: () => void;
  resetDisabled: boolean;
  metrics?: ListMetricsEntry | null;
  emptyHint?: ReactNode;
};

function ImportListEndpointSection({
  title,
  description,
  url,
  badge,
  onCopy,
  onReset,
  resetDisabled,
  metrics,
  emptyHint,
}: ImportListEndpointSectionProps) {
  const endpointBlock = (
    <div className="space-y-2">
      <label className="arr-field-label">Endpoint URL</label>
      <input type="text" readOnly value={url} title={url} className="arr-field-input" />
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={onCopy}>
          <Copy className="mr-1 h-4 w-4" />
          Copy
        </Button>
        <Button variant="outline" size="sm" onClick={onReset} disabled={resetDisabled}>
          <RotateCcw className="mr-1 h-4 w-4" />
          Reset
        </Button>
      </div>
    </div>
  );

  const statsBlock = metrics?.exists && (
    <div className="arr-stats-grid">
      <div>
        <div className="text-lg font-semibold">{metrics.entry_count.toLocaleString()}</div>
        <div className="text-xs text-muted-foreground">Artists</div>
      </div>
      <div>
        <div className="text-lg font-semibold">{formatFileSize(metrics.file_size)}</div>
        <div className="text-xs text-muted-foreground">File Size</div>
      </div>
      <div>
        <div className="text-lg font-semibold">{metrics.age_human}</div>
        <div className="text-xs text-muted-foreground">Last Updated</div>
      </div>
      <div>
        <div className="text-lg font-semibold">{formatStatus(metrics.status)}</div>
        <div className="text-xs text-muted-foreground">Status</div>
      </div>
    </div>
  );

  return (
    <ArrContentPanel>
      <ArrSectionHeader title={title} description={description} actions={badge} />
      <ArrPanelBody className="space-y-4">
        {endpointBlock}
        {emptyHint}
        {statsBlock}
      </ArrPanelBody>
    </ArrContentPanel>
  );
}

function LidarrIntegrationGuide() {
  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
  const playlistsyncUrl = `${baseUrl}/import_lists/discovery_playlistsync`;

  const body = (
    <>
      <p className="mb-4 text-muted-foreground">
        To add the Cmdarr playlist sync import list in Lidarr:
      </p>
      <div className="space-y-3">
        <div className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
            1
          </span>
          <span className="min-w-0 pt-0.5">
            Go to <strong>Settings → Import Lists</strong>
          </span>
        </div>
        <div className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
            2
          </span>
          <span className="min-w-0 pt-0.5">
            Click <strong>Add → Custom List</strong>
          </span>
        </div>
        <div className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
            3
          </span>
          <span className="min-w-0 pt-0.5">
            Set <strong>URL</strong> to:
          </span>
        </div>
        <div className="space-y-3 sm:ml-9">
          <div className="min-w-0 space-y-1">
            <code className="block break-all rounded bg-muted px-2 py-1.5 text-xs font-mono sm:text-sm">
              {playlistsyncUrl}
            </code>
            <span className="text-sm text-muted-foreground">
              (Playlist sync discovered artists)
            </span>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
            4
          </span>
          <span className="min-w-0 pt-0.5">
            Configure sync interval as desired (recommend 24-48 hours)
          </span>
        </div>
        <div className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
            5
          </span>
          <span className="min-w-0 pt-0.5">Save and test the configuration</span>
        </div>
      </div>
      <div className="mt-4 rounded-md bg-muted p-3">
        <p className="text-sm">
          <strong>Note:</strong> Last.fm Discovery now adds artists directly to Lidarr via API (see
          Discovery → Last.fm). Remove any old Lidarr custom list pointing at{" "}
          <code className="text-xs">/import_lists/discovery_lastfm</code>.
        </p>
      </div>
    </>
  );

  return (
    <ArrContentPanel className="border-blue-500/50 bg-blue-500/5">
      <ArrSectionHeader title="Lidarr Integration Guide" />
      <ArrPanelBody>{body}</ArrPanelBody>
    </ArrContentPanel>
  );
}

export function ImportListsPage() {
  const [metrics, setMetrics] = useState<ImportListMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resetDialogOpen, setResetDialogOpen] = useState<ResetListId | null>(null);
  const [resetting, setResetting] = useState(false);

  const loadMetrics = async () => {
    try {
      setError(null);
      const data = await api.getImportListMetrics();
      setMetrics(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load import list metrics";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, []);

  const handleReset = async (listId: ResetListId) => {
    try {
      setResetting(true);
      await api.resetImportList(listId);
      toast.success("Import list cleared");
      setResetDialogOpen(null);
      await loadMetrics();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to reset import list");
    } finally {
      setResetting(false);
    }
  };

  const copyToClipboard = async (url: string) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        toast.success("URL copied to clipboard");
        return;
      }
    } catch {
      /* fall through to legacy fallback */
    }
    // Fallback for HTTP/non-secure contexts where clipboard API is blocked
    try {
      const textarea = document.createElement("textarea");
      textarea.value = url;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      toast.success("URL copied to clipboard");
    } catch {
      toast.error("Failed to copy URL (try selecting and copying manually)");
    }
  };

  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
  const playlistsyncUrl = `${baseUrl}/import_lists/discovery_playlistsync`;

  if (loading) {
    return (
      <div className="space-y-6 arr-page-panels">
        <div className="text-center text-muted-foreground py-12">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 arr-page-panels">
        <ArrContentPanel>
          <ArrPanelBody className="flex min-h-[200px] flex-col items-center justify-center gap-4 p-8">
            <p className="text-lg font-medium text-destructive">Failed to Load</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={loadMetrics}>Try Again</Button>
          </ArrPanelBody>
        </ArrContentPanel>
      </div>
    );
  }

  return (
    <div className="space-y-6 arr-page-panels">
      <ArrPageToolbar>
        <Button variant="outline" size="sm" onClick={() => void loadMetrics()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </ArrPageToolbar>

      <div className="space-y-6">
        <ImportListEndpointSection
          title="Playlist Sync Discovery"
          description='Artists discovered from playlist sync operations (Spotify, ListenBrainz, etc.) when tracks fail to match in your library. Requires "Add new artists" to be checked in the playlist sync command settings (Commands → Edit). Empty is normal when playlists have no new artists to add, or maintenance has already cleaned up.'
          url={playlistsyncUrl}
          badge={
            metrics?.unified ? (
              <Badge
                variant={getStatusVariant(metrics.unified.status)}
                className="shrink-0 whitespace-nowrap"
              >
                {metrics.unified.exists ? formatStatus(metrics.unified.status) : "Not Available"}
              </Badge>
            ) : null
          }
          onCopy={() => void copyToClipboard(playlistsyncUrl)}
          onReset={() => setResetDialogOpen("playlistsync")}
          resetDisabled={!metrics?.unified?.exists || metrics.unified.entry_count === 0}
          metrics={metrics?.unified ?? null}
          emptyHint={
            !metrics?.unified?.exists || metrics.unified.entry_count === 0 ? (
              <div className="rounded-lg bg-muted p-3 text-sm text-muted-foreground">
                Empty is normal when no playlist sync commands have added artists, or maintenance
                has already cleaned up. This list is populated when playlist sync runs find new
                artists not in your library.
              </div>
            ) : undefined
          }
        />

        <LidarrIntegrationGuide />
      </div>

      {/* Reset confirmation dialog */}
      <Dialog open={!!resetDialogOpen} onOpenChange={(open) => !open && setResetDialogOpen(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Import List</DialogTitle>
            <DialogDescription>
              {resetDialogOpen &&
                `Clear all ${metrics?.unified?.entry_count ?? 0} artists from this import list? Artists already in Lidarr will not be removed.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetDialogOpen(null)} disabled={resetting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => resetDialogOpen && handleReset(resetDialogOpen)}
              disabled={resetting}
            >
              {resetting ? "Resetting..." : "Reset"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
