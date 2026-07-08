import { api } from "@/lib/api";
import {
  NrdExclusionListDialog,
  type NrdExclusionListItem,
} from "@/components/NrdExclusionListDialog";

type HiddenEventArtistsDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged?: () => void;
};

export function HiddenEventArtistsDialog({
  open,
  onOpenChange,
  onChanged,
}: HiddenEventArtistsDialogProps) {
  return (
    <NrdExclusionListDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Hidden artists"
      description="These artists are hidden from the upcoming events list. Restore to show their events again."
      emptyMessage="No hidden artists."
      loadItems={async (): Promise<NrdExclusionListItem[]> => {
        const res = await api.getHiddenEventArtists(500);
        return res.items.map((item) => ({
          key: item.artist_mbid,
          title: item.artist_name || item.artist_mbid,
          addedAt: item.hidden_at,
        }));
      }}
      onRestore={async (key) => {
        await api.unhideEventArtist(key);
      }}
      onRestoreAll={async () => {
        const res = await api.unhideAllEventArtists();
        return res.removed ?? 0;
      }}
      restoreAllConfirmTitle="Restore all hidden artists?"
      restoreAllConfirmDescription={(count) =>
        `Restore all ${count} hidden artist${count === 1 ? "" : "s"}? Their events will appear in the list again (if any).`
      }
      onChanged={onChanged}
    />
  );
}
