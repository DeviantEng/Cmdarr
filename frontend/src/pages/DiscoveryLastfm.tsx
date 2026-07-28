import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import {
  ExternalLink,
  Loader2,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Square,
  BookOpen,
  Disc3,
} from "lucide-react";
import { api, type LastfmDiscoveryResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { NumericInput } from "@/components/NumericInput";
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
  play_count?: number;
};

type SeedSource = "lidarr" | "plex";

type LidarrProfile = { id: number; name: string };

const LS_QUALITY_PROFILE = "discovery.lastfm.qualityProfileId";
const LS_METADATA_PROFILE = "discovery.lastfm.metadataProfileId";

function readStoredProfileId(key: string): number | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

function writeStoredProfileId(key: string, id: number) {
  try {
    localStorage.setItem(key, String(id));
  } catch {
    /* ignore quota / private mode */
  }
}

function pickProfileId(profiles: LidarrProfile[], preferred: number | null): string {
  if (!profiles.length) return "";
  if (preferred != null && profiles.some((p) => p.id === preferred)) {
    return String(preferred);
  }
  return String(profiles[0].id);
}

type DiscoveryLastfmPageProps = {
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

function formatCount(value: number | string | null | undefined): string | null {
  if (value == null || value === "") return null;
  const num = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(num)) return null;
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(num);
}

export function DiscoveryLastfmPage({
  showPageHeader = true,
  useArrPanel = false,
}: DiscoveryLastfmPageProps) {
  const [seedSource, setSeedSource] = useState<SeedSource>("lidarr");
  const [artists, setArtists] = useState<SeedArtist[]>([]);
  const [loadingArtists, setLoadingArtists] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [artistFilter, setArtistFilter] = useState("");
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  const [plexAccounts, setPlexAccounts] = useState<{ id: string; name: string }[]>([]);
  const [plexAccountId, setPlexAccountId] = useState("");
  const [lookbackDays, setLookbackDays] = useState(90);
  const [plexLimit, setPlexLimit] = useState(20);
  const [loadingPlex, setLoadingPlex] = useState(false);
  const [unmatchedPlex, setUnmatchedPlex] = useState<{ artist_name: string; play_count: number }[]>(
    []
  );

  const [qualityProfiles, setQualityProfiles] = useState<LidarrProfile[]>([]);
  const [metadataProfiles, setMetadataProfiles] = useState<LidarrProfile[]>([]);
  const [qualityProfileId, setQualityProfileId] = useState("");
  const [metadataProfileId, setMetadataProfileId] = useState("");
  const [loadingProfiles, setLoadingProfiles] = useState(true);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [results, setResults] = useState<LastfmDiscoveryResult[]>([]);
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

  const loadLidarrProfiles = useCallback(async () => {
    setLoadingProfiles(true);
    try {
      const res = await api.getLastfmDiscoveryLidarrProfiles();
      const quality = res.quality_profiles ?? [];
      const metadata = res.metadata_profiles ?? [];
      setQualityProfiles(quality);
      setMetadataProfiles(metadata);
      setQualityProfileId(pickProfileId(quality, readStoredProfileId(LS_QUALITY_PROFILE)));
      setMetadataProfileId(pickProfileId(metadata, readStoredProfileId(LS_METADATA_PROFILE)));
    } catch (e) {
      setQualityProfiles([]);
      setMetadataProfiles([]);
      setQualityProfileId("");
      setMetadataProfileId("");
      toast.error(e instanceof Error ? e.message : "Failed to load Lidarr profiles");
    } finally {
      setLoadingProfiles(false);
    }
  }, []);

  const loadLidarrArtists = useCallback(async () => {
    setLoadingArtists(true);
    try {
      const res = await api.getLastfmDiscoveryArtists("", 10000);
      setArtists(res.artists ?? []);
      setUnmatchedPlex([]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load Lidarr artists");
    } finally {
      setLoadingArtists(false);
    }
  }, []);

  const loadPlexAccounts = useCallback(async () => {
    try {
      const res = await api.getPlexAccounts();
      setPlexAccounts(res.accounts ?? []);
      if (!plexAccountId && res.accounts?.length) {
        setPlexAccountId(res.accounts[0].id);
      }
    } catch {
      setPlexAccounts([]);
    }
  }, [plexAccountId]);

  useEffect(() => {
    void loadLidarrArtists();
    void loadPlexAccounts();
    void loadLidarrProfiles();
  }, [loadLidarrArtists, loadPlexAccounts, loadLidarrProfiles]);

  useEffect(() => {
    setSelected({});
    setArtistFilter("");
    if (seedSource === "lidarr") {
      void loadLidarrArtists();
    } else {
      setArtists([]);
      setUnmatchedPlex([]);
    }
  }, [seedSource, loadLidarrArtists]);

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
      results: LastfmDiscoveryResult[];
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
            const data = await api.getLastfmDiscoverySession(id);
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
      const res = await api.syncLastfmDiscoveryArtists();
      toast.success(`Synced ${res.synced ?? 0} Lidarr artists`);
      if (seedSource === "lidarr") await loadLidarrArtists();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to sync Lidarr artists");
    } finally {
      setSyncing(false);
    }
  };

  const handleLoadPlexTop = async () => {
    if (!plexAccountId) {
      toast.error("Select a Plex account");
      return;
    }
    setLoadingPlex(true);
    try {
      const res = await api.getLastfmDiscoveryPlexTopArtists({
        account_id: plexAccountId,
        lookback_days: lookbackDays,
        limit: plexLimit,
      });
      setArtists(
        (res.artists ?? []).map((a) => ({
          artist_mbid: a.artist_mbid,
          artist_name: a.artist_name,
          lidarr_id: a.lidarr_id,
          play_count: a.play_count,
        }))
      );
      setUnmatchedPlex(res.unmatched ?? []);
      setSelected({});
      toast.success(
        `Loaded ${res.artists?.length ?? 0} matched artists` +
          (res.unmatched?.length ? ` (${res.unmatched.length} unmatched)` : "")
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load Plex top artists");
    } finally {
      setLoadingPlex(false);
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
    setAddedMbids({});
    try {
      const data = await api.startLastfmDiscoverySession(
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
      const data = await api.stopLastfmDiscoverySession(sessionId);
      applySession(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to stop search");
    }
  };

  const handleBio = async (artist: LastfmDiscoveryResult) => {
    setBioOpen(true);
    setBioTitle(artist.name);
    setBioText("");
    setBioUrl(artist.url || "");
    setBioStats({});
    setBioLoading(true);
    try {
      const res = await api.getLastfmDiscoveryBio(artist.mbid, artist.name);
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

  const handleAdd = async (artist: LastfmDiscoveryResult) => {
    const qid = Number(qualityProfileId);
    const mid = Number(metadataProfileId);
    if (!Number.isFinite(qid) || qid < 1 || !Number.isFinite(mid) || mid < 1) {
      toast.error("Select Lidarr quality and metadata profiles before adding");
      return;
    }
    setAddingMbid(artist.mbid);
    try {
      await api.addLastfmDiscoveryArtist({
        mbid: artist.mbid,
        artist_name: artist.name,
        search_for_missing_albums: true,
        quality_profile_id: qid,
        metadata_profile_id: mid,
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
              <SelectItem value="plex">Plex top listened</SelectItem>
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
          Sync Lidarr artists
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

  const seedPanel = (
    <Card className={cn(useArrPanel && "border-0 shadow-none bg-transparent")}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Seed artists</CardTitle>
        <CardDescription>
          {seedSource === "lidarr"
            ? "Search and select artists from your Lidarr library, then run a Last.fm similar search."
            : "Load your most-played Plex artists (matched to Lidarr), select seeds, then run."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-3 rounded-md border p-3">
          <p className="text-xs text-muted-foreground">
            Lidarr profiles used when adding recommended artists.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Quality profile</Label>
              <Select
                value={qualityProfileId}
                onValueChange={(v) => {
                  setQualityProfileId(v);
                  const n = Number(v);
                  if (Number.isFinite(n) && n > 0) writeStoredProfileId(LS_QUALITY_PROFILE, n);
                }}
                disabled={loadingProfiles || qualityProfiles.length === 0}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={loadingProfiles ? "Loading…" : "Select quality profile"}
                  />
                </SelectTrigger>
                <SelectContent>
                  {qualityProfiles.length === 0 ? (
                    <SelectItem value="__none" disabled>
                      No quality profiles
                    </SelectItem>
                  ) : (
                    qualityProfiles.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Metadata profile</Label>
              <Select
                value={metadataProfileId}
                onValueChange={(v) => {
                  setMetadataProfileId(v);
                  const n = Number(v);
                  if (Number.isFinite(n) && n > 0) writeStoredProfileId(LS_METADATA_PROFILE, n);
                }}
                disabled={loadingProfiles || metadataProfiles.length === 0}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={loadingProfiles ? "Loading…" : "Select metadata profile"}
                  />
                </SelectTrigger>
                <SelectContent>
                  {metadataProfiles.length === 0 ? (
                    <SelectItem value="__none" disabled>
                      No metadata profiles
                    </SelectItem>
                  ) : (
                    metadataProfiles.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <div className="rounded-md border p-3 text-sm text-muted-foreground">
          Scheduled auto-add is the <strong>Last.fm Discovery</strong> command under{" "}
          <Link className="underline underline-offset-2" to="/commands">
            Commands
          </Link>
          . It is independent of this interactive page. KPIs:{" "}
          <Link className="underline underline-offset-2" to="/system/discovery">
            System → Discovery
          </Link>
          .
        </div>

        {seedSource === "plex" && (
          <div className="space-y-3 rounded-md border p-3">
            <div className="space-y-2">
              <Label>Plex account</Label>
              <Select
                value={plexAccountId}
                onValueChange={setPlexAccountId}
                disabled={running || loadingPlex}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select account" />
                </SelectTrigger>
                <SelectContent>
                  {plexAccounts.length === 0 ? (
                    <SelectItem value="__none" disabled>
                      No Plex accounts (enable Plex in settings)
                    </SelectItem>
                  ) : (
                    plexAccounts.map((acc) => (
                      <SelectItem key={acc.id} value={acc.id}>
                        {acc.name || acc.id}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Lookback days</Label>
                <NumericInput
                  value={lookbackDays}
                  onChange={(v) => setLookbackDays(v ?? 90)}
                  min={7}
                  max={365}
                  defaultValue={90}
                  disabled={running || loadingPlex}
                />
              </div>
              <div className="space-y-2">
                <Label>Top artists</Label>
                <NumericInput
                  value={plexLimit}
                  onChange={(v) => setPlexLimit(v ?? 20)}
                  min={1}
                  max={50}
                  defaultValue={20}
                  disabled={running || loadingPlex}
                />
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleLoadPlexTop()}
              disabled={running || loadingPlex || !plexAccountId}
            >
              {loadingPlex ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Disc3 className="h-4 w-4" />
              )}
              Load top artists
            </Button>
            {unmatchedPlex.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {unmatchedPlex.length} Plex artist{unmatchedPlex.length === 1 ? "" : "s"} not in
                Lidarr cache (skipped as seeds).
              </p>
            )}
          </div>
        )}

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
          {loadingArtists && seedSource === "lidarr" ? (
            <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading artists…
            </div>
          ) : artists.length === 0 ? (
            <div className="space-y-2 p-4 text-sm text-muted-foreground">
              {seedSource === "lidarr" ? (
                <>
                  <p>
                    No cached Lidarr artists. Click Sync Lidarr artists, or ensure Lidarr is
                    configured.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleSync()}
                    disabled={syncing}
                  >
                    Sync Lidarr artists
                  </Button>
                </>
              ) : (
                <p>Load top artists from Plex to populate this list.</p>
              )}
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
                      <span className="min-w-0 flex-1 truncate">{a.artist_name}</span>
                      {typeof a.play_count === "number" && (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {a.play_count} plays
                        </span>
                      )}
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );

  const resultsPanel = (
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
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {results.map((r) => {
              const added = !!addedMbids[r.mbid];
              const listenersLabel = formatCount(r.listeners);
              const scrobblesLabel = formatCount(r.playcount);
              const statsLine = [
                listenersLabel ? `${listenersLabel} listeners` : null,
                scrobblesLabel ? `${scrobblesLabel} scrobbles` : null,
              ]
                .filter(Boolean)
                .join(" · ");
              return (
                <div
                  key={r.mbid}
                  className="flex flex-col overflow-hidden rounded-md border bg-card"
                >
                  <div className="relative aspect-square bg-muted">
                    {r.image_url ? (
                      <img
                        src={r.image_url}
                        alt=""
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                        <Disc3 className="h-12 w-12 opacity-40" />
                      </div>
                    )}
                  </div>
                  <div className="flex flex-1 flex-col gap-2 p-3">
                    <div className="min-w-0 space-y-1">
                      <div className="font-medium leading-snug line-clamp-2">{r.name}</div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge variant="secondary">{formatMatch(r.match_score)}</Badge>
                        {r.seed_count > 1 && <Badge variant="outline">{r.seed_count} seeds</Badge>}
                      </div>
                      {statsLine ? (
                        <p className="text-xs text-muted-foreground">{statsLine}</p>
                      ) : null}
                      {r.seed_names.length > 0 && (
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          Similar to: {r.seed_names.join(", ")}
                        </p>
                      )}
                    </div>
                    <div className="mt-auto flex flex-wrap gap-2 pt-1">
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
                        disabled={
                          added || addingMbid === r.mbid || !qualityProfileId || !metadataProfileId
                        }
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
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );

  const body = (
    <div className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
      {seedPanel}
      {resultsPanel}
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
            title="Last.fm Discovery"
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
          <h1 className="text-2xl font-bold tracking-tight">Last.fm Discovery</h1>
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
