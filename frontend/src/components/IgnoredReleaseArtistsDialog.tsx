import { useEffect, useState } from "react";
import { Loader2, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

type IgnoredReleaseArtistsDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged?: () => void;
};

export function IgnoredReleaseArtistsDialog({
  open,
  onOpenChange,
  onChanged,
}: IgnoredReleaseArtistsDialogProps) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<
    { artist_mbid: string; artist_name: string; ignored_at?: string | null }[]
  >([]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.getIgnoredReleaseArtists();
      setItems(res.items);
    } catch {
      toast.error("Failed to load ignored artists");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) void load();
  }, [open]);

  const restore = async (artistMbid: string) => {
    try {
      await api.unignoreReleaseArtist(artistMbid);
      toast.success("Artist tracking restored");
      setItems((prev) => prev.filter((a) => a.artist_mbid !== artistMbid));
      onChanged?.();
    } catch {
      toast.error("Failed to restore artist");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[80vh] max-w-lg flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Ignored artists</DialogTitle>
          <DialogDescription>
            These artists are excluded from new release discovery. Restore to track them again.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 space-y-2 overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No ignored artists.</p>
          ) : (
            items.map((artist) => (
              <div
                key={artist.artist_mbid}
                className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 font-medium">
                  {artist.artist_name || artist.artist_mbid}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="shrink-0 self-start sm:self-auto"
                  onClick={() => void restore(artist.artist_mbid)}
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  Restore
                </Button>
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
