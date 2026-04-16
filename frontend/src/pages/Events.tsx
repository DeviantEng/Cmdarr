import { useCallback, useEffect, useState } from "react";
import {
  Calendar,
  ExternalLink,
  EyeOff,
  Loader2,
  MapPin,
  Music,
  RefreshCw,
  RotateCcw,
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
import { toast } from "sonner";
import type { ConfigUpdateRequest } from "@/lib/types";

type ArtistEventRow = Awaited<ReturnType<typeof api.getUpcomingEvents>>["events"][number];

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
  const [hiddenItems, setHiddenItems] = useState<
    { artist_mbid: string; artist_name: string; hidden_at: string | null }[]
  >([]);
  const [confirmRestoreAll, setConfirmRestoreAll] = useState(false);
  const [refreshRunning, setRefreshRunning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ps, st, ev] = await Promise.all([
        api.getEventsProviderStatus(),
        api.getEventsSettings(),
        api.getUpcomingEvents({ limit: 200 }),
      ]);
      setProviderStatus(ps);
      setSettings(st);
      setEvents(ev.events);
      setRadiusInput(String(st.radius_miles ?? 100));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
      setLocationQuery("");
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
      const h = await api.getHiddenEventArtists();
      setHiddenItems(h.items);
    } catch {
      toast.error("Failed to load hidden artists");
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

  const hideArtist = async (ev: ArtistEventRow) => {
    try {
      await api.hideEventArtist(ev.artist_mbid, ev.artist_name);
      toast.success(`Hidden events for ${ev.artist_name}`);
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
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const restoreAll = async () => {
    try {
      await api.unhideAllEventArtists();
      toast.success("All artists restored");
      setConfirmRestoreAll(false);
      setHiddenOpen(false);
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
            (Music Sources → artist_events). At least one source must be enabled and fully
            configured before refresh runs.
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
            US-only geocoding (ZIP or city, state). Used to filter by distance when venue
            coordinates exist.
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
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Upcoming events
            </CardTitle>
            <CardDescription>
              Hide an artist to remove their shows from this list only.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={openHidden}>
            <EyeOff className="mr-2 h-4 w-4" />
            Hidden artists
          </Button>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No upcoming events in range. Run refresh after configuring providers and syncing
              Lidarr artists.
            </p>
          ) : (
            <div className="space-y-3">
              {events.map((ev) => (
                <div
                  key={`${ev.id}-${ev.starts_at_utc}`}
                  className="flex flex-col gap-2 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="font-semibold">{ev.artist_name}</div>
                    <div className="text-sm text-muted-foreground">
                      {ev.venue_name || "Venue TBD"}
                      {ev.venue_city && ` · ${ev.venue_city}`}
                      {ev.venue_region && `, ${ev.venue_region}`}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {ev.starts_at_utc
                        ? new Date(ev.starts_at_utc).toLocaleString(undefined, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })
                        : ev.local_date}
                      {ev.distance_miles != null && ` · ${ev.distance_miles} mi`}
                    </div>
                    <div className="flex flex-wrap gap-1 pt-1">
                      {ev.sources.map((s) => (
                        <Badge key={s} variant="secondary">
                          {sourceBadge(s)}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button variant="outline" size="sm" asChild>
                      <a href={ev.last_fm_events_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="mr-1 h-3.5 w-3.5" />
                        Last.fm
                      </a>
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => hideArtist(ev)}>
                      <EyeOff className="mr-1 h-3.5 w-3.5" />
                      Hide artist
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={hiddenOpen} onOpenChange={setHiddenOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Hidden artists</DialogTitle>
            <DialogDescription>
              Events are still collected; restore to show them again in the list.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmRestoreAll(true)}
              disabled={hiddenItems.length === 0}
            >
              <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
              Restore all
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto space-y-2">
            {hiddenItems.length === 0 ? (
              <p className="text-sm text-muted-foreground">No hidden artists.</p>
            ) : (
              hiddenItems.map((h) => (
                <div
                  key={h.artist_mbid}
                  className="flex items-center justify-between rounded border p-3"
                >
                  <span className="font-medium truncate">{h.artist_name || h.artist_mbid}</span>
                  <Button variant="outline" size="sm" onClick={() => restoreHidden(h.artist_mbid)}>
                    Restore
                  </Button>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmRestoreAll} onOpenChange={setConfirmRestoreAll}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore all hidden artists?</DialogTitle>
            <DialogDescription>
              This clears every hidden-artist entry. Their events will appear in the
              list again (if any).
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setConfirmRestoreAll(false)}>
              Cancel
            </Button>
            <Button onClick={restoreAll}>Restore all</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
