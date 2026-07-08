import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type NrdNotScannedDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function NrdNotScannedDialog({ open, onOpenChange }: NrdNotScannedDialogProps) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<{ artist_mbid: string; artist_name: string }[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    void api
      .getNrdNotScannedArtists()
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[80vh] max-w-lg flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Not yet scanned</DialogTitle>
          <DialogDescription>
            Lidarr artists with no new-release scan history. They will be picked up on the next
            discovery run.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 space-y-2 overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              All Lidarr artists have been scanned at least once.
            </p>
          ) : (
            <>
              {items.map((artist) => (
                <div key={artist.artist_mbid} className="rounded border px-3 py-2 text-sm">
                  {artist.artist_name || artist.artist_mbid}
                </div>
              ))}
              {total >= items.length && items.length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Showing {items.length}
                  {total > items.length ? ` of ${total}+` : ""} artist
                  {items.length === 1 ? "" : "s"}
                </p>
              ) : null}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
