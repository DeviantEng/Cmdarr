import { useState, useEffect, type ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
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
import { Copy, Disc, Music, RefreshCw, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

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

type ResetListId = "lastfm" | "playlistsync";

type ListMetricsEntry = {
  exists: boolean;
  entry_count: number;
  file_size: number;
  age_human: string;
  status: string;
};

type ImportListEndpointSectionProps = {
  useArrPanel: boolean;
  icon: ReactNode;
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
  useArrPanel,
  icon,
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
      <label className={cn("block text-sm font-medium", useArrPanel && "arr-field-label")}>
        Endpoint URL
      </label>
      <input
        type="text"
        readOnly
        value={url}
        title={url}
        className={cn(
          useArrPanel
            ? "arr-field-input"
            : "w-full min-w-0 truncate rounded-md border bg-muted px-3 py-2 text-xs font-mono sm:text-sm"
        )}
      />
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

  const statsBlock =
    metrics?.exists &&
    (useArrPanel ? (
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
    ) : (
      <div className="mt-4 rounded-lg bg-muted p-4">
        <h4 className="mb-3 text-sm font-medium">File Statistics</h4>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="text-center">
            <div className="text-lg font-semibold">{metrics.entry_count.toLocaleString()}</div>
            <div className="text-xs text-muted-foreground">Artists</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold">{formatFileSize(metrics.file_size)}</div>
            <div className="text-xs text-muted-foreground">File Size</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold">{metrics.age_human}</div>
            <div className="text-xs text-muted-foreground">Last Updated</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold">{formatStatus(metrics.status)}</div>
            <div className="text-xs text-muted-foreground">Status</div>
          </div>
        </div>
      </div>
    ));

  if (useArrPanel) {
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

  return (
    <Card>
      <CardContent className="p-4 md:p-6">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <h2 className="flex min-w-0 items-center gap-2 text-xl font-semibold">
            {icon}
            <span className="min-w-0">{title}</span>
          </h2>
          {badge}
        </div>
        <p className="mb-4 text-muted-foreground">{description}</p>
        {endpointBlock}
        {emptyHint}
        {statsBlock}
      </CardContent>
    </Card>
  );
}

function LidarrIntegrationGuide({ useArrPanel }: { useArrPanel: boolean }) {
  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
  const lastfmUrl = `${baseUrl}/import_lists/discovery_lastfm`;
  const playlistsyncUrl = `${baseUrl}/import_lists/discovery_playlistsync`;

  const body = (
    <>
      <p className="mb-4 text-muted-foreground">To add Cmdarr import lists in Lidarr:</p>
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
            Set <strong>URL</strong> to one of:
          </span>
        </div>
        <div className="space-y-3 sm:ml-9">
          <div className="min-w-0 space-y-1">
            <code className="block break-all rounded bg-muted px-2 py-1.5 text-xs font-mono sm:text-sm">
              {lastfmUrl}
            </code>
            <span className="text-sm text-muted-foreground">(Last.fm similar artists)</span>
          </div>
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
          <strong>Pro tip:</strong> You can add multiple import lists for different discovery
          sources! Each provides unique recommendations based on different algorithms.
        </p>
      </div>
    </>
  );

  if (useArrPanel) {
    return (
      <ArrContentPanel className="border-blue-500/50 bg-blue-500/5">
        <ArrSectionHeader title="Lidarr Integration Guide" />
        <ArrPanelBody>{body}</ArrPanelBody>
      </ArrContentPanel>
    );
  }

  return (
    <Card className="border-blue-500/50 bg-blue-500/5">
      <CardContent className="p-4 md:p-6">
        <h3 className="mb-4 text-lg font-semibold">Lidarr Integration Guide</h3>
        {body}
      </CardContent>
    </Card>
  );
}

type ImportListsPageProps = {
  showPageHeader?: boolean;
  useArrPanel?: boolean;
};

export function ImportListsPage({
  showPageHeader = true,
  useArrPanel = false,
}: ImportListsPageProps) {
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
  const lastfmUrl = `${baseUrl}/import_lists/discovery_lastfm`;
  const playlistsyncUrl = `${baseUrl}/import_lists/discovery_playlistsync`;

  const listHeader = showPageHeader ? (
    <div>
      <h1 className="text-3xl font-bold">Import Lists</h1>
      <p className="mt-2 text-muted-foreground">
        Available import list endpoints for Lidarr integration and music discovery automation.
      </p>
    </div>
  ) : null;

  if (loading) {
    return (
      <div className={cn("space-y-6", useArrPanel && "arr-page-panels")}>
        {listHeader}
        <div className="text-center text-muted-foreground py-12">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("space-y-6", useArrPanel && "arr-page-panels")}>
        {listHeader}
        <Card className="border-destructive">
          <CardContent className="flex min-h-[200px] flex-col items-center justify-center gap-4 p-8">
            <p className="text-lg font-medium text-destructive">Failed to Load</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={loadMetrics}>Try Again</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", useArrPanel && "arr-page-panels")}>
      {listHeader}

      {useArrPanel ? (
        <ArrPageToolbar>
          <Button variant="outline" size="sm" onClick={() => void loadMetrics()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </ArrPageToolbar>
      ) : null}

      <div className="space-y-6">
        <ImportListEndpointSection
          useArrPanel={useArrPanel}
          icon={<Music className="h-5 w-5 shrink-0" />}
          title="Last.fm Discovery"
          description="Similar artists discovered via Last.fm and MusicBrainz fuzzy matching. When enabled, typically adds new artists daily."
          url={lastfmUrl}
          badge={
            metrics?.lastfm ? (
              <Badge
                variant={getStatusVariant(metrics.lastfm.status)}
                className="shrink-0 whitespace-nowrap"
              >
                {metrics.lastfm.exists ? formatStatus(metrics.lastfm.status) : "Not Available"}
              </Badge>
            ) : null
          }
          onCopy={() => void copyToClipboard(lastfmUrl)}
          onReset={() => setResetDialogOpen("lastfm")}
          resetDisabled={!metrics?.lastfm?.exists || metrics.lastfm.entry_count === 0}
          metrics={metrics?.lastfm ?? null}
        />

        <ImportListEndpointSection
          useArrPanel={useArrPanel}
          icon={<Disc className="h-5 w-5 shrink-0" />}
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

        <LidarrIntegrationGuide useArrPanel={useArrPanel} />
      </div>

      {/* Reset confirmation dialog */}
      <Dialog open={!!resetDialogOpen} onOpenChange={(open) => !open && setResetDialogOpen(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Import List</DialogTitle>
            <DialogDescription>
              {resetDialogOpen &&
                `Clear all ${resetDialogOpen === "lastfm" ? (metrics?.lastfm?.entry_count ?? 0) : (metrics?.unified?.entry_count ?? 0)} artists from this import list? Artists already in Lidarr will not be removed.`}
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
