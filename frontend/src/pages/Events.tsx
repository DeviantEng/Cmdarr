import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Calendar,
  ExternalLink,
  EyeOff,
  Loader2,
  MapPin,
  MinusCircle,
  Music,
  RefreshCw,
  RotateCcw,
  Search,
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
import { toast } from "sonner";
import type { ConfigUpdateRequest } from "@/lib/types";

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
  const [artistFilter, setArtistFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [confirmHideArtist, setConfirmHideArtist] = useState<ArtistEventRow | null>(null);
  const [confirmHideEvent, setConfirmHideEvent] = useState<ArtistEventRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ps, st, ev, hA, hE] = await Promise.all([
        api.getEventsProviderStatus(),
        api.getEventsSettings(),
        api.getUpcomingEvents({ limit: 200 }),
        api.getHiddenEventArtists(),
        api.getHiddenEvents(),
      ]);
      setProviderStatus(ps);
      setSettings(st);
      setEvents(ev.events);
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
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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

  const runRefresh = async () => {
    setRefreshRunning(true);
    try {
      await api.executeCommand("artist_events_refresh", { triggered_by: "api" });
      toast.success("Artist events refresh started — check Commands for progress");
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
        <h1 className="text-3xl font-bold tracking-tight">Artist events</h1>
        <p className="text-muted-foreground mt-1">
          Upcoming shows, festivals, and other events for artists in your Lidarr library, aggregated
          from enabled providers. Sync Lidarr artists from New Releases first, then run the refresh
          command on a schedule or manually.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Music className="h-5 w-5" />
            Providers
          </CardTitle>
          <CardDescription>
            Toggle which sources participate in refresh. Set app IDs and API keys on{" "}
            <Link to="/config" className="underline font-medium text-foreground">
              Configuration
            </Link>{" "}
            (Config → Event Sources). At least one source must be enabled and fully configured
            before refresh runs.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {!providerStatus?.any_ready && (
            <p className="text-sm text-amber-600 dark:text-amber-400">
              No provider is fully configured. Enable a source below, then add credentials in{" "}
              <Link to="/config" className="underline font-medium">
                Configuration
              </Link>
              .
            </p>
          )}
          <div className="grid gap-6 md:grid-cols-3">
            <div className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <Label>Bandsintown</Label>
                <Switch
                  checked={settings?.bandsintown_enabled ?? false}
                  onCheckedChange={(c) => toggleProvider("ARTIST_EVENTS_BANDSINTOWN_ENABLED", c)}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Status: {providerStatus?.bandsintown.enabled ? "ready" : "needs app ID in Config"}
              </p>
            </div>
            <div className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <Label>Songkick</Label>
                <Switch
                  checked={settings?.songkick_enabled ?? false}
                  onCheckedChange={(c) => toggleProvider("ARTIST_EVENTS_SONGKICK_ENABLED", c)}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Status: {providerStatus?.songkick.enabled ? "ready" : "needs API key in Config"}
              </p>
            </div>
            <div className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <Label>Ticketmaster</Label>
                <Switch
                  checked={settings?.ticketmaster_enabled ?? false}
                  onCheckedChange={(c) => toggleProvider("ARTIST_EVENTS_TICKETMASTER_ENABLED", c)}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Status: {providerStatus?.ticketmaster.enabled ? "ready" : "needs API key in Config"}
              </p>
            </div>
          </div>
          <Button
            variant="secondary"
            onClick={runRefresh}
            disabled={refreshRunning || !providerStatus?.any_ready}
          >
            {refreshRunning ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Run artist events refresh
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            Location & radius
          </CardTitle>
          <CardDescription>
            Enter a ZIP or city and state, then save — Cmdarr stores coordinates and label for you.
            You do not need to set latitude, longitude, or radius under Configuration; those keys
            remain available for environment variables or automation only.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-2">
            <Label>Geocode</Label>
            <Input
              placeholder="e.g. 97201 or Portland, OR"
              value={locationQuery}
              onChange={(e) => setLocationQuery(e.target.value)}
            />
          </div>
          <Button onClick={handleGeocode} disabled={geoLoading}>
            {geoLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save location"}
          </Button>
          <div className="w-full space-y-2 sm:w-32">
            <Label>Radius (mi)</Label>
            <Input value={radiusInput} onChange={(e) => setRadiusInput(e.target.value)} />
          </div>
          <Button variant="outline" onClick={saveRadius}>
            Save radius
          </Button>
        </CardContent>
        {settings?.user_label && (
          <CardContent className="pt-0 text-sm text-muted-foreground">
            Saved: {settings.user_label} ({settings.user_lat}, {settings.user_lon})
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Upcoming events
            </CardTitle>
            <CardDescription>
              Filter the list, hide one show, or hide an entire artist. Hidden items stay in sync
              here.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={openHidden} className="shrink-0">
            <EyeOff className="mr-2 h-4 w-4" />
            Hidden
            {hiddenTotal > 0 ? (
              <span className="ml-1.5 rounded-md bg-muted px-1.5 py-0.5 text-xs font-normal tabular-nums">
                {hiddenArtistCount > 0 &&
                  `${hiddenArtistCount} artist${hiddenArtistCount === 1 ? "" : "s"}`}
                {hiddenArtistCount > 0 && hiddenEventCount > 0 ? " · " : ""}
                {hiddenEventCount > 0 &&
                  `${hiddenEventCount} event${hiddenEventCount === 1 ? "" : "s"}`}
              </span>
            ) : null}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search artist or venue…"
                value={artistFilter}
                onChange={(e) => setArtistFilter(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="w-full space-y-1.5 sm:w-48">
              <Label className="text-xs text-muted-foreground">Source</Label>
              <Select value={sourceFilter} onValueChange={setSourceFilter}>
                <SelectTrigger>
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
          </div>
          <p className="text-xs text-muted-foreground">
            Showing {filteredEvents.length} of {events.length} loaded events
            {artistFilter.trim() || sourceFilter !== "all" ? " (filtered)" : ""}.
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
                  .join(" · ");
                return (
                  <li
                    key={`${ev.id}-${ev.starts_at_utc}`}
                    className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:gap-3"
                  >
                    <div className="min-w-0 flex-1 space-y-0.5 sm:space-y-0">
                      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                        <span className="font-semibold leading-tight">{ev.artist_name}</span>
                        <span className="text-muted-foreground text-sm leading-tight">
                          {venueLine}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                        <span>{formatEventDate(ev)}</span>
                        {ev.distance_miles != null && (
                          <span className="tabular-nums">· {ev.distance_miles} mi</span>
                        )}
                        <span className="flex gap-1">
                          {ev.sources.map((s) => (
                            <Badge
                              key={s}
                              variant="secondary"
                              className="px-1.5 py-0 text-[10px] font-normal"
                            >
                              {sourceBadge(s)}
                            </Badge>
                          ))}
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
                          {[h.venue_name, h.venue_city].filter(Boolean).join(" · ")} ·{" "}
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
                ? `“${confirmHideArtist.artist_name}” will disappear from this list until you restore the artist from Hidden → Artists.`
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
