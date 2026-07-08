import { api } from "@/lib/api";
import {
  NrdExclusionListDialog,
  type NrdExclusionListItem,
} from "@/components/NrdExclusionListDialog";

type HiddenReleasesDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged?: () => void;
};

export function HiddenReleasesDialog({ open, onOpenChange, onChanged }: HiddenReleasesDialogProps) {
  return (
    <NrdExclusionListDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Hidden releases"
      description="Albums hidden from pending discovery. Restore to allow them to reappear on the next scan."
      emptyMessage="No hidden releases."
      loadItems={async (): Promise<NrdExclusionListItem[]> => {
        const res = await api.getDismissedReleases({ limit: 500 });
        return res.items.map((item) => ({
          key: String(item.id),
          title: item.artist_name,
          subtitle: item.album_title,
          addedAt: item.dismissed_at,
        }));
      }}
      onRestore={async (key) => {
        await api.restoreDismissed(Number(key));
      }}
      onRestoreAll={async () => {
        const res = await api.restoreAllDismissed();
        return res.restored_count ?? 0;
      }}
      restoreAllConfirmTitle="Restore all hidden releases?"
      restoreAllConfirmDescription={(count) =>
        `Restore all ${count} hidden release${count === 1 ? "" : "s"}? They may reappear on the next New Releases scan if still missing from MusicBrainz.`
      }
      onChanged={onChanged}
    />
  );
}
