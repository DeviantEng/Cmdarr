import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ExternalLink,
  Loader2,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Square,
  BookOpen,
} from "lucide-react";
import { api, type SimilarrResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  ArrContentPanel,
  ArrPageToolbar,
  ArrPanelBody,
  ArrSectionHeader,
} from "@/arr/components/ArrPageToolbar";
import { cn } from "@/lib/utils";

type SeedArtist = {
  artist_mbid: string;
  artist_name: string;
  lidarr_id?: number | null;
};

type SeedSource = "lidarr" | "plex";

type SimilarrPageProps = {
  showPageHeader?: boolean;
  useArrPanel?: boolean;
};

function stripHtml(html: string): string {
  if (!html) return "";
  const withBreaks = html
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n\n")
    .replace(/<[^>]+>/g, "");
  const textarea = document.createElement("textarea");
  textarea.innerHTML = withBreaks;
  return textarea.value.replace(/\n{3,}/g, "\n\n").trim();
}

function formatMatch(score: number): string {
  if (!Number.isFinite(score)) return "—";
  return `${Math.round(score * 100)}%`;
}

export function SimilarrPage({ showPageHeader = true, useArrPanel = false }: SimilarrPageProps) {
  const [seedSource, setSeedSource] = useState<SeedSource>("lidarr");
  const [artists, setArtists] = useState<SeedArtist[]>([]);
  const [loadingArtists, setLoadingArtists] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [artistFilter, setArtistFilter] = useState("");
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [results, setResults] = useState<SimilarrResult[]>([]);
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [addingMbid, setAddingMbid] = useState<string | null>(null);
  const [addedMbids, setAddedMbids] = useState<Record<string, boolean>>({});

  const [bioOpen, setBioOpen] = useState(false);
  const [bioLoading, setBioLoading] = useState(false);
  const [bioTitle, setBioTitle] = useState("");
  const [bioText, setBioText] = useState("");
  const [bioUrl, setBioUrl] = useState("");
  const [bioStats, setBioStats] = useState<{ listeners?: string; playcount?: string }>({});

  const pollRef = useRef<number | null>(null);
  const terminalNotified = useRef<string | null>(null);

  const loadArtists = useCallback(async () => {
    setLoadingArtists(true);
    try {
      const res = await api.getSimilarrArtists("", 10000);
      setArtists(res.artists ?? []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load Lidarr artists");
    } finally {
      setLoadingArtists(false);
    }
  }, []);

  useEffect(() => {
    void loadArtists();
  }, [loadArtists]);

  const filteredArtists = useMemo(() => {
    const q = artistFilter.trim().toLowerCase();
    if (!q) return artists;
    return artists.filter((a) => a.artist_name.toLowerCase().includes(q));
  }, [artists, artistFilter]);

  const selectedSeeds = useMemo(
    () => artists.filter((a) => selected[a.artist_mbid]),
    [artists, selected]
  );

  const selectedCount = selectedSeeds.length;

  const stopPolling = useCallback(() => {
    if (pollRef.current != null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const applySession = useCallback(
    (data: {
      session_id: string;
      status: string;
      elapsed_seconds: number;
      results: SimilarrResult[];
      error?: string | null;
    }) => {
      setSessionId(data.session_id);
      setSessionStatus(data.status);
      setElapsed(data.elapsed_seconds);
      setResults(data.results ?? []);
      const isRunning = data.status === "running";
      setRunning(isRunning);
      if (!isRunning) {
        stopPolling();
        const key = `${data.session_id}:${data.status}`;
        if (terminalNotified.current !== key) {
          terminalNotified.current = key;
          if (data.status === "stopped") toast.message("Search stopped");
          else if (data.status === "timed_out")
            toast.error(data.error || "Search hit internal failsafe timeout");
          else if (data.status === "completed")
            toast.success(`Search finished — ${data.results?.length ?? 0} artists found`);
          else if (data.status === "error") toast.error(data.error || "Search failed");
        }
      }
    },
    [stopPolling]
  );

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      pollRef.current = window.setInterval(() => {
        void (async () => {
          try {
            const data = await api.getSimilarrSession(id);
            applySession(data);
          } catch {
            /* ignore transient poll errors */
          }
        })();
      }, 1000);
    },
    [applySession, stopPolling]
  );

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await api.syncSimilarrArtists();
      toast.success(`Synced ${res.synced ?? 0} Lidarr artists`);
      await loadArtists();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to sync Lidarr artists");
    } finally {
      setSyncing(false);
    }
  };

  const toggleArtist = (mbid: string) => {
    setSelected((prev) => ({ ...prev, [mbid]: !prev[mbid] }));
  };

  const clearSelection = () => setSelected({});

  const selectFiltered = () => {
    setSelected((prev) => {
      const next = { ...prev };
      for (const a of filteredArtists) next[a.artist_mbid] = true;
      return next;
    });
  };

  const handleRun = async () => {
    if (selectedCount === 0) {
      toast.error("Select at least one artist");
      return;
    }
    setStarting(true);
    terminalNotified.current = null;
    try {
      const data = await api.startSimilarrSession(
        selectedSeeds.map((a) => ({ mbid: a.artist_mbid, name: a.artist_name }))
      );
      applySession(data);
      if (data.status === "running") startPolling(data.session_id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start search");
      setRunning(false);
    } finally {
      setStarting(false);
    }
  };

  const handleStop = async () => {
    if (!sessionId) return;
    try {
      const data = await api.stopSimilarrSession(sessionId);
      applySession(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to stop search");
    }
  };

  const handleBio = async (artist: SimilarrResult) => {
    setBioOpen(true);
    setBioTitle(artist.name);
    setBioText("");
    setBioUrl(artist.url || "");
    setBioStats({});
    setBioLoading(true);
    try {
      const res = await api.getSimilarrBio(artist.mbid, artist.name);
      const a = res.artist;
      setBioTitle(a.name || artist.name);
      setBioUrl(a.url || artist.url || "");
      setBioText(stripHtml(a.bio_summary || a.bio_content || "") || "No biography available.");
      setBioStats({
        listeners: a.listeners != null ? String(a.listeners) : undefined,
        playcount: a.playcount != null ? String(a.playcount) : undefined,
      });
    } catch (e) {
      setBioText(e instanceof Error ? e.message : "Failed to load biography");
    } finally {
      setBioLoading(false);
    }
  };

  const handleAdd = async (artist: SimilarrResult) => {
    setAddingMbid(artist.mbid);
    try {
      await api.addSimilarrArtist({
        mbid: artist.mbid,
        artist_name: artist.name,
        search_for_missing_albums: true,
      });
      setAddedMbids((prev) => ({ ...prev, [artist.mbid]: true }));
      toast.success(`Added ${artist.name} to Lidarr (search started)`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to add artist");
    } finally {
      setAddingMbid(null);
    }
  };

  const toolbar = (
    <ArrPageToolbar>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground whitespace-nowrap">Seed source</Label>
          <Select
            value={seedSource}
            onValueChange={(v) => setSeedSource(v as SeedSource)}
            disabled={running}
          >
            <SelectTrigger className="h-8 w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="lidarr">Lidarr library</SelectItem>
              <SelectItem value="plex" disabled>
                Plex top listened (Phase 2)
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleSync()}
          disabled={syncing || running}
        >
          {syncing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Refresh cache
        </Button>
        {!running ? (
          <Button
            size="sm"
            onClick={() => void handleRun()}
            disabled={starting || selectedCount === 0}
          >
            {starting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Radio className="h-4 w-4" />
            )}
            Run ({selectedCount})
          </Button>
        ) : (
          <Button size="sm" variant="destructive" onClick={() => void handleStop()}>
            <Square className="h-4 w-4" />
            Stop
          </Button>
        )}
        {sessionStatus && (
          <span className="text-xs text-muted-foreground">
            {sessionStatus}
            {elapsed > 0 ? ` · ${Math.round(elapsed)}s` : ""}
            {results.length > 0 ? ` · ${results.length} found` : ""}
          </span>
        )}
      </div>
    </ArrPageToolbar>
  );

  const body = (
    <div className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
      <Card className={cn(useArrPanel && "border-0 shadow-none bg-transparent")}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Seed artists</CardTitle>
          <CardDescription>
            Search and select artists from your Lidarr library, then run a Last.fm similar search.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              className="pl-8"
              placeholder="Search artists…"
              value={artistFilter}
              onChange={(e) => setArtistFilter(e.target.value)}
              disabled={running}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={selectFiltered}
              disabled={running || filteredArtists.length === 0}
            >
              Select filtered
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={clearSelection}
              disabled={running || selectedCount === 0}
            >
              Clear
            </Button>
            <span className="self-center text-xs text-muted-foreground">
              {selectedCount} selected · {filteredArtists.length}/{artists.length} shown
            </span>
          </div>
          <div className="max-h-[min(60vh,520px)] overflow-y-auto rounded-md border">
            {loadingArtists ? (
              <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading artists…
              </div>
            ) : artists.length === 0 ? (
              <div className="space-y-2 p-4 text-sm text-muted-foreground">
                <p>
                  No cached Lidarr artists. Click Refresh cache, or ensure Lidarr is configured.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleSync()}
                  disabled={syncing}
                >
                  Refresh cache
                </Button>
              </div>
            ) : filteredArtists.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground">No artists match your search.</div>
            ) : (
              <ul className="divide-y">
                {filteredArtists.map((a) => {
                  const checked = !!selected[a.artist_mbid];
                  return (
                    <li key={a.artist_mbid}>
                      <label
                        className={cn(
                          "flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-accent/50",
                          checked && "bg-accent/30",
                          running && "pointer-events-none opacity-70"
                        )}
                      >
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-primary"
                          checked={checked}
                          onChange={() => toggleArtist(a.artist_mbid)}
                          disabled={running}
                        />
                        <span className="truncate">{a.artist_name}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className={cn(useArrPanel && "border-0 shadow-none bg-transparent")}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Similar artists</CardTitle>
          <CardDescription>
            One-shot Last.fm lookup for your selected seeds. Results exclude artists already in
            Lidarr. Affinity rises when multiple seeds recommend the same artist.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {results.length === 0 ? (
            <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
              {running
                ? "Searching Last.fm for similar artists…"
                : "Select seed artists and click Run to discover similar artists."}
            </div>
          ) : (
            <ul className="space-y-2">
              {results.map((r) => {
                const added = !!addedMbids[r.mbid];
                return (
                  <li
                    key={r.mbid}
                    className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium truncate">{r.name}</span>
                        <Badge variant="secondary">{formatMatch(r.match_score)}</Badge>
                        {r.seed_count > 1 && <Badge variant="outline">{r.seed_count} seeds</Badge>}
                      </div>
                      {r.seed_names.length > 0 && (
                        <p className="text-xs text-muted-foreground truncate">
                          Similar to: {r.seed_names.join(", ")}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void handleBio(r)}
                      >
                        <BookOpen className="h-4 w-4" />
                        Bio
                      </Button>
                      {r.url ? (
                        <Button type="button" variant="ghost" size="sm" asChild>
                          <a href={r.url} target="_blank" rel="noreferrer">
                            <ExternalLink className="h-4 w-4" />
                            Last.fm
                          </a>
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        size="sm"
                        disabled={added || addingMbid === r.mbid}
                        onClick={() => void handleAdd(r)}
                      >
                        {addingMbid === r.mbid ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Plus className="h-4 w-4" />
                        )}
                        {added ? "Added" : "Add"}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );

  const dialog = (
    <Dialog open={bioOpen} onOpenChange={setBioOpen}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{bioTitle}</DialogTitle>
          <DialogDescription>
            {[
              bioStats.listeners ? `${bioStats.listeners} listeners` : null,
              bioStats.playcount ? `${bioStats.playcount} plays` : null,
            ]
              .filter(Boolean)
              .join(" · ") || "Last.fm biography"}
          </DialogDescription>
        </DialogHeader>
        {bioLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{bioText}</p>
        )}
        {bioUrl ? (
          <a
            className="inline-flex items-center gap-1 text-sm text-primary underline-offset-2 hover:underline"
            href={bioUrl}
            target="_blank"
            rel="noreferrer"
          >
            View on Last.fm <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : null}
      </DialogContent>
    </Dialog>
  );

  if (useArrPanel) {
    return (
      <>
        {toolbar}
        <ArrContentPanel>
          <ArrSectionHeader
            title="Similarr"
            description="Discover similar artists via Last.fm and add them to Lidarr."
          />
          <ArrPanelBody>{body}</ArrPanelBody>
        </ArrContentPanel>
        {dialog}
      </>
    );
  }

  return (
    <div className="space-y-4 p-4 sm:p-6">
      {showPageHeader && (
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Similarr</h1>
          <p className="text-muted-foreground">
            Discover similar artists via Last.fm and add them to Lidarr.
          </p>
        </div>
      )}
      {toolbar}
      {body}
      {dialog}
    </div>
  );
}
