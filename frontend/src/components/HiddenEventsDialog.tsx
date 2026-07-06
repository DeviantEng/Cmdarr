import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

type HiddenEventItem = Awaited<ReturnType<typeof api.getHiddenEvents>>["items"][number];

type HiddenEventsDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTab?: "artists" | "events";
  onChanged?: () => void;
};

export function HiddenEventsDialog({
  open,
  onOpenChange,
  initialTab = "artists",
  onChanged,
}: HiddenEventsDialogProps) {
  const [hiddenTab, setHiddenTab] = useState(initialTab);
  const [hiddenItems, setHiddenItems] = useState<
    { artist_mbid: string; artist_name: string; hidden_at: string | null }[]
  >([]);
  const [hiddenEventItems, setHiddenEventItems] = useState<HiddenEventItem[]>([]);
  const [confirmRestoreAll, setConfirmRestoreAll] = useState(false);
  const [confirmRestoreAllEvents, setConfirmRestoreAllEvents] = useState(false);

  useEffect(() => {
    if (open) setHiddenTab(initialTab);
  }, [open, initialTab]);

  const loadHidden = async () => {
    const [h, e] = await Promise.all([api.getHiddenEventArtists(), api.getHiddenEvents()]);
    setHiddenItems(h.items);
    setHiddenEventItems(e.items);
  };

  useEffect(() => {
    if (!open) return;
    void loadHidden().catch(() => toast.error("Failed to load hidden items"));
  }, [open]);

  const restoreHidden = async (mbid: string) => {
    try {
      await api.unhideEventArtist(mbid);
      toast.success("Restored");
      await loadHidden();
      onChanged?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const restoreHiddenEvent = async (eventId: number) => {
    try {
      await api.unhideEventRow(eventId);
      toast.success("Restored");
      await loadHidden();
      onChanged?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const restoreAll = async () => {
    try {
      await api.unhideAllEventArtists();
      toast.success("All artists restored");
      setConfirmRestoreAll(false);
      await loadHidden();
      onChanged?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  const restoreAllEvents = async () => {
    try {
      await api.unhideAllHiddenEvents();
      toast.success("All hidden events restored");
      setConfirmRestoreAllEvents(false);
      await loadHidden();
      onChanged?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex max-h-[80vh] max-w-lg flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>Hidden from list</DialogTitle>
            <DialogDescription>
              Data is still refreshed; restore to show items in the upcoming list again.
            </DialogDescription>
          </DialogHeader>
          <Tabs
            value={hiddenTab}
            onValueChange={(v) => setHiddenTab(v as "artists" | "events")}
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
                      <Button variant="outline" size="sm" onClick={() => void restoreHidden(h.artist_mbid)}>
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
                        <div className="text-xs text-muted-foreground">
                          {[h.venue_name, h.venue_city].filter(Boolean).join(" | ")} | {h.local_date}
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="shrink-0"
                        onClick={() => void restoreHiddenEvent(h.event_id)}
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

      <Dialog open={confirmRestoreAll} onOpenChange={setConfirmRestoreAll}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore all hidden artists?</DialogTitle>
            <DialogDescription>
              This clears every artist-level hide. Their events will appear in the list again (if any).
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setConfirmRestoreAll(false)}>
              Cancel
            </Button>
            <Button onClick={() => void restoreAll()}>Restore all</Button>
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
            <Button onClick={() => void restoreAllEvents()}>Restore all</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
