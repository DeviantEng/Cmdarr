import { api } from "@/lib/api";
import {
  NrdExclusionListDialog,
  type NrdExclusionListItem,
} from "@/components/NrdExclusionListDialog";

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
  return (
    <NrdExclusionListDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Ignored artists"
      description="These artists are excluded from new release discovery. Restore to track them again."
      emptyMessage="No ignored artists."
      loadItems={async (): Promise<NrdExclusionListItem[]> => {
        const res = await api.getIgnoredReleaseArtists(500);
        return res.items.map((artist) => ({
          key: artist.artist_mbid,
          title: artist.artist_name || artist.artist_mbid,
          addedAt: artist.ignored_at,
        }));
      }}
      onRestore={async (key) => {
        await api.unignoreReleaseArtist(key);
      }}
      onRestoreAll={async () => {
        const res = await api.restoreAllIgnoredReleaseArtists();
        return res.restored_count ?? 0;
      }}
      restoreAllConfirmTitle="Restore all ignored artists?"
      restoreAllConfirmDescription={(count) =>
        `Restore all ${count} ignored artist${count === 1 ? "" : "s"}? They will be included in discovery again on the next scan.`
      }
      onChanged={onChanged}
    />
  );
}
