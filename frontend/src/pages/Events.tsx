import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ExternalLink,
  EyeOff,
  Loader2,
  MinusCircle,
  RefreshCw,
  RotateCcw,
  Search,
  Star,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import type { ConfigUpdateRequest } from "@/lib/types";
import { collapseSourceLinksForDisplay } from "@/lib/eventSourceLinks";
import { cn } from "@/lib/utils";

type ArtistEventRow = Awaited<ReturnType<typeof api.getUpcomingEvents>>["events"][number];

type HiddenEventItem = Awaited<ReturnType<typeof api.getHiddenEvents>>["items"][number];

function formatEventDate(ev: ArtistEventRow): string {
  if (ev.starts_at_utc) {
    return new Date(ev.starts_at_utc).toLocaleDateString(undefined, { dateStyle: "medium" });
  }
  return ev.local_date;
}

export function EventsPage() {
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState<ArtistEventRow[]>([]);
  const [providerStatus, setProviderStatus] = useState<Awaited<
    ReturnType<typeof api.getEventsProviderStatus>
  > | null>(null);
  const [settings, setSettings] = useState<Awaited<
    ReturnType<typeof api.getEventsSettings>
  > | null>(null);
  const [locationQuery, setLocationQuery] = useState("");
  const [radiusInput, setRadiusInput] = useState("100");
  const [geoLoading, setGeoLoading] = useState(false);
  const [hiddenOpen, setHiddenOpen] = useState(false);
  const [hiddenTab, setHiddenTab] = useState("artists");
  const [hiddenItems, setHiddenItems] = useState<
    { artist_mbid: string; artist_name: string; hidden_at: string | null }[]
  >([]);
  const [hiddenEventItems, setHiddenEventItems] = useState<HiddenEventItem[]>([]);
  const [hiddenArtistCount, setHiddenArtistCount] = useState(0);
  const [hiddenEventCount, setHiddenEventCount] = useState(0);
  const [confirmRestoreAll, setConfirmRestoreAll] = useState(false);
  const [confirmRestoreAllEvents, setConfirmRestoreAllEvents] = useState(false);
  const [refreshRunning, setRefreshRunning] = useState(false);
  const [confirmForceRefreshAll, setConfirmForceRefreshAll] = useState(false);
  const [festivalDialogOpen, setFestivalDialogOpen] = useState(false);
  const [festivalCatalog, setFestivalCatalog] = useState<
    { key: string; label: string; event_kind: string; count: number }[]
  >([]);
  const [festivalsLoading, setFestivalsLoading] = useState(false);
  const [festivalBulkHiding, setFestivalBulkHiding] = useState(false);
  const [hiddenFestivalKeys, setHiddenFestivalKeys] = useState<string[]>([]);
  const [artistFilter, setArtistFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [interestFilter, setInterestFilter] = useState<"all" | "interested">("all");
  const [confirmHideArtist, setConfirmHideArtist] = useState<ArtistEventRow | null>(null);
  const [confirmHideEvent, setConfirmHideEvent] = useState<ArtistEventRow | null>(null);
  const [upcomingStoredCount, setUpcomingStoredCount] = useState<number | null>(null);
  const [excludeFestivals, setExcludeFestivals] = useState(() => {
    try {
      return localStorage.getItem("cmdarr.events.excludeFestivals") === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem("cmdarr.events.excludeFestivals", excludeFestivals ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [excludeFestivals]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ps, st, ev, hA, hE] = await Promise.all([
        api.getEventsProviderStatus(),
        api.getEventsSettings(),
        api.getUpcomingEvents({
          limit: 200,
          interested_only: interestFilter === "interested",
          exclude_festivals: excludeFestivals,
        }),
        api.getHiddenEventArtists(),
        api.getHiddenEvents(),
      ]);
      setProviderStatus(ps);
      setSettings(st);
      setHiddenFestivalKeys(st.hidden_festival_keys ?? []);
      setEvents(ev.events);
      setUpcomingStoredCount(ev.upcoming_stored_count ?? null);
      setRadiusInput(String(st.radius_miles ?? 100));
      setLocationQuery(st.user_label ?? "");
      setHiddenArtistCount(hA.items.length);
      setHiddenEventCount(hE.items.length);
      setHiddenItems(hA.items);
      setHiddenEventItems(hE.items);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, [interestFilter, excludeFestivals]);

  useEffect(() => {
    load();
  }, [load]);

  const festivalCatalogHasUnhidden = useMemo(
    () => festivalCatalog.some((i) => !hiddenFestivalKeys.includes(i.key)),
    [festivalCatalog, hiddenFestivalKeys],
  );

  const filteredEvents = useMemo(() => {
    let list = events;
    const q = artistFilter.trim().toLowerCase();
    if (q) {
      list = list.filter((ev) => {
        const venue =
          `${ev.venue_name || ""} ${ev.venue_city || ""} ${ev.venue_region || ""}`.toLowerCase();
        return ev.artist_name.toLowerCase().includes(q) || venue.includes(q);
      });
    }
    if (sourceFilter !== "all") {
      list = list.filter((ev) => ev.sources.includes(sourceFilter));
    }
    return list;
  }, [events, artistFilter, sourceFilter]);

  const saveConfig = async (key: string, req: ConfigUpdateRequest) => {
    await api.updateConfigSetting(key, req);
  };

  const handleGeocode = async () => {
    const q = locationQuery.trim();
    if (!q) {
      toast.error("Enter a ZIP or city and state");
      return;
    }
    setGeoLoading(true);
    try {
      const g = await api.geocodeEventsLocation(q);
      await saveConfig("ARTIST_EVENTS_USER_LAT", { value: String(g.lat), data_type: "string" });
      await saveConfig("ARTIST_EVENTS_USER_LON", { value: String(g.lon), data_type: "string" });
      await saveConfig("ARTIST_EVENTS_USER_LABEL", {
        value: g.label.slice(0, 500),
        data_type: "string",
      });
      toast.success("Location saved");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Geocoding failed");
    } finally {
      setGeoLoading(false);
    }
  };

  const saveRadius = async () => {
    const n = parseFloat(radiusInput);
    if (Number.isNaN(n) || n <= 0) {
      toast.error("Invalid radius");
      return;
    }
    try {
      await saveConfig("ARTIST_EVENTS_RADIUS_MILES", { value: String(n), data_type: "float" });
      toast.success("Radius saved");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    }
  };

  const openFestivals = async () => {
    setFestivalDialogOpen(true);
    setFestivalsLoading(true);
    try {
      const c = await api.getFestivalCatalog();
      setFestivalCatalog(c.items);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load festivals");
    } finally {
      setFestivalsLoading(false);
    }
  };

  const toggleFestivalHidden = async (key: string, hide: boolean) => {
    const next = new Set(hiddenFestivalKeys);
    if (hide) {
      next.add(key);
    } else {
      next.delete(key);
    }
    const arr = [...next].sort();
    try {
      await api.putFestivalHidden(arr);
      setHiddenFestivalKeys(arr);
      toast.success(hide ? "Hidden from list" : "Shown in list");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    }
  };

  const hideAllFestivalsInCatalog = async () => {
    if (festivalCatalog.length === 0) return;
    const next = new Set(hiddenFestivalKeys);
    let added = 0;
    for (const item of festivalCatalog) {
      if (!next.has(item.key)) {
        next.add(item.key);
        added += 1;
      }
    }
    if (added === 0) return;
    const arr = [...next].sort();
    setFestivalBulkHiding(true);
    try {
      await api.putFestivalHidden(arr);
      setHiddenFestivalKeys(arr);
      toast.success(`Hidden ${added} festival / tour group(s) from the upcoming list`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setFestivalBulkHiding(false);
    }
  };

  const openHidden = async () => {
    setHiddenOpen(true);
    try {
      const [h, e] = await Promise.all([api.getHiddenEventArtists(), api.getHiddenEvents()]);
      setHiddenItems(h.items);
      setHiddenEventItems(e.items);
      setHiddenArtistCount(h.items.length);
      setHiddenEventCount(e.items.length);
    } catch {
      toast.error("Failed to load hidden items");
    }
  };

  const runRefreshAllDue = async () => {
    setRefreshRunning(true);
    try {
      await api.executeCommand("artist_events_refresh", {
        triggered_by: "api",
        config_override: { refresh_all_due: true },
      });
      toast.success("Refreshing every due artist in one run — see Commands for progress.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start refresh");
    } finally {
      setRefreshRunning(false);
    }
  };

  const runForceRefreshAll = async () => {
    setConfirmForceRefreshAll(false);
    setRefreshRunning(true);
    try {
      await api.executeCommand("artist_events_refresh", {
        triggered_by: "api",
        config_override: { force_refresh_all: true },
      });
      toast.success(
        "Force refresh started — every Lidarr artist will be re-queried regardless of TTL. See Commands for progress."
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start refresh");
    } finally {
      setRefreshRunning(false);
    }
  };

  const doHideArtist = async () => {
    const ev = confirmHideArtist;
    if (!ev) return;
    try {
      await api.hideEventArtist(ev.artist_mbid, ev.artist_name);
      toast.success(`Hidden events for ${ev.artist_name}`);
      setConfirmHideArtist(null);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const doHideEvent = async () => {
    const ev = confirmHideEvent;
    if (!ev) return;
    try {
      await api.hideEventRow(ev.id);
      toast.success("Event hidden");
      setConfirmHideEvent(null);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const restoreHidden = async (mbid: string) => {
    try {
      await api.unhideEventArtist(mbid);
      toast.success("Restored");
      const h = await api.getHiddenEventArtists();
      setHiddenItems(h.items);
      setHiddenArtistCount(h.items.length);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const restoreHiddenEvent = async (eventId: number) => {
    try {
      await api.unhideEventRow(eventId);
      toast.success("Restored");
      const e = await api.getHiddenEvents();
      setHiddenEventItems(e.items);
      setHiddenEventCount(e.items.length);
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const restoreAll = async () => {
    try {
      await api.unhideAllEventArtists();
      toast.success("All artists restored");
      setConfirmRestoreAll(false);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const restoreAllEvents = async () => {
    try {
      await api.unhideAllHiddenEvents();
      toast.success("All hidden events restored");
      setConfirmRestoreAllEvents(false);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const toggleInterested = async (ev: ArtistEventRow) => {
    const next = !ev.interested;
    if (interestFilter === "interested" && !next) {
      setEvents((prev) => prev.filter((e) => e.id !== ev.id));
    } else {
      setEvents((prev) => prev.map((e) => (e.id === ev.id ? { ...e, interested: next } : e)));
    }
    try {
      await api.setEventInterested(ev.id, next);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to update");
      void load();
    }
  };

  const toggleProvider = async (
    key:
      | "ARTIST_EVENTS_BANDSINTOWN_ENABLED"
      | "ARTIST_EVENTS_SONGKICK_ENABLED"
      | "ARTIST_EVENTS_TICKETMASTER_ENABLED",
    checked: boolean
  ) => {
    try {
      await saveConfig(key, { value: checked, data_type: "bool" });
      const ps = await api.getEventsProviderStatus();
      setProviderStatus(ps);
      toast.success("Saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const sourceBadge = (p: string) => {
    if (p === "bandsintown") return "BIT";
    if (p === "songkick") return "SK";
    if (p === "ticketmaster") return "TM";
    return p;
  };

  const hiddenTotal = hiddenArtistCount + hiddenEventCount;

  if (loading && !settings) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Artist Events</h1>
        <p className="text-muted-foreground mt-1">
          Upcoming shows, festivals, and other events for artists in your Lidarr library, aggregated
          from enabled providers. Refreshes use cmdarr&apos;s cached Lidarr artist list; if that
          cache is empty, the command loads it from Lidarr before querying providers.{" "}
          <Link to="/new-releases" className="underline font-medium text-foreground">
            New Releases
          </Link>{" "}
          → Sync Lidarr artists updates the same cache anytime.
        </p>
      </div>

      <Card>
        <CardHeader className="space-y-1 px-4 py-3">
          <CardTitle className="text-base">Providers</CardTitle>
          <CardDescription className="text-xs leading-snug">
            Toggle sources; credentials in{" "}
            <Link to="/config" className="underline font-medium text-foreground">
              Configuration &gt; Event Sources
            </Link>
            . Bandsintown <code className="text-[10px]">app_id</code> is not the same as User-Agent
            (<code className="text-[10px]">CMDARR_USER_AGENT</code>). At least one source must be
            ready before refresh.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 px-4 pb-3 pt-0">
          {!providerStatus?.any_ready && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              No provider fully configured - add keys in{" "}
              <Link to="/config" className="underline font-medium">
                Configuration
              </Link>
              .
            </p>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-2 rounded-md border bg-muted/30 px-3 py-2">
            <div className="flex min-w-[10rem] flex-1 items-center justify-between gap-2">
              <Label className="text-xs font-normal">Bandsintown</Label>
              <div className="flex items-center gap-2">
                <Switch
                  checked={settings?.bandsintown_enabled ?? false}
                  onCheckedChange={(c) => toggleProvider("ARTIST_EVENTS_BANDSINTOWN_ENABLED", c)}
                />
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                  {providerStatus?.bandsintown.enabled ? "ready" : "needs app ID"}
                </span>
              </div>
            </div>
            <div className="flex min-w-[10rem] flex-1 items-center justify-between gap-2">
              <Label className="text-xs font-normal">Songkick</Label>
              <div className="flex items-center gap-2">
                <Switch
                  checked={settings?.songkick_enabled ?? false}
                  onCheckedChange={(c) => toggleProvider("ARTIST_EVENTS_SONGKICK_ENABLED", c)}
                />
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                  {providerStatus?.songkick.enabled ? "ready" : "needs key"}
                </span>
              </div>
            </div>
            <div className="flex min-w-[10rem] flex-1 items-center justify-between gap-2">
              <Label className="text-xs font-normal">Ticketmaster</Label>
              <div className="flex items-center gap-2">
                <Switch
                  checked={settings?.ticketmaster_enabled ?? false}
                  onCheckedChange={(c) => toggleProvider("ARTIST_EVENTS_TICKETMASTER_ENABLED", c)}
                />
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                  {providerStatus?.ticketmaster.enabled ? "ready" : "needs key"}
                </span>
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <div className="inline-flex">
              <Button
                variant="secondary"
                size="sm"
                onClick={runRefreshAllDue}
                disabled={refreshRunning || !providerStatus?.any_ready}
                className="rounded-r-none"
              >
                {refreshRunning ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Refresh all artists
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={refreshRunning || !providerStatus?.any_ready}
                    className="rounded-l-none border-l border-background/40 px-2"
                    aria-label="More refresh options"
                  >
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => setConfirmForceRefreshAll(true)}>
                    Force refresh all artists
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            <p className="text-[11px] leading-snug text-muted-foreground max-w-xl">
              <strong>Refresh all artists</strong> processes every artist past their interval (or
              never scanned). <strong>Force refresh all artists</strong> ignores the interval and
              re-queries every Lidarr artist - use after config changes or to recover from a partial
              scan; large libraries may need a higher command timeout.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="space-y-1 px-4 py-3">
          <CardTitle className="text-base">Location and radius</CardTitle>
          <CardDescription className="text-xs leading-snug">
            ZIP or city/state is saved as coordinates. With a saved location, shows without venue
            coordinates or outside your radius are omitted from the list below.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0">
          <div className="flex flex-wrap items-end gap-2 gap-y-2">
            <div className="min-w-[12rem] flex-1 space-y-1">
              <Label className="text-xs">Location</Label>
              <Input
                className="h-9"
                placeholder="e.g. 97201 or Portland, OR"
                value={locationQuery}
                onChange={(e) => setLocationQuery(e.target.value)}
              />
            </div>
            <Button className="h-9" size="sm" onClick={handleGeocode} disabled={geoLoading}>
              {geoLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
            </Button>
            <div className="w-24 space-y-1">
              <Label className="text-xs">Radius (mi)</Label>
              <Input
                className="h-9"
                value={radiusInput}
                onChange={(e) => setRadiusInput(e.target.value)}
              />
            </div>
            <Button className="h-9" variant="outline" size="sm" onClick={saveRadius}>
              Apply
            </Button>
          </div>
          {settings?.user_label && (
            <p className="mt-2 text-xs text-muted-foreground">
              Saved: {settings.user_label} ({settings.user_lat}, {settings.user_lon})
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            <CardTitle>Upcoming events</CardTitle>
            <CardDescription>
              Filter the list, hide one show, or hide an entire artist. Hidden items stay in sync
              here.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void openFestivals()}
              className="shrink-0"
            >
              Festivals
            </Button>
            <Button variant="outline" size="sm" onClick={openHidden} className="shrink-0">
              <EyeOff className="mr-2 h-4 w-4" />
              Hidden
              {hiddenTotal > 0 ? (
                <span className="ml-1.5 rounded-md bg-muted px-1.5 py-0.5 text-xs font-normal tabular-nums">
                  {hiddenArtistCount > 0 &&
                    `${hiddenArtistCount} artist${hiddenArtistCount === 1 ? "" : "s"}`}
                  {hiddenArtistCount > 0 && hiddenEventCount > 0 ? " | " : ""}
                  {hiddenEventCount > 0 &&
                    `${hiddenEventCount} event${hiddenEventCount === 1 ? "" : "s"}`}
                </span>
              ) : null}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
            <div className="relative min-w-[12rem] flex-1">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search artist or venue..."
                value={artistFilter}
                onChange={(e) => setArtistFilter(e.target.value)}
                className="h-9 pl-9"
              />
            </div>
            <div className="w-full space-y-1.5 sm:w-40">
              <Label className="text-xs text-muted-foreground">Interest</Label>
              <Select
                value={interestFilter}
                onValueChange={(v) => setInterestFilter(v as "all" | "interested")}
              >
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All events</SelectItem>
                  <SelectItem value="interested">Interested only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-full space-y-1.5 sm:w-44">
              <Label className="text-xs text-muted-foreground">Source</Label>
              <Select value={sourceFilter} onValueChange={setSourceFilter}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder="All sources" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All sources</SelectItem>
                  <SelectItem value="ticketmaster">Ticketmaster</SelectItem>
                  <SelectItem value="bandsintown">Bandsintown</SelectItem>
                  <SelectItem value="songkick">Songkick</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex min-w-[14rem] items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
              <Switch
                id="exclude-festivals"
                checked={excludeFestivals}
                onCheckedChange={(c) => setExcludeFestivals(Boolean(c))}
              />
              <Label htmlFor="exclude-festivals" className="cursor-pointer text-xs font-normal leading-snug">
                Exclude festivals &amp; tour packages
                <span className="mt-0.5 block text-[10px] text-muted-foreground">
                  Frees list slots (max 200) for regular shows
                </span>
              </Label>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Showing {filteredEvents.length} of {events.length} in this loaded page
            {artistFilter.trim() || sourceFilter !== "all" || interestFilter === "interested"
              ? " (search/source/interest filters)"
              : ""}
            . Up to 200 rows are returned per load.
            {upcomingStoredCount != null && upcomingStoredCount > events.length ? (
              <>
                {" "}
                {upcomingStoredCount.toLocaleString()} upcoming rows match your filters (interest +
                festival toggle); this response is capped at 200. A tight radius or many hidden items
                also reduce the list.
                {!excludeFestivals ? (
                  <>
                    {" "}
                    If the cap is mostly festivals/tours, turn on <strong>Exclude festivals</strong>{" "}
                    above.
                  </>
                ) : null}
              </>
            ) : null}
          </p>
          {events.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No upcoming events in range. Run refresh after configuring providers and syncing
              Lidarr artists.
            </p>
          ) : filteredEvents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events match your filters.</p>
          ) : (
            <ul className="divide-y rounded-md border">
              {filteredEvents.map((ev) => {
                const venueLine = [ev.venue_name || "Venue TBD", ev.venue_city, ev.venue_region]
                  .filter(Boolean)
                  .join(" | ");
                const rawSourceRows =
                  ev.source_links && ev.source_links.length > 0
                    ? ev.source_links
                    : ev.sources.map((s) => ({ provider: s, url: null as string | null }));
                const sourceRows = collapseSourceLinksForDisplay(rawSourceRows, ev.artist_name);
                return (
                  <li
                    key={`${ev.id}-${ev.starts_at_utc}`}
                    className={cn(
                      "flex flex-col gap-2 px-2 py-2 pl-1 sm:flex-row sm:items-center sm:gap-2 sm:pl-2",
                      ev.interested &&
                        "border-l-4 border-l-amber-500/90 bg-amber-500/[0.07] dark:bg-amber-500/10"
                    )}
                  >
                    <div className="flex shrink-0 items-start pt-0.5 sm:pt-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className={cn(
                          "h-8 w-8",
                          ev.interested && "text-amber-600 hover:text-amber-700 dark:text-amber-400"
                        )}
                        title={ev.interested ? "Remove from interested" : "Mark interested"}
                        onClick={() => void toggleInterested(ev)}
                      >
                        <Star
                          className={cn("h-4 w-4", ev.interested && "fill-current")}
                          aria-hidden
                        />
                        <span className="sr-only">
                          {ev.interested ? "Remove interested" : "Interested"}
                        </span>
                      </Button>
                    </div>
                    <div className="min-w-0 flex-1 space-y-0.5 sm:space-y-0">
                      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                        <span className="font-semibold leading-tight">{ev.artist_name}</span>
                        <span className="text-muted-foreground text-sm leading-tight">
                          {venueLine}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                        <span>{formatEventDate(ev)}</span>
                        {ev.event_kind === "festival" && (
                          <Badge
                            variant="outline"
                            className="h-5 px-1.5 text-[10px] font-normal"
                            title={ev.tm_event_name || "Festival or multi-day event"}
                          >
                            Festival
                          </Badge>
                        )}
                        {ev.event_kind === "tour_package" && (
                          <Badge
                            variant="outline"
                            className="h-5 px-1.5 text-[10px] font-normal"
                            title={ev.tm_event_name || "Multi-act tour or package listing"}
                          >
                            Tour
                          </Badge>
                        )}
                        {ev.distance_miles != null && (
                          <span className="tabular-nums">| {ev.distance_miles} mi</span>
                        )}
                        <span className="flex flex-wrap gap-1">
                          {sourceRows.map((row) => {
                            const label = sourceBadge(row.provider);
                            if (row.url) {
                              return (
                                <a
                                  key={row.provider}
                                  href={row.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center rounded-md border border-transparent bg-secondary px-1.5 py-0 text-[10px] font-normal text-secondary-foreground underline-offset-2 hover:underline"
                                >
                                  {label}
                                </a>
                              );
                            }
                            return (
                              <Badge
                                key={row.provider}
                                variant="secondary"
                                className="px-1.5 py-0 text-[10px] font-normal"
                              >
                                {label}
                              </Badge>
                            );
                          })}
                        </span>
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-1 sm:justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2"
                        asChild
                        title="Last.fm events"
                      >
                        <a href={ev.last_fm_events_url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink className="h-3.5 w-3.5" />
                          <span className="sr-only sm:not-sr-only sm:ml-1">Last.fm</span>
                        </a>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2"
                        title="Hide this show only"
                        onClick={() => setConfirmHideEvent(ev)}
                      >
                        <MinusCircle className="h-3.5 w-3.5" />
                        <span className="ml-1 hidden sm:inline">Hide event</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2"
                        title="Hide all shows for this artist"
                        onClick={() => setConfirmHideArtist(ev)}
                      >
                        <EyeOff className="h-3.5 w-3.5" />
                        <span className="ml-1 hidden sm:inline">Hide artist</span>
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Dialog open={festivalDialogOpen} onOpenChange={setFestivalDialogOpen}>
        <DialogContent className="flex max-h-[80vh] max-w-lg flex-col overflow-hidden">
          <DialogHeader className="space-y-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 space-y-1.5">
                <DialogTitle>Festivals & tour packages</DialogTitle>
                <DialogDescription>
                  Turn on Hide to remove that Ticketmaster tour or festival group from the upcoming
                  list. Events you marked interested still appear. Labels fill in after a refresh
                  with the new metadata.
                </DialogDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 shrink-0 self-start sm:self-center"
                disabled={
                  festivalsLoading ||
                  festivalCatalog.length === 0 ||
                  festivalBulkHiding ||
                  !festivalCatalogHasUnhidden
                }
                title={
                  festivalCatalog.length > 0 && !festivalCatalogHasUnhidden
                    ? "All groups in this list are already hidden"
                    : undefined
                }
                onClick={() => void hideAllFestivalsInCatalog()}
              >
                {festivalBulkHiding ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Hide all festivals"
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              <strong>Hide all festivals</strong> adds every group in this list (festivals and tour
              packages) to your hidden set. Groups beyond this dialog (catalog is capped) can still
              be hidden from the main list or after they appear here.
            </p>
          </DialogHeader>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {festivalsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : festivalCatalog.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No grouped tour or festival rows yet. After the next artist refresh, large multi-act
                Ticketmaster events appear here for bulk hiding.
              </p>
            ) : (
              festivalCatalog.map((item) => (
                <div
                  key={item.key}
                  className="flex items-start justify-between gap-3 rounded border px-3 py-2 text-sm"
                >
                  <div className="min-w-0 flex-1">
                    <div className="line-clamp-2 font-medium leading-tight">{item.label}</div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {item.count} listing{item.count === 1 ? "" : "s"} | {item.event_kind}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="whitespace-nowrap text-[10px] text-muted-foreground">
                      Hide
                    </span>
                    <Switch
                      checked={hiddenFestivalKeys.includes(item.key)}
                      onCheckedChange={(v) => void toggleFestivalHidden(item.key, v)}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={hiddenOpen} onOpenChange={setHiddenOpen}>
        <DialogContent className="flex max-h-[80vh] max-w-lg flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>Hidden from list</DialogTitle>
            <DialogDescription>
              Data is still refreshed; restore to show items in the upcoming list again.
            </DialogDescription>
          </DialogHeader>
          <Tabs
            value={hiddenTab}
            onValueChange={setHiddenTab}
            className="flex min-h-0 flex-1 flex-col"
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="artists">Artists ({hiddenItems.length})</TabsTrigger>
              <TabsTrigger value="events">Events ({hiddenEventItems.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="artists" className="mt-3 flex min-h-0 flex-1 flex-col gap-2">
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmRestoreAll(true)}
                  disabled={hiddenItems.length === 0}
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  Restore all artists
                </Button>
              </div>
              <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
                {hiddenItems.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No hidden artists.</p>
                ) : (
                  hiddenItems.map((h) => (
                    <div
                      key={h.artist_mbid}
                      className="flex items-center justify-between gap-2 rounded border px-3 py-2 text-sm"
                    >
                      <span className="min-w-0 truncate font-medium">
                        {h.artist_name || h.artist_mbid}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => restoreHidden(h.artist_mbid)}
                      >
                        Restore
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </TabsContent>
            <TabsContent value="events" className="mt-3 flex min-h-0 flex-1 flex-col gap-2">
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmRestoreAllEvents(true)}
                  disabled={hiddenEventItems.length === 0}
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  Restore all events
                </Button>
              </div>
              <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
                {hiddenEventItems.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No hidden single events.</p>
                ) : (
                  hiddenEventItems.map((h) => (
                    <div
                      key={h.event_id}
                      className="flex flex-col gap-1 rounded border px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <div className="font-medium">{h.artist_name}</div>
                        <div className="text-muted-foreground text-xs">
                          {[h.venue_name, h.venue_city].filter(Boolean).join(" | ")} |{" "}
                          {h.local_date}
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="shrink-0"
                        onClick={() => restoreHiddenEvent(h.event_id)}
                      >
                        Restore
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmHideArtist} onOpenChange={(o) => !o && setConfirmHideArtist(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hide all shows for this artist?</DialogTitle>
            <DialogDescription>
              {confirmHideArtist
                ? `"${confirmHideArtist.artist_name}" will disappear from this list until you restore the artist from Hidden > Artists.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setConfirmHideArtist(null)}>
              Cancel
            </Button>
            <Button onClick={() => void doHideArtist()}>Hide artist</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmHideEvent} onOpenChange={(o) => !o && setConfirmHideEvent(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hide this event only?</DialogTitle>
            <DialogDescription>
              {confirmHideEvent ? (
                <>
                  This show will be hidden from the list. Other dates for{" "}
                  <span className="font-medium text-foreground">
                    {confirmHideEvent.artist_name}
                  </span>{" "}
                  still appear unless you hide the artist.
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setConfirmHideEvent(null)}>
              Cancel
            </Button>
            <Button onClick={() => void doHideEvent()}>Hide event</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmRestoreAll} onOpenChange={setConfirmRestoreAll}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore all hidden artists?</DialogTitle>
            <DialogDescription>
              This clears every artist-level hide. Their events will appear in the list again (if
              any).
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setConfirmRestoreAll(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                void restoreAll();
              }}
            >
              Restore all
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmForceRefreshAll} onOpenChange={setConfirmForceRefreshAll}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Force refresh every artist?</DialogTitle>
            <DialogDescription>
              This single run queries <strong>every</strong> Lidarr artist, including ones that were
              scanned recently, ignoring the per-artist refresh interval. Useful after changing
              providers or recovering from a partial scan. Large libraries will take several minutes
              and may need a higher <strong>Timeout</strong> under Commands &gt; Artist Events
              Refresh.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setConfirmForceRefreshAll(false)}>
              Cancel
            </Button>
            <Button onClick={() => void runForceRefreshAll()}>Start force refresh</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmRestoreAllEvents} onOpenChange={setConfirmRestoreAllEvents}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore all hidden events?</DialogTitle>
            <DialogDescription>
              This clears every single-event hide. Those shows will appear in the list again.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setConfirmRestoreAllEvents(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                void restoreAllEvents();
              }}
            >
              Restore all
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
